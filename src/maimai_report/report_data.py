"""Pure display-data enrichment before explicit report preparation."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def support_enabled(value: object) -> bool:
    if not isinstance(value, bool):
        raise ValueError("Support must be true or false")
    return value


def _payload_body(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    body = payload.get("body")
    if isinstance(body, Mapping):
        return body
    if all(key in payload for key in ("pbs", "charts", "songs")):
        return payload
    raise ValueError("after-pbs JSON must contain a body object with pbs, charts, and songs")


def _make_maps(
    body: Mapping[str, Any],
) -> tuple[dict[str, Mapping[str, Any]], dict[str, Mapping[str, Any]]]:
    charts = body.get("charts")
    songs = body.get("songs")
    if not isinstance(charts, list) or not isinstance(songs, list):
        raise ValueError("after-pbs JSON is missing the charts or songs list")

    chart_map = {
        chart["chartID"]: chart
        for chart in charts
        if isinstance(chart, Mapping) and isinstance(chart.get("chartID"), str)
    }
    song_map = {
        song["id"]: song
        for song in songs
        if isinstance(song, Mapping) and isinstance(song.get("id"), str)
    }
    return chart_map, song_map


def _rate_value(record: Mapping[str, Any]) -> int:
    calculated = record.get("calculatedData")
    if not isinstance(calculated, Mapping):
        return 0
    value = calculated.get("rate")
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _display_version(
    record: Mapping[str, Any], chart_map: Mapping[str, Mapping[str, Any]]
) -> str | None:
    chart = chart_map.get(record.get("chartID"), {})
    chart_data = chart.get("data")
    if not isinstance(chart_data, Mapping):
        return None
    value = chart_data.get("displayVersion")
    return value if isinstance(value, str) else None


def _compact_record(
    record: Mapping[str, Any],
    chart_map: Mapping[str, Mapping[str, Any]],
    song_map: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    chart = chart_map.get(record.get("chartID"), {})
    song = song_map.get(record.get("songID"), {})
    if not song and isinstance(chart.get("song"), Mapping):
        song = chart["song"]

    score_data = record.get("scoreData")
    score_data = score_data if isinstance(score_data, Mapping) else {}
    optional = score_data.get("optional")
    optional = optional if isinstance(optional, Mapping) else {}
    judgements = score_data.get("judgements")
    judgements = judgements if isinstance(judgements, Mapping) else {}
    calculated = record.get("calculatedData")
    calculated = calculated if isinstance(calculated, Mapping) else {}
    chart_data = chart.get("data")
    chart_data = chart_data if isinstance(chart_data, Mapping) else {}

    return {
        "chartID": record.get("chartID"),
        "songID": record.get("songID"),
        "title": song.get("title"),
        "artist": song.get("artist"),
        "difficulty": chart.get("difficulty"),
        "level": chart.get("level"),
        "levelNum": chart.get("levelNum"),
        "displayVersion": chart_data.get("displayVersion"),
        "percent": score_data.get("percent"),
        "rate": calculated.get("rate"),
        "grade": score_data.get("grade"),
        "lamp": score_data.get("lamp"),
        "fast": optional.get("fast"),
        "slow": optional.get("slow"),
        "miss": judgements.get("miss"),
        "good": judgements.get("good"),
        "great": judgements.get("great"),
        "perfect": judgements.get("perfect"),
        "pcrit": judgements.get("pcrit"),
        "timeAchieved": record.get("timeAchieved"),
    }


def _version_names(
    report: Mapping[str, Any], explicit: Sequence[str] | None, *, required: bool
) -> list[str]:
    values: object = explicit if explicit is not None else report.get("currentNewDisplayVersions")
    if values is None:
        if required:
            raise ValueError(
                "Current-version display names are required to classify the New 15 pool"
            )
        return []
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise ValueError("Current-version display names must be a list of non-empty strings")
    names = sorted({value.strip() for value in values if isinstance(value, str) and value.strip()})
    if not names:
        raise ValueError("At least one current-version display name is required")
    if len(names) != len(values):
        invalid = [value for value in values if not isinstance(value, str) or not value.strip()]
        if invalid:
            raise ValueError("Current-version display names must be non-empty strings")
    return names


def _player_data(existing: object, overlay: Mapping[str, str] | None) -> dict[str, str]:
    result: dict[str, str] = {
        "username": "player",
        "displayName": "Player",
        "timezone": "UTC",
        "game": "maimai DX",
    }
    if existing is not None:
        if not isinstance(existing, Mapping):
            raise ValueError("report-input player value must be an object")
        for key in result:
            value = existing.get(key)
            if isinstance(value, str) and value.strip():
                result[key] = value.strip()
    if overlay is not None:
        aliases = {"display_name": "displayName"}
        for input_key, value in overlay.items():
            key = aliases.get(input_key, input_key)
            if key in result:
                if not isinstance(value, str) or not value.strip():
                    raise ValueError(f"Player {input_key!r} must be a non-empty string")
                result[key] = value.strip()
    if result["displayName"] == "Player" and result["username"] != "player":
        result["displayName"] = result["username"]
    if result["timezone"] != "UTC":
        try:
            ZoneInfo(result["timezone"])
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(
                f"Unknown or unavailable IANA timezone {result['timezone']!r}; correct "
                "the name, or on Windows install the project's 'timezone' extra"
            ) from exc
    return result


def enrich_report_data(
    report: dict[str, Any],
    after_payload: dict[str, Any] | None = None,
    *,
    player: Mapping[str, str] | None = None,
    current_version_display_names: Sequence[str] | None = None,
    support: bool | None = None,
) -> dict[str, Any]:
    """Return a display-ready copy of an existing report input.

    When an after-PBs response is supplied, all current-version PBs are compacted
    into ``after.newPool`` for target suggestions. No input object is mutated.
    """

    if not isinstance(report, dict):
        raise ValueError("report-input JSON must be an object")
    result = deepcopy(report)
    versions = _version_names(
        result,
        current_version_display_names,
        required=after_payload is not None,
    )
    if versions:
        result["currentNewDisplayVersions"] = versions

    after = result.setdefault("after", {})
    if not isinstance(after, dict):
        raise ValueError("report-input after value must be an object")

    if after_payload is not None:
        if not isinstance(after_payload, dict):
            raise ValueError("after-pbs JSON must be an object")
        body = _payload_body(after_payload)
        pbs = body.get("pbs")
        if not isinstance(pbs, list):
            raise ValueError("after-pbs JSON is missing the pbs list")
        chart_map, song_map = _make_maps(body)
        version_set = set(versions)
        new_pool = [
            pb
            for pb in pbs
            if isinstance(pb, Mapping) and _display_version(pb, chart_map) in version_set
        ]
        # Python's stable sort preserves the upstream PB order for equal rates.
        # The original report used that order, so retaining it avoids a visual
        # reshuffle during migration while still ranking higher rates first.
        new_pool.sort(key=_rate_value, reverse=True)
        after["newPool"] = [_compact_record(pb, chart_map, song_map) for pb in new_pool]

    session = result.setdefault("session", {})
    if not isinstance(session, dict):
        raise ValueError("report-input session value must be an object")
    scores = session.get("scores", [])
    if not isinstance(scores, list):
        raise ValueError("report-input session scores must be a list")
    achieved_times = [
        item["timeAchieved"]
        for item in scores
        if isinstance(item, Mapping)
        and isinstance(item.get("timeAchieved"), int)
        and not isinstance(item.get("timeAchieved"), bool)
    ]
    session["startTimeAchieved"] = min(achieved_times) if achieved_times else None
    session["endTimeAchieved"] = max(achieved_times) if achieved_times else None

    result["support"] = support_enabled(
        support if support is not None else result.get("support", True)
    )

    result["schemaVersion"] = 1
    result["player"] = _player_data(result.get("player"), player)
    result.setdefault("ratingVersionAssumption", "Configured current-version B35/N15")
    return result
