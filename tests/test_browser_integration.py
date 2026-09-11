import copy
import sys
import unittest
from unittest.mock import patch

from maimai_report.browser import export_browser_bundle, prepared_view
from maimai_report.render import build_html, validate_generated_html


def fixture():
    return {
        "format": "maimai-personal",
        "schema_version": "1.0.0",
        "engine_version": "0.1.0",
        "snapshot_id": "a" * 64,
        "cutoff_ms": 1000,
        "catalog": {"id": "synthetic", "version": "one", "sha256": "b" * 64},
        "chart_summaries": [
            {
                "chart_id": "chart:one",
                "title": "Fictional song",
                "difficulty": "MASTER",
                "format": "DX",
                "level": "12",
            }
        ],
        "recommendations": {
            "cards": [
                {
                    "chart_id": "chart:one",
                    "category": "rating",
                    "target_achievement": 97.0,
                    "gain_if_achieved": 5,
                    "previous_achievement": 96.0,
                }
            ]
        },
    }


class BrowserIntegrationTests(unittest.TestCase):
    def test_normal_render_and_bundle_consumption_need_no_engine(self):
        report = {"generatedAt": "2026-05-28T00:00:00Z", "support": False}
        with patch.dict(sys.modules, {"maimai_intelligence": None}):
            plain = build_html(report)
            html = build_html(
                report,
                recommendation_bundle=fixture(),
                browser_url="https://charts.example.test/browser/",
            )
            self.assertNotIn("browser-cards", plain)
            self.assertIn('"preparedRecommendations"', html)
            self.assertNotIn('"overlay"', html)
            self.assertNotIn('"raw_hashes"', html)
            self.assertNotIn("explore-similarity", html)
            validate_generated_html(html)
            self.assertEqual(build_html(report), plain)

    def test_future_cutoff_and_unsafe_links_rejected(self):
        report = {"generatedAt": "2026-05-28T00:00:00Z"}
        for url in (
            "javascript:alert(1)",
            "https://user:pass@example.test/",
            "https://example.test/?token=x",
            "http://example.test/",
        ):
            with self.assertRaises(ValueError):
                prepared_view(fixture(), report, url)
        future = fixture()
        future["cutoff_ms"] = 8_000_000_000_000
        with self.assertRaises(ValueError):
            prepared_view(future, report)

    def test_invalid_cards_rejected(self):
        report = {"generatedAt": "2026-05-28T00:00:00Z"}
        for mutate in (
            lambda b: b.update(schema_version="2"),
            lambda b: b["recommendations"]["cards"][0].update(chart_id="missing"),
            lambda b: b["recommendations"]["cards"][0].update(gain_if_achieved=float("nan")),
        ):
            bundle = copy.deepcopy(fixture())
            mutate(bundle)
            with self.assertRaises(ValueError):
                prepared_view(bundle, report)

    def test_export_explains_optional_install_and_never_acquires(self):
        with patch.dict(sys.modules, {"maimai_intelligence": None}):
            with self.assertRaisesRegex(RuntimeError, "optional"):
                export_browser_bundle({}, {}, {}, {})
