"""Synthetic selection configuration must not alter archive resource identity."""

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from maimai_report.errors import ConfigError
from maimai_report.history.bundle import ArchiveError
from maimai_report.installation.config import load_instance
from maimai_report.installation.deployment import stage, verify_staged
from maimai_report.installation.operations import render_capture
from tests.installation_fixture import ROOT, WEBP, capture, instance_file


class HistoryRevisionConfigTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / "instance.toml"
        self.original = instance_file(self.path)

    def test_explicit_selections_preserve_archive_and_recovery_identity(self):
        with self.path.open("a") as file:
            file.write(
                '[history.presentation_revisions]\n"' + "a" * 64 + '" = "' + "b" * 64 + '"\n'
            )
        selected = load_instance(self.path)
        self.assertEqual(selected.presentation_revisions, (("a" * 64, "b" * 64),))
        self.assertEqual(selected.identity(), self.original.identity())
        self.assertEqual(selected.history_config(), self.original.history_config())

    def test_malformed_or_oversized_maps_are_rejected(self):
        for pairs in (
            (("../escape", "a" * 64),),
            (("a" * 64, "wrong"),),
            (("a" * 64, None),),
            (("a" * 64, "b" * 64),) * 2,
            tuple((f"{i:064x}", "a" * 64) for i in range(257)),
        ):
            with self.subTest(pairs=pairs[:1]), self.assertRaises(ConfigError):
                replace(self.original, presentation_revisions=pairs).validate()
        with self.assertRaises(ConfigError):
            replace(
                self.original, history_enabled=False, presentation_revisions=(("a" * 64, "b" * 64),)
            ).validate()

    def test_staged_worker_contains_selection_and_detects_config_drift(self):
        selected = replace(self.original, presentation_revisions=(("a" * 64, "b" * 64),))
        source = self.root / "capture"
        capture(source, selected)
        render_capture(selected, source, offline=True)
        html = (source / "maimai-report.html").read_bytes()
        target = self.root / "stage"
        stage(selected, target, ROOT, html, WEBP)
        self.assertIn('"presentationRevisions": {"' + "a" * 64, (target / "worker.js").read_text())
        self.assertEqual((target / "report.html").read_bytes(), html)
        verify_staged(selected, target)
        with self.assertRaisesRegex(ArchiveError, "selections"):
            verify_staged(self.original, target)
