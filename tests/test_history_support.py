"""The history checkout receives only the retained report's support settings."""

import json
import unittest

from maimai_report.history.bundle import report_data
from maimai_report.history.support import history_support
from maimai_report.render import json_for_html


def report(support):
    return (
        '<script id="report-data" type="application/json">'
        + json_for_html({"support": support, "player": "private-player", "scores": [12345]})
        + "</script>"
    ).encode()


class HistorySupportTests(unittest.TestCase):
    def test_settings_are_validated_and_private_data_is_not_copied(self):
        settings = {
            "provider": "buy_me_a_coffee",
            "id": "synthetic-test",
            "label": "A </script> label",
            "description": "Synthetic checkout container",
            "color": "#007887",
        }
        assets = history_support(report(settings))
        self.assertEqual(report_data(assets["html"].encode()), {"support": settings})
        self.assertNotIn("private-player", json.dumps(assets))
        self.assertNotIn("12345", json.dumps(assets))
        self.assertNotIn("A </script>", assets["html"])

    def test_disabled_support_remains_disabled(self):
        self.assertEqual(history_support(report(None)), {})

    def test_invalid_support_fails_during_staging(self):
        with self.assertRaises(ValueError):
            history_support(report({"provider": "unexpected-provider"}))
