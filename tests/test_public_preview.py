"""The intentionally committed sample must never be replaced with player output."""

import tempfile
import unittest
from pathlib import Path

from maimai_report.render import render_demo


class PublicPreviewTests(unittest.TestCase):
    def test_public_sample_is_exactly_the_bundled_fictional_demo(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            generated = render_demo(Path(directory, "demo.html")).read_text(encoding="utf-8")
        sample = Path("docs/sample-report.html").read_text(encoding="utf-8")
        self.assertEqual(sample, generated)
        self.assertIn("Sample Player", sample)
        self.assertNotRegex(sample, r"(?i)https?://")
        self.assertIn("data:image/png;base64,", sample)

    def test_explicit_plain_display_contains_no_bundled_game_art(self) -> None:
        css = Path("src/maimai_report/assets/rating-fallback.css").read_text(encoding="utf-8")
        self.assertNotRegex(css, r"(?i)url\s*\(|data:|https?://")
        self.assertIn(".namecard .rating-value", css)
        self.assertIn("forced-colors: active", css)


if __name__ == "__main__":
    unittest.main()
