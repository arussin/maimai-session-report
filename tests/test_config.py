from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from maimai_report.config import AppConfig, get_api_token, load_config
from maimai_report.errors import ConfigError, MissingTokenError


class ConfigTests(unittest.TestCase):
    def test_utc_needs_no_external_timezone_database(self) -> None:
        with patch("maimai_report.config.ZoneInfo", side_effect=RuntimeError("no tzdb")):
            AppConfig(timezone="UTC").validate()

    def test_safe_defaults_are_offline_and_private(self) -> None:
        config = load_config(None, environ={})

        self.assertEqual(config.username, "")
        self.assertEqual(config.timezone, "UTC")
        self.assertEqual(config.game, "maimaidx")
        self.assertEqual(config.import_type, "api/myt-maimaidx")
        self.assertEqual(config.current_version_display_names, ())
        self.assertEqual(config.output_dir, Path("output"))
        self.assertFalse(config.publishing_enabled)
        self.assertFalse(hasattr(config, "api_token"))

    def test_precedence_is_cli_then_environment_then_file_then_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.toml"
            path.write_text(
                """
[kamaitachi]
username = "from-file"
game = "filegame"

[player]
display_name = "File Player"
timezone = "UTC"

[report]
current_version_display_names = ["File Version"]
output_dir = "file-output"

[actions]
artifact_retention_days = 4

[publishing]
enabled = false
provider = "cloudflare"
report_path = "/"
""".strip(),
                encoding="utf-8",
            )
            config = load_config(
                path,
                environ={
                    "MAIMAI_REPORT_USERNAME": "from-env",
                    "MAIMAI_REPORT_DISPLAY_NAME": "Env Player",
                    "MAIMAI_REPORT_ARTIFACT_RETENTION_DAYS": "8",
                },
                cli_overrides={"username": "from-cli", "output_dir": Path("cli-output")},
            )

        self.assertEqual(config.username, "from-cli")
        self.assertEqual(config.display_name, "Env Player")
        self.assertEqual(config.game, "filegame")
        self.assertEqual(config.output_dir, Path("cli-output"))
        self.assertEqual(config.artifact_retention_days, 8)
        self.assertEqual(config.current_version_display_names, ("File Version",))

    def test_documented_environment_name_wins_over_compatibility_alias(self) -> None:
        config = load_config(
            None,
            environ={
                "KAMAITACHI_USERNAME": "alias-user",
                "MAIMAI_REPORT_USERNAME": "documented-user",
            },
        )
        self.assertEqual(config.username, "documented-user")

    def test_current_versions_accept_json_with_commas_and_unicode(self) -> None:
        config = load_config(
            None,
            environ={
                "MAIMAI_REPORT_CURRENT_VERSION_DISPLAY_NAMES": (
                    '["Current, International", "現行バージョン"]'
                )
            },
        )
        self.assertEqual(
            config.current_version_display_names,
            ("Current, International", "現行バージョン"),
        )

    def test_empty_current_version_entry_is_rejected(self) -> None:
        with self.assertRaisesRegex(ConfigError, "empty display name"):
            load_config(
                None,
                environ={"MAIMAI_REPORT_CURRENT_VERSION_DISPLAY_NAMES": '["Current", ""]'},
            )

    def test_token_is_rejected_from_toml_even_when_blank(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.toml"
            path.write_text(
                '[kamaitachi]\nusername="user"\napi_token=""\n',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ConfigError, "not allowed"):
                load_config(path, environ={})

    def test_rejected_toml_token_value_is_not_echoed(self) -> None:
        sentinel = "synthetic-value-that-must-not-appear"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.toml"
            path.write_text(
                f'[kamaitachi]\nusername="user"\napi_token="{sentinel}"\n',
                encoding="utf-8",
            )
            with self.assertRaises(ConfigError) as captured:
                load_config(path, environ={})
        self.assertNotIn(sentinel, str(captured.exception))

    def test_missing_token_is_actionable_and_never_in_config(self) -> None:
        with self.assertRaisesRegex(MissingTokenError, "KAMAITACHI_API_TOKEN"):
            get_api_token({})
        self.assertIsNone(get_api_token({}, required=False))
        self.assertEqual(
            get_api_token({"KAMAITACHI_API_TOKEN": "  synthetic-test-value  "}),
            "synthetic-test-value",
        )

    def test_network_validation_requires_identity_and_version_names(self) -> None:
        with self.assertRaisesRegex(ConfigError, "username"):
            AppConfig().validate(for_network=True)
        with self.assertRaisesRegex(ConfigError, "current-version"):
            AppConfig(username="user").validate(for_network=True)
        AppConfig(
            username="user",
            current_version_display_names=("Current Version",),
        ).validate(for_network=True)

    def test_validation_catches_timezone_game_retention_and_output_file(self) -> None:
        with self.assertRaisesRegex(ConfigError, "IANA timezone"):
            AppConfig(timezone="Not/A_Real_Zone").validate()
        with self.assertRaisesRegex(ConfigError, "game identifier"):
            AppConfig(game="../../unsafe").validate()
        with self.assertRaisesRegex(ConfigError, "retention"):
            AppConfig(artifact_retention_days=0).validate()
        with tempfile.TemporaryDirectory() as directory:
            file_path = Path(directory) / "not-a-directory"
            file_path.write_text("x", encoding="utf-8")
            with self.assertRaisesRegex(ConfigError, "is a file"):
                AppConfig(output_dir=file_path).validate()

    def test_publishing_stays_disabled_and_requires_complete_explicit_config(self) -> None:
        config = AppConfig()
        self.assertFalse(config.publishing_enabled)
        with self.assertRaisesRegex(ConfigError, "Publishing is disabled"):
            config.validate(for_publish=True)
        with self.assertRaisesRegex(ConfigError, "incomplete"):
            AppConfig(publishing_enabled=True).validate(for_publish=True)

    def test_cloudflare_publish_uses_exactly_one_routing_mode(self) -> None:
        base = {
            "publishing_enabled": True,
            "cloudflare_account_id": "a" * 32,
            "cloudflare_worker_name": "fixture-worker",
        }
        AppConfig(
            **base,
            cloudflare_custom_domain="reports.example.invalid",
        ).validate(for_publish=True)
        AppConfig(
            **base,
            cloudflare_route_pattern="reports.example.invalid/private/*",
            cloudflare_zone_id="b" * 32,
        ).validate(for_publish=True)
        with self.assertRaisesRegex(ConfigError, "exactly one"):
            AppConfig(
                **base,
                cloudflare_custom_domain="reports.example.invalid",
                cloudflare_route_pattern="reports.example.invalid/private/*",
                cloudflare_zone_id="b" * 32,
            ).validate(for_publish=True)
        with self.assertRaisesRegex(ConfigError, "zone_id"):
            AppConfig(
                **base,
                cloudflare_route_pattern="reports.example.invalid/private/*",
            ).validate(for_publish=True)

    def test_missing_explicit_config_file_fails_when_requested(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "missing.toml"
            with self.assertRaisesRegex(ConfigError, "does not exist"):
                load_config(missing, environ={}, require_file=True)


if __name__ == "__main__":
    unittest.main()
