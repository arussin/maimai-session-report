"""Play identity must come from source evidence, not similar-looking scores."""

import unittest
from copy import deepcopy

from maimai_report._party import player_data as core

LEGACY = "legacy:" + "a" * 64


def fixture():
    data = core.empty(
        {
            "provider": "kamaitachi",
            "game": "maimaidx",
            "username": "fixture",
            "displayName": "Fixture",
            "key": "kamaitachi:maimaidx:fixture",
        }
    )
    chart = {k: "" for k in core.CHART_FIELDS}
    chart.update(
        chartID="chart",
        songID="song",
        format="DX",
        difficulty="EXPERT",
        constant=100,
        inGameID=None,
    )
    data["charts"]["chart"] = chart
    record = {k: None for k in core.RECORD_FIELDS}
    record.update(
        chartID="chart",
        achievement=970000,
        timeAchieved=1000,
        grade="S",
        rate=194,
        constant=100,
        lamp="CLEAR",
        sync="",
        displayVersion="old",
        maxCombo=120,
    )
    for pid, row in [("source-play", record), (LEGACY, {**record, "maxCombo": None})]:
        ref = core.digest(row)
        data["records"][ref] = row
        data["plays"][pid] = ref
    for when in [2000, 3000, 4000]:
        snap = {
            "capturedAt": when,
            "phase": "after",
            "complete": True,
            "versions": ["new"],
            "pbs": {"chart": core.digest(record)},
        }
        data["snapshots"][core.digest(snap)] = snap
    capture = {
        "capturedAt": 4000,
        "sourceKind": "sync",
        "sourceID": "fixture",
        "sessionID": "",
        "historyCoverage": "retained-window",
        "playIDs": list(data["plays"]),
        "snapshotIDs": list(data["snapshots"]),
    }
    data["captures"][core.digest(capture)] = capture
    return core.seal(data)


def reseal(data):
    data["captures"] = {core.digest(c): c for c in data["captures"].values()}
    return core.seal(data)


class ReconciliationTests(unittest.TestCase):
    def test_summary_copy_resolves_without_changing_pbs_or_source_observations(self):
        old = fixture()
        original = deepcopy(old)
        new = core.reconcile(old)
        self.assertEqual(list(new["plays"]), ["source-play"])
        self.assertEqual(new["records"], old["records"])
        self.assertEqual(new["snapshots"], old["snapshots"])
        self.assertEqual(core.current(new), core.current(old))
        self.assertEqual(old, original)
        self.assertEqual(core.reconcile(new), new)
        self.assertEqual(core.merge(old, new, old), new)
        self.assertEqual(core.merge(new, old), new)
        self.assertEqual(core.decode(core.encode(new)), new)

    def test_equal_scores_with_distinct_source_ids_and_ambiguous_summaries_survive(self):
        for second in ["another-source-play", "legacy:" + "b" * 64]:
            data = fixture()
            data["plays"][second] = data["plays"]["source-play"]
            next(iter(data["captures"].values()))["playIDs"].append(second)
            data = reseal(data)
            self.assertEqual(core.reconcile(data), data)

    def test_matching_across_unrelated_captures_is_not_enough(self):
        data = fixture()
        capture = next(iter(data["captures"].values()))
        other = {**deepcopy(capture), "capturedAt": 5000, "playIDs": [LEGACY]}
        capture["playIDs"] = ["source-play"]
        data["captures"][core.digest(other)] = other
        data = reseal(data)
        self.assertEqual(core.reconcile(data), data)

    def test_conflicting_known_fields_and_missing_play_times_are_not_guessed(self):
        for change in [{"maxCombo": 99}, {"timeAchieved": None}, {"timeAchieved": 0}]:
            data = fixture()
            row = {**data["records"][data["plays"][LEGACY]], **change}
            data["records"][core.digest(row)] = row
            data["plays"][LEGACY] = core.digest(row)
            data = reseal(data)
            self.assertEqual(core.reconcile(data), data)
