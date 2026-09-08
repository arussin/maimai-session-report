from __future__ import annotations

import json
import re
import tempfile
import unittest
from pathlib import Path

from maimai_report.cli import _support
from maimai_report.config import AppConfig, ConfigError, load_config
from maimai_report.fixtures import load_scenario
from maimai_report.render import build_html, enrich_report

BUY_ME_A_COFFEE_ORIGIN = "https://buymeacoffee.com"
SUPPORT = {
    "provider": "buy_me_a_coffee",
    "id": "synthetic-test",
    "label": "Buy me a maimai credit",
    "description": "Support me on Buy me a coffee!",
    "color": "#5F7FFF",
}
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


class SupportRendererTests(unittest.TestCase):
    def test_default_report_remains_sealed(self) -> None:
        report, after_payload = load_scenario("complete")
        html = build_html(enrich_report(report, after_payload))

        self.assertNotIn(BUY_ME_A_COFFEE_ORIGIN, html)
        self.assertIn("frame-src 'none'", html)
        self.assertNotIn("support", embedded_report(html))
        self.assertNotIn("cdnjs.buymeacoffee.com", html)
        self.assertNotIn("cdn.buymeacoffee.com", html)

    def test_enabled_report_uses_isolated_on_page_checkout(self) -> None:
        report, after_payload = load_scenario("complete")
        html = build_html(enrich_report(report, after_payload, support=SUPPORT))
        embedded = embedded_report(html)

        self.assertEqual(embedded["support"], SUPPORT)
        self.assertEqual(html.count(BUY_ME_A_COFFEE_ORIGIN), 1)
        self.assertIn(f"frame-src {BUY_ME_A_COFFEE_ORIGIN}", html)
        self.assertNotIn("https://www.buymeacoffee.com", html)
        self.assertNotIn("cdnjs.buymeacoffee.com", html)
        self.assertNotIn("cdn.buymeacoffee.com", html)
        self.assertNotIn("<script src=", html.lower())
        self.assertIn('document.createElement("iframe")', html)
        self.assertIn('frame.allow = "payment *"', html)
        self.assertIn('frame.referrerPolicy = "no-referrer"', html)
        self.assertIn('fallback.referrerPolicy = "no-referrer"', html)
        self.assertIn('openButton.addEventListener("click", openCheckout)', html)
        self.assertIn('"buymeacoffee.com"].join("/")', html)
        self.assertIn("reportFooter.before(card)", html)
        self.assertIn("support-checkout-dialog", html)
        self.assertIn("@media print", html)

    def test_support_values_are_normalized_without_mutating_input(self) -> None:
        report, after_payload = load_scenario("complete")
        supplied = {**SUPPORT, "color": "#5f7fff"}
        enriched = enrich_report(report, after_payload, support=supplied)

        self.assertEqual(enriched["support"]["color"], "#5F7FFF")
        self.assertEqual(supplied["color"], "#5f7fff")

    def test_invalid_or_unexpected_support_configuration_is_rejected(self) -> None:
        report, after_payload = load_scenario("complete")
        invalid_cases = (
            ({**SUPPORT, "provider": "other"}, "provider"),
            ({**SUPPORT, "id": 'synthetic-test"><script'}, "ID"),
            ({**SUPPORT, "color": "blue"}, "color"),
            ({**SUPPORT, "extra": "value"}, "Unknown support"),
        )
        for support, message in invalid_cases:
            with self.subTest(support=support):
                with self.assertRaisesRegex(ValueError, message):
                    enrich_report(report, after_payload, support=support)

    def test_unapproved_url_in_support_text_is_rejected(self) -> None:
        report, after_payload = load_scenario("complete")
        support = {**SUPPORT, "description": "See https://example.invalid"}
        enriched = enrich_report(report, after_payload, support=support)

        with self.assertRaisesRegex(ValueError, "unapproved external"):
            build_html(enriched)


class SupportConfigurationTests(unittest.TestCase):
    def test_environment_values_enable_support(self) -> None:
        config = load_config(
            None,
            environ={
                "MAIMAI_REPORT_BUY_ME_A_COFFEE_ID": "synthetic-test",
                "MAIMAI_REPORT_SUPPORT_LABEL": "Buy me a maimai credit",
                "MAIMAI_REPORT_SUPPORT_DESCRIPTION": "Support me on Buy me a coffee!",
                "MAIMAI_REPORT_SUPPORT_COLOR": "#5f7fff",
            },
        )

        self.assertEqual(config.buy_me_a_coffee_id, "synthetic-test")
        self.assertEqual(
            _support(config),
            {
                **SUPPORT,
                "color": "#5f7fff",
            },
        )

    def test_toml_values_enable_support(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            config_path = Path(temporary_directory, "config.toml")
            config_path.write_text(
                """
[support]
buy_me_a_coffee_id = "synthetic-test"
label = "Buy me a maimai credit"
description = "Support me on Buy me a coffee!"
color = "#5F7FFF"
""".strip(),
                encoding="utf-8",
            )
            config = load_config(config_path, environ={})

        self.assertEqual(config.buy_me_a_coffee_id, "synthetic-test")
        self.assertEqual(_support(config), SUPPORT)

    def test_empty_id_keeps_support_disabled(self) -> None:
        self.assertIsNone(_support(AppConfig()))

    def test_invalid_account_id_and_color_fail_during_config_load(self) -> None:
        with self.assertRaisesRegex(ConfigError, "Buy Me a Coffee ID"):
            load_config(None, environ={"MAIMAI_REPORT_BUY_ME_A_COFFEE_ID": "bad/id"})
        with self.assertRaisesRegex(ConfigError, "Support color"):
            load_config(None, environ={"MAIMAI_REPORT_SUPPORT_COLOR": "not-a-color"})


if __name__ == "__main__":
    unittest.main()
