"""Offline checks for the hosted verification's destructive cleanup boundary."""

import io
import json
import sqlite3
import tempfile
import unittest
from contextlib import redirect_stdout
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from maimai_report.history.bundle import ArchiveError
from maimai_report.history.storage import migration_sql
from maimai_report.installation.__main__ import main
from maimai_report.installation.verification import (
    TemporaryObjects,
    cleanup_database,
    exercise,
    fixture,
    verify_fresh,
)
from tests.installation_fixture import instance_file


class Objects:
    def __init__(self):
        self.data = {}
        self.bucket = "synthetic-test"
        self.client = self

    def get(self, key):
        return self.data.get(key)

    def create(self, key, raw):
        return self.data.setdefault(key, raw)

    def keys(self, prefix):
        return sorted(key for key in self.data if key.startswith(prefix))

    def delete_object(self, *, Bucket, Key):
        assert Bucket == self.bucket
        del self.data[Key]


class Database:
    def __init__(self):
        self.connection = sqlite3.connect(":memory:")
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys=ON")
        self.connection.executescript(migration_sql())

    def query(self, sql, params=()):
        try:
            rows = self.connection.execute(sql, params).fetchall()
            self.connection.commit()
            return [dict(row) for row in rows]
        except sqlite3.IntegrityError as exc:
            raise ArchiveError("Synthetic database constraint") from exc


class VerificationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.instance = replace(
            instance_file(self.root / "instance.toml"), origin="https://proof.example.test"
        )

    def providers(self):
        objects = [Objects(), Objects()]
        objects[0].bucket = self.instance.bucket
        objects[1].bucket = self.instance.backup_bucket
        databases = [Database(), Database()]
        for database in databases:
            self.addCleanup(database.connection.close)
        self.addCleanup(patch.stopall)
        patch("maimai_report.installation.verification.required", return_value="synthetic").start()
        patch("maimai_report.installation.verification.Cloudflare").start()
        patch("maimai_report.installation.verification.R2", side_effect=objects).start()
        patch("maimai_report.installation.verification.D1", side_effect=databases).start()
        patch("maimai_report.installation.verification.verify_private_bucket").start()
        return objects, databases

    def test_full_entry_retains_evidence_and_returns_empty_hosted_resources(self):
        objects, databases = self.providers()
        config = self.root / "instance.toml"
        config.write_text(
            config.read_text().replace("https://alpha.example.invalid", self.instance.origin)
        )
        with redirect_stdout(io.StringIO()) as stdout:
            code = main(
                [
                    "verify-fresh",
                    "--config",
                    str(config),
                    "--workdir",
                    str(self.root / "work"),
                    "--renderer-commit",
                    "a" * 40,
                    "--apply",
                ]
            )
        self.assertEqual(code, 0)
        self.assertNotIn(self.instance.account_id, stdout.getvalue())
        result = json.loads((self.root / "work/verify-fresh-result.json").read_text())
        self.assertTrue(result["syntheticCleanupVerified"])
        self.assertTrue(result["independentRecoveryEqual"])
        self.assertFalse(result["scoreImportStarted"])
        evidence = json.loads((self.root / "work/verify-fresh/evidence.json").read_text())
        journal = json.loads((self.root / "work/verify-fresh/ownership.json").read_text())
        self.assertEqual(evidence["status"], "passed")
        self.assertTrue(all(row["verified"] for row in evidence["cleanup"]))
        self.assertEqual(len(journal["captureIDs"]), 3)
        self.assertEqual(
            {row["bucket"] for row in journal["objects"]},
            {self.instance.bucket, self.instance.backup_bucket},
        )
        self.assertTrue(all(row["sha256"] for row in journal["objects"]))
        self.assertTrue(all(not obj.data for obj in objects))
        self.assertTrue(all(not db.query("SELECT * FROM captures") for db in databases))

    def test_explicit_apply_is_required_before_any_provider_access(self):
        with patch("maimai_report.installation.verification.Cloudflare") as network:
            with self.assertRaisesRegex(ArchiveError, "requires --apply"):
                verify_fresh(self.instance, self.root / "proof", "a" * 40)
            network.assert_not_called()
        self.assertFalse((self.root / "proof").exists())

    def test_nonempty_bucket_is_rejected_without_any_mutation(self):
        objects, databases = self.providers()
        objects[1].data["objects/existing-owner-data"] = b"synthetic stand-in for retained data"
        with self.assertRaisesRegex(ArchiveError, "inspect its private evidence"):
            verify_fresh(self.instance, self.root / "proof", "a" * 40, apply=True)
        self.assertEqual(objects[0].data, {})
        self.assertEqual(
            objects[1].data,
            {"objects/existing-owner-data": b"synthetic stand-in for retained data"},
        )
        self.assertTrue(all(not db.query("SELECT * FROM captures") for db in databases))
        evidence = json.loads((self.root / "proof/evidence.json").read_text())
        self.assertEqual(evidence["phase"], "preflight")
        self.assertEqual(evidence["status"], "failed")

    def test_nonempty_index_is_rejected_before_fixture_writes(self):
        objects, databases = self.providers()
        databases[0].query(
            "INSERT INTO archive_state(scope,latest_id) VALUES (?,NULL)",
            ("synthetic-existing:maimaidx",),
        )
        with self.assertRaises(ArchiveError):
            verify_fresh(self.instance, self.root / "proof", "a" * 40, apply=True)
        self.assertTrue(all(not obj.data for obj in objects))
        self.assertEqual(
            databases[0].query("SELECT scope FROM archive_state"),
            [{"scope": "synthetic-existing:maimaidx"}],
        )

    def test_cleanup_failure_does_not_skip_other_resources_or_expose_sdk_details(self):
        objects, databases = self.providers()
        with patch(
            "maimai_report.installation.verification.cleanup_database",
            side_effect=[RuntimeError("synthetic sensitive SDK details"), None],
        ):
            with self.assertRaisesRegex(ArchiveError, "inspect its private evidence") as failure:
                verify_fresh(self.instance, self.root / "proof", "a" * 40, apply=True)
        self.assertNotIn("sensitive SDK", str(failure.exception))
        evidence = json.loads((self.root / "proof/evidence.json").read_text())
        self.assertEqual(len(evidence["cleanup"]), 4)
        self.assertFalse(evidence["cleanup"][0]["verified"])
        self.assertTrue(all(row["verified"] for row in evidence["cleanup"][1:]))
        self.assertEqual(evidence["status"], "failed")
        self.assertTrue(all(not obj.data for obj in objects))
        self.assertTrue((self.root / "proof/ownership.json").exists())

    def test_cleanup_preserves_other_keys_and_refuses_changed_owned_bytes(self):
        objects = Objects()
        wrapped = TemporaryObjects(objects, "fixture")
        objects.data["objects/real"] = b"unrelated"
        wrapped.create("test", b"owned")
        objects.data[wrapped.prefix + "test"] = b"changed"
        with self.assertRaises(ArchiveError):
            wrapped.cleanup()
        self.assertEqual(len(objects.data), 2)
        objects.data[wrapped.prefix + "test"] = b"owned"
        wrapped.cleanup()
        self.assertEqual(objects.data, {"objects/real": b"unrelated"})

    def test_cleanup_refuses_unowned_keys_and_real_database_scope(self):
        objects = Objects()
        wrapped = TemporaryObjects(objects, "fixture")
        wrapped.create("test", b"owned")
        objects.data[wrapped.prefix + "unknown"] = b"unowned"
        with self.assertRaises(ArchiveError):
            wrapped.cleanup()
        self.assertEqual(len(objects.data), 2)
        database = Database()
        self.addCleanup(database.connection.close)
        with self.assertRaises(ArchiveError):
            cleanup_database(database, "owner:maimaidx", set())

    def test_full_exercise_and_scoped_cleanup(self):
        scope = "synthetic:hosted:offline"
        objects = [Objects(), Objects()]
        wrappers = [TemporaryObjects(obj, "fixture") for obj in objects]
        databases = [Database(), Database()]
        for database in databases:
            self.addCleanup(database.connection.close)
        with tempfile.TemporaryDirectory() as temp:
            bundles = [
                fixture(Path(temp) / name, scope, name, "a" * 40)
                for name in ("complete", "empty", "incomplete")
            ]
            result = exercise(*wrappers, *databases, bundles, scope)
            self.assertTrue(result["independentRecoveryEqual"])
            owned_ids = {bundle.capture_id for bundle in bundles}
            with self.assertRaises(ArchiveError):
                cleanup_database(databases[0], scope, set())
            for database in databases:
                cleanup_database(database, scope, owned_ids)
                self.assertEqual(database.query("SELECT * FROM captures"), [])
                self.assertEqual(database.query("SELECT * FROM rating_snapshots"), [])
            for wrapper in wrappers:
                wrapper.cleanup()
            self.assertTrue(all(not obj.data for obj in objects))


if __name__ == "__main__":
    unittest.main()
