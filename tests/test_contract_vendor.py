"""Offline consumer integrity and pinned v1 compatibility checks."""

import base64
import hashlib
import importlib.util
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from maimai_report._party import player_data
from maimai_report.contract_vendor import (
    FILES,
    SCHEMA,
    TARGETS,
    UPSTREAM,
    canonical,
    load_bundle,
    validate_bundle,
    vendor_bundle,
)
from maimai_report.fixtures import SCENARIOS, load_scenario
from maimai_report.party import from_documents
from maimai_report.render import enrich_report

REVISION = "a" * 40
ROOT = Path(__file__).resolve().parents[1] / "src/maimai_report"


def fixture_bundle():
    entries = {}
    for name, target in TARGETS.items():
        raw = (ROOT / target).read_bytes().replace(b"\r\n", b"\n")
        entries[name] = {
            "source_path": FILES[name],
            "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "content_base64": base64.b64encode(raw).decode(),
        }
    return {
        "schema_version": SCHEMA,
        "upstream": UPSTREAM,
        "upstream_revision": REVISION,
        "api_version": 1,
        "contracts": {"player_data": "maimai-player-data-1", "matching": "public-matching-1"},
        "files": entries,
    }


class ContractVendorTests(unittest.TestCase):
    def test_bundle_roundtrip_and_read_only_verification(self):
        bundle = fixture_bundle()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "contract.json"
            raw = canonical(bundle)
            archive.write_bytes(raw)
            loaded = load_bundle(archive, REVISION, hashlib.sha256(raw).hexdigest())
            destination = root / "consumer"
            vendor_bundle(loaded, REVISION, destination)
            before = {
                p.relative_to(destination): p.read_bytes()
                for p in destination.rglob("*")
                if p.is_file()
            }
            vendor_bundle(loaded, REVISION, destination, check=True)
            self.assertEqual(
                before,
                {
                    p.relative_to(destination): p.read_bytes()
                    for p in destination.rglob("*")
                    if p.is_file()
                },
            )
            with self.assertRaisesRegex(ValueError, "SHA256 mismatch"):
                load_bundle(archive, REVISION, "0" * 64)
            (destination / "_party/player_data.py").write_text("unexpected change")
            with self.assertRaisesRegex(ValueError, "differs"):
                vendor_bundle(loaded, REVISION, destination, check=True)

    def test_invalid_bundle_never_replaces_any_vendor_file(self):
        original = fixture_bundle()
        changes = [
            lambda b: b.update(upstream_revision="b" * 40),
            lambda b: b["files"]["player_data.py"].update(source_path="../../private.json"),
            lambda b: b["files"]["player_data.py"].update(sha256="0" * 64),
            lambda b: b["files"].update(unknown=b["files"]["LICENSE"]),
            lambda b: b["files"]["LICENSE"].update(bytes=True),
        ]
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory)
            vendor_bundle(original, REVISION, destination)
            before = {p: p.read_bytes() for p in destination.rglob("*") if p.is_file()}
            for change in changes:
                broken = deepcopy(original)
                change(broken)
                with self.assertRaises(ValueError):
                    vendor_bundle(broken, REVISION, destination)
                self.assertEqual(before, {p: p.read_bytes() for p in before})

    def test_exported_player_module_accepts_existing_report_corpus_identically(self):
        # The same corpus is reusable against the candidate registry bundle in the
        # cross-repository acceptance check; no report package is imported upstream.
        bundle = fixture_bundle()
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "candidate_player.py"
            source.write_bytes(validate_bundle(bundle, REVISION)["player_data.py"])
            spec = importlib.util.spec_from_file_location("candidate_player", source)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            for scenario in SCENARIOS:
                report, pbs = load_scenario(scenario)
                data = from_documents(enrich_report(report, pbs), pbs)
                with self.subTest(scenario=scenario):
                    self.assertEqual(module.validate(deepcopy(data)), data)
                    self.assertEqual(module.encode(data), player_data.encode(data))
                    self.assertEqual(module.current(data), player_data.current(data))
                    self.assertEqual(module.merge(data, data), player_data.merge(data, data))

    def test_candidate_comparison_and_player_corpus(self):
        path = ROOT.parents[1] / "scripts/check_party_contract.py"
        spec = importlib.util.spec_from_file_location("contract_acceptance", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        result = module.check_bundle(fixture_bundle(), REVISION)
        self.assertEqual(result, {"report_scenarios": len(SCENARIOS), "comparison_profiles": 5})
