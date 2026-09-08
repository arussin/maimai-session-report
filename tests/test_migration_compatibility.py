from __future__ import annotations

import re
import unittest
from pathlib import Path

from maimai_report.cli import _player
from maimai_report.config import AppConfig
from maimai_report.render import enrich_report


class MigrationCompatibilityTests(unittest.TestCase):
    def test_api_game_identifier_uses_existing_report_label(self) -> None:
        player = _player(AppConfig(username="player", display_name="Player", game="maimaidx"))
        self.assertEqual(player["game"], "maimai DX")

    def test_equal_rate_new_pool_keeps_upstream_order(self) -> None:
        report = {
            "currentNewDisplayVersions": ["Current"],
            "after": {},
            "session": {"scores": []},
        }
        after_payload = {
            "body": {
                "pbs": [
                    {"chartID": "chart-b", "songID": "song-b", "calculatedData": {"rate": 200}},
                    {"chartID": "chart-a", "songID": "song-a", "calculatedData": {"rate": 200}},
                ],
                "charts": [
                    {"chartID": "chart-b", "data": {"displayVersion": "Current"}},
                    {"chartID": "chart-a", "data": {"displayVersion": "Current"}},
                ],
                "songs": [
                    {"id": "song-b", "title": "B"},
                    {"id": "song-a", "title": "A"},
                ],
            }
        }

        enriched = enrich_report(report, after_payload)

        self.assertEqual(
            [item["chartID"] for item in enriched["after"]["newPool"]],
            ["chart-b", "chart-a"],
        )

    def test_private_action_contract_is_pinned_and_fail_closed(self) -> None:
        action = Path("action.yml").read_text(encoding="utf-8")
        uses = re.findall(r"^\s*uses:\s*([^\s#]+)", action, re.MULTILINE)

        self.assertEqual(
            uses,
            ["actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1"],
        )
        self.assertIn("github.event.repository.private", action)
        self.assertIn("github.action_path", action)
        self.assertIn("sync-and-render", action)
        self.assertNotIn("secrets.", action)


if __name__ == "__main__":
    unittest.main()
