"""Pure score compaction, rating-pool, and session-delta calculations."""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable
from typing import Any

from .errors import CalculationError

JSONDict = dict[str, Any]


def make_maps(body: JSONDict) -> tuple[dict[str, JSONDict], dict[str, JSONDict]]:
    charts = body.get("charts")
    songs = body.get("songs")
    if not isinstance(charts, list) or not isinstance(songs, list):
        raise CalculationError("Score data is missing its charts or songs list.")
    chart_map = {
        chart["chartID"]: chart
        for chart in charts
        if isinstance(chart, dict) and isinstance(chart.get("chartID"), str)
    }
    song_map = {
        song["id"]: song
        for song in songs
        if isinstance(song, dict) and isinstance(song.get("id"), str)
    }
    return chart_map, song_map


def compact_record(
    record: JSONDict,
    chart_map: dict[str, JSONDict],
    song_map: dict[str, JSONDict],
) -> JSONDict:
    chart = chart_map.get(record.get("chartID"), {})
    song = song_map.get(record.get("songID"), {})
    if not song and isinstance(chart.get("song"), dict):
        song = chart["song"]

    score_data = record.get("scoreData") if isinstance(record.get("scoreData"), dict) else {}
    optional = score_data.get("optional") if isinstance(score_data.get("optional"), dict) else {}
    judgements = (
        score_data.get("judgements") if isinstance(score_data.get("judgements"), dict) else {}
    )
    calculated = (
        record.get("calculatedData") if isinstance(record.get("calculatedData"), dict) else {}
    )
    chart_data = chart.get("data") if isinstance(chart.get("data"), dict) else {}

    return {
        "scoreID": record.get("scoreID"),
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


def rate_value(record: JSONDict) -> int:
    calculated = record.get("calculatedData")
    if not isinstance(calculated, dict):
        return 0
    value = calculated.get("rate")
    return value if isinstance(value, int) else 0


def percent_value(record: JSONDict) -> float:
    score_data = record.get("scoreData")
    if not isinstance(score_data, dict):
        return -1.0
    value = score_data.get("percent")
    return float(value) if isinstance(value, (int, float)) else -1.0


def display_version(record: JSONDict, chart_map: dict[str, JSONDict]) -> str | None:
    chart = chart_map.get(record.get("chartID"), {})
    data = chart.get("data")
    if not isinstance(data, dict):
        return None
    value = data.get("displayVersion")
    return value if isinstance(value, str) else None


def rating_summary(
    body: JSONDict,
    current_version_display_names: Iterable[str],
) -> JSONDict:
    """Calculate the audited top-35 legacy plus top-15 current-version pools."""

    chart_map, song_map = make_maps(body)
    pbs_value = body.get("pbs")
    if not isinstance(pbs_value, list):
        raise CalculationError("PB data is missing its pbs list.")
    pbs = [pb for pb in pbs_value if isinstance(pb, dict)]
    sorted_pbs = sorted(pbs, key=rate_value, reverse=True)
    current_versions = frozenset(current_version_display_names)

    new_pool = [pb for pb in sorted_pbs if display_version(pb, chart_map) in current_versions]
    old_pool = [pb for pb in sorted_pbs if display_version(pb, chart_map) not in current_versions]
    new15 = new_pool[:15]
    old35 = old_pool[:35]
    best50 = sorted_pbs[:50]

    return {
        "pbCount": len(pbs),
        "naiveRating": sum(rate_value(pb) for pb in best50),
        "old35Rating": sum(rate_value(pb) for pb in old35),
        "new15Rating": sum(rate_value(pb) for pb in new15),
        "reconstructedRating": sum(rate_value(pb) for pb in old35 + new15),
        "newPoolPlayed": len(new_pool),
        "newSlotsFilled": len(new15),
        "old35Floor": rate_value(old35[-1]) if len(old35) == 35 else 0,
        "new15Floor": rate_value(new15[-1]) if len(new15) == 15 else 0,
        "old35": [compact_record(pb, chart_map, song_map) for pb in old35],
        "new15": [compact_record(pb, chart_map, song_map) for pb in new15],
    }


def build_report_input(
    before_pbs: JSONDict,
    before_scores: JSONDict,
    after_pbs: JSONDict,
    after_scores: JSONDict,
    current_version_display_names: Iterable[str],
    *,
    generated_at: dt.datetime | None = None,
) -> JSONDict:
    """Build the compact deterministic report model from validated API bodies."""

    versions = tuple(sorted(set(current_version_display_names)))
    after_chart_map, after_song_map = make_maps(after_pbs)
    after_score_chart_map, after_score_song_map = make_maps(after_scores)

    before_pb_values = before_pbs.get("pbs")
    after_pb_values = after_pbs.get("pbs")
    before_score_values = before_scores.get("scores")
    after_score_values = after_scores.get("scores")
    if not isinstance(before_pb_values, list) or not isinstance(after_pb_values, list):
        raise CalculationError("Before/after PB data must contain pbs lists.")
    if not isinstance(before_score_values, list) or not isinstance(after_score_values, list):
        raise CalculationError("Before/after recent-score data must contain scores lists.")

    before_pb_map = {
        pb["chartID"]: pb
        for pb in before_pb_values
        if isinstance(pb, dict) and isinstance(pb.get("chartID"), str)
    }

    changed: list[JSONDict] = []
    for pb in after_pb_values:
        if not isinstance(pb, dict) or not isinstance(pb.get("chartID"), str):
            continue
        previous = before_pb_map.get(pb["chartID"])
        if (
            previous is None
            or rate_value(previous) != rate_value(pb)
            or percent_value(previous) != percent_value(pb)
            or previous.get("scoreData", {}).get("lamp") != pb.get("scoreData", {}).get("lamp")
        ):
            compact = compact_record(pb, after_chart_map, after_song_map)
            compact["changeType"] = "new" if previous is None else "improved"
            compact["previousPercent"] = None if previous is None else percent_value(previous)
            compact["previousRate"] = None if previous is None else rate_value(previous)
            compact["previousLamp"] = (
                None if previous is None else previous.get("scoreData", {}).get("lamp")
            )
            changed.append(compact)

    before_score_times = [
        score.get("timeAchieved")
        for score in before_score_values
        if isinstance(score, dict) and isinstance(score.get("timeAchieved"), int)
    ]
    cutoff = max(before_score_times, default=None)

    session_scores: list[JSONDict] = []
    for score in after_score_values:
        if not isinstance(score, dict):
            continue
        achieved = score.get("timeAchieved")
        if not isinstance(achieved, int):
            continue
        if cutoff is None or achieved > cutoff:
            session_scores.append(
                compact_record(score, after_score_chart_map, after_score_song_map)
            )
    session_scores.sort(key=lambda item: item.get("timeAchieved") or 0)

    before_rating = rating_summary(before_pbs, versions)
    after_rating = rating_summary(after_pbs, versions)

    return {
        "generatedAt": _format_timestamp(generated_at),
        "ratingVersionAssumption": "Configured-version Old 35 + New 15",
        "currentNewDisplayVersions": list(versions),
        "before": before_rating,
        "after": after_rating,
        "delta": {
            "pbCount": after_rating["pbCount"] - before_rating["pbCount"],
            "naiveRating": after_rating["naiveRating"] - before_rating["naiveRating"],
            "old35Rating": after_rating["old35Rating"] - before_rating["old35Rating"],
            "new15Rating": after_rating["new15Rating"] - before_rating["new15Rating"],
            "reconstructedRating": (
                after_rating["reconstructedRating"] - before_rating["reconstructedRating"]
            ),
        },
        "session": {
            "cutoffTimeAchieved": cutoff,
            "scoreCount": len(session_scores),
            "scores": session_scores,
            "changedPBCount": len(changed),
            "newPBCount": sum(1 for item in changed if item["changeType"] == "new"),
            "improvedPBCount": sum(1 for item in changed if item["changeType"] == "improved"),
            "changedPBs": sorted(
                changed,
                key=lambda item: (
                    (item.get("rate") or 0) - (item.get("previousRate") or 0),
                    item.get("percent") or 0,
                ),
                reverse=True,
            ),
        },
    }


def _format_timestamp(value: dt.datetime | None) -> str:
    timestamp = dt.datetime.now(dt.UTC) if value is None else value
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise CalculationError("generated_at must include timezone information.")
    return timestamp.astimezone(dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
