"""Bounded, credential-free verification of deliberately public report exports."""

import io
import json
import tempfile
import unittest
import urllib.error
from dataclasses import replace
from email.message import Message
from pathlib import Path
from unittest.mock import Mock, patch

from maimai_report.history.bundle import ArchiveError, sha256
from maimai_report.installation.deployment import verify_access, verify_public_import
from tests.installation_fixture import instance_file


class Response(io.BytesIO):
    def __init__(self, body, kind, cors=True):
        super().__init__(body)
        self.status = 200
        self.headers = Message()
        self.headers["Content-Type"] = kind
        if cors:
            self.headers["Access-Control-Allow-Origin"] = "https://maimai.party"


class PublicImportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.instance = replace(
            instance_file(Path(self.temp.name) / "instance.toml"), public_player_imports=True
        )
        self.raw = b"synthetic compressed payload"
        self.path = self.instance.prefix + "party/data/" + sha256(self.raw) + ".gz"
        self.manifest = {
            "object": {"sha256": sha256(self.raw), "bytes": len(self.raw), "path": self.path}
        }

    def responses(self, cors=True):
        return [
            Response(json.dumps(self.manifest).encode(), "application/json", cors),
            Response(self.raw, "application/gzip", cors),
        ]

    def test_preflight_accepts_existing_public_export_and_postflight_requires_cors(self):
        opener = Mock()
        with patch("urllib.request.build_opener", return_value=opener):
            opener.open.side_effect = self.responses(cors=False)
            verify_access(self.instance)
            opener.open.side_effect = self.responses(cors=False)
            with self.assertRaisesRegex(ArchiveError, "CORS"):
                verify_public_import(self.instance, require_cors=True)
            opener.open.side_effect = self.responses()
            verify_public_import(self.instance, require_cors=True)
        for call in opener.open.call_args_list:
            request = call.args[0]
            self.assertEqual(request.get_header("Origin"), "https://maimai.party")
            self.assertFalse(request.has_header("Authorization"))
            self.assertFalse(request.has_header("Cookie"))
            self.assertFalse(request.has_header("Referer"))
            self.assertTrue(
                request.full_url.startswith(self.instance.origin + self.instance.prefix)
            )

    def test_bad_payload_hash_length_content_type_and_credential_policy_fail(self):
        for problem in (
            "hash",
            "size",
            "login",
            "credentials",
            "wildcard",
            "oversized",
            "redirect",
            "denied",
        ):
            with self.subTest(problem=problem):
                responses = self.responses()
                if problem == "hash":
                    responses[1] = Response(b"x" * len(self.raw), "application/gzip")
                elif problem == "size":
                    responses[1] = Response(self.raw[:-1], "application/gzip")
                elif problem == "login":
                    responses[0] = Response(b"<html>Login</html>", "text/html")
                elif problem == "credentials":
                    responses[0].headers["Access-Control-Allow-Credentials"] = "true"
                elif problem == "wildcard":
                    responses[0].headers.replace_header("Access-Control-Allow-Origin", "*")
                elif problem == "oversized":
                    responses[0] = Response(b" " * (128 * 1024 + 1), "application/json")
                elif problem in {"redirect", "denied"}:
                    responses = [
                        urllib.error.HTTPError(
                            self.instance.origin,
                            302 if problem == "redirect" else 403,
                            "blocked",
                            {},
                            None,
                        )
                    ]
                with patch(
                    "urllib.request.build_opener",
                    return_value=Mock(open=Mock(side_effect=responses)),
                ):
                    with self.assertRaises(ArchiveError):
                        verify_public_import(self.instance, require_cors=True)

    def test_manifest_cannot_fetch_another_origin_path_or_oversized_object(self):
        for value in (
            "https://other.invalid/data.gz",
            "/other/party/data/" + sha256(self.raw) + ".gz",
            "../data.gz",
        ):
            self.manifest["object"]["path"] = value
            opener = Mock(open=Mock(side_effect=self.responses()))
            with patch("urllib.request.build_opener", return_value=opener):
                with self.assertRaises(ArchiveError):
                    verify_public_import(self.instance)
            self.assertEqual(opener.open.call_count, 1)
        self.manifest["object"]["path"] = self.path
        for value in (True, 0, 32 * 1024 * 1024 + 1):
            self.manifest["object"]["bytes"] = value
            opener = Mock(open=Mock(side_effect=self.responses()))
            with patch("urllib.request.build_opener", return_value=opener):
                with self.assertRaises(ArchiveError):
                    verify_public_import(self.instance)
            self.assertEqual(opener.open.call_count, 1)
