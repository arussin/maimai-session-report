"""Deterministic, fictional report scenarios.

Every title, artist, identifier, score, and timestamp in this module is synthetic.
The fixtures intentionally resemble Kamaitachi response shapes without containing
player data copied from any account.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

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
_GRADES = ("S", "S+", "SS", "SS+", "SSS", "SSS+")
_LAMPS = ("CLEAR", "FULL COMBO", "FULL COMBO+", "ALL PERFECT")
_UNICODE_TITLES = (
    "星屑コンチェルト（Synthetic）",
    "夜明けのシグナル（Synthetic）",
    "月光ステップ（Synthetic）",
    "虹色リズム（Synthetic）",
)


def _record(index: int, *, current: bool, rate: int) -> dict[str, Any]:
    prefix = "Current" if current else "Legacy"
    song_id = f"synthetic-song-{'new' if current else 'old'}-{index:02d}"
    chart_id = f"synthetic-chart-{'new' if current else 'old'}-{index:02d}"
    title = (
        _UNICODE_TITLES[index]
        if current and index < len(_UNICODE_TITLES)
        else f"Synthetic {prefix} Track {index + 1:02d}"
    )
    level_num = 10.0 + (index % 10) * 0.4 + (1.0 if current else 0.0)
    percent = min(100.5, 96.2 + (index % 9) * 0.53)
    fast = 8 + (index * 7) % 48
    slow = 6 + (index * 11) % 52
    return {
        "chartID": chart_id,
        "songID": song_id,
        "title": title,
        "artist": f"Example Composer {(index % 5) + 1}",
        "difficulty": _DIFFICULTIES[index % len(_DIFFICULTIES)],
        "level": f"{level_num:.1f}",
        "levelNum": level_num,
        "displayVersion": CURRENT_VERSION if current else LEGACY_VERSION,
        "percent": round(percent, 4),
        "rate": rate,
        "grade": _GRADES[index % len(_GRADES)],
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


def _summary(
    old_pool: list[dict[str, Any]],
    current_pool: list[dict[str, Any]],
) -> dict[str, Any]:
    old35 = old_pool[:35]
    new15 = current_pool[:15]
    all_rates = sorted([item["rate"] for item in old_pool + current_pool], reverse=True)
    old_rating = sum(item["rate"] for item in old35)
    new_rating = sum(item["rate"] for item in new15)
    return {
        "pbCount": len(old_pool) + len(current_pool),
        "naiveRating": sum(all_rates[:50]),
        "old35Rating": old_rating,
        "new15Rating": new_rating,
        "reconstructedRating": old_rating + new_rating,
        "newPoolPlayed": len(current_pool),
        "newSlotsFilled": len(new15),
        "old35Floor": old35[-1]["rate"] if len(old35) == 35 else 0,
        "new15Floor": new15[-1]["rate"] if len(new15) == 15 else 0,
        "old35": deepcopy(old35),
        "new15": deepcopy(new15),
    }


def _session(
    old_pool: list[dict[str, Any]],
    current_pool: list[dict[str, Any]],
    *,
    incomplete: bool,
) -> dict[str, Any]:
    selected = [current_pool[0], current_pool[-1], old_pool[0], old_pool[8]]
    if not incomplete:
        selected.extend((current_pool[5], old_pool[17]))

    changed: list[dict[str, Any]] = []
    for index, source in enumerate(selected):
        item = deepcopy(source)
        is_new = index in ({0, 1} if incomplete else {0, 1, 4})
        item["changeType"] = "new" if is_new else "improved"
        item["previousPercent"] = None if is_new else round(item["percent"] - 0.42, 4)
        item["previousRate"] = None if is_new else item["rate"] - (5 + index * 2)
        item["timeAchieved"] = BASE_TIME + index * 7 * 60_000
        changed.append(item)

    scores = [deepcopy(item) for item in changed]
    for index, item in enumerate(scores):
        item.pop("changeType", None)
        item.pop("previousPercent", None)
        item.pop("previousRate", None)
        item["timeAchieved"] = BASE_TIME + index * 7 * 60_000
    if not incomplete:
        for index, source in enumerate((old_pool[3], current_pool[9]), start=len(scores)):
            item = deepcopy(source)
            item["rate"] -= 9
            item["percent"] = round(item["percent"] - 0.31, 4)
            item["timeAchieved"] = BASE_TIME + index * 7 * 60_000
            scores.append(item)

    return {
        "cutoffTimeAchieved": BASE_TIME - 1,
        "scoreCount": len(scores),
        "scores": scores,
        "changedPBCount": len(changed),
        "newPBCount": sum(item["changeType"] == "new" for item in changed),
        "improvedPBCount": sum(item["changeType"] == "improved" for item in changed),
        "changedPBs": changed,
    }


def _build_active(*, current_count: int, incomplete: bool) -> tuple[dict[str, Any], dict[str, Any]]:
    old_pool = [_record(index, current=False, rate=315 - index * 2) for index in range(35)]
    current_pool = [
        _record(index, current=True, rate=326 - index * 3) for index in range(current_count)
    ]
    after = _summary(old_pool, current_pool)
    old_gain = 12 if incomplete else 24
    new_gain = 31 if incomplete else 47
    before = {
        **{key: deepcopy(value) for key, value in after.items()},
        "pbCount": after["pbCount"] - (2 if incomplete else 3),
        "naiveRating": after["naiveRating"] - old_gain - new_gain,
        "old35Rating": after["old35Rating"] - old_gain,
        "new15Rating": after["new15Rating"] - new_gain,
        "reconstructedRating": after["reconstructedRating"] - old_gain - new_gain,
        "newPoolPlayed": max(0, after["newPoolPlayed"] - 2),
        "newSlotsFilled": max(0, after["newSlotsFilled"] - 2),
    }
    report = {
        "generatedAt": "2026-05-28T18:30:00Z",
        "ratingVersionAssumption": "Synthetic configured-version B35/N15",
        "currentNewDisplayVersions": [CURRENT_VERSION],
        "player": {
            "username": "sample-player",
            "displayName": "Sample Player",
            "timezone": "UTC",
            "game": "maimai DX",
        },
        "before": before,
        "after": after,
        "delta": {
            "pbCount": after["pbCount"] - before["pbCount"],
            "naiveRating": after["naiveRating"] - before["naiveRating"],
            "old35Rating": old_gain,
            "new15Rating": new_gain,
            "reconstructedRating": old_gain + new_gain,
        },
        "session": _session(old_pool, current_pool, incomplete=incomplete),
    }

    raw_parts = [_raw_record(item) for item in old_pool + current_pool]
    after_payload = {
        "success": True,
        "body": {
            "pbs": [part[0] for part in raw_parts],
            "charts": [part[1] for part in raw_parts],
            "songs": [part[2] for part in raw_parts],
        },
    }
    return report, after_payload


def _build_complete() -> tuple[dict[str, Any], dict[str, Any]]:
    # Eighteen played current-version charts exercise targets beyond the counted N15.
    return _build_active(current_count=18, incomplete=False)


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
    return _build_active(current_count=8, incomplete=True)


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
