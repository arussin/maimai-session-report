from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from maimai_report import cli
from maimai_report.fixtures import load_scenario


class CLITests(unittest.TestCase):
    def test_required_commands_are_registered(self) -> None:
        parser = cli.build_parser()
        for argv in (
            ["doctor"],
            ["demo", "--output", "demo.html"],
            [
                "render",
                "--report-input",
                "report.json",
                "--after-pbs",
                "pbs.json",
                "--output",
                "report.html",
            ],
            ["sync"],
            ["sync-and-render", "--output", "report.html"],
            ["serve", "--file", "report.html"],
        ):
            self.assertEqual(parser.parse_args(argv).command, argv[0])

    def test_argparse_errors_use_exit_code_two(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as raised:
                cli.build_parser().parse_args(["demo"])
        self.assertEqual(raised.exception.code, cli.EXIT_USAGE)

    def test_demo_is_offline_and_returns_zero(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory, "demo.html")
            with (
                patch("maimai_report.cli.synchronize") as synchronize,
                patch("maimai_report.cli.KamaitachiClient") as client,
                contextlib.redirect_stdout(io.StringIO()),
            ):
                code = cli.main(["demo", "--output", str(output)])
            self.assertEqual(code, cli.EXIT_OK)
            self.assertTrue(output.is_file())
            self.assertNotIn("http://", output.read_text(encoding="utf-8"))
            self.assertNotIn("https://", output.read_text(encoding="utf-8"))
            synchronize.assert_not_called()
            client.assert_not_called()

    def test_render_is_local_only(self) -> None:
        report, after = load_scenario("incomplete")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report_path = root / "report-input.json"
            after_path = root / "after-pbs.json"
            output = root / "rendered.html"
            report_path.write_text(json.dumps(report), encoding="utf-8")
            after_path.write_text(json.dumps(after), encoding="utf-8")
            with (
                patch("maimai_report.cli.synchronize") as synchronize,
                patch("maimai_report.cli.KamaitachiClient") as client,
                patch.dict(os.environ, {}, clear=True),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                code = cli.main(
                    [
                        "render",
                        "--report-input",
                        str(report_path),
                        "--after-pbs",
                        str(after_path),
                        "--output",
                        str(output),
                    ]
                )
            self.assertEqual(code, cli.EXIT_OK)
            self.assertTrue(output.is_file())
            synchronize.assert_not_called()
            client.assert_not_called()

    def test_offline_doctor_never_constructs_a_client_or_syncs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            stdout = io.StringIO()
            with (
                patch("maimai_report.cli.synchronize") as synchronize,
                patch("maimai_report.cli.KamaitachiClient") as client,
                patch.dict(os.environ, {}, clear=True),
                contextlib.redirect_stdout(stdout),
            ):
                code = cli.main(["doctor", "--output-dir", directory])
            self.assertEqual(code, cli.EXIT_OK)
            self.assertIn("no network request made", stdout.getvalue())
            self.assertIn("without initiating a sync", stdout.getvalue())
            synchronize.assert_not_called()
            client.assert_not_called()

    def test_network_doctor_makes_authenticated_read_but_no_import(self) -> None:
        instance = Mock()
        instance.get_pbs.return_value = {
            "success": True,
            "body": {"pbs": [], "charts": [], "songs": []},
        }
        with tempfile.TemporaryDirectory() as directory:
            with (
                patch("maimai_report.cli.KamaitachiClient", return_value=instance),
                patch("maimai_report.cli.synchronize") as synchronize,
                patch.dict(os.environ, {"KAMAITACHI_API_TOKEN": "not-a-real-token"}, clear=True),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                code = cli.main(
                    [
                        "doctor",
                        "--network",
                        "--username",
                        "synthetic-user",
                        "--current-version",
                        "Synthetic Current",
                        "--output-dir",
                        directory,
                    ]
                )
            self.assertEqual(code, cli.EXIT_OK)
            instance.get_pbs.assert_called_once_with(
                "synthetic-user", "maimaidx", authenticated=True
            )
            self.assertFalse(hasattr(instance, "start_import") and instance.start_import.called)
            synchronize.assert_not_called()

    def test_network_doctor_rejects_an_unsuccessful_api_envelope(self) -> None:
        instance = Mock()
        instance.get_pbs.return_value = {"success": False, "body": {}}
        stderr = io.StringIO()
        with tempfile.TemporaryDirectory() as directory:
            with (
                patch("maimai_report.cli.KamaitachiClient", return_value=instance),
                patch("maimai_report.cli.synchronize") as synchronize,
                patch.dict(os.environ, {"KAMAITACHI_API_TOKEN": "not-a-real-token"}, clear=True),
                contextlib.redirect_stderr(stderr),
            ):
                code = cli.main(
                    [
                        "doctor",
                        "--network",
                        "--username",
                        "synthetic-user",
                        "--current-version",
                        "Synthetic Current",
                        "--output-dir",
                        directory,
                    ]
                )
        self.assertEqual(code, cli.EXIT_OPERATION)
        self.assertIn("Fetching pbs was unsuccessful", stderr.getvalue())
        self.assertNotIn("not-a-real-token", stderr.getvalue())
        synchronize.assert_not_called()

    def test_sync_missing_token_is_safe_and_actionable(self) -> None:
        stderr = io.StringIO()
        with tempfile.TemporaryDirectory() as directory:
            with (
                patch.dict(os.environ, {}, clear=True),
                contextlib.redirect_stderr(stderr),
            ):
                code = cli.main(
                    [
                        "sync",
                        "--username",
                        "synthetic-user",
                        "--current-version",
                        "Synthetic Current",
                        "--output-dir",
                        directory,
                    ]
                )
        self.assertEqual(code, cli.EXIT_OPERATION)
        message = stderr.getvalue()
        self.assertIn("KAMAITACHI_API_TOKEN", message)
        self.assertIn("environment", message)
        self.assertNotIn("Bearer", message)

    def test_unwritable_shape_is_rejected_before_sync(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output_file = Path(directory, "not-a-directory")
            output_file.write_text("occupied", encoding="utf-8")
            with (
                patch("maimai_report.cli.synchronize") as synchronize,
                patch.dict(
                    os.environ,
                    {"KAMAITACHI_API_TOKEN": "not-a-real-token"},
                    clear=True,
                ),
                contextlib.redirect_stderr(io.StringIO()),
            ):
                code = cli.main(
                    [
                        "sync",
                        "--username",
                        "synthetic-user",
                        "--current-version",
                        "Synthetic Current",
                        "--output-dir",
                        str(output_file),
                    ]
                )
            self.assertEqual(code, cli.EXIT_OPERATION)
            synchronize.assert_not_called()

    def test_invalid_local_input_returns_operation_exit_code(self) -> None:
        stderr = io.StringIO()
        with tempfile.TemporaryDirectory() as directory:
            with contextlib.redirect_stderr(stderr):
                code = cli.main(
                    [
                        "render",
                        "--report-input",
                        str(Path(directory, "missing.json")),
                        "--after-pbs",
                        str(Path(directory, "also-missing.json")),
                        "--output",
                        str(Path(directory, "report.html")),
                    ]
                )
        self.assertEqual(code, cli.EXIT_OPERATION)
        self.assertIn("missing.json", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
