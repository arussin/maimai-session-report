from __future__ import annotations

import contextlib
import io
import tempfile
import threading
import unittest
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path

from maimai_report.render import BUY_ME_A_COFFEE_ORIGIN, render_demo
from maimai_report.server import make_handler, serve_file


class LocalServerTests(unittest.TestCase):
    def test_checkout_headers_follow_each_report_without_leaking_between_handlers(self):
        with tempfile.TemporaryDirectory() as directory:
            for enabled in (True, False, True):
                report = render_demo(Path(directory, "demo.html"), support=enabled)
                server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(report))
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                try:
                    connection = HTTPConnection("127.0.0.1", server.server_port, timeout=2)
                    connection.request("HEAD", "/")
                    response = connection.getresponse()
                    response.read()
                    csp = response.getheader("Content-Security-Policy")
                    payment = response.getheader("Permissions-Policy")
                    if enabled:
                        self.assertIn(f"frame-src {BUY_ME_A_COFFEE_ORIGIN}", csp)
                        self.assertIn(f'payment=(self "{BUY_ME_A_COFFEE_ORIGIN}")', payment)
                    else:
                        self.assertIn("frame-src 'none'", csp)
                        self.assertIn("payment=()", payment)
                    self.assertIn("connect-src 'none'", csp)
                    self.assertEqual(response.getheader("Referrer-Policy"), "no-referrer")
                    connection.close()
                finally:
                    server.shutdown()
                    server.server_close()
                    thread.join(timeout=2)

    def test_wildcard_bind_is_rejected_for_private_reports(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory, "report.html")
            report.write_text("<!doctype html><title>Offline</title>", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Wildcard server binds are disabled"):
                serve_file(report, host="0.0.0.0")  # noqa: S104 - rejection test
            for host in ("", "   "):
                with self.subTest(host=host):
                    with self.assertRaisesRegex(ValueError, "Wildcard server binds are disabled"):
                        serve_file(report, host=host)

    def test_handler_serves_only_the_report_with_private_headers(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory, "report.html")
            report.write_text("<!doctype html><title>Offline</title>", encoding="utf-8")
            server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(report))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                connection = HTTPConnection("127.0.0.1", server.server_port, timeout=2)
                connection.request("GET", "/")
                response = connection.getresponse()
                body = response.read()
                self.assertEqual(response.status, 200)
                self.assertIn(b"Offline", body)
                self.assertEqual(
                    response.getheader("Cache-Control"), "private, no-store, max-age=0"
                )
                self.assertEqual(response.getheader("X-Frame-Options"), "DENY")
                self.assertIn("connect-src 'none'", response.getheader("Content-Security-Policy"))
                connection.close()

                connection = HTTPConnection("127.0.0.1", server.server_port, timeout=2)
                connection.request("GET", "/private.json")
                response = connection.getresponse()
                response.read()
                self.assertEqual(response.status, 404)
                connection.close()

                connection = HTTPConnection("127.0.0.1", server.server_port, timeout=2)
                connection.request(
                    "GET",
                    "/?private-marker=must-not-be-logged",
                    headers={"Host": "attacker.example.invalid"},
                )
                response = connection.getresponse()
                response.read()
                self.assertEqual(response.status, 421)
                self.assertEqual(
                    response.getheader("Cache-Control"), "private, no-store, max-age=0"
                )
                connection.close()

                captured = io.StringIO()
                with contextlib.redirect_stderr(captured):
                    connection = HTTPConnection("127.0.0.1", server.server_port, timeout=2)
                    connection.request("GET", "/?private-marker=must-not-be-logged")
                    response = connection.getresponse()
                    response.read()
                    self.assertEqual(response.status, 200)
                    connection.close()
                self.assertNotIn("must-not-be-logged", captured.getvalue())
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
