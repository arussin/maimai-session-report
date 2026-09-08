from __future__ import annotations

import json
import tempfile
import unittest
import urllib.error
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock, patch

from maimai_report.history.bundle import ArchiveError
from maimai_report.installation import deployment, operations
from tests.installation_fixture import ROOT, WEBP, capture, instance_file


def multipart(modules):
    parts = []
    for name, content in modules.items():
        parts.append(
            b'--synthetic-boundary\r\nContent-Disposition: form-data; name="'
            + name.encode()
            + b'"\r\n\r\n'
            + content
            + b"\r\n"
        )
    return b"".join(
        parts
    ) + b"--synthetic-boundary--\r\n", "multipart/form-data; boundary=synthetic-boundary"


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        self.instance = replace(
            instance_file(self.path / "instance.toml"), origin="https://release.example.test"
        )
        self.source = self.path / "capture"
        capture(self.source, self.instance)
        operations.render_capture(self.instance, self.source)
        self.html = (self.source / "maimai-report.html").read_bytes()
        self.modules = {
            "report.html": self.html,
            "b50.webp": WEBP,
            "worker.js": b"// synthetic original",
        }
        self.settings = {
            "bindings": [
                {
                    "name": "HISTORY_OBJECTS",
                    "type": "r2_bucket",
                    "bucket_name": self.instance.bucket,
                },
                {"name": "HISTORY_DB", "type": "d1", "id": self.instance.database_id},
                {"name": "HISTORY_SCOPE", "type": "plain_text", "text": self.instance.scope},
                {"name": "HISTORY_ORIGIN", "type": "plain_text", "text": self.instance.origin},
                {"name": "HISTORY_PREFIX", "type": "plain_text", "text": self.instance.prefix},
            ],
            "limits": {"cpu_ms": 50},
            "compatibility_date": "2026-08-31",
        }
        self.api = Mock()
        self.api.routes.return_value = [{"id": "synthetic-route", **self.instance.route}]
        self.api.state.side_effect = self.state
        self.addCleanup(patch.stopall)
        patch("maimai_report.installation.deployment.WorkerAPI", return_value=self.api).start()
        self.access = patch("maimai_report.installation.deployment.verify_access").start()
        self.copies = patch(
            "maimai_report.installation.deployment.verify_retained_copies", return_value="a" * 64
        ).start()

    def state(self, endpoint):
        if endpoint == "content/v2":
            return multipart(self.modules)
        if endpoint == "settings":
            return json.loads(json.dumps(self.settings))
        if endpoint == "subdomain":
            return {"enabled": False, "previews_enabled": False}
        if endpoint == "deployments":
            return {
                "deployments": [
                    {
                        "versions": [
                            {
                                "version_id": "33333333-3333-4333-8333-333333333333",
                                "percentage": 100,
                            }
                        ]
                    }
                ]
            }
        raise AssertionError(endpoint)

    def test_retained_release_saves_rollback_and_checks_both_hosted_copies(self):
        destination = self.path / "release"
        deployment.prepare_release(self.instance, destination, ROOT)
        self.copies.assert_called_once_with(self.instance, self.html, WEBP)
        self.assertEqual((destination / "report.html").read_bytes(), self.html)
        self.assertEqual((destination / "staged/report.html").read_bytes(), self.html)
        self.assertEqual(
            (destination / "worker-multipart.bin").read_bytes(), multipart(self.modules)[0]
        )
        deployment.recheck(self.instance, destination)
        self.assertEqual(self.access.call_count, 2)

    def test_release_rejects_live_module_settings_or_staged_changes(self):
        for change in ("module", "settings", "staged"):
            with self.subTest(change=change):
                destination = self.path / change
                deployment.prepare_release(self.instance, destination, ROOT)
                if change == "module":
                    self.modules["worker.js"] = b"// synthetic newer deployment"
                elif change == "settings":
                    self.settings["limits"]["cpu_ms"] = 60
                else:
                    (destination / "staged/report.html").write_bytes(b"changed stage")
                with self.assertRaisesRegex(ArchiveError, "changed"):
                    deployment.recheck(self.instance, destination)
                self.modules["worker.js"] = b"// synthetic original"
                self.settings["limits"]["cpu_ms"] = 50

    def test_rollback_plan_uses_saved_version_and_rejects_newer_unrelated_deployment(self):
        destination = self.path / "release"
        deployment.prepare_release(self.instance, destination, ROOT)
        self.modules["worker.js"] = b"// synthetic refactored worker"
        deployment.verify_release(self.instance, destination)
        result = deployment.rollback_plan(self.instance, destination, self.path / "rollback")
        self.assertEqual(result["version"], "33333333-3333-4333-8333-333333333333")
        self.modules["worker.js"] = b"// synthetic separate later release"
        with self.assertRaisesRegex(ArchiveError, "changed after"):
            deployment.rollback_plan(self.instance, destination, self.path / "rollback")

    def test_wrangler_cache_is_allowed_but_extra_release_inputs_and_edits_are_rejected(self):
        destination = self.path / "release"
        deployment.prepare_release(self.instance, destination, ROOT)
        stage = destination / "staged"
        (stage / ".wrangler").mkdir()
        (stage / ".wrangler/cache.json").write_text("{}")
        deployment.verify_staged(self.instance, stage)
        (stage / ".env").write_text("SYNTHETIC=true")
        with self.assertRaisesRegex(ArchiveError, "unexpected files"):
            deployment.verify_staged(self.instance, stage)
        (stage / ".env").unlink()
        config = stage / "wrangler.generated.json"
        config.write_text(config.read_text().replace(self.instance.worker_name, "foreign-worker"))
        with self.assertRaisesRegex(ArchiveError, "bytes changed"):
            deployment.verify_staged(self.instance, stage)

    def test_first_required_b50_publication_can_replace_empty_bootstrap(self):
        self.modules.pop("b50.webp")
        self.modules["report.html"] = (
            b'<script id="report-data" type="application/json">{}</script>'
        )
        destination = self.path / "first-publication"
        result = deployment.prepare_release(
            replace(self.instance, b50_mode="required"), destination, ROOT, source=self.source
        )
        self.assertIsNotNone(result["b50Sha256"])
        self.assertEqual((destination / "staged/report.html").read_bytes(), self.html)
        self.copies.assert_not_called()

    def test_bootstrap_rejects_an_existing_worker_before_storage_changes(self):
        self.api.routes.return_value = []
        with patch("maimai_report.installation.deployment.Cloudflare") as storage:
            with self.assertRaisesRegex(ArchiveError, "already exists"):
                deployment.verify_empty_installation(self.instance)
        storage.assert_not_called()

    def test_bootstrap_has_no_invented_session_and_required_b50_does_not_block_empty_setup(self):
        with patch("maimai_report.installation.deployment.verify_empty_installation") as empty:
            destination = self.path / "bootstrap"
            result = deployment.bootstrap(
                replace(self.instance, b50_mode="required"), destination, ROOT
            )
        empty.assert_called_once()
        html = (destination / "staged/report.html").read_text()
        self.assertIn("No scores have been imported", html)
        self.assertNotIn('"session"', html)
        self.assertTrue(result["bootstrap"])
        self.assertIsNone(result["b50Sha256"])


class AccessTests(unittest.TestCase):
    def test_signed_out_checks_reject_arbitrary_redirects_without_sending_credentials(self):
        with tempfile.TemporaryDirectory() as temp:
            instance = instance_file(Path(temp) / "instance.toml")
            for location, accepted in (
                ("https://synthetic.cloudflareaccess.com/cdn-cgi/access/login", True),
                ("https://synthetic.cloudflareaccess.com.evil.invalid/login", False),
                ("https://other.example.invalid/", False),
            ):
                requests = []

                def open_request(request, timeout, requests=requests, location=location):
                    requests.append(request)
                    raise urllib.error.HTTPError(
                        request.full_url, 302, "synthetic redirect", {"Location": location}, None
                    )

                opener = Mock()
                opener.open.side_effect = open_request
                with patch("urllib.request.build_opener", return_value=opener):
                    if accepted:
                        deployment.verify_access(instance)
                        self.assertEqual(len(requests), 8)
                    else:
                        with self.assertRaises(ArchiveError):
                            deployment.verify_access(instance)
                self.assertTrue(all(not r.has_header("Authorization") for r in requests))


if __name__ == "__main__":
    unittest.main()
