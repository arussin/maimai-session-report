from __future__ import annotations

import json
import math
import re
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from maimai_report.fixtures import CURRENT_VERSION, SCENARIOS, load_scenario
from maimai_report.render import (
    build_html,
    enrich_report,
    json_for_html,
    render_demo,
    render_from_files,
    validate_generated_html,
)

_REPORT_DATA = re.compile(
    r'<script id="report-data" type="application/json">(.*?)</script>', re.DOTALL
)


def embedded_report(html: str) -> dict[str, object]:
    match = _REPORT_DATA.search(html)
    if match is None:
        raise AssertionError("generated HTML has no report-data element")
    value = json.loads(match.group(1))
    if not isinstance(value, dict):
        raise AssertionError("embedded report is not an object")
    return value


class JsonEmbeddingTests(unittest.TestCase):
    def test_script_breakout_and_html_special_characters_are_escaped(self) -> None:
        report, after_payload = load_scenario("complete")
        dangerous = '</script><img src=x onerror="alert(1)"> & \u2028 \u2029 tail'
        report["player"]["displayName"] = dangerous
        html = build_html(enrich_report(report, after_payload))

        self.assertNotIn("</script><img", html)
        self.assertNotIn("<img src=x", html)
        self.assertIn(r"\u003c/script\u003e", html)
        self.assertIn(r"\u0026", html)
        self.assertEqual(embedded_report(html)["player"]["displayName"], dangerous)

    def test_json_encoder_is_compact_sorted_and_rejects_non_finite_numbers(self) -> None:
        self.assertEqual(json_for_html({"z": 1, "a": "<"}), r'{"a":"\u003c","z":1}')
        with self.assertRaisesRegex(ValueError, "JSON"):
            json_for_html({"notFinite": math.nan})

    def test_template_like_player_text_is_not_reprocessed(self) -> None:
        report, after_payload = load_scenario("complete")
        report["player"]["displayName"] = "__INLINE_JS__"
        html = build_html(enrich_report(report, after_payload))

        self.assertEqual(embedded_report(html)["player"]["displayName"], "__INLINE_JS__")
        self.assertEqual(html.count('(() => {\n  "use strict";'), 1)


class FixtureCoverageTests(unittest.TestCase):
    def test_complete_fixture_exercises_full_pools_and_session_features(self) -> None:
        report, after_payload = load_scenario("complete")
        enriched = enrich_report(report, after_payload)

        self.assertEqual(len(enriched["after"]["old35"]), 35)
        self.assertEqual(len(enriched["after"]["new15"]), 15)
        self.assertGreater(len(enriched["after"]["newPool"]), 15)
        self.assertGreater(enriched["delta"]["reconstructedRating"], 0)
        change_types = {item["changeType"] for item in enriched["session"]["changedPBs"]}
        self.assertEqual(change_types, {"new", "improved"})
        self.assertGreater(sum(item["fast"] for item in enriched["session"]["scores"]), 0)
        self.assertGreater(sum(item["slow"] for item in enriched["session"]["scores"]), 0)
        self.assertGreater(len({item["difficulty"] for item in enriched["session"]["scores"]}), 2)
        self.assertGreater(len({item["grade"] for item in enriched["session"]["scores"]}), 2)
        self.assertLess(
            enriched["session"]["startTimeAchieved"],
            enriched["session"]["endTimeAchieved"],
        )
        self.assertTrue(any("星屑" in item["title"] for item in enriched["after"]["new15"]))

    def test_empty_fixture_has_a_true_no_change_session(self) -> None:
        report, after_payload = load_scenario("empty")
        enriched = enrich_report(report, after_payload)

        self.assertEqual(enriched["delta"]["reconstructedRating"], 0)
        self.assertEqual(enriched["session"]["scoreCount"], 0)
        self.assertEqual(enriched["session"]["changedPBs"], [])
        self.assertIsNone(enriched["session"]["startTimeAchieved"])
        self.assertIsNone(enriched["session"]["endTimeAchieved"])
        self.assertIn("No new PBs this time", build_html(enriched))

    def test_incomplete_fixture_has_open_new_15_slots(self) -> None:
        report, after_payload = load_scenario("incomplete")
        enriched = enrich_report(report, after_payload)

        self.assertEqual(len(enriched["after"]["old35"]), 35)
        self.assertEqual(len(enriched["after"]["new15"]), 8)
        self.assertEqual(enriched["after"]["newSlotsFilled"], 8)
        self.assertEqual(enriched["after"]["new15Floor"], 0)
        self.assertEqual(len(enriched["after"]["newPool"]), 8)
        self.assertIn("Open slot", build_html(enriched))

    def test_scenarios_are_independent_and_unknown_names_are_actionable(self) -> None:
        first, _ = load_scenario("complete")
        second, _ = load_scenario("complete")
        first["player"]["displayName"] = "Changed"
        self.assertEqual(second["player"]["displayName"], "Sample Player")
        self.assertEqual(SCENARIOS, ("complete", "empty", "incomplete"))
        with self.assertRaisesRegex(ValueError, "complete, empty, incomplete"):
            load_scenario("missing")


class RendererBehaviorTests(unittest.TestCase):
    def test_current_version_configuration_controls_new_pool(self) -> None:
        report, after_payload = load_scenario("complete")
        configured = enrich_report(
            report,
            after_payload,
            current_version_display_names=[CURRENT_VERSION],
        )
        absent = enrich_report(
            report,
            after_payload,
            current_version_display_names=["Fictional Different Version"],
        )
        self.assertEqual(len(configured["after"]["newPool"]), 18)
        self.assertEqual(absent["after"]["newPool"], [])

    def test_missing_current_version_names_fail_before_rendering(self) -> None:
        report, after_payload = load_scenario("complete")
        report.pop("currentNewDisplayVersions")
        with self.assertRaisesRegex(ValueError, "Current-version display names"):
            enrich_report(report, after_payload)

    def test_enrichment_does_not_mutate_inputs_and_validates_timezone(self) -> None:
        report, after_payload = load_scenario("complete")
        original_report = deepcopy(report)
        original_after = deepcopy(after_payload)
        enrich_report(report, after_payload)
        self.assertEqual(report, original_report)
        self.assertEqual(after_payload, original_after)

        with self.assertRaisesRegex(ValueError, "IANA timezone"):
            enrich_report(report, after_payload, player={"timezone": "Not/A_Zone"})

    def test_output_is_deterministic_and_has_no_external_runtime_urls(self) -> None:
        report, after_payload = load_scenario("complete")
        enriched = enrich_report(report, after_payload)
        first = build_html(enriched)
        second = build_html(enriched)

        self.assertEqual(first, second)
        validate_generated_html(first)
        self.assertNotIn("<script src=", first.lower())
        self.assertNotIn("<link ", first.lower())
        self.assertNotRegex(first, re.compile(r"@import\s+url", re.IGNORECASE))
        self.assertIn("Content-Security-Policy", first)
        self.assertIn("prefers-reduced-motion", first)
        self.assertIn("@media print", first)

    def test_external_url_in_report_data_is_rejected(self) -> None:
        report, after_payload = load_scenario("complete")
        report["player"]["displayName"] = "https://example.invalid/player"
        with self.assertRaisesRegex(ValueError, "external HTTP"):
            build_html(enrich_report(report, after_payload))

    def test_demo_and_existing_json_inputs_render_locally(self) -> None:
        report, after_payload = load_scenario("complete")
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            report_path = root / "report-input.json"
            after_path = root / "after-pbs.json"
            report_path.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
            after_path.write_text(json.dumps(after_payload, ensure_ascii=False), encoding="utf-8")

            from_files = render_from_files(
                report_path,
                after_path,
                root / "from-files.html",
            )
            demo = render_demo(root / "demo.html")

            self.assertTrue(from_files.is_file())
            self.assertTrue(demo.is_file())
            self.assertEqual(
                embedded_report(from_files.read_text(encoding="utf-8")),
                embedded_report(demo.read_text(encoding="utf-8")),
            )


if __name__ == "__main__":
    unittest.main()
