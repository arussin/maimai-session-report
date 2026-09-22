"""Both DNS and direct numeric-address attempts must be rejected before a socket opens."""

import socket
import unittest
from types import SimpleNamespace

from scripts.run_offline_tests import audit_network, loopback


class OfflineRunnerTests(unittest.TestCase):
    def test_only_loopback_names_and_addresses_are_eligible(self):
        for host in (
            "localhost",
            "LOCALHOST.",
            b"localhost",
            "127.0.0.1",
            "::1",
            "::ffff:127.0.0.1",
        ):
            self.assertTrue(loopback(host))
        for host in ("maimai.party", "127.0.0.1.example.invalid", "192.0.2.1", "0.0.0.0", "::"):  # noqa: S104 -- rejected wildcard fixture
            self.assertFalse(loopback(host))

    def test_dns_and_connection_audit_events_reject_non_loopback(self):
        for event in ("socket.getaddrinfo", "socket.gethostbyname", "socket.gethostbyaddr"):
            with self.assertRaises(PermissionError):
                audit_network(event, ("example.invalid",))
            audit_network(event, ("127.0.0.1",))
        for family in (socket.AF_INET, socket.AF_INET6):
            with self.assertRaises(PermissionError):
                audit_network(
                    "socket.connect", (SimpleNamespace(family=family), ("192.0.2.1", 443))
                )
        audit_network(
            "socket.connect", (SimpleNamespace(family=socket.AF_INET), ("127.0.0.1", 4180))
        )
