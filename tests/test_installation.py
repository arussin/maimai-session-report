from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from maimai_report.errors import ConfigError
from maimai_report.history.bundle import ArchiveError, report_data
from maimai_report.installation import deployment, operations
from maimai_report.installation.__main__ import main
from maimai_report.installation.config import load_instance, validate_workflow_pins
from scripts.package_installation import FILES, package
from tests.installation_fixture import ROOT, WEBP, capture, instance_file


class InstallationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        self.config = self.path / "instance.toml"
        self.instance = instance_file(self.config)

    def test_template_has_safe_defaults_and_is_not_live_ready(self):
        value = load_instance(ROOT / "templates/private-caller/instance.toml")
        self.assertFalse(value.app.publishing_enabled)
        self.assertTrue(value.app.support_enabled)
        self.assertEqual(value.b50_mode, "optional")
        for operation in ("sync", "setup", "prepare-release"):
            with self.subTest(operation=operation), self.assertRaises(ConfigError):
                value.validate(operation)

    def test_support_setting_applies_to_capture_and_first_session_page(self):
        for enabled in (True, False):
            with self.subTest(enabled=enabled):
                instance = replace(
                    self.instance, app=replace(self.instance.app, support_enabled=enabled)
                )
                source = self.path / f"capture-{enabled}"
                capture(source, instance)
                with patch("urllib.request.build_opener") as network:
                    operations.render_capture(instance, source)
                self.assertIs(
                    report_data((source / "maimai-report.html").read_bytes())["support"],
                    enabled,
                )
                network.assert_not_called()
                with (
                    patch("maimai_report.installation.deployment.verify_empty_installation"),
                    patch("maimai_report.installation.deployment.stage") as stage,
                    patch("urllib.request.build_opener") as network,
                ):
                    deployment.bootstrap(instance, self.path / f"bootstrap-{enabled}", ROOT)
                stage.assert_called_once()
                self.assertIs(report_data(stage.call_args.args[3])["support"], enabled)
                network.assert_not_called()

    def test_secret_keys_unknown_fields_and_environment_conflicts_fail_offline(self):
        original = self.config.read_text()
        for added in (
            '[credentials]\npassword="synthetic-only"\n',
            '[unused]\nfoo="bar"\n',
            '[unsafe]\nitems=[{api_token="synthetic-only"}]\n',
        ):
            with self.subTest(added=added):
                self.config.write_text(original + added)
                with (
                    patch("urllib.request.build_opener") as network,
                    self.assertRaises(ConfigError),
                ):
                    load_instance(self.config)
                network.assert_not_called()
        self.config.write_text(original)
        with self.assertRaisesRegex(ConfigError, "conflicts"):
            load_instance(
                self.config, environ={"MAIMAI_REPORT_USERNAME": "another-synthetic-owner"}
            )
        self.assertEqual(
            load_instance(
                self.config, environ={"MAIMAI_REPORT_USERNAME": self.instance.app.username}
            ),
            self.instance,
        )

    def test_identity_validation_handles_partial_setup_and_rejects_shared_recovery(self):
        for values in (
            {"backup_bucket": self.instance.bucket},
            {"recovery_database_id": self.instance.database_id},
            {"prefix": "/alpha/extra/"},
            {"origin": "https://example.invalid:443"},
        ):
            with self.subTest(values=values), self.assertRaises(ConfigError):
                replace(self.instance, **values).validate()
        pending = replace(
            self.instance,
            database_id="",
            recovery_database_id="",
            origin="https://setup.example.test",
        )
        pending.validate("setup")
        with self.assertRaises(ConfigError):
            pending.validate("archive")

    def test_complete_empty_and_incomplete_keep_analytical_inputs_and_archive_identity(self):
        for scenario in ("complete", "empty", "incomplete"):
            with self.subTest(scenario=scenario):
                source = self.path / scenario
                original = capture(source, self.instance, scenario, b50=scenario != "incomplete")
                raw = {p.name: p.read_bytes() for p in source.iterdir()}
                with patch("urllib.request.build_opener") as network:
                    result = operations.render_capture(self.instance, source)
                    bundle = operations.validate_capture(self.instance, source, "a" * 40)
                network.assert_not_called()
                operations.retained_report_matches(source)
                html = (source / "maimai-report.html").read_bytes()
                displayed = report_data(html)
                for key, value in original["session"].items():
                    self.assertEqual(displayed["session"][key], value)
                self.assertEqual(result["meaningful"], scenario != "empty")
                self.assertEqual(result["b50Available"], scenario != "incomplete")
                self.assertEqual(
                    bundle.capture_id,
                    operations.validate_capture(self.instance, source, "a" * 40).capture_id,
                )
                for name, content in raw.items():
                    self.assertEqual((source / name).read_bytes(), content)

    def test_required_b50_cannot_silently_drop_missing_scores(self):
        source = self.path / "incomplete"
        capture(source, self.instance, "incomplete", b50=False)
        with self.assertRaisesRegex(ArchiveError, "35 old and 15 new"):
            operations.render_capture(replace(self.instance, b50_mode="required"), source)
        self.assertTrue((source / "report-input.json").is_file())

    def test_publish_rejects_wrong_owner_and_stale_rendered_session(self):
        source = self.path / "capture"
        capture(source, self.instance)
        operations.render_capture(self.instance, source)
        other = instance_file(self.path / "other.toml", owner="beta")
        with self.assertRaisesRegex(ArchiveError, "different player"):
            operations.validate_capture(other, source, "a" * 40)
        report = json.loads((source / "report-input.json").read_bytes())
        report["after"]["reconstructedRating"] += 1
        (source / "report-input.json").write_text(json.dumps(report))
        with self.assertRaisesRegex(ArchiveError, "differs"):
            operations.retained_report_matches(source)

    def test_two_installations_stage_their_own_routes_and_preserve_retained_bytes(self):
        for owner in ("alpha", "beta"):
            instance = instance_file(self.path / f"{owner}.toml", owner=owner)
            source = self.path / owner
            capture(source, instance)
            operations.render_capture(instance, source)
            html = (source / "maimai-report.html").read_bytes()
            with patch("urllib.request.build_opener") as network:
                stage = self.path / f"{owner}-stage"
                result = deployment.stage(
                    instance, stage, ROOT, html, WEBP, settings={"limits": {"cpu_ms": 50}}
                )
            network.assert_not_called()
            self.assertEqual((stage / "report.html").read_bytes(), html)
            self.assertEqual((stage / "b50.webp").read_bytes(), WEBP)
            wrangler = json.loads((stage / "wrangler.generated.json").read_bytes())
            self.assertEqual(wrangler["routes"], [instance.route])
            self.assertEqual(wrangler["limits"], {"cpu_ms": 50})
            self.assertEqual(wrangler["vars"]["HISTORY_SCOPE"], instance.scope)
            self.assertFalse(wrangler["workers_dev"])
            self.assertEqual(result["reportSha256"], hashlib.sha256(html).hexdigest())
            with self.assertRaisesRegex(ArchiveError, "empty directory"):
                deployment.stage(instance, stage, ROOT, html, WEBP)

    def test_disabled_history_does_not_require_storage_credentials(self):
        instance = replace(
            self.instance, history_enabled=False, origin="https://offline.example.test"
        )
        with patch("maimai_report.installation.operations.Cloudflare") as storage:
            result = operations.preflight(instance, storage_only=True)
            self.assertFalse(result["storageVerified"])
            archived = operations.storage(instance, "archive", self.path)
            self.assertFalse(archived["storageAccessed"])
        storage.assert_not_called()

    def test_foreign_and_duplicate_bindings_are_rejected(self):
        entries = [
            {"name": "HISTORY_OBJECTS", "type": "r2_bucket", "bucket_name": self.instance.bucket},
            {"name": "HISTORY_DB", "type": "d1", "id": self.instance.database_id},
            {"name": "HISTORY_SCOPE", "type": "plain_text", "text": self.instance.scope},
            {"name": "HISTORY_ORIGIN", "type": "plain_text", "text": self.instance.origin},
            {"name": "HISTORY_PREFIX", "type": "plain_text", "text": self.instance.prefix},
        ]
        deployment.verify_bindings({"bindings": entries}, self.instance)
        for bad in (entries[:-1], entries + [entries[0]], entries + [{"name": "OTHER"}]):
            with self.assertRaises(ArchiveError):
                deployment.verify_bindings({"bindings": bad}, self.instance)
        entries[0]["bucket_name"] = "foreign-synthetic-bucket"
        with self.assertRaises(ArchiveError):
            deployment.verify_bindings({"bindings": entries}, self.instance)

    def test_sync_refuses_reused_capture_directory_before_any_import(self):
        source = self.path / "retained"
        capture(source, self.instance)
        with patch("maimai_report.installation.operations.synchronize") as sync:
            with self.assertRaisesRegex(ArchiveError, "never be overwritten"):
                operations.sync(self.instance, source)
        sync.assert_not_called()

    def test_validate_cli_uses_no_network_and_reports_success_without_identifiers(self):
        stdout = io.StringIO()
        with (
            patch.dict(os.environ, {}, clear=True),
            patch("urllib.request.build_opener") as network,
        ):
            with contextlib.redirect_stdout(stdout):
                result = main(
                    ["validate", "--config", str(self.config), "--workdir", str(self.path / "work")]
                )
        self.assertEqual(result, 0)
        network.assert_not_called()
        self.assertNotIn(self.instance.account_id, stdout.getvalue())

    def test_packaged_template_is_complete_deterministic_and_has_only_one_core_pin(self):
        one, two = self.path / "one.zip", self.path / "two.zip"
        package(one, "a" * 40)
        package(two, "a" * 40)
        self.assertEqual(one.read_bytes(), two.read_bytes())
        with zipfile.ZipFile(one) as artifact:
            self.assertEqual(set(artifact.namelist()), set(FILES))
            for name in artifact.namelist():
                self.assertNotIn(b"__CORE_SHA__", artifact.read(name))
            artifact.extractall(self.path / "installed")  # noqa: S202 -- locally created, exact allowlisted ZIP
        load_instance(self.path / "installed/instance.toml")
        workflows = self.path / "installed/.github/workflows"
        self.assertEqual(validate_workflow_pins(workflows), "a" * 40)
        changed = workflows / "refresh.yml"
        changed.write_text(changed.read_text().replace("a" * 40, "b" * 40))
        with self.assertRaisesRegex(ConfigError, "same core commit"):
            validate_workflow_pins(workflows)
        self.assertEqual(
            one.with_suffix(".zip.sha256").read_text().split()[0],
            hashlib.sha256(one.read_bytes()).hexdigest(),
        )

    def test_workflow_intent_guard_blocks_sync_rerun_public_caller_and_unapproved_deploy(self):
        env = {
            **os.environ,
            "INSTANCE_PRIVATE": "true",
            "INSTANCE_APPLY": "false",
            "INSTANCE_PROMOTE": "false",
            "INSTANCE_RECOVERY": "false",
            "GITHUB_RUN_ATTEMPT": "1",
        }
        for changes in (
            {"INSTANCE_OPERATION": "sync", "GITHUB_RUN_ATTEMPT": "2"},
            {"INSTANCE_OPERATION": "health", "INSTANCE_PRIVATE": "false"},
            {"INSTANCE_OPERATION": "release"},
            {"INSTANCE_OPERATION": "render", "INSTANCE_SOURCE_RUN": "not-a-run"},
            {"INSTANCE_OPERATION": "verify-fresh"},
            {
                "INSTANCE_OPERATION": "verify-fresh",
                "INSTANCE_APPLY": "true",
                "INSTANCE_SOURCE_RUN": "123",
            },
            {
                "INSTANCE_OPERATION": "verify-fresh",
                "INSTANCE_APPLY": "true",
                "INSTANCE_RECOVERY": "true",
            },
            {
                "INSTANCE_OPERATION": "verify-fresh",
                "INSTANCE_APPLY": "true",
                "INSTANCE_PRIVATE": "false",
            },
        ):
            run = subprocess.run(  # noqa: S603 -- fixed script and synthetic env
                [sys.executable, str(ROOT / "installation/check-inputs.py")],
                env={**env, **changes},
                capture_output=True,
            )  # noqa: S603 -- fixed script and synthetic env
            self.assertNotEqual(run.returncode, 0)
        approved = subprocess.run(  # noqa: S603 -- fixed script and synthetic env
            [sys.executable, str(ROOT / "installation/check-inputs.py")],
            env={
                **env,
                "INSTANCE_OPERATION": "verify-fresh",
                "INSTANCE_APPLY": "true",
                "INSTANCE_SOURCE_RUN": "",
            },
            capture_output=True,
        )
        self.assertEqual(approved.returncode, 0, approved.stderr)


if __name__ == "__main__":
    unittest.main()
