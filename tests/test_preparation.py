"""Characterize the unchanged HTML boundary before preparing report data separately."""

import hashlib
import json
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from maimai_report.fixtures import load_scenario
from maimai_report.preparation import PartyContext, prepare_report
from maimai_report.render import build_html, enrich_report, render_prepared


class PreparationTests(unittest.TestCase):
    def test_all_original_report_bytes_are_unchanged(self):
        # Captured before this refactor from c4992ce14e3b5a0821e96a801c8cf925f60f41cf.
        expected = json.loads(Path("tests/fixtures/preparation-baseline.json").read_text())
        for key, digest in expected.items():
            scenario, support, enabled, hosted = key.split(":")
            with self.subTest(case=key):
                report, pbs = load_scenario(scenario)
                html = build_html(
                    enrich_report(report, pbs, support=support == "1"),
                    party_enabled=enabled == "1",
                    party_latest_path="/maimai/party/latest.json" if hosted == "1" else None,
                )
                self.assertEqual(hashlib.sha256(html.encode()).hexdigest(), digest)

    def test_explicit_context_matches_legacy_context_without_mutating_either(self):
        report, pbs = load_scenario("complete")
        report = enrich_report(report, pbs)
        report["_partyEnabled"] = True
        report["_partyLatestPath"] = "/maimai/party/latest.json"
        original = deepcopy(report)
        context = PartyContext(dataset=report["_partyData"], latest_path=report["_partyLatestPath"])
        clean = {key: value for key, value in report.items() if not key.startswith("_party")}
        prepared = prepare_report(clean, context=context)
        self.assertEqual(render_prepared(prepared), build_html(report))
        self.assertEqual(report, original)
        self.assertFalse(any(key.startswith("_party") for key in prepared.data))

    def test_rendering_a_prepared_report_never_recalculates_personal_data(self):
        report, pbs = load_scenario("complete")
        prepared = prepare_report(enrich_report(report, pbs))
        with patch("maimai_report.preparation.prepare_recommendations", side_effect=AssertionError):
            first = render_prepared(prepared)
            self.assertEqual(render_prepared(prepared), first)

    def test_prepared_data_does_not_alias_input(self):
        report, pbs = load_scenario("complete")
        report = enrich_report(report, pbs)
        prepared = prepare_report(report)
        report["player"]["displayName"] = "changed after preparation"
        self.assertNotEqual(prepared.data["player"]["displayName"], report["player"]["displayName"])

    def test_explicit_pipeline_prepares_once_before_artwork_and_rendering(self):
        import tempfile

        from maimai_report.artwork import prepare_prepared_jackets
        from maimai_report.party import from_documents, prepare_dataset
        from maimai_report.preparation import enrich_report_data, prepare_recommendations

        report, pbs = load_scenario("complete")
        original = deepcopy(report)
        enriched = enrich_report_data(report, pbs)
        self.assertFalse(any(key.startswith("_party") for key in enriched))
        dataset = prepare_dataset(enriched, after_payload=pbs)
        self.assertEqual(dataset, from_documents(enriched, pbs))
        self.assertEqual(report, original)
        with patch(
            "maimai_report.preparation.prepare_recommendations", wraps=prepare_recommendations
        ) as derive:
            prepared = prepare_report(enriched, context=PartyContext(dataset=dataset))
            with tempfile.TemporaryDirectory() as directory:
                prepare_prepared_jackets(prepared, Path(directory), offline=True)
            render_prepared(prepared)
            render_prepared(prepared)
        self.assertEqual(derive.call_count, 1)
        self.assertFalse(any(key.startswith("_party") for key in prepared.data))

    def test_production_entry_points_do_not_use_legacy_context_fields_or_facades(self):
        root = Path(__file__).resolve().parents[1] / "src/maimai_report"
        for relative in ("cli.py", "installation/operations.py", "installation/verification.py"):
            source = (root / relative).read_text()
            for token in (
                '"_partyData"',
                '"_partyCatalog"',
                '"_partyEnabled"',
                '"_partyLatestPath"',
                "enrich_report(",
                "render_report(",
                "prepare_jackets(",
            ):
                self.assertNotIn(token, source, relative)
        for path in root.rglob("*.py"):
            if path.name == "compatibility.py":
                continue
            for token in (
                '"_partyData"',
                '"_partyCatalog"',
                '"_partyEnabled"',
                '"_partyLatestPath"',
            ):
                self.assertNotIn(token, path.read_text(), str(path))

    def test_mapped_catalog_retained_history_and_artwork_match_prior_commit(self):
        from maimai_report.artwork import _report_songs
        from tests.preparation_cases import mapped_cases

        expected = json.loads(Path("tests/fixtures/preparation-mapped-baseline.json").read_text())
        for name, report, jackets in mapped_cases():
            with self.subTest(case=name):
                context = PartyContext.from_legacy(report)
                prepared = prepare_report(report, context=context)
                self.assertEqual(
                    prepared.data["partyRecommendations"]["practice"]["chart"]["chartID"], "harder"
                )
                self.assertIn("other", _report_songs(prepared.data))
                actual = hashlib.sha256(
                    render_prepared(prepared, jackets=jackets).encode()
                ).hexdigest()
                self.assertEqual(actual, expected["cases"][name])
