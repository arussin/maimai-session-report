"""Loopback-only, allowlisted synthetic fixture server for CI."""

from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).parent / "generated"
ALLOWED = {
    f"/{name}.html": (f"{name}.html", "text/html;charset=utf-8")
    for name in ("complete", "empty", "incomplete", "presentation")
}
ALLOWED["/synthetic-b50.webp"] = ("synthetic-b50.webp", "image/webp")
ALLOWED["/b50.webp"] = ("b50.webp", "image/webp")


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        file = ALLOWED.get(urlsplit(self.path).path)
        if not file:
            self.send_error(404)
            return
        data = (ROOT / file[0]).read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", file[1])
        self.send_header("Cache-Control", "private, no-store")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Permissions-Policy", 'payment=(self "https://buymeacoffee.com")')
        if file[1] == "image/webp":
            self.send_header("Content-Disposition", 'attachment; filename="maimai-b50.webp"')
        self.end_headers()
        self.wfile.write(data)


if __name__ == "__main__":
    HTTPServer(("127.0.0.1", 4180), Handler).serve_forever()
