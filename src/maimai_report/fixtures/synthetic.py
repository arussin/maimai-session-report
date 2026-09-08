"""Deterministic, fictional report scenarios.

Every title, artist, identifier, score, and timestamp in this module is synthetic.
The fixtures intentionally resemble Kamaitachi response shapes without containing
player data copied from any account.
"""

from __future__ import annotations

import datetime as dt
import math
from copy import deepcopy
from typing import Any

from ..calculations import build_report_input

CURRENT_VERSION = "maimai DX Synthetic Current"
LEGACY_VERSION = "maimai DX Synthetic Legacy"
SCENARIOS = ("complete", "empty", "incomplete")
BASE_TIME = 1_780_000_000_000

_DIFFICULTIES = (
    "DX BASIC",
    "DX ADVANCED",
    "DX EXPERT",
    "DX MASTER",
    "DX Re:MASTER",
)
_LAMPS = ("CLEAR", "FULL COMBO", "FULL COMBO+", "ALL PERFECT")
_UNICODE_TITLES = (
    "星屑コンチェルト（Synthetic）",
    "夜明けのシグナル（Synthetic）",
    "月光ステップ（Synthetic）",
    "虹色リズム（Synthetic）",
)


def _achievement(percent: float, level_num: float) -> dict[str, Any]:
    """Fictional scores follow the same documented threshold model as the UI."""
    thresholds = (
        (100.5, "SSS+", 22.4),
        (100, "SSS", 21.6),
        (99.5, "SS+", 21.1),
        (99, "SS", 20.8),
        (98, "S+", 20.3),
        (97, "S", 20.0),
        (94, "AAA", 17.6),
    )
    _, grade, coefficient = next(item for item in thresholds if percent >= item[0])
    return {
        "percent": round(percent, 4),
        "grade": grade,
        "rate": math.floor(level_num * min(percent, 100.5) / 100 * coefficient),
    }


def _record(index: int, *, current: bool) -> dict[str, Any]:
    prefix = "Current" if current else "Legacy"
    song_id = f"synthetic-song-{'new' if current else 'old'}-{index:02d}"
    chart_id = f"synthetic-chart-{'new' if current else 'old'}-{index:02d}"
    title = (
        _UNICODE_TITLES[index]
        if current and index < len(_UNICODE_TITLES)
        else f"Synthetic {prefix} Track {index + 1:02d}"
    )
    level_num = round((13.6 if current else 12.9) + (index % 10) * 0.1, 1)
    percent = (100.5, 99.85, 99.35, 98.7, 100.15, 98.4, 100.6, 99.7, 97.8)[index % 9]
    if current and index >= 16:
        # Uncounted, near-S charts make the real target calculation visible.
        level_num, percent = (14.8, 96.78) if index == 16 else (15.0, 96.42)
    fast = 8 + (index * 7) % 48
    slow = 6 + (index * 11) % 52
    return {
        "chartID": chart_id,
        "songID": song_id,
        "title": title,
        "artist": f"Example Composer {(index % 5) + 1}",
        "difficulty": _DIFFICULTIES[2 + index % 3],
        "level": str(int(level_num)) + ("+" if round(level_num % 1, 1) >= 0.7 else ""),
        "levelNum": level_num,
        "displayVersion": CURRENT_VERSION if current else LEGACY_VERSION,
        **_achievement(percent, level_num),
        "lamp": _LAMPS[index % len(_LAMPS)],
        "fast": fast,
        "slow": slow,
        "miss": index % 3,
        "good": 2 + index % 7,
        "great": 10 + index % 19,
        "perfect": 400 + index * 3,
        "pcrit": 700 + index * 5,
        "timeAchieved": BASE_TIME - (index + (0 if current else 100)) * 86_400_000,
    }


def _raw_record(record: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    pb = {
        "chartID": record["chartID"],
        "songID": record["songID"],
        "scoreData": {
            "percent": record["percent"],
            "grade": record["grade"],
            "lamp": record["lamp"],
            "optional": {"fast": record["fast"], "slow": record["slow"]},
            "judgements": {
                "miss": record["miss"],
                "good": record["good"],
                "great": record["great"],
                "perfect": record["perfect"],
                "pcrit": record["pcrit"],
            },
        },
        "calculatedData": {"rate": record["rate"]},
        "timeAchieved": record["timeAchieved"],
    }
    chart = {
        "chartID": record["chartID"],
        "songID": record["songID"],
        "difficulty": record["difficulty"],
        "level": record["level"],
        "levelNum": record["levelNum"],
        "data": {"displayVersion": record["displayVersion"]},
    }
    song = {
        "id": record["songID"],
        "title": record["title"],
        "artist": record["artist"],
    }
    return pb, chart, song


def _build_consistent(
    *, current_count: int, incomplete: bool
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Use the production model on invented before/after inputs, not adjusted totals."""
    old_pool = [_record(index, current=False) for index in range(35)]
    new_pool = [_record(index, current=True) for index in range(current_count)]
    records = old_pool + new_pool
    selected = [new_pool[0], new_pool[-1], old_pool[0], old_pool[8]]
    if not incomplete:
        selected.extend((new_pool[5], old_pool[17]))
    new_ids = {item["chartID"] for item in selected[:2]}
    if not incomplete:
        new_ids.add(new_pool[5]["chartID"])
    for index, item in enumerate(selected):
        item["timeAchieved"] = BASE_TIME + index * 7 * 60_000
    prior = []
    changed_ids = {item["chartID"] for item in selected}
    for item in records:
        if item["chartID"] in new_ids:
            continue
        previous = deepcopy(item)
        if item["chartID"] in changed_ids:
            previous.update(_achievement(item["percent"] - 0.63, item["levelNum"]))
            previous["timeAchieved"] = BASE_TIME - 86_400_000
        prior.append(previous)
    plays = deepcopy(selected)
    if not incomplete:
        for index, source in enumerate((old_pool[4], new_pool[9]), start=len(plays)):
            item = deepcopy(source)
            item.update(_achievement(item["percent"] - 0.31, item["levelNum"]))
            item["timeAchieved"] = BASE_TIME + index * 7 * 60_000
            plays.append(item)

    def body(items: list[dict[str, Any]], key: str) -> dict[str, Any]:
        parts = [_raw_record(item) for item in items]
        return {
            key: [part[0] for part in parts],
            "charts": [part[1] for part in parts],
            "songs": [part[2] for part in parts],
        }

    after = body(records, "pbs")
    cutoff = deepcopy(old_pool[-1])
    cutoff["timeAchieved"] = BASE_TIME - 1
    report = build_report_input(
        body(prior, "pbs"),
        body([cutoff], "scores"),
        after,
        body(plays, "scores"),
        (CURRENT_VERSION,),
        generated_at=dt.datetime.fromtimestamp((plays[-1]["timeAchieved"] + 60_000) / 1000, dt.UTC),
    )
    report["player"] = {
        "username": "sample-player",
        "displayName": "Sample Player",
        "timezone": "UTC",
        "game": "maimai DX",
    }
    return report, {"success": True, "body": after}


def _build_complete() -> tuple[dict[str, Any], dict[str, Any]]:
    # Eighteen played current-version charts exercise targets beyond the counted N15.
    return _build_consistent(current_count=18, incomplete=False)


def _build_empty() -> tuple[dict[str, Any], dict[str, Any]]:
    report, after_payload = _build_complete()
    report["generatedAt"] = "2026-05-29T18:30:00Z"
    report["before"] = deepcopy(report["after"])
    report["delta"] = {
        "pbCount": 0,
        "naiveRating": 0,
        "old35Rating": 0,
        "new15Rating": 0,
        "reconstructedRating": 0,
    }
    report["session"] = {
        "cutoffTimeAchieved": BASE_TIME,
        "scoreCount": 0,
        "scores": [],
        "changedPBCount": 0,
        "newPBCount": 0,
        "improvedPBCount": 0,
        "changedPBs": [],
    }
    return report, after_payload


def _build_incomplete() -> tuple[dict[str, Any], dict[str, Any]]:
    return _build_consistent(current_count=8, incomplete=True)


def load_scenario(name: str = "complete") -> tuple[dict[str, Any], dict[str, Any]]:
    """Return independent copies of one bundled scenario."""

    builders = {
        "complete": _build_complete,
        "empty": _build_empty,
        "incomplete": _build_incomplete,
    }
    try:
        report, after_payload = builders[name]()
    except KeyError as exc:
        choices = ", ".join(SCENARIOS)
        raise ValueError(f"Unknown demo scenario {name!r}; choose one of: {choices}") from exc
    return deepcopy(report), deepcopy(after_payload)


__all__ = ["CURRENT_VERSION", "LEGACY_VERSION", "SCENARIOS", "load_scenario"]
