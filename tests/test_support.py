"""Developer support is a single boolean with a fixed, click-only checkout."""

import unittest

from maimai_report.fixtures import load_scenario
from maimai_report.render import (
    build_html,
    enrich_report,
    support_enabled_in_html,
    validate_generated_html,
)
from tests.test_render import embedded_report


class SupportRendererTests(unittest.TestCase):
    def test_default_report_uses_isolated_developer_checkout(self):
        report, pbs = load_scenario()
        html = build_html(enrich_report(report, pbs))
        self.assertIs(embedded_report(html)["support"], True)
        self.assertIn("frame-src 'none'", html)
        self.assertIn('const checkoutUrl = "https://maimai.party/support.html";', html)
        self.assertIn(
            'const repositoryUrl = "https://github.com/arussin/maimai-session-report";', html
        )
        self.assertIn('anchor.rel = "noopener noreferrer"', html)
        self.assertIn('anchor.referrerPolicy = "no-referrer"', html)
        self.assertIn("popup,width=540,height=780,noopener,noreferrer", html)
        self.assertIn("const supportAvailable = false;", html)
        self.assertNotIn('createElement("iframe")', html)
        self.assertNotIn("buymeacoffee", html.lower())
        validate_generated_html(html)

    def test_disabled_report_is_sealed_and_contains_no_checkout_controller(self):
        report, pbs = load_scenario()
        html = build_html(enrich_report(report, pbs, support=False))
        self.assertIs(embedded_report(html)["support"], False)
        public_links = (
            "https://maimai.party",
            "https://github.com/arussin/maimai-session-report/blob/main/docs/PLAYER_FILE.md",
        )
        without_links = html
        for link in public_links:
            without_links = without_links.replace(link, "")
        self.assertNotRegex(without_links, r"https?://")
        self.assertIn("frame-src 'none'", html)
        self.assertNotIn("initializeProjectLinks", html)
        self.assertFalse(support_enabled_in_html(html))
        validate_generated_html(html)

    def test_disabled_flag_survives_rerender_and_override_does_not_mutate_input(self):
        report, pbs = load_scenario()
        report["support"] = True
        disabled = enrich_report(report, pbs, support=False)
        self.assertIs(report["support"], True)
        self.assertIs(enrich_report(disabled, pbs)["support"], False)
        self.assertIs(enrich_report(disabled, pbs, support=True)["support"], True)

    def test_support_only_accepts_a_boolean(self):
        report, pbs = load_scenario()
        for invalid in (0, 1, "true", [], {}, {"unexpected": "value"}, None):
            with self.subTest(value=invalid):
                report["support"] = invalid
                with self.assertRaisesRegex(ValueError, "Support must be true or false"):
                    build_html(report)
                with self.assertRaisesRegex(ValueError, "Support must be true or false"):
                    enrich_report(report, pbs)

    def test_checkout_origin_in_player_data_is_not_an_allowlist_escape(self):
        report, pbs = load_scenario()
        for text in (
            "https://maimai.party/support.html",
            "https://github.com/arussin/maimai-session-report",
        ):
            report["player"]["displayName"] = text
            with self.assertRaisesRegex(ValueError, "unapproved external"):
                build_html(enrich_report(report, pbs))

    def test_validation_rejects_unexpected_external_urls_and_missing_controller(self):
        report, pbs = load_scenario()
        html = build_html(enrich_report(report, pbs))
        for changed in (
            html + '<img src="https://example.invalid/image.png">',
            html + '<a href="https://maimai.party/support.html">extra</a>',
            html.replace("const supportAvailable = false;", "const supportAvailable = true;"),
            html.replace('"support":true', '"support":"true"'),
        ):
            with self.subTest():
                with self.assertRaises(ValueError):
                    validate_generated_html(changed)

    def test_unrelated_or_duplicate_html_data_cannot_enable_payment(self):
        for html in (
            '<p>"support":true</p>',
            '<script id="report-data" type="application/json">{bad}</script>',
            '<script id="report-data" type="application/json">{"support":true}</script>' * 2,
        ):
            self.assertFalse(support_enabled_in_html(html))
            with self.assertRaises(ValueError):
                validate_generated_html(html)
