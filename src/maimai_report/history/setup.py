"""Repeatable hosted setup. No routes, Access policies, secrets or public domains change."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlsplit

from .bundle import ArchiveError, canonical, load_json
from .cloudflare import D1, Cloudflare
from .storage import migration_sql


def config_file(path: Path) -> dict:
    if path.suffix == ".toml":
        from ..installation.config import load_instance

        return load_instance(path, operation="plan").history_config()
    config = load_json(path.read_bytes())
    if config.get("schemaVersion") != 1:
        raise ArchiveError("Unsupported history configuration")
    if not re.fullmatch(r"[0-9a-f]{32}", str(config.get("accountId"))):
        raise ArchiveError("Set the owner's Cloudflare account ID")
    for key in ("bucket", "backupBucket", "databaseName", "recoveryDatabaseName"):
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,61}[a-z0-9]", str(config.get(key))):
            raise ArchiveError(f"Set a valid private resource name: {key}")
    if (
        config["bucket"] == config["backupBucket"]
        or config["databaseName"] == config["recoveryDatabaseName"]
    ):
        raise ArchiveError("Recovery requires independent resources")
    if not re.fullmatch(r"[a-zA-Z0-9_.:-]{1,160}", str(config.get("scope"))):
        raise ArchiveError("Set an installation scope for one owner and game")
    origin = urlsplit(config.get("origin", ""))
    if (
        origin.scheme != "https"
        or not origin.hostname
        or origin.path
        or origin.query
        or origin.fragment
        or origin.username
        or origin.password
        or origin.port
    ):
        raise ArchiveError("History requires the exact existing HTTPS origin")
    if not re.fullmatch(r"/[a-zA-Z0-9_-]+/", str(config.get("prefix"))):
        raise ArchiveError("History must stay under one protected path prefix")
    return config


def resource_plan(config: dict) -> dict:
    return {
        "privateBuckets": [config["bucket"], config["backupBucket"]],
        "databases": [config["databaseName"], config["recoveryDatabaseName"]],
        "scope": config["scope"],
        "origin": config["origin"],
        "prefix": config["prefix"],
        "retention": "Durable; no expiration rules installed",
        "publicAccess": False,
        "deployWorker": False,
        "changeAccessPolicy": False,
    }


def preserves_completed_objects(rule: object) -> bool:
    """Allow incomplete-upload cleanup, never expiration of completed captures."""
    if not isinstance(rule, dict):
        return False
    if rule.get("enabled") is False:
        return True
    allowed = {"id", "enabled", "conditions", "abortMultipartUploadsTransition"}
    if rule.get("enabled") is not True or set(rule) - allowed:
        return False
    abort = rule.get("abortMultipartUploadsTransition")
    if not isinstance(abort, dict) or set(abort) != {"condition"}:
        return False
    condition = abort["condition"]
    return (
        isinstance(rule.get("conditions"), dict)
        and isinstance(condition, dict)
        and set(condition) == {"type", "maxAge"}
        and condition["type"] == "Age"
        and type(condition["maxAge"]) is int
        and condition["maxAge"] > 0
    )


def verify_private_bucket(api: Cloudflare, bucket: str) -> None:
    base = f"/r2/buckets/{bucket}"
    managed = api.request(base + "/domains/managed")
    custom = api.request(base + "/domains/custom")
    lifecycle = api.request(base + "/lifecycle")
    if managed.get("enabled") is not False:
        raise ArchiveError("Archive bucket must have its r2.dev domain disabled")
    if not isinstance(custom.get("domains"), list) or custom["domains"]:
        raise ArchiveError("Archive bucket must have no custom public domains")
    if not isinstance(lifecycle.get("rules"), list) or not all(
        preserves_completed_objects(rule) for rule in lifecycle["rules"]
    ):
        raise ArchiveError("Review bucket lifecycle rules before durable history is enabled")


def provision(api: Cloudflare, config: dict) -> dict:
    """Reuse named resources; create missing ones without reconfiguring existing resources."""
    result = dict(config)
    buckets = {row["name"] for row in api.request("/r2/buckets")["buckets"]}
    for key in ("bucket", "backupBucket"):
        name = config[key]
        if name not in buckets:
            api.request("/r2/buckets", method="POST", data={"name": name})
        verify_private_bucket(api, name)
    databases = []
    page = 1
    while True:
        rows = api.request(f"/d1/database?per_page=100&page={page}")
        databases.extend(rows)
        if len(rows) < 100:
            break
        page += 1
    for name_key, id_key in (
        ("databaseName", "databaseId"),
        ("recoveryDatabaseName", "recoveryDatabaseId"),
    ):
        matches = [row for row in databases if row["name"] == config[name_key]]
        if len(matches) > 1:
            raise ArchiveError("More than one D1 database has the requested name")
        value = (
            matches[0]
            if matches
            else api.request("/d1/database", method="POST", data={"name": config[name_key]})
        )
        database_id = value.get("uuid", value.get("id"))
        if config.get(id_key) and config[id_key] != database_id:
            raise ArchiveError("Configured D1 UUID differs from the named resource")
        database = D1(api, database_id)
        tables = database.query(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE '_cf_%' AND name NOT LIKE 'sqlite_%'"
        )
        allowed = {"history_migrations", "captures", "rating_snapshots", "archive_state"}
        if any(row["name"] not in allowed for row in tables):
            raise ArchiveError("Refusing to migrate a database containing unrelated tables")
        database.query(migration_sql())
        result[id_key] = database_id
    return result


def bindings(config: dict) -> dict:
    return {
        "r2_buckets": [{"binding": "HISTORY_OBJECTS", "bucket_name": config["bucket"]}],
        "d1_databases": [
            {
                "binding": "HISTORY_DB",
                "database_name": config["databaseName"],
                "database_id": config["databaseId"],
            }
        ],
        "vars": {
            "HISTORY_SCOPE": config["scope"],
            "HISTORY_ORIGIN": config["origin"],
            "HISTORY_PREFIX": config["prefix"],
        },
        "workers_dev": False,
        "preview_urls": False,
    }


def save_config(path: Path, config: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical(config) + b"\n")
