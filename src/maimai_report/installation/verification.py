"""Exercise the real hosted adapters with temporary, explicitly synthetic captures.

This fresh-install check requires empty archives and indexes. Cleanup is restricted
to this run's random object prefix and synthetic database scope. Real archive
objects, schema, resource settings, and Worker routes are never deleted or changed.
"""

from __future__ import annotations

import os
import re
import tempfile
import uuid
from pathlib import Path

from ..fixtures import load_scenario
from ..history.bundle import ArchiveError, canonical, prepare_capture, sha256
from ..history.cloudflare import D1, R2, Cloudflare, required
from ..history.setup import verify_private_bucket
from ..history.storage import archive, backup, immutable, rebuild
from ..render import build_html, enrich_report
from .config import Instance


def check(condition, message):
    if not condition:
        raise ArchiveError(message)


class TemporaryObjects:
    """Keep fixture keys outside the archive namespace and record every owned byte."""

    def __init__(self, objects, run_id, on_change=lambda: None):
        self.on_change = on_change
        self.objects = objects
        self.prefix = f"synthetic-verification/{run_id}/"
        self.created = {}

    def get(self, key):
        return self.objects.get(self.prefix + key)

    def create(self, key, raw):
        full = self.prefix + key
        existing = self.objects.get(full)
        if existing is None:
            # Record before writing, so a lost upload response can still be cleaned up.
            self.created[full] = sha256(raw)
            self.on_change()
        return self.objects.create(full, raw)

    def keys(self, prefix):
        for key in self.objects.keys(self.prefix + prefix):
            yield key[len(self.prefix) :]

    def cleanup(self):
        keys = set(self.objects.keys(self.prefix))
        check(keys <= self.created.keys(), "Unknown object in synthetic test prefix")
        # Verify the complete deletion list before deleting any fixture object.
        for key in keys:
            raw = self.objects.get(key)
            check(
                raw is not None and sha256(raw) == self.created[key],
                "Synthetic cleanup refused changed content",
            )
        for key in sorted(keys):
            self.objects.client.delete_object(Bucket=self.objects.bucket, Key=key)
        check(not list(self.objects.keys(self.prefix)), "Synthetic object cleanup incomplete")


class InterruptFinalize:
    def __init__(self, database):
        self.database = database

    def query(self, sql, params=()):
        if sql.startswith("UPDATE captures SET state="):
            raise ArchiveError("Intentional synthetic interruption before finalization")
        return self.database.query(sql, params)


def expect_rejection(operation, message):
    try:
        operation()
    except ArchiveError:
        return
    raise ArchiveError(message)


def fixture(directory, scope, scenario, renderer_commit):
    directory.mkdir()
    report, pbs = load_scenario(scenario)
    report["player"]["displayName"] = "SYNTHETIC HOSTED VERIFICATION"
    meta = {
        "syncCompleted": True,
        "importID": f"{scope}:{scenario}",
        "sessionScoreCount": report["session"]["scoreCount"],
        "changedPBCount": report["session"]["changedPBCount"],
    }
    files = {
        "report-input.json": report,
        "metadata.json": meta,
        "after-pbs.json": pbs,
        "before-pbs.json": pbs,
        "before-recent-scores.json": {"body": {"scores": []}},
        "after-recent-scores.json": {"body": {"scores": report["session"]["scores"]}},
    }
    if scenario == "incomplete":
        del files["before-recent-scores.json"]
    for name, value in files.items():
        (directory / name).write_bytes(canonical(value))
    html = build_html(enrich_report(report, pbs)).replace(
        '<body class="clean-checkpoint">',
        '<body class="clean-checkpoint"><aside>SYNTHETIC HOSTED TEST DATA</aside>',
    )
    path = directory / "maimai-report.html"
    path.write_text(html, encoding="utf-8")
    return prepare_capture(
        directory,
        scope=scope,
        timezone="UTC",
        source_id=f"synthetic-{scenario}",
        renderer_commit=renderer_commit,
        rendered_html=path,
        promote=True,
    )


def database_snapshot(database, scope):
    return {
        "captures": database.query("SELECT * FROM captures WHERE scope=? ORDER BY id", (scope,)),
        "ratings": database.query(
            "SELECT r.* FROM rating_snapshots r JOIN captures c ON c.id=r.capture_id "
            "WHERE c.scope=? ORDER BY r.capture_id,r.phase",
            (scope,),
        ),
        "latest": database.query("SELECT * FROM archive_state WHERE scope=?", (scope,)),
    }


def cleanup_database(database, scope, owned_ids):
    check(scope.startswith("synthetic:hosted:"), "Refusing non-synthetic database cleanup")
    rows = database.query("SELECT id FROM captures WHERE scope=?", (scope,))
    check({row["id"] for row in rows} <= owned_ids, "Unknown synthetic database capture")
    database.query("DELETE FROM archive_state WHERE scope=?", (scope,))
    database.query(
        "DELETE FROM rating_snapshots WHERE capture_id IN (SELECT id FROM captures WHERE scope=?)",
        (scope,),
    )
    database.query("DELETE FROM captures WHERE scope=?", (scope,))
    check(
        database_snapshot(database, scope) == {"captures": [], "ratings": [], "latest": []},
        "Synthetic database cleanup incomplete",
    )


def exercise(primary, secondary, database, recovery, bundles, scope):
    complete, empty, incomplete = bundles
    expect_rejection(
        lambda: archive(complete, primary, InterruptFinalize(database)),
        "Interrupted synthetic capture unexpectedly finalized",
    )
    check(
        database.query("SELECT state FROM captures WHERE id=?", (complete.capture_id,))
        == [{"state": "staged"}],
        "Interrupted capture did not remain staged",
    )
    database.query(
        "DELETE FROM rating_snapshots WHERE capture_id=? AND phase='before'", (complete.capture_id,)
    )
    expect_rejection(
        lambda: database.query(
            "UPDATE captures SET state='ready' WHERE id=?", (complete.capture_id,)
        ),
        "Hosted D1 accepted an incomplete rating snapshot",
    )
    check(not database_snapshot(database, scope)["latest"], "Incomplete capture became latest")
    archive(complete, primary, database)
    archive(complete, primary, database)
    check(len(database_snapshot(database, scope)["captures"]) == 1, "Retry duplicated a capture")
    archive(empty, primary, database)
    check(
        database_snapshot(database, scope)["latest"][0]["latest_id"] == complete.capture_id,
        "Empty capture displaced the latest meaningful session",
    )
    archive(incomplete, primary, database)
    check(
        "before-recent-scores.json" in incomplete.manifest["missing"],
        "Incomplete original inputs lost their annotation",
    )
    key, original = next(iter(complete.objects.items()))
    expect_rejection(
        lambda: immutable(primary, key, b"synthetic conflict"),
        "Immutable object conflict was accepted",
    )
    check(primary.get(key) == original, "Immutable bytes changed")
    copied = backup(primary, secondary, scope)
    restored = rebuild(secondary, recovery, scope)
    check(restored == {"captures": 3, "sessions": 2}, "Hosted restore counts differ")
    rebuild(secondary, recovery, scope)
    check(
        database_snapshot(database, scope) == database_snapshot(recovery, scope),
        "Independent hosted recovery differs from the primary index",
    )
    return {
        "synthetic": True,
        "hostedAdapters": True,
        "captures": 3,
        "sessions": 2,
        "retryAndInterruptedRepair": True,
        "incompleteFinalizationRejected": True,
        "emptyDidNotReplaceLatest": True,
        "immutableConflictRejected": True,
        "independentRecoveryEqual": True,
        "backup": copied,
    }


def verify_fresh(instance: Instance, output: Path, renderer_commit: str, *, apply: bool = False):
    """Run only on empty configured resources; retain scoped evidence even on failure."""
    check(apply, "verify-fresh requires --apply for temporary synthetic writes and cleanup")
    instance.validate("verify-fresh")
    check(instance.history_enabled, "Hosted history is disabled in instance.toml")
    check(re.fullmatch(r"[0-9a-f]{40}", renderer_commit), "Select the exact verifier commit")
    check(not output.exists() or not any(output.iterdir()), "Use an empty verification directory")
    output.mkdir(parents=True, exist_ok=True)
    evidence = {
        "schemaVersion": 1,
        "status": "running",
        "phase": "preflight",
        "identity": instance.identity(),
        "rendererCommit": renderer_commit,
        "synthetic": True,
        "scoreImportStarted": False,
        "workerDeployed": False,
    }

    def save():
        (output / "evidence.json").write_bytes(canonical(evidence) + b"\n")

    save()
    try:
        result = _verify_resources(instance, output, renderer_commit, evidence, save)
    except Exception as exc:
        evidence["status"] = "failed"
        evidence["errorType"] = type(exc).__name__
        save()
        # Do not expose an SDK exception's request details, SQL or credential-bearing text.
        raise ArchiveError(
            "Hosted verification stopped; inspect its private evidence artifact"
        ) from None
    evidence.update(status="passed", phase="complete", checks=result)
    save()
    return {**result, "scoreImportStarted": False, "workerDeployed": False}


def _verify_resources(instance, output, renderer_commit, evidence, save):
    api = Cloudflare(instance.account_id, required(os.environ, "CLOUDFLARE_HISTORY_API_TOKEN"))
    databases = [D1(api, key) for key in (instance.database_id, instance.recovery_database_id)]
    objects = []
    for bucket in (instance.bucket, instance.backup_bucket):
        verify_private_bucket(api, bucket)
        objects.append(R2(instance.account_id, bucket))
        check(
            next(iter(objects[-1].keys("")), None) is None,
            "Fresh-install verification requires empty buckets; existing history was untouched",
        )
    for database in databases:
        for table in ("captures", "rating_snapshots", "archive_state"):
            check(
                database.query("SELECT COUNT(*) n FROM " + table)[0]["n"] == 0,  # noqa: S608 -- literal table allowlist
                "Fresh-install verification requires empty indexes; existing history was untouched",
            )
    run_id = uuid.uuid4().hex
    scope = f"synthetic:hosted:{run_id}"
    evidence.update(phase="exercise", scope=scope, runID=run_id)
    wrappers = []

    def journal():
        ownership = {
            "schemaVersion": 1,
            "identity": instance.identity(),
            "scope": scope,
            "runID": run_id,
            "captureIDs": sorted(owned_ids),
            "objects": [
                {"bucket": wrapper.objects.bucket, "sha256": wrapper.created}
                for wrapper in wrappers
            ],
        }
        (output / "ownership.json").write_bytes(canonical(ownership) + b"\n")

    wrappers.extend(TemporaryObjects(obj, run_id, journal) for obj in objects)
    with tempfile.TemporaryDirectory(prefix="synthetic-hosted-") as temp:
        bundles = [
            fixture(Path(temp) / name, scope, name, renderer_commit)
            for name in ("complete", "empty", "incomplete")
        ]
        owned_ids = {bundle.capture_id for bundle in bundles}
        journal()
        save()
        try:
            result = exercise(*wrappers, *databases, bundles, scope)
        finally:
            evidence["phase"] = "cleanup"
            evidence["cleanup"] = []
            cleanup_failed = False
            # A failure in one resource must not skip cleanup of the other owned fixtures.
            for kind, targets in (("database", databases), ("bucket", wrappers)):
                for index, target in enumerate(targets):
                    record = {"kind": kind, "copy": index, "verified": False}
                    try:
                        if kind == "database":
                            cleanup_database(target, scope, owned_ids)
                        else:
                            target.cleanup()
                        record["verified"] = True
                    except Exception as exc:
                        cleanup_failed = True
                        record["errorType"] = type(exc).__name__
                    evidence["cleanup"].append(record)
                    save()
            check(not cleanup_failed, "Synthetic cleanup incomplete; retain the ownership journal")
    evidence["phase"] = "final-read"
    save()
    check(
        all(next(iter(obj.keys("")), None) is None for obj in objects),
        "Unexpected objects appeared during fresh-install verification",
    )
    for database in databases:
        for table in ("captures", "rating_snapshots", "archive_state"):
            check(
                database.query("SELECT COUNT(*) n FROM " + table)[0]["n"] == 0,  # noqa: S608 -- literal table allowlist
                "Unexpected index records appeared during fresh-install verification",
            )
    result["syntheticCleanupVerified"] = True
    return result
