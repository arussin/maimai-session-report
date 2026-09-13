from __future__ import annotations

import contextlib
import datetime as dt
import io
import json
import tempfile
import unittest
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from maimai_report import cli
from maimai_report.capture import (
    capture_existing,
    list_sessions,
    make_baseline,
    save_baseline,
    write_capture,
)
from maimai_report.config import AppConfig
from maimai_report.errors import APIResponseError, ConfigError
from maimai_report.history.bundle import prepare_capture, validate_capture_contents
from maimai_report.io import write_json
from maimai_report.render import enrich_report, render_report
from tests.test_calculations import body_from_parts, score_parts

START = 1_780_000_000_000
NOW = dt.datetime.fromtimestamp((START + 1_000_000) / 1000, dt.UTC)
BEFORE = dt.datetime.fromtimestamp((START - 1_000_000) / 1000, dt.UTC)


def fixture(count=2):
    parts = []
    for index in range(count):
        record, chart, song = score_parts(
            1, rate=278, version="Current", percent=98, achieved=START + index * 1000
        )
        record.update(
            scoreID=f"play-{index}",
            userID=42,
            game="maimaidx",
            service="site-importer (DIRECT-MANUAL)",
        )
        parts.append((record, chart, song))
    body = body_from_parts(parts, key="scores")
    body.update(
        user={"id": 42, "username": "test-player"},
        session={
            "sessionID": "external-session",
            "userID": 42,
            "game": "maimaidx",
            "timeStarted": START,
            "timeEnded": START + (count - 1) * 1000,
            "scoreIDs": [p[0]["scoreID"] for p in parts],
            "name": "Official network session",
        },
    )
    pbs = {"success": True, "body": body_from_parts(parts[-1:], key="pbs")}
    return {"success": True, "body": body}, pbs


class Reader:
    def __init__(self, count=2):
        self.session, self.pbs = fixture(count)
        self.calls = []

    def get_session(self, sid):
        self.calls.append(("session", sid))
        return deepcopy(self.session)

    def get_sessions(self, username, game):
        self.calls.append(("sessions", username, game))
        return {"success": True, "body": [deepcopy(self.session["body"]["session"])]}

    def get_pbs(self, username, game):
        self.calls.append(("pbs", username, game))
        return deepcopy(self.pbs)

    def start_import(self, *_args):
        raise AssertionError("Read-only capture must not import")

    def get_recent_scores(self, *_args):
        raise AssertionError("Session capture must not use the truncated recent-score endpoint")


class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = AppConfig(
            username="test-player",
            current_version_display_names=("Current",),
            output_dir=self.root / "output",
            support_enabled=False,
        )

    def capture(self, reader=None, **kwargs):
        return capture_existing(
            self.config,
            session_id="external-session",
            client=reader or Reader(),
            generated_at=NOW,
            **kwargs,
        )

    def baseline(self, when=BEFORE):
        before = {
            "success": True,
            "body": body_from_parts(
                [
                    score_parts(
                        1, rate=266, version="Current", percent=97, achieved=START - 2_000_000
                    )
                ],
                key="pbs",
            ),
        }
        path = self.root / "earlier.baseline.json"
        write_json(path, make_baseline(self.config, before, when))
        return path

    def test_complete_large_session_has_all_repeated_chart_plays_and_only_reads(self):
        reader = Reader(150)
        capture = self.capture(reader)
        result = capture[0]
        self.assertEqual(
            reader.calls, [("session", "external-session"), ("pbs", "test-player", "maimaidx")]
        )
        self.assertEqual(result.report_input["session"]["scoreCount"], 150)
        self.assertEqual(len({s["scoreID"] for s in result.report_input["session"]["scores"]}), 150)
        self.assertEqual(result.report_input["after"]["reconstructedRating"], 278)
        self.assertIsNone(result.report_input["delta"]["reconstructedRating"])
        self.assertIsNone(result.report_input["before"]["pbCount"])
        self.assertFalse(result.metadata["importStarted"])

    def test_equal_timestamps_and_exact_duplicates_do_not_lose_or_double_count_plays(self):
        reader = Reader()
        reader.session["body"]["scores"][1]["timeAchieved"] = START
        reader.session["body"]["scores"].append(deepcopy(reader.session["body"]["scores"][0]))
        self.assertEqual(self.capture(reader)[0].report_input["session"]["scoreCount"], 2)

    def test_missing_details_preserve_core_scores(self):
        reader = Reader()
        for score in reader.session["body"]["scores"]:
            score["scoreData"].pop("optional")
            score["scoreData"].pop("judgements")
        report = self.capture(reader)[0].report_input
        self.assertEqual(report["session"]["scoreCount"], 2)
        self.assertTrue(
            all(s["fast"] is None and s["miss"] is None for s in report["session"]["scores"])
        )

    def test_incomplete_or_foreign_sessions_fail_before_pb_read(self):
        changes = [
            lambda b: b["scores"].pop(),
            lambda b: b["user"].update(username="someone-else"),
            lambda b: b["session"].update(game="maimai"),
            lambda b: b["session"].update(userID=999),
            lambda b: b["session"].update(scoreIDs=["unexpected"]),
            lambda b: b["scores"][0].update(timeAchieved=None),
            lambda b: b["scores"][0].update(userID=999),
            lambda b: b["scores"][0].update(chartID="missing"),
            lambda b: b["scores"][0].update(songID=[]),
            lambda b: b["scores"][0]["calculatedData"].clear(),
            lambda b: b["scores"].append({**b["scores"][0], "timeAchieved": START + 1}),
        ]
        for change in changes:
            reader = Reader()
            change(reader.session["body"])
            with self.subTest(change=change), self.assertRaises(APIResponseError):
                self.capture(reader)
            self.assertEqual(len(reader.calls), 1)

    def test_empty_response_cannot_turn_a_selected_session_into_a_snapshot(self):
        reader = Reader()
        reader.session = {}
        with self.assertRaises(APIResponseError):
            self.capture(reader)
        self.assertEqual(len(reader.calls), 1)

    def test_lamp_only_changes_count_without_inventing_rating_gain(self):
        reader = Reader()
        path = self.root / "lamp.baseline.json"
        write_json(path, make_baseline(self.config, reader.pbs, BEFORE))
        reader.pbs["body"]["pbs"][0]["scoreData"]["lamp"] = "FULL COMBO"
        result = self.capture(reader, baseline_path=path)[0].report_input
        self.assertEqual(result["session"]["changedPBCount"], 1)
        self.assertEqual(result["delta"]["reconstructedRating"], 0)
        self.assertEqual(result["session"]["changedPBs"][0]["lamp"], "FULL COMBO")
        self.assertNotEqual(result["session"]["changedPBs"][0]["previousLamp"], "FULL COMBO")

    def test_baseline_comparison_is_explicitly_account_snapshot_scope(self):
        result = self.capture(baseline_path=self.baseline())[0]
        self.assertEqual(result.report_input["delta"]["reconstructedRating"], 12)
        self.assertEqual(result.report_input["session"]["changedPBCount"], 1)
        self.assertEqual(result.report_input["comparison"]["scope"], "snapshot")
        self.assertTrue(result.report_input["comparison"]["available"])

    def test_wrong_baselines_never_silently_produce_gains(self):
        for key, value in (
            ("username", "wrong-player"),
            ("game", "maimai"),
            ("currentNewDisplayVersions", ["Other"]),
            ("capturedAt", NOW.isoformat()),
        ):
            path = self.baseline()
            saved = json.loads(path.read_text())
            saved[key] = value
            write_json(path, saved)
            with self.subTest(key=key), self.assertRaises(ConfigError):
                self.capture(baseline_path=path)

    def test_pb_only_snapshot_does_not_invent_session_records_or_improvements(self):
        reader = Reader()
        reader.pbs["body"]["pbs"][0]["timeAchieved"] = None
        result = capture_existing(self.config, pb_snapshot=True, client=reader, generated_at=NOW)[0]
        self.assertEqual(reader.calls, [("pbs", "test-player", "maimaidx")])
        self.assertEqual(result.report_input["capture"]["kind"], "pb-snapshot")
        self.assertEqual(result.report_input["session"]["scoreCount"], 0)
        self.assertEqual(result.report_input["session"]["changedPBCount"], 0)
        self.assertEqual(result.report_input["after"]["reconstructedRating"], 278)

    def test_latest_and_list_sessions_use_explicit_read_routes(self):
        reader = Reader()
        self.assertEqual(
            list_sessions(self.config, client=reader)[0]["sessionID"], "external-session"
        )
        report = capture_existing(self.config, latest=True, client=reader, generated_at=NOW)[
            0
        ].report_input
        self.assertEqual(report["session"]["scoreCount"], 2)

    def test_missing_selection_and_wrong_game_fail_without_network(self):
        reader = Reader()
        with self.assertRaises(ConfigError):
            capture_existing(self.config, client=reader)
        with self.assertRaises(ConfigError):
            capture_existing(replace(self.config, game="maimai"), latest=True, client=reader)
        self.assertEqual(reader.calls, [])

    def test_baselines_and_captures_cannot_overwrite_retained_files(self):
        reader = Reader()
        baseline = self.baseline()
        with self.assertRaises(ConfigError):
            save_baseline(self.config, baseline, client=reader)
        self.assertEqual(reader.calls, [])
        capture = self.capture()
        write_capture(capture, self.config.output_dir)
        with self.assertRaises(ConfigError):
            write_capture(capture, self.config.output_dir)

    def test_unknown_baseline_survives_render_and_history_round_trip(self):
        capture = self.capture()
        write_capture(capture, self.config.output_dir)
        result = capture[0]
        report = enrich_report(result.report_input, result.after_pbs, support=False)
        html = self.config.output_dir / "report.html"
        render_report(report, html, badge_pack="plain")
        bundle = prepare_capture(
            self.config.output_dir,
            scope="test-player:maimaidx",
            timezone="UTC",
            source_id="test-read-only",
            renderer_commit="a" * 40,
            rendered_html=html,
        )
        validate_capture_contents(bundle)
        self.assertEqual(bundle.manifest["sortMs"], int(NOW.timestamp() * 1000))
        self.assertEqual(bundle.manifest["startMs"], START)
        self.assertIsNone(bundle.manifest["before"]["reconstructedRating"])
        self.assertIn("baseline.json", bundle.manifest["files"])
        self.assertIn("kamaitachi-session.json", bundle.manifest["files"])

    def test_cli_generates_without_submission_credentials(self):
        with (
            patch("maimai_report.capture.read_client", return_value=Reader()),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            status = cli.run(
                cli.build_parser().parse_args(
                    [
                        "from-kamaitachi",
                        "--session-id",
                        "external-session",
                        "--username",
                        "test-player",
                        "--current-version",
                        "Current",
                        "--output-dir",
                        str(self.config.output_dir),
                        "--output",
                        str(self.root / "report.html"),
                        "--no-support",
                        "--badge-pack",
                        "plain",
                    ]
                ),
                environ={},
            )
        self.assertEqual(status, 0)
        self.assertTrue((self.root / "report.html").is_file())
        self.assertTrue((self.config.output_dir / "baseline.json").is_file())
