"""Authored sorting edge cases; no account data or retained report is read."""

from copy import deepcopy
from pathlib import Path

from maimai_report.fixtures import load_scenario
from maimai_report.render import build_html, enrich_report

# These deliberately include malformed/absent retained display fields. They test
# presentation ordering, not valid rating inputs or contribution attribution.
# Array positions are the expected detail identities in score-sort.spec.js.
columns = "title difficulty level levelNum percent grade rate fast slow timeAchieved".split()
values = [
    ["Sort 02 Twin", "Expert", "9", 9, "9.5", "D", "9", "9", 2, "1700000009000"],
    ["Sort 10 Zebra", "Expert", "9+", None, "100", "SSS+", "100", "10", 1, 1700000001000],
    ["Sort 02 Twin", "Expert", "9", 9, 99.9, "SSS", 100, 9, 10, 1700000003000],
    ["Sort 03 Basic", "Basic", "10", "10", 99.9, "SS+", 20, 9, 2, 1700000003000],
    ["Sort 04 Advanced", "DX Advanced", "9", 9, 0, "C", 0, 0, 0, 0],
    ["Sort 05 Master", "Master", "9", 9, None, None, None, None, None, None],
    ["Sort 06 Remaster", "DX Re:Master", "9", 9, "", "mystery", "", "", "", ""],
    [
        "Sort 07 Invalid",
        "DX Expert",
        "10",
        10,
        "invalid",
        "S",
        "invalid",
        "invalid",
        "invalid",
        "invalid",
    ],
    ["Sort 08 DX", "DX Expert", "9", 9, 98, "AAA", 80, 9, None, 1700000008000],
    ["Sort 09 Missing level", "Expert", "", None, 97, "AA", 70, None, 2, 1700000006000],
    ["", "", "", None, 95, "A", 60, 9, "invalid", 1700000005000],
    ["Sort 11 Missing constant", "Expert", "9+", None, 96, "BBB", 65, 9, 2, 1700000004000],
    ["Sort 12 Lower constant", "Expert", "9", 8.9, 94, "BB", 55, 9, 2, 1700000007000],
]
scores = []
for index, row in enumerate(values):
    identity = 0 if index == 2 else index
    scores.append(
        dict(
            zip(columns, row, strict=True),
            songID=f"synthetic-sort-song-{identity}",
            chartID=f"synthetic-sort-chart-{identity}",
            artist="Synthetic Sorting Composer",
            displayVersion="Synthetic Sorting Version",
            lamp="FULL COMBO" if index == 2 else "CLEAR",
            pcrit=100 + index,
            perfect=200 + index,
            great=index,
            good=0,
            miss=0,
        )
    )

# new PBs use a zero baseline; improved PBs require both retained ratings.
changes = []
for index, kind, previous in [
    (2, "improved", "9"),
    (3, "new", None),
    (8, "improved", "70"),
    (9, "improved", 70),
    (1, "improved", 120),
    (5, "improved", 10),
    (12, "improved", None),
    (11, "improved", ""),
    (7, "improved", 50),
    (4, "new", None),
]:
    item = deepcopy(scores[index])
    item.update(
        changeType=kind, previousRate=previous, previousPercent=None if kind == "new" else 9
    )
    changes.append(item)

source, pbs = load_scenario("empty")
report = enrich_report(source, pbs)
report["player"]["displayName"] = "Synthetic Sorting Player"
report["session"].update(scores=scores, changedPBs=changes, newPBCount=2, improvedPBCount=8)
root = Path(__file__).parent / "generated"
root.mkdir(exist_ok=True)
(root / "score-sort.html").write_text(build_html(report), encoding="utf-8")

# Visible levels form separate bands: normal 9 is before 9+, regardless of
# whether either record retained a chart constant. Never invent a 9+ constant.
level_scores = []
for index, (difficulty, level, constant) in enumerate(
    [
        ("Expert", "9", 9.5),
        ("Expert", "9+", None),
        ("Expert", "9", 9.6),
        ("DX Expert", "9+", 9.7),
        ("Expert", "10+", 10.7),
        ("Expert", "", None),
        ("Expert", "", 9.6),
        ("Expert", "9+", 9.7),
        ("Expert", "10", 10.4),
        ("Expert", "9", None),
    ]
):
    item = deepcopy(scores[0])
    item.update(
        title=f"Synthetic Level Sort {index}",
        songID=f"synthetic-level-song-{index}",
        chartID=f"synthetic-level-chart-{index}",
        difficulty=difficulty,
        level=level,
        levelNum=constant,
    )
    level_scores.append(item)
level_report = deepcopy(report)
level_report["session"].update(scores=level_scores, changedPBs=[], newPBCount=0, improvedPBCount=0)
(root / "score-sort-levels.html").write_text(build_html(level_report), encoding="utf-8")
