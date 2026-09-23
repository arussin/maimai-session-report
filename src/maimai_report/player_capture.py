"""Allowlisted capture export and cumulative local player files."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from ._party import player_data as core

GRADE_BOUNDARIES = (
    (1005000, "SSS+"),
    (1000000, "SSS"),
    (995000, "SS+"),
    (990000, "SS"),
    (980000, "S+"),
    (970000, "S"),
    (940000, "AAA"),
    (900000, "AA"),
    (800000, "A"),
    (750000, "BBB"),
    (700000, "BB"),
    (600000, "B"),
    (500000, "C"),
    (0, "D"),
)


def timestamp(value):
    if type(value) is int:
        return value
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is not None:
                return int(parsed.timestamp() * 1000)
        except ValueError:
            pass
    return 0


def body(value):
    return value.get("body", value) if isinstance(value, dict) else {}


def identity(report, player=None):
    existing = report.get("player", {}).get("username")
    supplied = (player or {}).get("username")
    if existing and supplied and existing.lower() != supplied.lower():
        raise ValueError("History belongs to a different player")
    p = {**report.get("player", {}), **(player or {})}
    username = p.get("username") or "player"
    return {
        "key": "kamaitachi:maimaidx:" + username.lower(),
        "provider": "kamaitachi",
        "game": "maimaidx",
        "username": username,
        "displayName": p.get("displayName") or p.get("display_name") or username,
    }


def chart_record(item):
    difficulty = str(item.get("difficulty") or "UNKNOWN").upper()
    fmt = "DX" if difficulty.startswith("DX ") or item.get("format") == "DX" else "STD"
    difficulty = difficulty.removeprefix("DX ").replace("REMASTER", "RE:MASTER")
    return {
        "chartID": str(item["chartID"]),
        "songID": str(item.get("songID") or item["chartID"]),
        "title": str(item.get("title") or ""),
        "artist": str(item.get("artist") or ""),
        "format": fmt,
        "difficulty": difficulty,
        "level": str(item.get("level") or ""),
        "constant": core.number(item.get("levelNum"), 10),
        "displayVersion": str(item.get("displayVersion") or ""),
        "inGameID": core.number(item.get("inGameID")),
    }


def observation(item):
    achievement = core.number(item.get("percent"), 10000)
    grade = item.get("grade") or (
        next(g for minimum, g in GRADE_BOUNDARIES if achievement >= minimum)
        if achievement is not None
        else ""
    )
    value = {k: None for k in core.RECORD_FIELDS}
    value.update(
        chartID=str(item["chartID"]),
        achievement=achievement,
        grade=str(grade),
        lamp=str(item.get("lamp") or ""),
        sync=str(item.get("sync") or ""),
        constant=core.number(item.get("levelNum"), 10),
        displayVersion=str(item.get("displayVersion") or ""),
    )
    for key in (
        "rate",
        "timeAchieved",
        "dxScore",
        "maxDxScore",
        "maxCombo",
        "fast",
        "slow",
        "miss",
        "good",
        "great",
        "perfect",
        "pcrit",
    ):
        value[key] = core.number(item.get(key))
    return value


def compact_payload(payload, key):
    from .calculations import compact_record, make_maps

    value = body(payload)
    if not isinstance(value.get(key), list):
        return []
    if not value[key]:
        return []
    charts, songs = ({}, {}) if all("percent" in r for r in value[key]) else make_maps(value)
    result = []
    for record in value[key]:
        if not isinstance(record, dict) or not record.get("chartID"):
            raise ValueError("Invalid retained score record")
        row = dict(record) if "percent" in record else compact_record(record, charts, songs)
        optional = record.get("scoreData", {}).get("optional") or {}
        row.update(
            sync=optional.get("sync", row.get("sync")),
            dxScore=optional.get("dxScore", row.get("dxScore")),
            maxDxScore=optional.get("maxDxScore", row.get("maxDxScore")),
            maxCombo=optional.get("maxCombo", row.get("maxCombo")),
            inGameID=charts.get(record["chartID"], {})
            .get("data", {})
            .get("inGameID", row.get("inGameID")),
        )
        # Keep provenance during export only; it is not part of a score observation.
        row["composedFrom"] = record.get("composedFrom")
        result.append(row)
    return result


def pb_play_id(row, captured_at):
    """Only a dated, single-source PB describes one recoverable historical play.

    Tachi PBs can combine the percent and lamp from different scores. A date alone
    cannot turn that composite into a play. One Best Percent reference means all
    retained score fields came from that source; use its identity, never a saved date.
    """
    refs = row.get("composedFrom")
    when = row.get("timeAchieved")
    if (
        not isinstance(refs, list)
        or len(refs) != 1
        or not isinstance(refs[0], dict)
        or refs[0].get("name") != "Best Percent"
        or not isinstance(refs[0].get("scoreID"), str)
        or not refs[0]["scoreID"]
        or type(when) is not int
        or not 0 < when <= captured_at
        or core.number(row.get("percent"), 10000) is None
    ):
        return None
    return refs[0]["scoreID"]


def from_documents(
    report: Mapping[str, Any],
    after_payload: Mapping[str, Any] | None = None,
    *,
    documents: Mapping[str, Any] | None = None,
    player: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    documents = documents or {}
    data = core.empty(identity(report, player))
    source = report.get("capture", report.get("source", {}))
    captured = timestamp(source.get("ratingAsOf") or report.get("generatedAt"))
    versions = report.get("currentNewDisplayVersions", [])
    snapshot_ids, play_ids = [], []
    pb_history = []

    def add(item):
        if not item.get("chartID"):
            raise ValueError("Personal data requires an exact provider chart ID")
        c, r = chart_record(item), observation(item)
        data["charts"][c["chartID"]] = c
        ref = core.digest(r)
        data["records"][ref] = r
        return ref

    before_payload = documents.get("before-pbs.json")
    if before_payload is not None and body(before_payload).get("pbs"):
        baseline = documents.get("baseline.json", {})
        # A before-sync capture has no independent timestamp in older archives.
        # Its phase states what was observed, without inventing a prior play time.
        when = timestamp(report.get("comparison", {}).get("baselineAt")) or captured
        if baseline.get("capturedAt") and baseline.get("pbsPayload") == before_payload:
            when = timestamp(baseline["capturedAt"])
        before_rows = compact_payload(before_payload, "pbs")
        refs = {str(r["chartID"]): add(r) for r in before_rows}
        pb_history.append((when, before_rows))
        snap = {
            "capturedAt": when,
            "phase": "before",
            "complete": True,
            "versions": versions,
            "pbs": refs,
        }
        sid = core.digest(snap)
        data["snapshots"][sid] = snap
        snapshot_ids.append(sid)
    complete = after_payload is not None and isinstance(body(after_payload).get("pbs"), list)
    rows = (
        compact_payload(after_payload, "pbs")
        if complete
        else list(
            {
                r["chartID"]: r
                for name in ("old35", "new15", "newPool")
                for r in report.get("after", {}).get(name, [])
                if r.get("chartID")
            }.values()
        )
    )
    refs = {str(r["chartID"]): add(r) for r in rows}
    pb_history.append((captured, rows))
    snap = {
        "capturedAt": captured,
        "phase": "after",
        "complete": complete,
        "versions": versions,
        "pbs": refs,
    }
    sid = core.digest(snap)
    data["snapshots"][sid] = snap
    snapshot_ids.append(sid)
    raw_rows = []
    for name in ("before-recent-scores.json", "after-recent-scores.json"):
        raw_rows.extend(compact_payload(documents.get(name), "scores"))
    # Keep source score IDs. A legacy compact score without one is retained with
    # a capture-local identity; identical timestamps never collapse repeat plays.
    raw_rows.extend(report.get("session", {}).get("scores", []))
    for index, row in enumerate(raw_rows):
        ref = add(row)
        pid = str(row.get("scoreID") or f"legacy:{core.digest([captured, index, ref])}")
        old = data["plays"].get(pid)
        if old is None or data["records"][old] == data["records"][ref]:
            data["plays"][pid] = ref
        elif row.get("scoreID") and index >= len(raw_rows) - len(
            report.get("session", {}).get("scores", [])
        ):
            # Compact views omit optional fields. Keep the raw observation.
            pass
        else:
            data["plays"][pid] = ref
        play_ids.append(pid)
    capture = {
        "capturedAt": captured,
        "sourceKind": str(source.get("kind") or "sync"),
        "sourceID": str(
            documents.get("metadata.json", {}).get("importID") or source.get("sessionID") or ""
        ),
        "sessionID": str(source.get("sessionID") or ""),
        "historyCoverage": "complete-session"
        if source.get("kind") == "session"
        else "retained-window",
        "playIDs": sorted(set(play_ids)),
        "snapshotIDs": sorted(snapshot_ids),
    }
    data["captures"][core.digest(capture)] = capture
    # These scores predate their PB snapshot and do not belong to this session.
    # Keep their provenance separate, including when an actual recent score also
    # exists. Provider IDs deduplicate repeated snapshots and subsequent imports.
    raw_play_ids = set(data["plays"])
    recovered_ids = set()
    for when, history_rows in sorted(pb_history, key=lambda item: item[0]):
        for row in history_rows:
            pid = pb_play_id(row, when)
            if pid is None:
                continue
            ref = add(row)
            if (
                pid in data["plays"]
                and data["records"][data["plays"][pid]]["chartID"] != row["chartID"]
            ):
                raise ValueError("A retained source score refers to different charts")
            if pid not in raw_play_ids:
                data["plays"][pid] = ref
            recovered_ids.add(pid)
    if recovered_ids:
        history_capture = {
            "capturedAt": captured,
            "sourceKind": "pb-history",
            "sourceID": capture["sourceID"],
            "sessionID": "",
            "historyCoverage": "retained-window",
            # Recent observations in these same documents provide evidence to
            # reconcile legacy summaries, without attributing older PBs to a session.
            "playIDs": sorted(recovered_ids | raw_play_ids),
            "snapshotIDs": [],
        }
        data["captures"][core.digest(history_capture)] = history_capture
    return core.reconcile(core.seal(data))


def documents_from_directory(path):
    names = (
        "report-input.json",
        "metadata.json",
        "after-pbs.json",
        "before-pbs.json",
        "before-recent-scores.json",
        "after-recent-scores.json",
        "baseline.json",
        "kamaitachi-session.json",
    )
    result = {}
    for name in names:
        file = path / name
        if file.is_symlink():
            raise ValueError("History inputs may not be symlinks")
        if file.is_file():
            if file.stat().st_size > 20 * 1024 * 1024:
                raise ValueError("Retained capture input exceeds 20 MiB")
            result[name] = json.loads(file.read_bytes())
    return result


def from_path(path, *, player=None):
    path = Path(path)
    if path.is_symlink():
        raise ValueError("History inputs may not be symlinks")
    if path.is_file():
        yield core.read(path)
    elif (path / "report-input.json").is_file():
        docs = documents_from_directory(path)
        if docs.get("metadata.json", {}).get("syncCompleted") is not True:
            raise ValueError("History capture does not confirm completion")
        yield from_documents(
            docs["report-input.json"], docs.get("after-pbs.json"), documents=docs, player=player
        )
    elif (path / "manifest.json").is_file():
        from .history.bundle import read_bundle

        bundle = read_bundle(path)
        yield from_bundle(bundle, player=player)
    elif path.is_dir():
        children = sorted(
            p
            for p in path.iterdir()
            if p.is_dir()
            and not p.is_symlink()
            and ((p / "report-input.json").is_file() or (p / "manifest.json").is_file())
        )
        if not children:
            raise ValueError("No retained captures found in history folder")
        for child in children:
            if (child / "report-input.json").is_file() or (child / "manifest.json").is_file():
                yield from from_path(child, player=player)
    else:
        raise ValueError("Player history input does not exist")


def from_bundle(bundle, *, player=None):
    from .history.bundle import sha256, validate_capture_contents, validate_manifest

    validate_manifest(bundle.manifest)
    for entry in bundle.manifest["files"].values():
        raw = bundle.objects.get(entry["key"])
        if raw is None or len(raw) != entry["bytes"] or sha256(raw) != entry["sha256"]:
            raise ValueError("Retained capture failed object verification")
    validate_capture_contents(bundle)
    docs = {
        name: json.loads(bundle.objects[entry["key"]])
        for name, entry in bundle.manifest["files"].items()
        if name.endswith(".json")
    }
    return from_documents(
        docs["report-input.json"], docs.get("after-pbs.json"), documents=docs, player=player
    )


@contextmanager
def file_lock(path):
    lock = Path(str(path) + ".lock")
    lock.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise ValueError(
            "Another process is updating this player file. Retry when it completes."
        ) from None
    try:
        os.close(descriptor)
        yield
    finally:
        lock.unlink(missing_ok=True)


def prepare_dataset(
    report, *, source=None, history=(), player_file=None, dataset=None, after_payload=None
):
    datasets = []
    player = report.get("player")
    if source is not None and (Path(source) / "report-input.json").is_file():
        # The current render may explicitly supply just analytical input and PBs.
        # Additional history imports still require a validated complete capture.
        docs = documents_from_directory(Path(source))
        datasets.append(from_documents(report, docs.get("after-pbs.json"), documents=docs))
    else:
        datasets.append(dataset or from_documents(report, after_payload))
    for path in history:
        datasets.extend(from_path(path, player=player))
    if player_file:
        with file_lock(player_file):
            if Path(player_file).exists():
                datasets.insert(0, core.read(player_file))
            result = core.merge(*datasets)
            core.write(player_file, result)
    else:
        result = core.merge(*datasets)
    return result
