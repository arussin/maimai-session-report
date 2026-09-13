"""Validated owner settings. Credentials are never part of the serialized model."""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, replace
from pathlib import Path
from urllib.parse import urlsplit
from uuid import UUID

from ..config import _ENVIRONMENT_FIELDS, AppConfig, _coerce_value, config_values
from ..errors import ConfigError

APP_TABLES = {"kamaitachi", "player", "report", "support", "actions", "publishing"}
CLOUD_FIELDS = {"account_id", "zone_id", "worker_name", "origin", "prefix"}
HISTORY_FIELDS = {
    "enabled",
    "scope",
    "bucket",
    "backup_bucket",
    "database_name",
    "database_id",
    "recovery_database_name",
    "recovery_database_id",
}
SECRET_KEYS = {
    "token",
    "api_key",
    "password",
    "secret",
    "access_code",
    "access_key_id",
    "secret_access_key",
    "credentials",
    "authorization",
    "cookie",
}


def _table(document: dict, name: str, allowed: set[str]) -> dict:
    value = document.get(name, {})
    if not isinstance(value, dict) or set(value) - allowed:
        raise ConfigError(f"Invalid or unknown setting in [{name}]; see the instance reference")
    return value


def _no_secrets(value: object) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            key = key.lower().replace("-", "_")
            if key in SECRET_KEYS or key.endswith(("_token", "_secret", "_password", "_key")):
                raise ConfigError("Credentials belong in GitHub Actions secrets, not instance.toml")
            _no_secrets(item)
    elif isinstance(value, list):
        for item in value:
            _no_secrets(item)


def _text(table: dict, key: str, default: str = "") -> str:
    value = table.get(key, default)
    if not isinstance(value, str) or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ConfigError(f"{key} must be text without control characters")
    return value.strip()


def _bool(table: dict, key: str, default: bool) -> bool:
    value = table.get(key, default)
    if type(value) is not bool:
        raise ConfigError(f"{key} must be true or false")
    return value


@dataclass(frozen=True)
class Instance:
    app: AppConfig
    account_id: str
    zone_id: str
    worker_name: str
    origin: str
    prefix: str
    scope: str
    bucket: str
    backup_bucket: str
    database_name: str
    database_id: str
    recovery_database_name: str
    recovery_database_id: str
    history_enabled: bool = True
    b50_mode: str = "optional"
    artwork_enabled: bool = True

    def validate(self, operation: str = "validate") -> None:
        self.app.validate(for_network=operation in {"sync", "capture"})
        if not re.fullmatch(r"[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)*", str(self.app.output_dir)):
            raise ConfigError("report.output_dir must be a relative capture directory")
        if str(self.app.output_dir).split("/")[0] in {
            "src",
            "tests",
            "templates",
            "installation",
            "deploy",
            "adapters",
            "scripts",
        }:
            raise ConfigError("report.output_dir must not overwrite application source")
        if self.app.game != "maimaidx":
            raise ConfigError("The hosted installation supports one maimaidx owner/game")
        if self.b50_mode not in {"disabled", "optional", "required"}:
            raise ConfigError("b50.mode must be disabled, optional, or required")
        for name in ("account_id", "zone_id"):
            value = getattr(self, name)
            if value and not re.fullmatch(r"[0-9a-f]{32}", value):
                raise ConfigError(f"cloudflare.{name} must be a 32-character hexadecimal ID")
        for name in (
            "worker_name",
            "bucket",
            "backup_bucket",
            "database_name",
            "recovery_database_name",
        ):
            if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,61}[a-z0-9]", getattr(self, name)):
                raise ConfigError(f"{name} must be a lowercase resource name (3–63 characters)")
        if self.bucket == self.backup_bucket or self.database_name == self.recovery_database_name:
            raise ConfigError("History and recovery need distinct buckets and databases")
        for name in ("database_id", "recovery_database_id"):
            value = getattr(self, name)
            if value:
                try:
                    if str(UUID(value)) != value:
                        raise ValueError
                except ValueError as exc:
                    raise ConfigError(f"history.{name} must be a canonical UUID") from exc
        if self.database_id and self.database_id == self.recovery_database_id:
            raise ConfigError("Primary and recovery database IDs must be distinct")
        if not re.fullmatch(r"[a-zA-Z0-9_.:-]{1,160}", self.scope):
            raise ConfigError("history.scope must identify one owner and game")
        try:
            origin = urlsplit(self.origin)
            invalid = (
                origin.scheme != "https"
                or not origin.hostname
                or origin.path
                or origin.query
                or origin.fragment
                or origin.username
                or origin.password
                or origin.port
                or origin.netloc != origin.hostname
                or not re.fullmatch(r"[a-z0-9][a-z0-9.-]*[a-z0-9]", origin.hostname)
            )
        except ValueError as exc:
            raise ConfigError("cloudflare.origin must be an exact HTTPS origin") from exc
        if invalid:
            raise ConfigError("cloudflare.origin must be an exact HTTPS origin without a path")
        if not re.fullmatch(r"/[a-zA-Z0-9_-]+/", self.prefix):
            raise ConfigError("cloudflare.prefix must be one protected segment, such as /maimai/")
        hosted = operation in {
            "plan",
            "setup",
            "preflight",
            "verify-fresh",
            "archive",
            "backup",
            "rebuild",
            "health",
            "stage",
            "prepare-release",
            "prepare-publish",
            "rollback-plan",
            "verify-rollback",
            "recheck",
            "verify-release",
            "rollback",
            "bootstrap",
        }
        if operation == "archive" and not self.history_enabled:
            hosted = False
        if hosted and (not self.account_id or not self.zone_id):
            raise ConfigError("Set cloudflare.account_id and zone_id before hosted operations")
        if hosted and operation not in {"plan", "setup"} and self.history_enabled:
            if not self.database_id or not self.recovery_database_id:
                raise ConfigError(
                    "Run explicit setup and record both database IDs in instance.toml"
                )
        if operation in {
            "stage",
            "prepare-release",
            "prepare-publish",
            "rollback-plan",
            "verify-rollback",
            "recheck",
            "verify-release",
            "rollback",
            "bootstrap",
        }:
            if not self.app.publishing_enabled:
                raise ConfigError("Publishing is disabled in instance.toml")
        if (
            hosted
            and operation != "stage"
            and (origin.hostname.endswith(".invalid") or origin.hostname == "example.com")
        ):
            raise ConfigError("Replace the fictional origin before a hosted operation")

    def history_config(self) -> dict:
        return {
            "schemaVersion": 1,
            "accountId": self.account_id,
            "bucket": self.bucket,
            "backupBucket": self.backup_bucket,
            "databaseName": self.database_name,
            "recoveryDatabaseName": self.recovery_database_name,
            "scope": self.scope,
            "timezone": self.app.timezone,
            "origin": self.origin,
            "prefix": self.prefix,
            "databaseId": self.database_id,
            "recoveryDatabaseId": self.recovery_database_id,
        }

    def identity(self) -> dict:
        return {
            **self.history_config(),
            "workerName": self.worker_name,
            "zoneId": self.zone_id,
            "historyEnabled": self.history_enabled,
        }

    @property
    def route(self) -> dict:
        return {
            "pattern": urlsplit(self.origin).netloc + self.prefix.rstrip("/") + "*",
            "zone_id": self.zone_id,
        }


def load_instance(
    path: Path, *, operation: str = "validate", environ: dict | None = None
) -> Instance:
    try:
        document = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ConfigError("Could not read instance.toml; check its path and TOML syntax") from exc
    _no_secrets(document)
    if type(document.get("schema_version")) is not int or document["schema_version"] != 1:
        raise ConfigError("instance.toml requires schema_version = 1")
    if set(document) - APP_TABLES - {"schema_version", "cloudflare", "history", "b50", "artwork"}:
        raise ConfigError("Unknown instance section; see the configuration reference")
    _table(document, "publishing", {"enabled", "provider"})
    app_document = {k: v for k, v in document.items() if k in APP_TABLES}
    app = AppConfig(**config_values(app_document, source="instance.toml"))
    if app.publishing_provider != "cloudflare":
        raise ConfigError("The hosted installation uses publishing.provider = cloudflare")
    cloud = _table(document, "cloudflare", CLOUD_FIELDS)
    history = _table(document, "history", HISTORY_FIELDS)
    b50 = _table(document, "b50", {"mode"})
    artwork = _table(document, "artwork", {"enabled"})
    values = {key: _text(cloud, key) for key in CLOUD_FIELDS}
    values.update({key: _text(history, key) for key in HISTORY_FIELDS - {"enabled"}})
    instance = Instance(
        app=replace(
            app,
            cloudflare_account_id=values["account_id"],
            cloudflare_zone_id=values["zone_id"],
            cloudflare_worker_name=values["worker_name"],
            report_path=values["prefix"],
        ),
        **values,
        history_enabled=_bool(history, "enabled", True),
        b50_mode=_text(b50, "mode", "optional"),
        artwork_enabled=_bool(artwork, "enabled", True),
    )
    instance.validate(operation)
    for name, field in _ENVIRONMENT_FIELDS:
        if environ and name in environ:
            value = _coerce_value(field, environ[name], source=name)
            if value != getattr(instance.app, field):
                raise ConfigError(f"{name} conflicts with instance.toml; keep one editable value")
    return instance


def validate_workflow_pins(directory: Path) -> str:
    """Validate the four installation entry points without a second dependency lock."""
    pins = set()
    pattern = re.compile(
        r"^\s*(?:-\s*)?uses:\s*arussin/maimai-session-report(?:/[A-Za-z0-9_./-]+)?@([^\s]+)",
        re.M,
    )
    for name in ("validate", "refresh", "history", "release"):
        path = directory / (name + ".yml")
        try:
            references = pattern.findall(path.read_text())
        except OSError as exc:
            raise ConfigError(f"Installation workflow is missing: {name}.yml") from exc
        if not references or any(not re.fullmatch(r"[0-9a-f]{40}", ref) for ref in references):
            raise ConfigError(f"{name}.yml must pin the core to a complete commit SHA")
        pins.update(references)
    if len(pins) != 1:
        raise ConfigError("The four installation workflows must pin the same core commit")
    return next(iter(pins))
