"""Hosted archive contract: content-addressed R2 first, then a rebuildable D1 index."""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path
from typing import Protocol

from .bundle import (
    ArchiveError,
    CaptureBundle,
    canonical,
    load_json,
    sha256,
    validate_capture_contents,
    validate_manifest,
)


class Objects(Protocol):
    def get(self, key: str) -> bytes | None: ...

    def create(self, key: str, raw: bytes) -> bytes:
        """Create only if absent, returning the stored bytes even if another writer won."""
        ...

    def keys(self, prefix: str) -> Iterable[str]: ...


class Database(Protocol):
    def query(self, sql: str, params: tuple = ()) -> list[dict]: ...


def migration_sql() -> str:
    return Path(__file__).with_name("0001_history.sql").read_text(encoding="utf-8")


def immutable(objects: Objects, key: str, raw: bytes) -> None:
    if objects.create(key, raw) != raw:
        raise ArchiveError("Immutable archive object conflicts with existing content")


def verify_objects(objects: Objects, manifest: dict) -> None:
    validate_manifest(manifest)
    content = {}
    for entry in manifest["files"].values():
        raw = objects.get(entry["key"])
        if raw is None or len(raw) != entry["bytes"] or sha256(raw) != entry["sha256"]:
            raise ArchiveError("Hosted capture is incomplete or its checksum differs")
        content[entry["key"]] = raw
    validate_capture_contents(CaptureBundle(manifest, content))


def install_marker(objects: Objects, scope: str) -> None:
    raw = canonical({"schemaVersion": 1, "scope": scope, "product": "maimai-report-history"})
    current = objects.get("installation.json")
    if current is None and next(iter(objects.keys("")), None) is not None:
        raise ArchiveError("Refusing to adopt a non-empty bucket without an installation marker")
    immutable(objects, "installation.json", raw)


def index_capture(database: Database, manifest: dict, key: str, raw: bytes) -> None:
    """Every retry is safe. The SQL trigger commits readiness and latest together."""
    validate_manifest(manifest)
    capture_id = manifest["captureID"]
    existing = database.query("SELECT manifest_hash,state FROM captures WHERE id=?", (capture_id,))
    digest = sha256(raw)
    if existing:
        if existing[0]["manifest_hash"] != digest:
            raise ArchiveError("Indexed capture conflicts with its immutable publication")
        if existing[0]["state"] == "ready":
            return
    report, image = manifest["report"] or {}, manifest["b50"] or {}
    database.query(
        """INSERT OR IGNORE INTO captures
        (id,scope,input_hash,manifest_key,manifest_hash,captured_ms,sort_ms,start_ms,end_ms,
         timezone,versions,meaningful,promote,score_count,pb_count,source_id,renderer_commit,
         missing,report_key,report_hash,b50_key,b50_hash,b50_provenance)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            capture_id,
            manifest["scope"],
            manifest["inputHash"],
            key,
            digest,
            manifest["capturedAtMs"],
            manifest["sortMs"],
            manifest["startMs"],
            manifest["endMs"],
            manifest["timezone"],
            canonical(manifest["versions"]).decode(),
            int(manifest["meaningful"]),
            int(manifest["promote"]),
            manifest["scoreCount"],
            manifest["changedPBCount"],
            manifest["source"]["id"],
            manifest["rendererCommit"],
            canonical(manifest["missing"]).decode(),
            report.get("key"),
            report.get("sha256"),
            image.get("key"),
            image.get("sha256"),
            manifest["b50Provenance"],
        ),
    )
    for phase in ("before", "after"):
        snap = manifest[phase]
        database.query(
            """INSERT OR IGNORE INTO rating_snapshots
            (capture_id,phase,reconstructed,naive,old_rating,new_rating,old_floor,new_floor,
             old_count,new_count,pb_count,new_pool_played) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                capture_id,
                phase,
                snap.get("reconstructedRating"),
                snap.get("naiveRating"),
                snap.get("old35Rating"),
                snap.get("new15Rating"),
                snap.get("old35Floor"),
                snap.get("new15Floor"),
                snap.get("oldSlotsFilled"),
                snap.get("newSlotsFilled"),
                snap.get("pbCount"),
                snap.get("newPoolPlayed"),
            ),
        )
    database.query("UPDATE captures SET state='ready' WHERE id=? AND state='staged'", (capture_id,))


def archive(bundle: CaptureBundle, objects: Objects, database: Database) -> dict:
    manifest = bundle.manifest
    validate_manifest(manifest)
    install_marker(objects, manifest["scope"])
    for entry in manifest["files"].values():
        raw = bundle.objects.get(entry["key"])
        if raw is None or sha256(raw) != entry["sha256"] or len(raw) != entry["bytes"]:
            raise ArchiveError("Capture bundle failed object verification")
    validate_capture_contents(bundle)
    base = f"captures/{bundle.capture_id}"
    # First source and every later retry remain independently recoverable.
    first = objects.get(f"{base}/manifest.json")
    if first is not None and load_json(first)["inputHash"] != manifest["inputHash"]:
        raise ArchiveError("Upstream import identity was reused with different capture inputs")
    for key, raw in bundle.objects.items():
        immutable(objects, key, raw)
    first = objects.create(f"{base}/manifest.json", bundle.manifest_bytes)
    if load_json(first)["inputHash"] != manifest["inputHash"]:
        raise ArchiveError("Concurrent capture identity conflict")
    immutable(
        objects, f"{base}/sources/{sha256(bundle.manifest_bytes)}.json", bundle.manifest_bytes
    )
    # An unsuccessful normal publication is retained for repair, never made latest.
    if manifest["meaningful"] and not manifest["promote"]:
        return {"captureID": bundle.capture_id, "state": "retained", "meaningful": True}
    key = f"{base}/published.json"
    published = objects.create(key, bundle.manifest_bytes)
    chosen = load_json(published)
    if chosen["inputHash"] != manifest["inputHash"]:
        raise ArchiveError("Published capture identity conflict")
    verify_objects(objects, chosen)
    index_capture(database, chosen, key, published)
    return {"captureID": bundle.capture_id, "state": "ready", "meaningful": chosen["meaningful"]}


def rebuild(objects: Objects, database: Database, scope: str) -> dict:
    """Rebuild a fresh hosted index without score APIs or local archive state."""
    install_marker(objects, scope)
    count = meaningful = 0
    for key in objects.keys("captures/"):
        if not re.fullmatch(r"captures/[0-9a-f]{64}/published\.json", key):
            continue
        raw = objects.get(key)
        if raw is None:
            raise ArchiveError("Published manifest disappeared during reconstruction")
        manifest = load_json(raw)
        if manifest["scope"] != scope or key != f"captures/{manifest['captureID']}/published.json":
            raise ArchiveError("Manifest scope or key differs from its installation")
        verify_objects(objects, manifest)
        index_capture(database, manifest, key, raw)
        count += 1
        meaningful += int(manifest["meaningful"])
    return {"captures": count, "sessions": meaningful}


def backup(source: Objects, destination: Objects, scope: str) -> dict:
    """Copy immutable objects into an independent hosted bucket; never delete anything."""
    install_marker(source, scope)
    install_marker(destination, scope)
    count = size = 0
    for key in source.keys(""):
        if not (
            key == "installation.json"
            or re.fullmatch(
                r"objects/sha256/[0-9a-f]{64}|captures/[0-9a-f]{64}/"
                r"(?:manifest\.json|published\.json|sources/[0-9a-f]{64}\.json)",
                key,
            )
        ):
            raise ArchiveError("Unexpected object in the archive; backup needs explicit review")
        raw = source.get(key)
        if raw is None:
            raise ArchiveError("Archive changed during backup")
        immutable(destination, key, raw)
        count += 1
        size += len(raw)
    return {"objects": count, "bytes": size}


def backup_capture(source: Objects, destination: Objects, scope: str, capture_id: str) -> dict:
    """Back up only this capture on the normal write path, with bounded per-session work."""
    if not re.fullmatch(r"[0-9a-f]{64}", capture_id):
        raise ArchiveError("Invalid backup capture identity")
    install_marker(source, scope)
    install_marker(destination, scope)
    count = size = 0
    for key in source.keys(f"captures/{capture_id}/"):
        raw = source.get(key)
        if raw is None:
            raise ArchiveError("Capture disappeared during backup")
        manifest = load_json(raw)
        if manifest.get("captureID") != capture_id or manifest.get("scope") != scope:
            raise ArchiveError("Capture backup scope mismatch")
        verify_objects(source, manifest)
        for entry in manifest["files"].values():
            value = source.get(entry["key"])
            if value is None:
                raise ArchiveError("Capture object disappeared during backup")
            immutable(destination, entry["key"], value)
            count += 1
            size += len(value)
        immutable(destination, key, raw)
    return {"verifiedObjectReferences": count, "verifiedBytes": size}
