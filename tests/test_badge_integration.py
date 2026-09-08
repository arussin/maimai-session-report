"""Badge selection is explicit, validated before networking, and shared by render paths."""

import contextlib
import io
import os
import socket
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from maimai_report import cli
from maimai_report.badges import export_badge_pack
from maimai_report.config import load_config
from maimai_report.installation import operations
from maimai_report.render import validate_generated_html
from tests.installation_fixture import capture, instance_file


class BadgeIntegrationTests(unittest.TestCase):
    def test_config_precedence_and_default(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory, "config.toml")
            config.write_text('[report]\nbadge_pack="plain"\n')
            self.assertEqual(load_config(None, environ={}).badge_pack, "builtin")
            self.assertEqual(load_config(config, environ={}).badge_pack, "plain")
            env = {"MAIMAI_REPORT_BADGE_PACK": "builtin"}
            self.assertEqual(load_config(config, environ=env).badge_pack, "builtin")
            self.assertEqual(
                load_config(config, environ=env, cli_overrides={"badge_pack": "plain"}).badge_pack,
                "plain",
            )

    def test_export_demo_and_doctor_with_custom_pack_are_offline(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(os.environ, {}, clear=True),
            patch.object(socket, "socket", side_effect=AssertionError("Network forbidden")),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            root = Path(directory)
            self.assertEqual(cli.main(["export-badges", "--output-dir", str(root / "pack")]), 0)
            manifest = root / "pack/badges.toml"
            self.assertEqual(
                cli.main(
                    ["doctor", "--badge-pack", str(manifest), "--output-dir", str(root / "out")]
                ),
                0,
            )
            output = root / "demo.html"
            self.assertEqual(
                cli.main(["demo", "--badge-pack", str(manifest), "--output", str(output)]), 0
            )
            self.assertIn("data:image/webp;base64,", output.read_text())
            validate_generated_html(output.read_text(encoding="utf-8"))

    def test_invalid_pack_prevents_network_doctor_and_sync(self):
        with tempfile.TemporaryDirectory() as directory:
            for command in (
                ["sync"],
                ["sync-and-render", "--output", str(Path(directory, "x.html"))],
                ["doctor", "--network"],
            ):
                with (
                    patch.dict(os.environ, {}, clear=True),
                    patch("maimai_report.cli.synchronize") as sync,
                    patch("maimai_report.cli.KamaitachiClient") as client,
                    contextlib.redirect_stderr(io.StringIO()),
                ):
                    status = cli.main(
                        command + ["--badge-pack", str(Path(directory, "missing.toml"))]
                    )
                    self.assertEqual(status, cli.EXIT_OPERATION)
                    sync.assert_not_called()
                    client.assert_not_called()

    def test_demo_explicit_plain_wins_over_environment_and_excludes_game_images(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory, "plain.html")
            with (
                patch.dict(os.environ, {"MAIMAI_REPORT_BADGE_PACK": "builtin"}, clear=True),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                self.assertEqual(
                    cli.main(["demo", "--badge-pack", "plain", "--output", str(output)]), 0
                )
            self.assertNotIn("data:image/webp;base64,", output.read_text())

    def test_private_installation_uses_same_pack_without_changing_score_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = export_badge_pack(root / "pack")
            instance = instance_file(root / "instance.toml")
            instance = replace(instance, app=replace(instance.app, badge_pack=str(manifest)))
            source = root / "capture"
            capture(source, instance)
            before = (source / "report-input.json").read_bytes()
            with patch.object(socket, "socket", side_effect=AssertionError("Network forbidden")):
                operations.render_capture(instance, source)
            self.assertEqual((source / "report-input.json").read_bytes(), before)
            self.assertIn("data:image/webp;base64,", (source / "maimai-report.html").read_text())
