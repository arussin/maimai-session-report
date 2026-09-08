from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from .render import BUY_ME_A_COFFEE_ORIGIN, support_enabled_in_html, validate_generated_html

SECURITY_HEADERS = {
    "Cache-Control": "private, no-store, max-age=0",
    "Content-Security-Policy": (
        "default-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'; "
        "object-src 'none'; connect-src 'none'; font-src 'none'; media-src 'none'; "
        "manifest-src 'none'; worker-src 'none'; img-src data:; style-src 'unsafe-inline'; "
        "script-src 'unsafe-inline'"
    ),
    "Permissions-Policy": (
        "accelerometer=(), camera=(), geolocation=(), gyroscope=(), microphone=(), "
        "payment=(), usb=()"
    ),
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-Robots-Tag": "noindex, nofollow, noarchive",
}
LOCAL_HOSTNAMES = frozenset({"127.0.0.1", "localhost", "::1"})


def make_handler(
    report_file: Path,
    *,
    allowed_hostnames: frozenset[str] = LOCAL_HOSTNAMES,
) -> type[BaseHTTPRequestHandler]:
    payload = report_file.read_bytes()
    headers = dict(SECURITY_HEADERS)
    html = payload.decode("utf-8", errors="replace")
    enabled = support_enabled_in_html(html)
    if enabled:
        # Only generated, validated documents receive the checkout exception.
        validate_generated_html(html)
        headers["Permissions-Policy"] = headers["Permissions-Policy"].replace(
            "payment=()", f'payment=(self "{BUY_ME_A_COFFEE_ORIGIN}")'
        )
    frame_origin = BUY_ME_A_COFFEE_ORIGIN if enabled else "'none'"
    headers["Content-Security-Policy"] += f"; frame-src {frame_origin}"
    allowed = frozenset(name.casefold().strip("[]") for name in allowed_hostnames)

    class ReportHandler(BaseHTTPRequestHandler):
        server_version = "maimai-report-local"
        sys_version = ""

        def _send_headers(self, status: int, *, length: int = 0) -> None:
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(length))
            for name, value in headers.items():
                self.send_header(name, value)
            self.end_headers()

        def _host_is_allowed(self) -> bool:
            value = self.headers.get("Host", "")
            if not value or any(character.isspace() for character in value):
                return False
            try:
                parsed = urlsplit(f"//{value}")
                hostname = parsed.hostname
                port = parsed.port
            except ValueError:
                return False
            return (
                hostname is not None
                and parsed.username is None
                and parsed.password is None
                and not parsed.path
                and not parsed.query
                and not parsed.fragment
                and (port is None or 0 <= port <= 65535)
                and hostname.casefold().strip("[]") in allowed
            )

        def _reject_disallowed_host(self) -> bool:
            if self._host_is_allowed():
                return False
            self._send_headers(421)
            return True

        def do_GET(self) -> None:  # noqa: N802
            if self._reject_disallowed_host():
                return
            if urlsplit(self.path).path not in {"/", "/index.html"}:
                self._send_headers(404)
                return
            self._send_headers(200, length=len(payload))
            self.wfile.write(payload)

        def do_HEAD(self) -> None:  # noqa: N802
            if self._reject_disallowed_host():
                return
            if urlsplit(self.path).path not in {"/", "/index.html"}:
                self._send_headers(404)
                return
            self._send_headers(200, length=len(payload))

        def do_POST(self) -> None:  # noqa: N802
            if self._reject_disallowed_host():
                return
            self._send_headers(405)

        def log_message(self, format: str, *args: object) -> None:
            # Request targets may contain sensitive query strings. Keep this private
            # single-file server silent instead of risking accidental disclosure.
            return

    return ReportHandler


def serve_file(report_file: Path, *, host: str = "127.0.0.1", port: int = 8000) -> None:
    path = report_file.expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Report file does not exist: {path}")
    if not 1 <= port <= 65535:
        raise ValueError("Port must be between 1 and 65535")
    normalized_host = host.strip().casefold().strip("[]")
    if not normalized_host or normalized_host in {
        "0.0.0.0",  # noqa: S104 - rejected sentinel, never passed to the server
        "::",
    }:
        raise ValueError(
            "Wildcard server binds are disabled for private reports; keep 127.0.0.1 "
            "or choose one exact interface address explicitly."
        )
    allowed_hostnames = (
        LOCAL_HOSTNAMES if normalized_host in LOCAL_HOSTNAMES else frozenset({normalized_host})
    )
    server = ThreadingHTTPServer(
        (host, port), make_handler(path, allowed_hostnames=allowed_hostnames)
    )
    shown_host = "localhost" if host == "127.0.0.1" else host
    print(f"Serving {path} at http://{shown_host}:{server.server_port}/")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
