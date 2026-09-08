from __future__ import annotations

import json
import unittest

from maimai_report.errors import ImportFailedError, ImportStreamEndedError
from maimai_report.sse import iter_events, wait_for_completion


class SSETests(unittest.TestCase):
    def test_done_event_completes(self) -> None:
        wait_for_completion([b"event: progress\n", b"data: 50\n", b"\n", b"event: done\n", b"\n"])

    def test_failure_never_relays_private_upstream_descriptions(self) -> None:
        for description in (
            "MYT rejected the import",
            "Bearer synthetic-private-token",
            "cardAccessCode=synthetic-private-code",
            "Cookie: synthetic-private-cookie",
            "https://private-service.invalid/internal-detail",
            "private-details-" * 100,
        ):
            with self.subTest(description=description):
                with self.assertRaises(ImportFailedError) as raised:
                    wait_for_completion(
                        [
                            "event: import:failed\n",
                            "data: " + json.dumps({"description": description}) + "\n",
                            "\n",
                        ]
                    )
                self.assertIn("Check the import status", str(raised.exception))
                self.assertNotIn(description, str(raised.exception))

    def test_malformed_failure_data_does_not_echo_body(self) -> None:
        with self.assertRaisesRegex(ImportFailedError, "MYT import failed"):
            wait_for_completion(
                ["event: import:failed\n", "data: not-json secret-like-body\n", "\n"]
            )

    def test_stream_eof_before_completion_fails(self) -> None:
        with self.assertRaisesRegex(ImportStreamEndedError, "before completion"):
            wait_for_completion(["event: progress\n", "data: 99\n", "\n"])

    def test_unterminated_done_is_not_treated_as_complete(self) -> None:
        with self.assertRaises(ImportStreamEndedError):
            wait_for_completion(["event: done\n"])

    def test_multiline_data_comments_and_unknown_fields(self) -> None:
        events = list(
            iter_events(
                [
                    ": heartbeat\n",
                    "event: progress\n",
                    "id: 12\n",
                    "data: first\n",
                    "data:second\n",
                    "\n",
                ]
            )
        )
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].name, "progress")
        self.assertEqual(events[0].data, "first\nsecond")


if __name__ == "__main__":
    unittest.main()
