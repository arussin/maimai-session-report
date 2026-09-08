"""Offline archive integrity, retry, partial-write and reconstruction behavior."""

from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from maimai_report.fixtures import load_scenario
from maimai_report.history.bundle import (
    ArchiveError,
    CaptureBundle,
    canonical,
    prepare_capture,
    read_bundle,
)
from maimai_report.history.storage import archive, backup, migration_sql, rebuild
from maimai_report.render import build_html, enrich_report


class MemoryObjects:
    """Only a test double. Production has no local storage adapter."""

    def __init__(self):
        self.data = {}

    def get(self, key):
        return self.data.get(key)

    def create(self, key, raw):
        self.data.setdefault(key, raw)
        return self.data[key]

    def keys(self, prefix):
        return iter(sorted(key for key in self.data if key.startswith(prefix)))


class SQLite:
    def __init__(self):
        self.connection = sqlite3.connect(":memory:")
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(migration_sql())
        self.fail_before_finalize = False

    def query(self, sql, params=()):
        if self.fail_before_finalize and sql.startswith("UPDATE captures"):
            raise ArchiveError("Synthetic interrupted write")
        rows = self.connection.execute(sql, params).fetchall()
        self.connection.commit()
        return [dict(row) for row in rows]


def source_fixture(path, scenario="complete"):
    path.mkdir(parents=True, exist_ok=True)
    report, pbs = load_scenario(scenario)
    meta = {
        "syncCompleted": True,
        "sessionScoreCount": report["session"]["scoreCount"],
        "changedPBCount": report["session"]["changedPBCount"],
    }
    for name, data in (
        ("report-input.json", report),
        ("metadata.json", meta),
        ("after-pbs.json", pbs),
        ("before-pbs.json", pbs),
        ("before-recent-scores.json", {"body": {"scores": []}}),
        ("after-recent-scores.json", {"body": {"scores": report["session"]["scores"]}}),
    ):
        (path / name).write_bytes(canonical(data))
    (path / "maimai-report.html").write_text(
        build_html(enrich_report(report, pbs)), encoding="utf-8"
    )
    return report


def prepared(path, **changes):
    values = {
        "scope": "synthetic:maimaidx",
        "timezone": "America/New_York",
        "source_id": "synthetic-run-1",
        "renderer_commit": "a" * 40,
        "rendered_html": path / "maimai-report.html",
        "promote": True,
    }
    values.update(changes)
    return prepare_capture(path, **values)


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        source_fixture(self.path)
        self.objects, self.db = MemoryObjects(), SQLite()
        self.addCleanup(self.db.connection.close)

    def test_preserves_every_original_byte_and_round_trips(self):
        bundle = prepared(self.path)
        for name in ("report-input.json", "metadata.json", "after-pbs.json", "maimai-report.html"):
            self.assertEqual(
                bundle.objects[bundle.manifest["files"][name]["key"]],
                (self.path / name).read_bytes(),
            )
        destination = self.path / "portable"
        bundle.write(destination)
        self.assertEqual(read_bundle(destination), bundle)

    def test_repeated_capture_is_one_session_and_preserves_source_variants(self):
        first = prepared(self.path)
        archive(first, self.objects, self.db)
        report = json.loads((self.path / "report-input.json").read_text())
        report["generatedAt"] = "2026-05-29T18:30:00Z"
        (self.path / "report-input.json").write_bytes(canonical(report))
        second = prepared(self.path, source_id="synthetic-retry")
        self.assertEqual(first.capture_id, second.capture_id)
        archive(second, self.objects, self.db)
        self.assertEqual(self.db.query("SELECT COUNT(*) n FROM captures")[0]["n"], 1)
        self.assertEqual(len(list(self.objects.keys(f"captures/{first.capture_id}/sources/"))), 2)
        self.assertEqual(
            self.objects.get(f"captures/{first.capture_id}/manifest.json"), first.manifest_bytes
        )

    def test_incomplete_rating_snapshots_cannot_finalize_and_can_be_repaired(self):
        bundle = prepared(self.path)
        self.db.fail_before_finalize = True
        with self.assertRaises(ArchiveError):
            archive(bundle, self.objects, self.db)
        self.db.fail_before_finalize = False
        self.db.query("DELETE FROM rating_snapshots WHERE phase='before'")
        with self.assertRaisesRegex(sqlite3.IntegrityError, "Both rating snapshots"):
            self.db.query("UPDATE captures SET state='ready' WHERE id=?", (bundle.capture_id,))
        self.assertEqual(self.db.query("SELECT state FROM captures")[0]["state"], "staged")
        self.assertEqual(self.db.query("SELECT * FROM archive_state"), [])
        archive(bundle, self.objects, self.db)
        self.assertEqual(self.db.query("SELECT state FROM captures")[0]["state"], "ready")
        self.assertEqual(
            self.db.query("SELECT latest_id FROM archive_state")[0]["latest_id"],
            bundle.capture_id,
        )

    def test_same_upstream_import_with_changed_input_is_a_conflict(self):
        meta = json.loads((self.path / "metadata.json").read_text())
        meta["importID"] = "synthetic-import"
        (self.path / "metadata.json").write_bytes(canonical(meta))
        archive(prepared(self.path), self.objects, self.db)
        report = json.loads((self.path / "report-input.json").read_text())
        report["delta"]["synthetic-change"] = 1
        (self.path / "report-input.json").write_bytes(canonical(report))
        with self.assertRaises(ArchiveError):
            archive(prepared(self.path, rendered_html=None), self.objects, self.db)

    def test_scope_prevents_mixing_owners(self):
        archive(prepared(self.path), self.objects, self.db)
        with self.assertRaises(ArchiveError):
            archive(prepared(self.path, scope="other:maimaidx"), self.objects, self.db)

    def test_empty_refresh_never_replaces_latest(self):
        first = prepared(self.path)
        archive(first, self.objects, self.db)
        empty_path = self.path / "empty"
        source_fixture(empty_path, "empty")
        archive(prepared(empty_path), self.objects, self.db)
        self.assertEqual(
            self.db.query("SELECT latest_id FROM archive_state")[0]["latest_id"], first.capture_id
        )
        self.assertEqual(
            self.db.query("SELECT COUNT(*) n FROM captures WHERE meaningful=1")[0]["n"], 1
        )

    def test_partial_write_stays_invisible_then_retry_finishes(self):
        bundle = prepared(self.path)
        self.db.fail_before_finalize = True
        with self.assertRaises(ArchiveError):
            archive(bundle, self.objects, self.db)
        self.assertEqual(self.db.query("SELECT state FROM captures")[0]["state"], "staged")
        self.assertEqual(self.db.query("SELECT * FROM archive_state"), [])
        self.db.fail_before_finalize = False
        archive(bundle, self.objects, self.db)
        self.assertEqual(self.db.query("SELECT state FROM captures")[0]["state"], "ready")

    def test_missing_render_is_retained_and_repair_does_not_need_a_sync(self):
        raw = prepared(self.path, rendered_html=None)
        archive(raw, self.objects, self.db)
        self.assertEqual(self.db.query("SELECT * FROM captures"), [])
        repaired = prepared(self.path)
        archive(repaired, self.objects, self.db)
        self.assertEqual(self.db.query("SELECT COUNT(*) n FROM captures")[0]["n"], 1)
        self.assertEqual(
            self.objects.get(f"captures/{raw.capture_id}/manifest.json"), raw.manifest_bytes
        )

    def test_incomplete_original_envelope_is_labelled_not_invented(self):
        (self.path / "before-recent-scores.json").unlink()
        bundle = prepared(self.path)
        self.assertIn("before-recent-scores.json", bundle.manifest["missing"])
        self.assertIsNone(bundle.manifest["b50"])
        archive(bundle, self.objects, self.db)

    def test_invalid_count_and_changed_analysis_are_rejected(self):
        path = self.path / "report-input.json"
        report = json.loads(path.read_text())
        report["session"]["scoreCount"] += 1
        path.write_bytes(canonical(report))
        with self.assertRaises(ArchiveError):
            prepared(self.path)
        source_fixture(self.path)
        html = self.path / "maimai-report.html"
        html.write_text(html.read_text().replace('"naiveRating":14426', '"naiveRating":14427'))
        with self.assertRaises(ArchiveError):
            prepared(self.path)

    def test_content_addressed_collision_fails_without_visible_capture(self):
        bundle = prepared(self.path)
        self.objects.data["installation.json"] = canonical(
            {"schemaVersion": 1, "scope": "synthetic:maimaidx", "product": "maimai-report-history"}
        )
        self.objects.data[next(iter(bundle.objects))] = b"corrupt"
        with self.assertRaises(ArchiveError):
            archive(bundle, self.objects, self.db)
        self.assertEqual(self.db.query("SELECT * FROM captures"), [])

    def test_unsafe_manifest_paths_are_rejected_before_upload(self):
        bundle = prepared(self.path)
        manifest = deepcopy(bundle.manifest)
        manifest["files"]["metadata.json"]["key"] = "../../private"
        with self.assertRaises(ArchiveError):
            archive(CaptureBundle(manifest, bundle.objects), self.objects, self.db)
        self.assertEqual(self.objects.data, {})

    def test_two_identical_attempts_are_both_retained(self):
        report = json.loads((self.path / "report-input.json").read_text())
        report["session"]["scores"].append(deepcopy(report["session"]["scores"][0]))
        report["session"]["scoreCount"] += 1
        (self.path / "report-input.json").write_bytes(canonical(report))
        meta = json.loads((self.path / "metadata.json").read_text())
        meta["sessionScoreCount"] += 1
        (self.path / "metadata.json").write_bytes(canonical(meta))
        bundle = prepared(self.path, rendered_html=None)
        raw = json.loads(bundle.objects[bundle.manifest["files"]["report-input.json"]["key"]])
        self.assertEqual(raw["session"]["scores"][-1], raw["session"]["scores"][0])
        self.assertEqual(raw["session"]["scoreCount"], len(raw["session"]["scores"]))

    def test_backup_and_fresh_index_restore_all_history(self):
        bundle = prepared(self.path)
        archive(bundle, self.objects, self.db)
        independent = MemoryObjects()
        summary = backup(self.objects, independent, "synthetic:maimaidx")
        self.assertEqual(summary["objects"], len(self.objects.data))
        self.objects.data.clear()  # Recovery cannot use the original archive or runner inputs.
        restored = SQLite()
        self.addCleanup(restored.connection.close)
        self.assertEqual(
            rebuild(independent, restored, "synthetic:maimaidx"), {"captures": 1, "sessions": 1}
        )
        self.assertEqual(
            restored.query("SELECT latest_id FROM archive_state")[0]["latest_id"], bundle.capture_id
        )
        rebuild(independent, restored, "synthetic:maimaidx")
        self.assertEqual(restored.query("SELECT COUNT(*) n FROM captures")[0]["n"], 1)

    def test_corrupt_backup_cannot_become_visible(self):
        bundle = prepared(self.path)
        archive(bundle, self.objects, self.db)
        self.objects.data[bundle.manifest["report"]["key"]] = b"corrupt"
        restored = SQLite()
        self.addCleanup(restored.connection.close)
        with self.assertRaises(ArchiveError):
            rebuild(self.objects, restored, "synthetic:maimaidx")
        self.assertEqual(restored.query("SELECT * FROM archive_state"), [])

    def test_older_backfill_does_not_move_latest_backwards(self):
        bundle = prepared(self.path)
        path = self.path / "newer"
        report = source_fixture(path)
        for score in report["session"]["scores"]:
            score["timeAchieved"] += 1000
        (path / "report-input.json").write_bytes(canonical(report))
        pbs = json.loads((path / "after-pbs.json").read_text())
        (path / "maimai-report.html").write_text(build_html(enrich_report(report, pbs)))
        newer = prepared(path)
        archive(newer, self.objects, self.db)
        archive(bundle, self.objects, self.db)
        self.assertEqual(
            self.db.query("SELECT latest_id FROM archive_state")[0]["latest_id"], newer.capture_id
        )

    def test_manifest_cannot_change_original_rating_or_identity(self):
        bundle = prepared(self.path)
        for field in ("rating", "identity"):
            manifest = deepcopy(bundle.manifest)
            if field == "rating":
                manifest["after"]["reconstructedRating"] += 1
            else:
                manifest["captureID"] = "f" * 64
            with self.assertRaises(ArchiveError):
                archive(CaptureBundle(manifest, bundle.objects), self.objects, self.db)
        self.assertEqual(self.db.query("SELECT * FROM archive_state"), [])

    def test_finalized_metrics_cannot_be_silently_edited(self):
        bundle = prepared(self.path)
        archive(bundle, self.objects, self.db)
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.query(
                "UPDATE rating_snapshots SET reconstructed=0 WHERE capture_id=?",
                (bundle.capture_id,),
            )


if __name__ == "__main__":
    unittest.main()
