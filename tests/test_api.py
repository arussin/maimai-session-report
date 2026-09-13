from __future__ import annotations

import io
import json
import unittest
import urllib.error
import urllib.request
from typing import Any

from maimai_report.api import KamaitachiClient, validate_score_payload
from maimai_report.errors import (
    APIHTTPError,
    APIResponseError,
    APITransportError,
    ImportFailedError,
    ImportStreamError,
    MissingTokenError,
)
from maimai_report.errors import (
    ImportError as MaimaiImportError,
)


class FakeResponse:
    def __init__(
        self,
        *,
        status: int = 200,
        payload: object | None = None,
        raw: bytes | None = None,
        lines: list[bytes] | None = None,
    ) -> None:
        self.status = status
        self._raw = raw if raw is not None else json.dumps(payload).encode("utf-8")
        self._lines = lines or []

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return self._raw

    def __iter__(self):  # type: ignore[no-untyped-def]
        return iter(self._lines)


class RecordingOpener:
    def __init__(self, *outcomes: object) -> None:
        self.outcomes = list(outcomes)
        self.calls: list[tuple[urllib.request.Request, float]] = []

    def __call__(self, request: urllib.request.Request, *, timeout: float) -> Any:
        self.calls.append((request, timeout))
        if not self.outcomes:
            raise AssertionError("Unexpected network call")
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


class APITests(unittest.TestCase):
    def test_session_endpoints_are_public_reads_and_encode_identifiers(self) -> None:
        opener = RecordingOpener(
            FakeResponse(payload={"success": True, "body": []}),
            FakeResponse(payload={"success": True, "body": {}}),
        )
        client = KamaitachiClient("synthetic-submission-token", opener=opener)
        client.get_sessions("user/name", "maimaidx")
        client.get_session("session/name")
        paths = ["/users/user%2Fname/games/maimaidx/sessions/recent", "/sessions/session%2Fname"]
        for (request, _), path in zip(opener.calls, paths, strict=True):
            self.assertTrue(request.full_url.endswith(path))
            self.assertEqual(request.method, "GET")
            self.assertIsNone(request.get_header("Authorization"))
            self.assertIsNone(request.get_header("X-user-intent"))

    def test_public_fetch_encodes_path_and_sends_no_bearer_token(self) -> None:
        opener = RecordingOpener(FakeResponse(payload={"success": True, "body": {}}))
        client = KamaitachiClient("synthetic-token", opener=opener)

        payload = client.get_pbs("user/name", "maimaidx")

        self.assertTrue(payload["success"])
        request, timeout = opener.calls[0]
        self.assertEqual(timeout, 60)
        self.assertTrue(request.full_url.endswith("/users/user%2Fname/games/maimaidx/pbs/all"))
        self.assertIsNone(request.get_header("Authorization"))

    def test_start_import_is_authenticated_and_validates_accepted_response(self) -> None:
        opener = RecordingOpener(
            FakeResponse(
                status=202,
                payload={"success": True, "body": {"importID": "import-123"}},
            )
        )
        client = KamaitachiClient("synthetic-token", opener=opener)

        import_id = client.start_import("api/myt-maimaidx")

        self.assertEqual(import_id, "import-123")
        request, _timeout = opener.calls[0]
        self.assertEqual(request.method, "POST")
        self.assertEqual(request.get_header("Authorization"), "Bearer synthetic-token")
        self.assertEqual(request.get_header("X-user-intent"), "true")
        self.assertEqual(json.loads(request.data or b"{}"), {"importType": "api/myt-maimaidx"})

    def test_authenticated_read_sends_bearer_without_user_intent(self) -> None:
        opener = RecordingOpener(FakeResponse(payload={"success": True, "body": {}}))
        client = KamaitachiClient("synthetic-token", opener=opener)

        client.get_pbs("user", "maimaidx", authenticated=True)

        request, _timeout = opener.calls[0]
        self.assertEqual(request.get_header("Authorization"), "Bearer synthetic-token")
        self.assertIsNone(request.get_header("X-user-intent"))

    def test_import_cannot_start_without_token(self) -> None:
        opener = RecordingOpener()
        client = KamaitachiClient(None, opener=opener)
        with self.assertRaises(MissingTokenError):
            client.start_import("api/myt-maimaidx")
        self.assertEqual(opener.calls, [])

    def test_import_start_requires_accepted_status_and_import_id(self) -> None:
        wrong_status = KamaitachiClient(
            "synthetic-token",
            opener=RecordingOpener(
                FakeResponse(
                    status=200,
                    payload={"success": True, "body": {"importID": "id"}},
                )
            ),
        )
        with self.assertRaisesRegex(MaimaiImportError, "did not queue"):
            wrong_status.start_import("api/myt-maimaidx")

        missing_id = KamaitachiClient(
            "synthetic-token",
            opener=RecordingOpener(FakeResponse(status=202, payload={"success": True, "body": {}})),
        )
        with self.assertRaisesRegex(MaimaiImportError, "did not queue"):
            missing_id.start_import("api/myt-maimaidx")

    def test_authenticated_read_cannot_run_without_token(self) -> None:
        opener = RecordingOpener()
        client = KamaitachiClient(None, opener=opener)
        with self.assertRaises(MissingTokenError):
            client.get_pbs("user", "maimaidx", authenticated=True)
        self.assertEqual(opener.calls, [])

    def test_http_error_does_not_echo_response_body_or_token(self) -> None:
        secret_body = b"sensitive response body"
        error = urllib.error.HTTPError(
            "https://unit.test/path",
            403,
            "Forbidden",
            {},
            io.BytesIO(secret_body),
        )
        opener = RecordingOpener(error)
        client = KamaitachiClient(
            "synthetic-secret-token",
            base_url="https://unit.test",
            opener=opener,
        )
        with self.assertRaises(APIHTTPError) as captured:
            client.request_json("/path", authenticated=True)
        message = str(captured.exception)
        self.assertIn("HTTP 403", message)
        self.assertNotIn(secret_body.decode(), message)
        self.assertNotIn("synthetic-secret-token", message)

    def test_transport_and_json_shape_failures_are_domain_errors(self) -> None:
        failing = KamaitachiClient(
            None,
            opener=RecordingOpener(urllib.error.URLError("offline")),
        )
        with self.assertRaises(APITransportError):
            failing.request_json("/test")

        invalid_json = KamaitachiClient(
            None,
            opener=RecordingOpener(FakeResponse(raw=b"not json")),
        )
        with self.assertRaises(APIResponseError):
            invalid_json.request_json("/test")

        non_object = KamaitachiClient(
            None,
            opener=RecordingOpener(FakeResponse(payload=[])),
        )
        with self.assertRaisesRegex(APIResponseError, "non-object"):
            non_object.request_json("/test")

    def test_score_response_validation_requires_all_lists(self) -> None:
        valid = {
            "success": True,
            "body": {"pbs": [], "charts": [], "songs": []},
        }
        self.assertIs(validate_score_payload(valid, "pbs"), valid["body"])
        with self.assertRaisesRegex(APIResponseError, "charts"):
            validate_score_payload(
                {"success": True, "body": {"pbs": [], "songs": []}},
                "pbs",
            )
        with self.assertRaisesRegex(APIResponseError, "unsuccessful"):
            validate_score_payload({"success": False}, "pbs")

    def test_sse_wait_has_explicit_timeout_no_auth_and_no_polling(self) -> None:
        opener = RecordingOpener(
            FakeResponse(
                lines=[
                    b"event: progress\n",
                    b"data: 50\n",
                    b"\n",
                    b"event: done\n",
                    b"\n",
                ]
            )
        )
        client = KamaitachiClient("synthetic-token", opener=opener)

        client.wait_for_import("id/with/slash")

        self.assertEqual(len(opener.calls), 1)
        request, timeout = opener.calls[0]
        self.assertEqual(timeout, 650)
        self.assertTrue(request.full_url.endswith("/imports/id%2Fwith%2Fslash/stream"))
        self.assertEqual(request.get_header("Accept"), "text/event-stream")
        self.assertIsNone(request.get_header("Authorization"))

    def test_sse_failure_and_http_failure_are_clear(self) -> None:
        failed_import = KamaitachiClient(
            "synthetic-token",
            opener=RecordingOpener(
                FakeResponse(
                    lines=[
                        b"event: import:failed\n",
                        b'data: {"description":"Import rejected"}\n',
                        b"\n",
                    ]
                )
            ),
        )
        with self.assertRaisesRegex(ImportFailedError, "Check the import status"):
            failed_import.wait_for_import("id")

        http_error = urllib.error.HTTPError(
            "https://unit.test/stream",
            502,
            "Bad Gateway",
            {},
            None,
        )
        unavailable = KamaitachiClient(
            "synthetic-token",
            opener=RecordingOpener(http_error),
        )
        with self.assertRaisesRegex(ImportStreamError, "HTTP 502"):
            unavailable.wait_for_import("id")


if __name__ == "__main__":
    unittest.main()
