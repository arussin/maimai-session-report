"""Synthetic fixture requests must survive browser pre-opened idle connections."""

import importlib.util
import socket
import tempfile
import threading
import unittest
from http.client import HTTPConnection
from pathlib import Path


class FixtureServerTests(unittest.TestCase):
    def test_idle_connection_cannot_block_allowlisted_fixture_and_response_framing(self):
        spec = importlib.util.spec_from_file_location(
            "authored_fixture_server", Path(__file__).parent / "browser" / "server.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            module.ROOT = Path(directory)
            payload = b"<!doctype html><title>Authored fixture</title>"
            (module.ROOT / "empty.html").write_bytes(payload)
            server = module.make_server(port=0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            idle = socket.create_connection(server.server_address, timeout=2)
            request = HTTPConnection(*server.server_address, timeout=2)
            try:
                # Send no headers on the first connection, like a browser preconnect.
                # A serial HTTPServer stalls here until the idle connection closes.
                request.request("GET", "/empty.html")
                response = request.getresponse()
                self.assertEqual(response.status, 200)
                self.assertEqual(response.getheader("Content-Length"), str(len(payload)))
                self.assertEqual(response.read(), payload)
                request.request("GET", "/../not-allowlisted.html")
                self.assertEqual(request.getresponse().status, 404)
            finally:
                request.close()
                idle.close()
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
