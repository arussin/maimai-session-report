"""Offline provenance, packaging, and downstream security-patch regression checks."""

import hashlib
import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from build_backend.maimai_build_backend import _metadata, _wheel_entries
from scripts import harden_tomomai


class TomomaiNoticeTests(unittest.TestCase):
    def test_adapter_is_credited_and_separately_licensed(self):
        source = Path("adapters/tomomai/render.ts").read_text()
        self.assertIn("SPDX-License-Identifier: AGPL-3.0-only", source)
        self.assertIn("shedaniel/tomomai", source)
        self.assertIn(
            "GNU AFFERO GENERAL PUBLIC LICENSE", Path("adapters/tomomai/LICENSE").read_text()
        )
        notice = Path("THIRD_PARTY_NOTICES.md").read_text()
        for text in ("7608b9c250f4a8778cdfd4768cdecb7628cd5889", "SEGA", "AGPL", "MIT"):
            self.assertIn(text, notice)

    def test_wheel_does_not_relicense_artwork_as_mit_or_bundle_agpl_adapter(self):
        self.assertIn("MIT AND LicenseRef-SEGA-Game-Artwork", _metadata())
        entries = _wheel_entries(editable=False)
        self.assertTrue(any(name.endswith("licenses/THIRD_PARTY_NOTICES.md") for name in entries))
        self.assertTrue(any(name.endswith("licenses/docs/RATING_ASSETS.md") for name in entries))
        self.assertFalse(any("adapters/tomomai" in name or "_tomomai" in name for name in entries))

    def test_tls_patch_is_offline_narrow_and_idempotent(self):
        fixture = "const agent = {connect: {timeout: 30_000, rejectUnauthorized: false}};\n"
        with tempfile.TemporaryDirectory() as directory:
            checkout = Path(directory)
            target = checkout / harden_tomomai.CATALOGUE_PATH
            target.parent.mkdir(parents=True)
            target.write_text(fixture)
            with (
                patch.object(
                    harden_tomomai,
                    "UPSTREAM_FILES",
                    {harden_tomomai.CATALOGUE_PATH: hashlib.sha256(fixture.encode()).hexdigest()},
                ),
                patch.object(socket, "socket", side_effect=AssertionError("Network forbidden")),
            ):
                self.assertTrue(harden_tomomai.harden(checkout))
                expected = harden_tomomai.NOTICE + fixture.replace(
                    harden_tomomai.OLD, harden_tomomai.NEW
                )
                self.assertEqual(target.read_text(), expected)
                self.assertFalse(harden_tomomai.harden(checkout))
                target.write_text(expected + "// unexpected change\n")
                with self.assertRaisesRegex(ValueError, "reviewed pin"):
                    harden_tomomai.harden(checkout)

    def test_unreviewed_upstream_source_is_not_modified(self):
        with tempfile.TemporaryDirectory() as directory:
            checkout = Path(directory)
            target = checkout / harden_tomomai.CATALOGUE_PATH
            target.parent.mkdir(parents=True)
            target.write_text("unreviewed source")
            with self.assertRaisesRegex(ValueError, "reviewed pin"):
                harden_tomomai.harden(checkout)
            self.assertEqual(target.read_text(), "unreviewed source")

    def test_all_sources_are_verified_before_any_change(self):
        source = "rejectUnauthorized: false\n"
        digest = hashlib.sha256(source.encode()).hexdigest()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first, second = root / "first.ts", root / "second.ts"
            first.write_text(source)
            second.write_text("unexpected revision")
            with patch.object(
                harden_tomomai, "UPSTREAM_FILES", {"first.ts": digest, "second.ts": digest}
            ):
                with self.assertRaisesRegex(ValueError, "reviewed pin"):
                    harden_tomomai.harden(root)
            self.assertEqual(first.read_text(), source)

    def test_action_applies_guard_before_upstream_build(self):
        action = Path("installation/action.yml").read_text()
        self.assertLess(action.index("scripts/harden_tomomai.py"), action.index("corepack enable"))
