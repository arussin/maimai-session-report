"""Read existing Kamaitachi sessions and retain explicit PB comparison snapshots.

These operations never submit scores. Selected-session plays and account-wide
PB comparisons are separate: current PBs are not a historical session snapshot.
"""

from __future__ import annotations

import datetime as dt
import math
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

from .api import KamaitachiClient, validate_score_payload
from .calculations import _format_timestamp, build_report_input, compact_record, make_maps
from .config import AppConfig
from .errors import APIResponseError, ConfigError
from .io import write_json
from .render import read_json
from .sync import SyncResult, write_sync_result

JSONDict = dict[str, Any]
EMPTY_SCORES: JSONDict = {"scores": [], "charts": [], "songs": []}


def validate_config(config: AppConfig) -> None:
    config.validate(for_network=True)
    if config.game != "maimaidx":
        raise ConfigError("Existing-session reports currently support maimai DX only.")


def read_client() -> KamaitachiClient:
    # These public read endpoints do not need the score-submission credential.
    return KamaitachiClient(None)


def _validate_records(body: JSONDict, key: str) -> None:
    charts, songs = make_maps(body)
    seen = set()
    for record in body[key]:
        if not isinstance(record, dict):
            raise APIResponseError("Kamaitachi returned an invalid score record.")
        cid = record.get("chartID")
        chart = charts.get(cid, {}) if isinstance(cid, str) else {}
        score, calc = record.get("scoreData"), record.get("calculatedData")
        if not isinstance(score, dict) or not isinstance(calc, dict):
            raise APIResponseError("Score is missing its achievement or rating data.")
        percent, rate = score.get("percent"), calc.get("rate")
        constant = chart.get("levelNum")
        if (
            not chart
            or not isinstance(record.get("songID"), str)
            or record["songID"] not in songs
            or type(percent) not in (int, float)
            or not math.isfinite(percent)
            or not 0 <= percent <= 101
            or type(rate) is not int
            or rate < 0
            or type(constant) not in (int, float)
            or not math.isfinite(constant)
            or constant <= 0
            or not isinstance(chart.get("data"), dict)
            or not isinstance(chart["data"].get("displayVersion"), str)
            or not chart["data"]["displayVersion"]
        ):
            raise APIResponseError(
                "Score or chart metadata is incomplete; rating cannot be calculated reliably."
            )
        if key == "pbs" and cid in seen:
            raise APIResponseError("PB response repeats a chart.")
        seen.add(cid)


def list_sessions(config: AppConfig, *, client: Any = None) -> list[JSONDict]:
    validate_config(config)
    payload = (client or read_client()).get_sessions(config.username, config.game)
    sessions = payload.get("body")
    if payload.get("success") is not True or not isinstance(sessions, list):
        raise APIResponseError("Kamaitachi did not return a session list.")
    for item in sessions:
        if not isinstance(item, dict) or not re.fullmatch(
            r"[A-Za-z0-9_-]{1,128}", str(item.get("sessionID", ""))
        ):
            raise APIResponseError("Kamaitachi returned an invalid session summary.")
        if item.get("game") != config.game or item.get("playtype", "Single") != "Single":
            raise APIResponseError("Session list contains a different game.")
        for key in ("timeStarted", "timeEnded"):
            if type(item.get(key)) is not int or item[key] < 0:
                raise APIResponseError("Session summary has an invalid timestamp.")
    return sorted(sessions, key=lambda s: (s["timeEnded"], s["sessionID"]), reverse=True)


def make_baseline(
    config: AppConfig, payload: JSONDict, when: dt.datetime | None = None
) -> JSONDict:
    _validate_records(validate_score_payload(payload, "pbs"), "pbs")
    return {
        "schemaVersion": 1,
        "kind": "kamaitachi-pb-baseline",
        "username": config.username,
        "game": config.game,
        "currentNewDisplayVersions": sorted(config.current_version_display_names),
        "capturedAt": _format_timestamp(when),
        "pbsPayload": deepcopy(payload),
    }


def save_baseline(config: AppConfig, output: Path, *, client: Any = None) -> Path:
    validate_config(config)
    if output.exists():
        raise ConfigError(
            "Choose a new baseline filename; saved comparisons are never overwritten."
        )
    payload = (client or read_client()).get_pbs(config.username, config.game)
    return write_json(output, make_baseline(config, payload))


def _read_baseline(config: AppConfig, path: Path, before_ms: int) -> JSONDict:
    value = read_json(path)
    if (
        value.get("schemaVersion") != 1
        or value.get("kind") != "kamaitachi-pb-baseline"
        or str(value.get("username", "")).casefold() != config.username.casefold()
        or value.get("game") != config.game
        or value.get("currentNewDisplayVersions") != sorted(config.current_version_display_names)
    ):
        raise ConfigError("Baseline must belong to this player, game and configured release.")
    try:
        when = dt.datetime.fromisoformat(value["capturedAt"].replace("Z", "+00:00"))
        if when.utcoffset() is None or not 0 <= when.timestamp() * 1000 < before_ms:
            raise ValueError
    except (KeyError, AttributeError, TypeError, ValueError, OverflowError) as exc:
        raise ConfigError(
            "Baseline must be dated before the selected session or snapshot."
        ) from exc
    payload = value.get("pbsPayload")
    if not isinstance(payload, dict):
        raise ConfigError("Baseline is missing its PB response.")
    _validate_records(validate_score_payload(payload, "pbs"), "pbs")
    return value


def _session_body(payload: JSONDict, config: AppConfig, session_id: str) -> JSONDict:
    body = validate_score_payload(payload, "scores")
    _validate_records(body, "scores")
    session, user = body.get("session"), body.get("user")
    if not isinstance(session, dict) or not isinstance(user, dict):
        raise APIResponseError("Session response is missing its identity.")
    if (
        session.get("sessionID") != session_id
        or session.get("game") != config.game
        or session.get("playtype", "Single") != "Single"
        or str(user.get("username", "")).casefold() != config.username.casefold()
        or session.get("userID") is None
        or session["userID"] != user.get("id")
    ):
        raise APIResponseError("Selected session does not belong to this player and game.")
    for key in ("timeStarted", "timeEnded"):
        if type(session.get(key)) is not int or session[key] < 0:
            raise APIResponseError("Selected session has invalid timestamps.")
    if session["timeStarted"] > session["timeEnded"]:
        raise APIResponseError("Selected session has reversed timestamps.")
    ids = session.get("scoreIDs")
    if not isinstance(ids, list) or not ids or any(not isinstance(i, str) or not i for i in ids):
        raise APIResponseError("Selected session has no valid score membership.")
    if len(ids) != len(set(ids)):
        raise APIResponseError("Selected session repeats a score ID.")
    charts, songs = make_maps(body)
    records = {}
    for score in body["scores"]:
        if not isinstance(score, dict) or not isinstance(score.get("scoreID"), str):
            raise APIResponseError("Session score is missing a stable score ID.")
        sid = score["scoreID"]
        when = score.get("timeAchieved")
        if (
            sid not in ids
            or score.get("userID") != session["userID"]
            or score.get("game") != config.game
            or type(when) is not int
            or not session["timeStarted"] <= when <= session["timeEnded"]
            or score.get("chartID") not in charts
            or score.get("songID") not in songs
        ):
            raise APIResponseError("Session contains inconsistent score or chart data.")
        if sid in records and records[sid] != score:
            raise APIResponseError("Session contains conflicting records for one score ID.")
        records[sid] = score
    if set(ids) != set(records):
        raise APIResponseError("Session scores are incomplete; no partial report was generated.")
    body = deepcopy(body)
    body["scores"] = sorted(records.values(), key=lambda s: (s["timeAchieved"], s["scoreID"]))
    return body


def capture_existing(
    config: AppConfig,
    *,
    session_id: str | None = None,
    latest: bool = False,
    pb_snapshot: bool = False,
    baseline_path: Path | None = None,
    client: Any = None,
    generated_at: dt.datetime | None = None,
) -> tuple[SyncResult, JSONDict, JSONDict | None]:
    validate_config(config)
    if sum((bool(session_id), latest, pb_snapshot)) != 1:
        raise ConfigError("Choose a session ID, latest session, or PB snapshot.")
    if session_id and not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", session_id):
        raise ConfigError("Use the session ID shown by the sessions command.")
    active = client or read_client()
    if latest:
        sessions = list_sessions(config, client=active)
        if not sessions:
            raise ConfigError("No Kamaitachi sessions found. Import recent plays first.")
        session_id = sessions[0]["sessionID"]
    raw_session = active.get_session(session_id) if session_id else None
    session_body = _session_body(raw_session, config, session_id) if session_id else EMPTY_SCORES
    now = generated_at or dt.datetime.now(dt.UTC)
    boundary = session_body["session"]["timeStarted"] if session_id else int(now.timestamp() * 1000)
    baseline = _read_baseline(config, baseline_path, boundary) if baseline_path else None
    after_payload = active.get_pbs(config.username, config.game)
    after = validate_score_payload(after_payload, "pbs")
    _validate_records(after, "pbs")
    before_payload = (
        baseline["pbsPayload"]
        if baseline
        else {"success": True, "body": {"pbs": [], "charts": [], "songs": []}}
    )
    before = validate_score_payload(before_payload, "pbs")
    model = build_report_input(
        before,
        EMPTY_SCORES,
        after,
        session_body,
        config.current_version_display_names,
        generated_at=now,
    )
    # The complete session endpoint owns membership; never apply a recent-score cutoff.
    charts, songs = make_maps(session_body)
    model["session"]["scores"] = [compact_record(s, charts, songs) for s in session_body["scores"]]
    model["session"]["scoreCount"] = len(session_body["scores"])
    model["capture"] = {
        "source": "kamaitachi",
        "kind": "pb-snapshot" if pb_snapshot else "session",
        "sessionID": session_id,
        "ratingAsOf": model["generatedAt"],
    }
    model["comparison"] = {
        "available": baseline is not None,
        "scope": "snapshot",
        "baselineAt": baseline["capturedAt"] if baseline else None,
    }
    if baseline is None:
        for key, value in model["before"].items():
            model["before"][key] = [] if isinstance(value, list) else None
        model["delta"] = dict.fromkeys(model["delta"])
        model["session"].update(changedPBs=[], changedPBCount=0, newPBCount=0, improvedPBCount=0)
    metadata = {
        "syncCompleted": True,
        "captureSource": "kamaitachi",
        "importStarted": False,
        "sessionID": session_id,
        "fetchedAt": model["generatedAt"],
        "beforePBCount": model["before"]["pbCount"],
        "afterPBCount": model["after"]["pbCount"],
        "sessionScoreCount": model["session"]["scoreCount"],
        "changedPBCount": model["session"]["changedPBCount"],
    }
    result = SyncResult(
        before_payload,
        {"success": True, "body": deepcopy(EMPTY_SCORES)},
        after_payload,
        {"success": True, "body": session_body},
        model,
        metadata,
    )
    return result, make_baseline(config, after_payload, now), raw_session


def write_capture(capture: tuple[SyncResult, JSONDict, JSONDict | None], output: Path) -> None:
    if output.exists() and any(output.iterdir()):
        raise ConfigError("Choose an empty capture directory so retained reports stay intact.")
    result, baseline, raw_session = capture
    write_sync_result(result, output)
    write_json(output / "baseline.json", baseline)
    if raw_session:
        write_json(output / "kamaitachi-session.json", raw_session)
