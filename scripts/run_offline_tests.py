"""Run the synthetic Python suite with audited non-loopback connections denied."""

from __future__ import annotations

import ipaddress
import socket
import sys
import traceback
import unittest
from pathlib import Path


def loopback(host):
    if isinstance(host, bytes):
        host = host.decode("ascii", errors="replace")
    if str(host).lower().rstrip(".") == "localhost":
        return True
    try:
        address = ipaddress.ip_address(str(host).split("%", 1)[0])
        return address.is_loopback or bool(
            getattr(address, "ipv4_mapped", None) and address.ipv4_mapped.is_loopback
        )
    except ValueError:
        return False


def audit_network(event, arguments):
    if event in {"socket.getaddrinfo", "socket.gethostbyname", "socket.gethostbyaddr"}:
        host = arguments[0]
        # None asks getaddrinfo for a local wildcard binding, not a remote lookup.
        if host is None:
            return
    elif event == "socket.connect":
        connection, address = arguments
        if connection.family not in {socket.AF_INET, socket.AF_INET6}:
            return
        host = address[0]
    else:
        return
    if not loopback(host):
        raise PermissionError("Offline tests deny non-loopback network access")


def main():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    blocked = []

    def guard(event, arguments):
        try:
            audit_network(event, arguments)
        except PermissionError:
            blocked.append(
                {
                    "event": event,
                    "tests": [
                        frame.name
                        for frame in traceback.extract_stack()
                        if frame.name.startswith("test_")
                    ],
                }
            )
            raise

    sys.addaudithook(guard)
    suite = unittest.defaultTestLoader.discover(str(root / "tests"), top_level_dir=str(root))
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    print(f"Offline network guard: {len(blocked)} non-loopback attempts denied")
    if blocked:
        print("Tests that attempted external access:", blocked)
    return 0 if result.wasSuccessful() and not blocked else 1


if __name__ == "__main__":
    raise SystemExit(main())
