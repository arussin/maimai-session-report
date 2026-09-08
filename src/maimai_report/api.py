"""Small, injectable Kamaitachi HTTP client built on the standard library."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from typing import Any

from .errors import (
    APIHTTPError,
    APIResponseError,
    APITransportError,
    ImportError,
    ImportStreamError,
    MissingTokenError,
)
from .sse import wait_for_completion

API_BASE = "https://kamai.tachi.ac/api/v1"
USER_AGENT = "maimai-session-report/0.1"

UrlOpener = Callable[..., Any]


class KamaitachiClient:
    """Perform the exact low-request sync sequence when explicitly called."""

    def __init__(
        self,
        token: str | None,
        *,
        base_url: str = API_BASE,
        user_agent: str = USER_AGENT,
        request_timeout: float = 60,
        import_timeout: float = 650,
        opener: UrlOpener | None = None,
    ) -> None:
        if not base_url.startswith("https://"):
            raise ValueError("Kamaitachi API base URL must use HTTPS.")
        if request_timeout <= 0 or import_timeout <= 0:
            raise ValueError("Network timeouts must be positive.")
        self._token = token.strip() if isinstance(token, str) else ""
        self._base_url = base_url.rstrip("/")
        self._user_agent = user_agent
        self._request_timeout = request_timeout
        self._import_timeout = import_timeout
        self._opener = urllib.request.urlopen if opener is None else opener

    def request_json(
        self,
        path: str,
        *,
        method: str = "GET",
        body: dict[str, Any] | None = None,
        authenticated: bool = False,
        user_intent: bool = False,
        timeout: float | None = None,
    ) -> tuple[int, dict[str, Any]]:
        """Request one JSON object without logging credentials or response bodies."""

        if not path.startswith("/"):
            raise ValueError("Kamaitachi API paths must begin with '/'.")
        method = method.upper()
        headers = {
            "Accept": "application/json",
            "User-Agent": self._user_agent,
        }
        data = None
        if body is not None:
            data = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if authenticated:
            if not self._token:
                raise MissingTokenError(
                    "KAMAITACHI_API_TOKEN is required to start an import; configure it in "
                    "the process environment."
                )
            headers["Authorization"] = f"Bearer {self._token}"
        if user_intent:
            if not authenticated:
                raise ValueError("user_intent requires an authenticated request.")
            headers["X-User-Intent"] = "true"

        # ``base_url`` is rejected unless it is HTTPS in __init__; paths are local.
        request = urllib.request.Request(  # noqa: S310
            f"{self._base_url}{path}",
            data=data,
            headers=headers,
            method=method,
        )
        request_timeout = self._request_timeout if timeout is None else timeout

        try:
            with self._opener(request, timeout=request_timeout) as response:
                status_value = getattr(response, "status", None)
                status = int(status_value if status_value is not None else response.getcode())
                raw = response.read()
        except urllib.error.HTTPError as exc:
            raise APIHTTPError(method, path, exc.code) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise APITransportError(
                f"Kamaitachi request failed for {method} {path}; check connectivity and retry "
                "only with another explicit command."
            ) from exc

        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise APIResponseError(
                f"Kamaitachi returned invalid JSON for {method} {path}."
            ) from exc
        if not isinstance(payload, dict):
            raise APIResponseError(
                f"Kamaitachi returned a non-object response for {method} {path}."
            )
        return status, payload

    def get_pbs(
        self,
        username: str,
        game: str,
        *,
        authenticated: bool = False,
    ) -> dict[str, Any]:
        path = _user_game_path(username, game, "pbs/all")
        _status, payload = self.request_json(path, authenticated=authenticated)
        return payload

    def get_recent_scores(
        self,
        username: str,
        game: str,
        *,
        authenticated: bool = False,
    ) -> dict[str, Any]:
        path = _user_game_path(username, game, "scores/recent")
        _status, payload = self.request_json(path, authenticated=authenticated)
        return payload

    def start_import(self, import_type: str) -> str:
        status, payload = self.request_json(
            "/import/from-api",
            method="POST",
            body={"importType": import_type},
            authenticated=True,
            user_intent=True,
        )
        body = require_success(payload, "Starting MYT sync")
        import_id = body.get("importID")
        if status != 202 or not isinstance(import_id, str) or not import_id:
            raise ImportError("Kamaitachi did not queue the MYT sync as expected.")
        return import_id

    def wait_for_import(self, import_id: str) -> None:
        encoded_id = urllib.parse.quote(import_id, safe="")
        path = f"/imports/{encoded_id}/stream"
        # ``base_url`` is rejected unless it is HTTPS; the opaque ID is URL-encoded.
        request = urllib.request.Request(  # noqa: S310
            f"{self._base_url}{path}",
            headers={
                "Accept": "text/event-stream",
                "Cache-Control": "no-cache",
                "User-Agent": self._user_agent,
            },
            method="GET",
        )
        try:
            with self._opener(request, timeout=self._import_timeout) as response:
                wait_for_completion(response)
        except urllib.error.HTTPError as exc:
            raise ImportStreamError(f"Import progress stream returned HTTP {exc.code}.") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise ImportStreamError(
                "Import progress stream failed; run another sync only after checking "
                "Kamaitachi import status."
            ) from exc


def require_success(payload: dict[str, Any], context: str) -> dict[str, Any]:
    if payload.get("success") is not True:
        raise APIResponseError(f"{context} was unsuccessful.")
    body = payload.get("body")
    if not isinstance(body, dict):
        raise APIResponseError(f"{context} did not return a body object.")
    return body


def validate_score_payload(payload: dict[str, Any], score_key: str) -> dict[str, Any]:
    if score_key not in {"pbs", "scores"}:
        raise ValueError("score_key must be 'pbs' or 'scores'.")
    body = require_success(payload, f"Fetching {score_key}")
    for key in (score_key, "charts", "songs"):
        if not isinstance(body.get(key), list):
            raise APIResponseError(f"Kamaitachi response is missing the {key!r} list.")
    return body


def _user_game_path(username: str, game: str, suffix: str) -> str:
    encoded_user = urllib.parse.quote(username, safe="")
    encoded_game = urllib.parse.quote(game, safe="")
    return f"/users/{encoded_user}/games/{encoded_game}/{suffix}"
