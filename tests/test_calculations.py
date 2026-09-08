from __future__ import annotations

import datetime as dt
import unittest
from typing import Any

from maimai_report.calculations import build_report_input, compact_record, make_maps, rating_summary
from maimai_report.errors import CalculationError


def score_parts(
    index: int,
    *,
    rate: int,
    version: str,
    percent: float = 97.0,
    achieved: int = 1_000,
    title: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    chart_id = f"chart-{index}"
    song_id = f"song-{index}"
    record = {
        "chartID": chart_id,
        "songID": song_id,
        "scoreData": {
            "percent": percent,
            "grade": "S",
            "lamp": "CLEAR",
            "optional": {"fast": index + 1, "slow": index + 2},
            "judgements": {
                "miss": 0,
                "good": 1,
                "great": 2,
                "perfect": 100,
                "pcrit": 500,
            },
        },
        "calculatedData": {"rate": rate},
        "timeAchieved": achieved,
    }
    chart = {
        "chartID": chart_id,
        "difficulty": "DX Master" if index % 2 else "Standard Expert",
        "level": "13+",
        "levelNum": 13.7,
        "data": {"displayVersion": version},
    }
    song = {
        "id": song_id,
        "title": title or f"Synthetic Song {index}",
        "artist": "Fixture Artist",
    }
    return record, chart, song


def body_from_parts(
    parts: list[tuple[dict[str, Any], dict[str, Any], dict[str, Any]]],
    *,
    key: str,
) -> dict[str, Any]:
    return {
        key: [record for record, _chart, _song in parts],
        "charts": [chart for _record, chart, _song in parts],
        "songs": [song for _record, _chart, song in parts],
    }


class RatingCalculationTests(unittest.TestCase):
    def test_old35_new15_and_naive_top50_are_classified_separately(self) -> None:
        old_parts = [
            score_parts(index, rate=1_500 - index, version="Legacy") for index in range(40)
        ]
        new_parts = [
            score_parts(100 + index, rate=2_000 - index, version="Current") for index in range(20)
        ]
        body = body_from_parts(old_parts + new_parts, key="pbs")

        summary = rating_summary(body, ("Current",))

        self.assertEqual(len(summary["old35"]), 35)
        self.assertEqual(len(summary["new15"]), 15)
        self.assertEqual(summary["newPoolPlayed"], 20)
        self.assertEqual(summary["newSlotsFilled"], 15)
        self.assertEqual(summary["old35Rating"], sum(1_500 - index for index in range(35)))
        self.assertEqual(summary["new15Rating"], sum(2_000 - index for index in range(15)))
        self.assertEqual(
            summary["reconstructedRating"],
            summary["old35Rating"] + summary["new15Rating"],
        )
        expected_naive = sum(2_000 - index for index in range(20)) + sum(
            1_500 - index for index in range(30)
        )
        self.assertEqual(summary["naiveRating"], expected_naive)
        self.assertEqual(summary["old35Floor"], 1_500 - 34)
        self.assertEqual(summary["new15Floor"], 2_000 - 14)

    def test_incomplete_pools_have_zero_floor_and_keep_all_entries(self) -> None:
        parts = [
            score_parts(1, rate=100, version="Current"),
            score_parts(2, rate=90, version="Current"),
            score_parts(3, rate=80, version="Legacy"),
        ]
        summary = rating_summary(body_from_parts(parts, key="pbs"), ("Current",))
        self.assertEqual(summary["newSlotsFilled"], 2)
        self.assertEqual(summary["new15Floor"], 0)
        self.assertEqual(summary["old35Floor"], 0)
        self.assertEqual(len(summary["old35"]), 1)

    def test_current_version_configuration_controls_classification(self) -> None:
        part = score_parts(1, rate=123, version="Version A")
        body = body_from_parts([part], key="pbs")
        self.assertEqual(rating_summary(body, ("Version A",))["newSlotsFilled"], 1)
        self.assertEqual(rating_summary(body, ("Version B",))["newSlotsFilled"], 0)
        self.assertEqual(len(rating_summary(body, ("Version B",))["old35"]), 1)

    def test_compact_record_preserves_unicode_and_html_special_text_as_data(self) -> None:
        part = score_parts(
            1,
            rate=123,
            version="現行版",
            title='曲 </script> & <b> "test"',
        )
        body = body_from_parts([part], key="pbs")
        chart_map, song_map = make_maps(body)
        compact = compact_record(part[0], chart_map, song_map)
        self.assertEqual(compact["title"], '曲 </script> & <b> "test"')
        self.assertEqual(compact["displayVersion"], "現行版")

    def test_missing_lists_fail_clearly(self) -> None:
        with self.assertRaisesRegex(CalculationError, "charts or songs"):
            rating_summary({"pbs": []}, ("Current",))


class SessionCalculationTests(unittest.TestCase):
    def test_changed_pbs_and_strict_session_cutoff(self) -> None:
        before_parts = [
            score_parts(1, rate=100, version="Legacy", percent=95.0),
            score_parts(2, rate=200, version="Current", percent=98.0),
        ]
        after_parts = [
            score_parts(1, rate=110, version="Legacy", percent=96.0, achieved=1_200),
            score_parts(2, rate=200, version="Current", percent=98.0, achieved=1_200),
            score_parts(3, rate=150, version="Current", percent=97.0, achieved=1_100),
        ]
        before_pbs = body_from_parts(before_parts, key="pbs")
        after_pbs = body_from_parts(after_parts, key="pbs")
        before_scores = body_from_parts(
            [score_parts(9, rate=50, version="Legacy", achieved=1_000)],
            key="scores",
        )
        after_score_parts = [
            score_parts(10, rate=50, version="Legacy", achieved=1_200),
            score_parts(11, rate=50, version="Legacy", achieved=1_000),
            score_parts(12, rate=50, version="Legacy", achieved=1_100),
        ]
        after_scores = body_from_parts(after_score_parts, key="scores")

        report = build_report_input(
            before_pbs,
            before_scores,
            after_pbs,
            after_scores,
            ("Current",),
            generated_at=dt.datetime(2026, 1, 2, 3, 4, 5, tzinfo=dt.UTC),
        )

        self.assertEqual(report["generatedAt"], "2026-01-02T03:04:05Z")
        self.assertEqual(report["currentNewDisplayVersions"], ["Current"])
        self.assertEqual(report["session"]["cutoffTimeAchieved"], 1_000)
        self.assertEqual(report["session"]["scoreCount"], 2)
        self.assertEqual(
            [item["timeAchieved"] for item in report["session"]["scores"]],
            [1_100, 1_200],
        )
        self.assertEqual(report["session"]["changedPBCount"], 2)
        self.assertEqual(report["session"]["newPBCount"], 1)
        self.assertEqual(report["session"]["improvedPBCount"], 1)
        changed = report["session"]["changedPBs"]
        self.assertEqual([item["chartID"] for item in changed], ["chart-3", "chart-1"])
        self.assertIsNone(changed[0]["previousRate"])
        self.assertEqual(changed[1]["previousRate"], 100)

    def test_percent_only_change_is_an_improved_pb(self) -> None:
        before_part = score_parts(1, rate=100, version="Legacy", percent=95.0)
        after_part = score_parts(1, rate=100, version="Legacy", percent=95.1)
        empty_scores = body_from_parts([], key="scores")
        report = build_report_input(
            body_from_parts([before_part], key="pbs"),
            empty_scores,
            body_from_parts([after_part], key="pbs"),
            empty_scores,
            ("Current",),
            generated_at=dt.datetime(2026, 1, 1, tzinfo=dt.UTC),
        )
        self.assertEqual(report["session"]["improvedPBCount"], 1)
        self.assertEqual(report["session"]["changedPBs"][0]["previousPercent"], 95.0)

    def test_empty_session_is_valid(self) -> None:
        part = score_parts(1, rate=100, version="Legacy", achieved=1_000)
        pbs = body_from_parts([part], key="pbs")
        scores = body_from_parts([part], key="scores")
        report = build_report_input(
            pbs,
            scores,
            pbs,
            scores,
            ("Current",),
            generated_at=dt.datetime(2026, 1, 1, tzinfo=dt.UTC),
        )
        self.assertEqual(report["session"]["scoreCount"], 0)
        self.assertEqual(report["session"]["changedPBCount"], 0)
        self.assertEqual(report["delta"]["reconstructedRating"], 0)

    def test_empty_before_recent_list_includes_all_valid_after_scores(self) -> None:
        empty_pbs = body_from_parts([], key="pbs")
        empty_scores = body_from_parts([], key="scores")
        after_scores = body_from_parts(
            [
                score_parts(1, rate=50, version="Legacy", achieved=200),
                score_parts(2, rate=50, version="Legacy", achieved=100),
            ],
            key="scores",
        )
        report = build_report_input(
            empty_pbs,
            empty_scores,
            empty_pbs,
            after_scores,
            ("Current",),
            generated_at=dt.datetime(2026, 1, 1, tzinfo=dt.UTC),
        )
        self.assertIsNone(report["session"]["cutoffTimeAchieved"])
        self.assertEqual(
            [item["timeAchieved"] for item in report["session"]["scores"]],
            [100, 200],
        )

    def test_naive_generated_timestamp_is_rejected(self) -> None:
        empty_pbs = body_from_parts([], key="pbs")
        empty_scores = body_from_parts([], key="scores")
        with self.assertRaisesRegex(CalculationError, "timezone"):
            build_report_input(
                empty_pbs,
                empty_scores,
                empty_pbs,
                empty_scores,
                (),
                generated_at=dt.datetime(2026, 1, 1),
            )


if __name__ == "__main__":
    unittest.main()
