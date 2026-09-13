"""Recover source-backed PB history without inventing composite or session plays."""

import unittest
from copy import deepcopy

from maimai_report._party import player_data as core
from maimai_report.party import from_documents


class PBPlayRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.report = {
            "player": {"username": "fixture"},
            "generatedAt": "2026-09-13T18:00:00Z",
            "capture": {"kind": "session", "sessionID": "later-session"},
        }
        self.pb = {
            "chartID": "older-chart",
            "songID": "older-song",
            "title": "Fictional older play",
            "difficulty": "DX ADVANCED",
            "levelNum": 8,
            "percent": 99.2345,
            "rate": 165,
            "lamp": "FULL COMBO+",
            "timeAchieved": 1786400000000,
            "composedFrom": [{"name": "Best Percent", "scoreID": "original-score"}],
        }

    def export(self, pb=None, report=None, **documents):
        return from_documents(report or self.report, {"pbs": [pb or self.pb]}, documents=documents)

    def test_original_date_and_id_are_recovered_without_assigning_later_session(self):
        data = self.export()
        self.assertEqual(list(data["plays"]), ["original-score"])
        play = data["records"][data["plays"]["original-score"]]
        self.assertEqual(play["timeAchieved"], self.pb["timeAchieved"])
        self.assertEqual(play["achievement"], 992345)
        session = next(c for c in data["captures"].values() if c["sessionID"])
        self.assertEqual(session["playIDs"], [])
        self.assertEqual(core.offer(data)["profile"]["sessionCount"], 1)
        history = next(c for c in data["captures"].values() if c["sourceKind"] == "pb-history")
        self.assertEqual(history["sessionID"], "")
        self.assertEqual(history["playIDs"], ["original-score"])

    def test_missing_ambiguous_or_invalid_provenance_does_not_create_plays(self):
        cases = [
            {"composedFrom": None},
            {"composedFrom": []},
            {"composedFrom": [{"name": "Best Lamp", "scoreID": "lamp-score"}]},
            {"composedFrom": self.pb["composedFrom"] + [{"name": "Best Lamp", "scoreID": "other"}]},
            {"composedFrom": [{"name": "Best Percent", "scoreID": ""}]},
            {"timeAchieved": None},
            {"timeAchieved": 0},
            {"timeAchieved": 2000000000000},
            {"percent": None},
        ]
        for change in cases:
            with self.subTest(change=change):
                data = self.export({**self.pb, **change})
                self.assertEqual(data["plays"], {})
                self.assertEqual(len(core.current(data)[0]), 1)

    def test_repeat_snapshots_old_file_and_reimport_preserve_one_play(self):
        old = self.export({**self.pb, "composedFrom": None})
        new = self.export(**{"before-pbs.json": {"pbs": [self.pb]}})
        later = self.export(report={**self.report, "generatedAt": "2026-09-14T18:00:00Z"})
        combined = core.merge(old, new, later, old, new)
        self.assertEqual(list(combined["plays"]), ["original-score"])
        self.assertEqual(combined, core.merge(later, new, old))
        self.assertTrue(set(old["records"]) <= set(combined["records"]))
        self.assertTrue(set(old["snapshots"]) <= set(combined["snapshots"]))

    def test_raw_score_takes_precedence_and_distinct_source_ids_stay_distinct(self):
        raw = {**self.pb, "scoreID": "original-score", "maxCombo": 369}
        repeat = {**raw, "scoreID": "another-score"}
        data = self.export(**{"after-recent-scores.json": {"scores": [raw, repeat]}})
        self.assertEqual(set(data["plays"]), {"original-score", "another-score"})
        self.assertEqual(data["records"][data["plays"]["original-score"]]["maxCombo"], 369)

    def test_compatible_legacy_summary_uses_recovered_source_identity(self):
        summary = {k: v for k, v in self.pb.items() if k != "composedFrom"}
        report = {**self.report, "session": {"scores": [summary]}}
        data = self.export(report=report)
        self.assertEqual(list(data["plays"]), ["original-score"])
        session = next(c for c in data["captures"].values() if c["sessionID"])
        self.assertEqual(session["playIDs"], ["original-score"])

    def test_raw_provider_payload_retains_provenance_but_not_in_observation(self):
        payload = {
            "body": {
                "pbs": [
                    {
                        "chartID": "older-chart",
                        "songID": "older-song",
                        "timeAchieved": self.pb["timeAchieved"],
                        "composedFrom": deepcopy(self.pb["composedFrom"]),
                        "scoreData": {"percent": 99.2345, "lamp": "FULL COMBO+"},
                        "calculatedData": {"rate": 165},
                    }
                ],
                "charts": [{"chartID": "older-chart", "difficulty": "DX ADVANCED", "levelNum": 8}],
                "songs": [{"id": "older-song", "title": "Fictional older play"}],
            }
        }
        before = deepcopy(payload)
        data = from_documents(self.report, payload)
        self.assertEqual(list(data["plays"]), ["original-score"])
        self.assertNotIn("composedFrom", data["records"][data["plays"]["original-score"]])
        self.assertEqual(payload, before)

    def test_before_snapshot_can_recover_a_play_absent_from_current_pb(self):
        data = from_documents(
            self.report, {"pbs": []}, documents={"before-pbs.json": {"pbs": [self.pb]}}
        )
        self.assertEqual(list(data["plays"]), ["original-score"])
        self.assertEqual(core.current(data)[0], {})
