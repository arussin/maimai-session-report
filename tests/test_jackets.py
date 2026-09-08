from __future__ import annotations

import base64
import json
import re
import unittest

from maimai_report.fixtures import load_scenario
from maimai_report.render import build_html, enrich_report


class LocalJacketTests(unittest.TestCase):
    def setUp(self) -> None:
        report, payload = load_scenario("complete")
        self.report = enrich_report(report, payload)
        self.image = (
            "data:image/png;base64,"
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jHn0AAAAASUVORK5CYII="
        )

    def test_optional_artwork_keeps_report_data_and_csp_unchanged(self) -> None:
        without = build_html(self.report)
        with_art = build_html(self.report, jackets={"synthetic-song": self.image})
        for pattern in [
            r'<script id="report-data" type="application/json">(.*?)</script>',
            r'<meta http-equiv="Content-Security-Policy" content="(.*?)"',
        ]:
            self.assertEqual(re.search(pattern, without)[1], re.search(pattern, with_art)[1])
        artwork = re.search(
            r'<script id="jacket-data" type="application/json">(.*?)</script>', with_art
        )[1]
        self.assertEqual(json.loads(artwork), {"synthetic-song": self.image})
        self.assertNotIn("https://", with_art)

    def test_remote_images_svg_and_disguised_html_are_rejected(self) -> None:
        for image in [
            "https://example.com/song.png",
            "data:image/svg+xml;base64,PHN2Zz4=",
            "data:image/png;base64," + base64.b64encode(b"<html>not an image</html>").decode(),
            "data:image/png;base64,invalid",
        ]:
            with self.subTest(image=image), self.assertRaises(ValueError):
                build_html(self.report, jackets={"synthetic-song": image})

    def test_oversized_artwork_is_rejected(self) -> None:
        oversized = (
            "data:image/png;base64,"
            + base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"x" * 204_800).decode()
        )
        with self.assertRaisesRegex(ValueError, "200 KiB"):
            build_html(self.report, jackets={"synthetic-song": oversized})

    def test_song_identifier_cannot_escape_the_data_element(self) -> None:
        malicious = '</script><img src=x onerror="alert(1)">'
        html = build_html(self.report, jackets={malicious: self.image})
        self.assertNotIn(malicious, html)
        self.assertIn(r"\u003c/script\u003e", html)
