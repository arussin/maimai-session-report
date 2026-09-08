from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from maimai_report import cli
from maimai_report.fixtures import load_scenario
from maimai_report.history.bundle import report_data


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
                patch.dict(os.environ, {}, clear=True),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                code = cli.main(["demo", "--output", str(output)])
            self.assertEqual(code, cli.EXIT_OK)
            self.assertTrue(output.is_file())
            self.assertIs(report_data(output.read_bytes())["support"], True)
            synchronize.assert_not_called()
            client.assert_not_called()

    def test_demo_support_switch_overrides_environment_without_personal_config(self) -> None:
        cases = (
            ([], {}, True),
            ([], {"MAIMAI_REPORT_SUPPORT_ENABLED": "false"}, False),
            (["--no-support"], {"MAIMAI_REPORT_SUPPORT_ENABLED": "true"}, False),
            (["--support"], {"MAIMAI_REPORT_SUPPORT_ENABLED": "false"}, True),
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "config.toml"
            config.write_text("not valid TOML [", encoding="utf-8")
            output = root / "demo.html"
            for options, environment, expected in cases:
                with (
                    self.subTest(options=options, environment=environment),
                    patch("urllib.request.build_opener") as network,
                    patch.dict(
                        os.environ,
                        {
                            "MAIMAI_REPORT_CONFIG": str(config),
                            "MAIMAI_REPORT_TIMEZONE": "Not/A_Real_Zone",
                            **environment,
                        },
                        clear=True,
                    ),
                    contextlib.redirect_stdout(io.StringIO()),
                ):
                    self.assertEqual(
                        cli.main(["demo", "--output", str(output), *options]), cli.EXIT_OK
                    )
                    html = output.read_bytes()
                    self.assertIs(report_data(html)["support"], expected)
                    if not expected:
                        self.assertNotIn(b"http://", html)
                        self.assertNotIn(b"https://", html)
                    network.assert_not_called()

    def test_demo_invalid_support_setting_fails_before_rendering(self) -> None:
        with (
            patch.dict(os.environ, {"MAIMAI_REPORT_SUPPORT_ENABLED": "invalid"}, clear=True),
            patch("maimai_report.cli.render_demo") as render,
            contextlib.redirect_stderr(io.StringIO()) as stderr,
        ):
            code = cli.main(["demo", "--output", "unused.html"])
        self.assertEqual(code, cli.EXIT_OPERATION)
        self.assertIn("true or false", stderr.getvalue())
        render.assert_not_called()

    def test_support_switch_is_available_on_configured_commands(self) -> None:
        parser = cli.build_parser()
        for command in ("doctor", "sync"):
            with self.subTest(command=command):
                self.assertIsNone(parser.parse_args([command]).support_enabled)
                self.assertIs(parser.parse_args([command, "--support"]).support_enabled, True)
                self.assertIs(parser.parse_args([command, "--no-support"]).support_enabled, False)

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
            self.assertIs(report_data(output.read_bytes())["support"], True)
            synchronize.assert_not_called()
            client.assert_not_called()

    def test_render_can_disable_support_from_saved_inputs(self) -> None:
        report, after = load_scenario("empty")
        report["support"] = True
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report_path = root / "report-input.json"
            after_path = root / "after-pbs.json"
            output = root / "rendered.html"
            report_path.write_text(json.dumps(report), encoding="utf-8")
            after_path.write_text(json.dumps(after), encoding="utf-8")
            with (
                patch("urllib.request.build_opener") as network,
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
                        "--no-support",
                    ]
                )
            self.assertEqual(code, cli.EXIT_OK)
            self.assertIs(report_data(output.read_bytes())["support"], False)
            self.assertNotIn("https://", output.read_text(encoding="utf-8"))
            network.assert_not_called()

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
            self.assertIn(
                "Developer support: enabled; in-page checkout loads only after a click",
                stdout.getvalue(),
            )
            synchronize.assert_not_called()
            client.assert_not_called()

    def test_doctor_reports_support_opt_out_without_network(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with (
                patch("urllib.request.build_opener") as network,
                patch.dict(os.environ, {}, clear=True),
                contextlib.redirect_stdout(io.StringIO()) as stdout,
            ):
                code = cli.main(["doctor", "--output-dir", directory, "--no-support"])
            self.assertEqual(code, cli.EXIT_OK)
            self.assertIn("Developer support: disabled", stdout.getvalue())
            network.assert_not_called()

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

    def test_sync_and_render_passes_support_choice_to_renderer(self) -> None:
        report, after = load_scenario("complete")
        result = SimpleNamespace(report_input=report, after_pbs=after)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory, "report.html")
            with (
                patch("maimai_report.cli.synchronize", return_value=result) as synchronize,
                patch("maimai_report.cli.write_sync_result", return_value={}),
                patch.dict(os.environ, {}, clear=True),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                code = cli.main(
                    [
                        "sync-and-render",
                        "--username",
                        "synthetic-user",
                        "--current-version",
                        "Synthetic Current",
                        "--output-dir",
                        directory,
                        "--output",
                        str(output),
                        "--no-support",
                    ]
                )
            self.assertEqual(code, cli.EXIT_OK)
            synchronize.assert_called_once()
            self.assertFalse(synchronize.call_args.args[0].support_enabled)
            self.assertIs(report_data(output.read_bytes())["support"], False)

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
