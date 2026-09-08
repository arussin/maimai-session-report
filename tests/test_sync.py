from __future__ import annotations

import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from maimai_report.config import AppConfig
from maimai_report.errors import APIResponseError, ConfigError, ImportFailedError, MissingTokenError
from maimai_report.sync import synchronize, write_sync_result


def wrapped(key: str, records: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "success": True,
        "body": {
            key: records or [],
            "charts": [],
            "songs": [],
        },
    }


class FakeSyncClient:
    def __init__(
        self,
        *,
        before_pbs: dict[str, Any] | None = None,
        before_scores: dict[str, Any] | None = None,
        after_pbs: dict[str, Any] | None = None,
        after_scores: dict[str, Any] | None = None,
        wait_error: Exception | None = None,
    ) -> None:
        self.pbs = [before_pbs or wrapped("pbs"), after_pbs or wrapped("pbs")]
        self.scores = [before_scores or wrapped("scores"), after_scores or wrapped("scores")]
        self.wait_error = wait_error
        self.calls: list[object] = []
        self.import_count = 0

    def get_pbs(self, username: str, game: str) -> dict[str, Any]:
        self.calls.append(("pbs", username, game))
        return self.pbs.pop(0)

    def get_recent_scores(self, username: str, game: str) -> dict[str, Any]:
        self.calls.append(("scores", username, game))
        return self.scores.pop(0)

    def start_import(self, import_type: str) -> str:
        self.calls.append(("start", import_type))
        self.import_count += 1
        return "synthetic-import-id"

    def wait_for_import(self, import_id: str) -> None:
        self.calls.append(("wait", import_id))
        if self.wait_error is not None:
            raise self.wait_error


def live_config() -> AppConfig:
    return AppConfig(
        username="fixture-user",
        display_name="Fixture Player",
        timezone="UTC",
        game="maimaidx",
        import_type="api/myt-maimaidx",
        current_version_display_names=("Synthetic Current",),
    )


class SyncTests(unittest.TestCase):
    def test_sync_starts_exactly_one_import_and_waits_once_without_polling(self) -> None:
        client = FakeSyncClient()
        result = synchronize(
            live_config(),
            environ={"KAMAITACHI_API_TOKEN": "synthetic-token"},
            client=client,
            generated_at=dt.datetime(2026, 1, 1, tzinfo=dt.UTC),
        )

        self.assertEqual(client.import_count, 1)
        self.assertEqual(
            client.calls,
            [
                ("pbs", "fixture-user", "maimaidx"),
                ("scores", "fixture-user", "maimaidx"),
                ("start", "api/myt-maimaidx"),
                ("wait", "synthetic-import-id"),
                ("pbs", "fixture-user", "maimaidx"),
                ("scores", "fixture-user", "maimaidx"),
            ],
        )
        self.assertTrue(result.metadata["syncCompleted"])
        self.assertEqual(result.metadata["fetchedAt"], "2026-01-01T00:00:00Z")

    def test_missing_token_fails_before_any_client_or_network_action(self) -> None:
        client = FakeSyncClient()
        with self.assertRaises(MissingTokenError):
            synchronize(live_config(), environ={}, client=client)
        self.assertEqual(client.calls, [])

    def test_invalid_configuration_fails_before_token_or_client_action(self) -> None:
        client = FakeSyncClient()
        with self.assertRaises(ConfigError):
            synchronize(
                AppConfig(username="fixture-user"),
                environ={"KAMAITACHI_API_TOKEN": "synthetic-token"},
                client=client,
            )
        self.assertEqual(client.calls, [])

    def test_invalid_before_response_prevents_import(self) -> None:
        client = FakeSyncClient(before_pbs={"success": True, "body": {"pbs": []}})
        with self.assertRaises(APIResponseError):
            synchronize(
                live_config(),
                environ={"KAMAITACHI_API_TOKEN": "synthetic-token"},
                client=client,
            )
        self.assertEqual(client.import_count, 0)
        self.assertEqual(len(client.calls), 1)

    def test_sse_failure_stops_without_after_fetch_or_retry(self) -> None:
        client = FakeSyncClient(wait_error=ImportFailedError("Synthetic import failure"))
        with self.assertRaisesRegex(ImportFailedError, "Synthetic import failure"):
            synchronize(
                live_config(),
                environ={"KAMAITACHI_API_TOKEN": "synthetic-token"},
                client=client,
            )
        self.assertEqual(client.import_count, 1)
        self.assertEqual(
            [call[0] for call in client.calls if isinstance(call, tuple)],
            [
                "pbs",
                "scores",
                "start",
                "wait",
            ],
        )

    def test_private_outputs_use_audited_names_and_valid_json(self) -> None:
        result = synchronize(
            live_config(),
            environ={"KAMAITACHI_API_TOKEN": "synthetic-token"},
            client=FakeSyncClient(),
            generated_at=dt.datetime(2026, 1, 1, tzinfo=dt.UTC),
        )
        with tempfile.TemporaryDirectory() as directory:
            outputs = write_sync_result(result, Path(directory) / "private-output")
            self.assertEqual(
                set(outputs),
                {
                    "before-pbs.json",
                    "after-pbs.json",
                    "before-recent-scores.json",
                    "after-recent-scores.json",
                    "report-input.json",
                    "metadata.json",
                },
            )
            for path in outputs.values():
                self.assertTrue(path.is_file())
                self.assertIsInstance(json.loads(path.read_text(encoding="utf-8")), dict)


if __name__ == "__main__":
    unittest.main()
