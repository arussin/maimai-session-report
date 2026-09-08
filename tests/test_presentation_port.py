"""Guard the approved direct-port assets and the fictional public showcase."""

import base64
import hashlib
import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from maimai_report.fixtures import SCENARIOS, load_scenario
from maimai_report.fixtures.artwork import demo_jackets
from maimai_report.fixtures.synthetic import _achievement
from maimai_report.render import enrich_report, render_demo


class PresentationPortTests(unittest.TestCase):
    def test_approved_layout_interactions_and_support_assets_are_unchanged(self):
        # Git blob IDs of the reviewed original presentation (UTF-8 / LF).
        # A deliberate redesign must update this explicit compatibility decision.
        expected = {
            "styles.css": "a7f885c289eff931b1dd0efee16d701a427e37f7",
            "app.js": "24180d45654b08a57ed20564ccf886e89a10fb36",
            "support.css": "c65a3d29d4c8ebac63f412e864d5ddab6ae5fa27",
            "support.js": "fb2eb58c0b1d0f6d1a538043576babb24012d3e9",
        }
        for name, digest in expected.items():
            with self.subTest(asset=name):
                content = (
                    Path("src/maimai_report/assets", name).read_text(encoding="utf-8").encode()
                )
                blob = b"blob " + str(len(content)).encode() + b"\0" + content
                self.assertEqual(hashlib.sha1(blob, usedforsecurity=False).hexdigest(), digest)

    def test_demo_totals_and_grades_agree_with_their_score_rows(self):
        for scenario in SCENARIOS:
            source, pbs = load_scenario(scenario)
            model = enrich_report(source, pbs)
            with self.subTest(scenario=scenario):
                for snapshot in ("before", "after"):
                    state = model[snapshot]
                    for key, size in (("old35", 35), ("new15", 15)):
                        self.assertEqual(
                            state[key + "Rating"], sum(row["rate"] for row in state[key])
                        )
                        self.assertLessEqual(len(state[key]), size)
                        for row in state[key]:
                            expected = _achievement(row["percent"], row["levelNum"])
                            self.assertEqual(row["rate"], expected["rate"])
                            self.assertEqual(row["grade"], expected["grade"])
                    self.assertEqual(
                        state["reconstructedRating"], state["old35Rating"] + state["new15Rating"]
                    )
                for key in ("reconstructedRating", "old35Rating", "new15Rating", "naiveRating"):
                    self.assertEqual(
                        model["delta"][key], model["after"][key] - model["before"][key]
                    )

    def test_complete_demo_has_real_positive_gain_target_candidates(self):
        source, pbs = load_scenario()
        model = enrich_report(source, pbs)
        floor = model["after"]["new15Floor"]
        candidates = [
            row
            for row in model["after"]["newPool"]
            if 94.5 <= row["percent"] < 97
            and _achievement(97, row["levelNum"])["rate"] > max(row["rate"], floor)
        ]
        self.assertGreaterEqual(len(candidates), 2)

    def test_demo_tiles_are_local_deterministic_and_synthetic_only(self):
        _, pbs = load_scenario()
        first = demo_jackets(pbs)
        self.assertEqual(first, demo_jackets(pbs))
        self.assertEqual(len(first), len(pbs["body"]["songs"]))
        for image in first.values():
            content = base64.b64decode(image.split(",")[1], validate=True)
            self.assertTrue(content.startswith(b"\x89PNG\r\n\x1a\n"))
            self.assertLess(len(content), 20_000)
        pbs["body"]["songs"][0]["id"] = "not-a-fixture"
        with self.assertRaisesRegex(ValueError, "synthetic"):
            demo_jackets(pbs)

    def test_demo_generation_cannot_open_a_network_socket(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(
                socket, "socket", side_effect=AssertionError("Demo tried to use the network")
            ),
        ):
            self.assertTrue(render_demo(Path(directory, "demo.html")).is_file())
