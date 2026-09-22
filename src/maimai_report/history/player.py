"""Verified immutable player objects, with a separate compare-and-swap publication pointer."""

from __future__ import annotations

import re

from .._party import player_data as core
from ..player_capture import from_bundle
from .bundle import ArchiveError, CaptureBundle, canonical, load_json, sha256, validate_manifest
from .storage import immutable, install_marker


def latest(objects, database, scope):
    rows = database.query(
        "SELECT r.metadata FROM player_state s JOIN player_revisions r "
        "ON r.scope=s.scope AND r.revision=s.revision WHERE s.scope=?",
        (scope,),
    )
    if not rows:
        return None
    meta = load_json(rows[0]["metadata"].encode())
    raw = objects.get(meta["key"])
    if raw is None or sha256(raw) != meta["sha256"] or len(raw) != meta["bytes"]:
        raise ArchiveError("Published player data failed object verification")
    data = core.decode(raw)
    if data["revision"] != meta["revision"] or core.offer(data) != meta["offer"]:
        raise ArchiveError("Published player metadata does not match its dataset")
    return meta, data


def retained(objects, scope, player):
    """Initial backfill reads each retained capture once, including PB-only captures."""
    install_marker(objects, scope)
    for key in objects.keys("captures/"):
        if not re.fullmatch(r"captures/[a-f0-9]{64}/manifest\.json", key):
            continue
        raw = objects.get(key)
        if raw is None:
            raise ArchiveError("A retained capture disappeared during player-data backfill")
        manifest = load_json(raw)
        validate_manifest(manifest)
        if manifest["scope"] != scope:
            raise ArchiveError("Retained capture belongs to a different installation")
        content = {entry["key"]: objects.get(entry["key"]) for entry in manifest["files"].values()}
        if any(value is None for value in content.values()):
            raise ArchiveError("Player-data backfill found an incomplete retained capture")
        yield from_bundle(CaptureBundle(manifest, content), player=player)


def publish(objects, database, scope, additions, *, recovery_objects=None):
    additions = list(additions)
    if not additions:
        return {"state": "empty"}
    database.query("INSERT OR IGNORE INTO player_state(scope,revision) VALUES(?,NULL)", (scope,))
    for _ in range(8):
        previous = latest(objects, database, scope)
        data = core.merge(*([previous[1]] if previous else []), *additions)
        if previous and previous[0]["revision"] == data["revision"]:
            return {
                "state": "unchanged",
                "revision": data["revision"],
                "capturedAt": core.offer(data)["capturedAt"],
            }
        raw = core.encode(data)
        # Encode validates the entire object and its bounds; verify the actual bytes too.
        if core.decode(raw) != data:
            raise ArchiveError("Player-data encoding failed verification")
        digest = sha256(raw)
        meta = {
            "schemaVersion": 1,
            "scope": scope,
            "revision": data["revision"],
            "key": f"objects/sha256/{digest}",
            "sha256": digest,
            "bytes": len(raw),
            "offer": core.offer(data),
        }
        manifest = canonical(meta)
        if len(manifest) > 1024 * 1024:
            raise ArchiveError("Player revision metadata exceeds 1 MiB; no history was omitted")
        revision_key = f"players/{data['revision']}.json"
        for destination in (objects, recovery_objects):
            if destination is None:
                continue
            install_marker(destination, scope)
            immutable(destination, meta["key"], raw)
            immutable(destination, revision_key, manifest)
        database.query(
            "INSERT OR IGNORE INTO player_revisions(scope,revision,metadata) VALUES(?,?,?)",
            (scope, data["revision"], manifest.decode()),
        )
        # A concurrent publisher cannot drop either capture: losers reload and merge.
        rows = database.query(
            "UPDATE player_state SET revision=? WHERE scope=? AND revision IS ? RETURNING revision",
            (data["revision"], scope, previous[0]["revision"] if previous else None),
        )
        if rows:
            return {
                "state": "ready",
                "revision": data["revision"],
                "capturedAt": meta["offer"]["capturedAt"],
            }
    raise ArchiveError("Concurrent player-data updates did not settle; retry this retained capture")


def materialize(
    objects, database, scope, player, *, bundle=None, backfill=False, recovery_objects=None
):
    previous = latest(objects, database, scope)
    additions = (
        retained(objects, scope, player)
        if backfill or previous is None
        else [from_bundle(bundle, player=player)]
    )
    return publish(objects, database, scope, additions, recovery_objects=recovery_objects)
