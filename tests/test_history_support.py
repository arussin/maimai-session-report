"""The history checkout receives only the retained report's support flag."""

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
    def test_flag_is_validated_and_private_data_is_not_copied(self):
        assets = history_support(report(True))
        self.assertEqual(report_data(assets["html"].encode()), {"support": True})
        self.assertNotIn("private-player", json.dumps(assets))
        self.assertNotIn("12345", json.dumps(assets))

    def test_disabled_support_remains_disabled(self):
        self.assertEqual(history_support(report(False)), {})

    def test_invalid_support_fails_during_staging(self):
        with self.assertRaises(ValueError):
            history_support(report("unexpected"))
