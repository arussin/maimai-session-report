"""Small installation operations around the existing analytical and archive engines."""

from __future__ import annotations

import json
import os
import re
from dataclasses import replace
from pathlib import Path

from ..artwork import prepare_jackets
from ..cli import _player, _support
from ..history.bundle import prepare_capture, report_data
from ..history.cloudflare import D1, R2, Cloudflare, required
from ..history.setup import provision, resource_plan, verify_private_bucket
from ..history.storage import archive, backup, backup_capture, rebuild
from ..io import write_json
from ..render import enrich_report, read_json, render_report
from ..sync import synchronize, write_sync_result
from .config import Instance
from .deployment import WorkerAPI, check, verify_access, verify_bindings, verify_domains


def meaningful(source: Path) -> bool:
    metadata = read_json(source / "metadata.json")
    check(metadata.get("syncCompleted") is True, "Capture does not confirm a completed sync")
    counts = [metadata.get("sessionScoreCount", 0), metadata.get("changedPBCount", 0)]
    check(all(type(value) is int and value >= 0 for value in counts), "Invalid capture counts")
    return any(value > 0 for value in counts)


def b50_ready(instance: Instance, source: Path) -> bool:
    after = read_json(source / "report-input.json").get("after", {})
    complete = len(after.get("old35") or []) == 35 and len(after.get("new15") or []) == 15
    if instance.b50_mode == "required":
        check(complete, "B50 requires 35 old and 15 new charts; captured inputs remain retained")
    return complete and instance.b50_mode != "disabled"


def validate_capture(
    instance: Instance,
    source: Path,
    renderer: str,
    *,
    promote: bool = False,
    source_id: str = "retained-review",
):
    receipt = source / "render-provenance.json"
    if receipt.is_file():
        provenance = read_json(receipt)
        if renderer:
            check(
                renderer == provenance.get("rendererCommit"),
                "Renderer pin differs from retained provenance",
            )
        renderer = provenance.get("rendererCommit", "")
        source_id = provenance.get("sourceID", source_id)
    report = read_json(source / "report-input.json")
    player = report.get("player", {})
    if player.get("username"):
        check(player["username"] == instance.app.username, "Capture belongs to a different player")
    html_path = source / "maimai-report.html"
    return prepare_capture(
        source,
        scope=instance.scope,
        timezone=instance.app.timezone,
        source_id=source_id,
        renderer_commit=renderer,
        rendered_html=html_path if html_path.is_file() else None,
        promote=promote,
    )


def sync(instance: Instance, source: Path) -> None:
    instance.validate("sync")
    check(
        not source.exists() or not any(source.iterdir()),
        "Sync needs an empty capture directory; retained captures must never be overwritten",
    )
    result = synchronize(replace(instance.app, output_dir=source), environ=os.environ)
    write_sync_result(result, source)


def render_capture(instance: Instance, source: Path, *, fetch_artwork: bool = False) -> dict:
    meaningful(source)
    original = read_json(source / "report-input.json")
    after_path = source / "after-pbs.json"
    report = enrich_report(
        original,
        read_json(after_path) if after_path.is_file() else None,
        player=_player(instance.app),
        support=_support(instance.app),
        current_version_display_names=original.get("currentNewDisplayVersions"),
    )
    jackets = {}
    jacket_path = source / "jackets.json"
    if jacket_path.is_file():
        jackets = read_json(jacket_path)
    elif (source / "maimai-report.html").is_file():
        prior = (source / "maimai-report.html").read_text()
        match = re.search(r'<script id="jacket-data"[^>]*>(.*?)</script>', prior, re.S)
        if match:
            jackets = json.loads(match[1])
    if fetch_artwork and instance.artwork_enabled:
        artwork = prepare_jackets(report, source / "artwork-cache")
        jackets = artwork.jackets
        write_json(source / "artwork-cache/provenance.json", artwork.provenance)
    write_json(jacket_path, jackets)
    b50 = source / "maimai-b50.webp"
    ready = b50_ready(instance, source)
    available = ready and b50.is_file()
    if available:
        raw = b50.read_bytes()
        check(raw[:4] == b"RIFF" and raw[8:12] == b"WEBP", "B50 output is not a WebP")
    check(
        instance.b50_mode != "required" or available,
        "Required B50 renderer did not produce an image",
    )
    render_report(
        report,
        source / "maimai-report.html",
        jackets=jackets,
        b50_path=instance.prefix + "b50.webp" if available else None,
        b50_unavailable=instance.b50_mode != "disabled" and not available,
    )
    return {"meaningful": meaningful(source), "b50Available": available}


def storage(
    instance: Instance,
    operation: str,
    workdir: Path,
    *,
    source: Path | None = None,
    source_id: str = "",
    renderer: str = "",
    promote: bool = False,
    recovery: bool = False,
    apply: bool = False,
) -> dict:
    instance.validate(operation)
    if not instance.history_enabled:
        check(operation == "archive", "Hosted history is disabled in instance.toml")
        return {"historyEnabled": False, "storageAccessed": False}
    config = instance.history_config()
    if operation == "plan":
        return resource_plan(config)
    if operation == "setup":
        check(apply, "Setup is read-only until --apply is explicitly supplied")
    api = Cloudflare(instance.account_id, required(os.environ, "CLOUDFLARE_HISTORY_API_TOKEN"))
    if operation == "setup":
        configured = provision(api, config)
        # Preserve owner comments and settings: return a snippet instead of rewriting TOML.
        workdir.mkdir(parents=True, exist_ok=True)
        snippet = (
            "# Replace these two entries in your existing [history] table.\n"
            f'database_id = "{configured["databaseId"]}"\n'
            f'recovery_database_id = "{configured["recoveryDatabaseId"]}"\n'
        )
        (workdir / "setup-result.toml").write_text(snippet)
        return {
            "resourcesReady": True,
            "workerDeployed": False,
            "configurationPatch": "setup-result.toml",
        }
    bucket = instance.backup_bucket if recovery else instance.bucket
    database_id = instance.recovery_database_id if recovery else instance.database_id
    verify_private_bucket(api, bucket)
    objects, database = R2(instance.account_id, bucket), D1(api, database_id)
    if operation == "archive":
        check(source is not None, "Choose a retained capture to archive")
        bundle = validate_capture(
            instance,
            source,
            renderer,
            source_id=source_id,
            promote=promote and instance.app.publishing_enabled,
        )
        result = archive(bundle, objects, database)
        verify_private_bucket(api, instance.backup_bucket)
        result["backup"] = backup_capture(
            objects,
            R2(instance.account_id, instance.backup_bucket),
            instance.scope,
            bundle.capture_id,
        )
        return result
    if operation == "backup":
        verify_private_bucket(api, instance.backup_bucket)
        return backup(objects, R2(instance.account_id, instance.backup_bucket), instance.scope)
    if operation == "rebuild":
        return rebuild(objects, database, instance.scope)
    return {
        "index": database.query(
            "SELECT state,meaningful,COUNT(*) count FROM captures "
            "WHERE scope=? GROUP BY state,meaningful",
            (instance.scope,),
        ),
        "latest": database.query(
            "SELECT latest_id FROM archive_state WHERE scope=?", (instance.scope,)
        ),
        "privateBucketVerified": True,
        "archiveMarkerPresent": objects.get("installation.json") is not None,
    }


def preflight(instance: Instance, *, storage_only: bool = False) -> dict:
    instance.validate("preflight")
    if instance.history_enabled:
        api = Cloudflare(instance.account_id, required(os.environ, "CLOUDFLARE_HISTORY_API_TOKEN"))
        for bucket in (instance.bucket, instance.backup_bucket):
            verify_private_bucket(api, bucket)
            R2(instance.account_id, bucket).get("installation.json")
        for database_id in (instance.database_id, instance.recovery_database_id):
            D1(api, database_id).query("SELECT version FROM history_migrations LIMIT 1")
    if not storage_only:
        worker = WorkerAPI(instance)
        worker.routes()
        verify_bindings(worker.state("settings"), instance)
        verify_domains(worker)
        verify_access(instance)
    return {
        "storageVerified": instance.history_enabled,
        "workerVerified": not storage_only,
        "scoreImportStarted": False,
    }


def retained_report_matches(source: Path) -> None:
    """Ensure a publishable artifact contains the same analytical input, not a stale HTML."""
    original = read_json(source / "report-input.json")
    displayed = report_data((source / "maimai-report.html").read_bytes())
    for key in ("before", "after", "session", "currentNewDisplayVersions"):
        # Enrichment adds complete pool records; compare each retained analytical field.
        value = original.get(key)
        if isinstance(value, dict):
            check(
                all(displayed.get(key, {}).get(k) == v for k, v in value.items()),
                "Rendered report differs from retained analytical inputs",
            )
        else:
            check(
                displayed.get(key) == value,
                "Rendered report differs from retained analytical inputs",
            )
