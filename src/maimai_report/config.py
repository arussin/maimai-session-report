"""Load and validate non-secret application configuration."""

from __future__ import annotations

import json
import os
import re
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, fields
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .badges import validate_badge_pack
from .errors import ConfigError, MissingTokenError

DEFAULT_CONFIG_PATH = Path("config.toml")
# This is an environment-variable name, never a credential value.
TOKEN_ENVIRONMENT_VARIABLE = "KAMAITACHI_API_TOKEN"  # noqa: S105


@dataclass(frozen=True, slots=True)
class AppConfig:
    """Resolved configuration. Secret credentials are intentionally absent."""

    username: str = ""
    display_name: str = "Player"
    timezone: str = "UTC"
    game: str = "maimaidx"
    import_type: str = "api/myt-maimaidx"
    current_version_display_names: tuple[str, ...] = ()
    output_dir: Path = Path("output")
    badge_pack: str = "builtin"
    support_enabled: bool = True
    artifact_retention_days: int = 7
    publishing_enabled: bool = False
    publishing_provider: str = "cloudflare"
    cloudflare_account_id: str = ""
    cloudflare_zone_id: str = ""
    cloudflare_worker_name: str = ""
    cloudflare_custom_domain: str = ""
    cloudflare_route_pattern: str = ""
    report_path: str = "/"

    def validate(self, *, for_network: bool = False, for_publish: bool = False) -> None:
        """Validate values for local, network, or publishing use.

        Offline/demo use deliberately permits an empty username and empty current-version
        list. Network validation requires both so a mistaken default can never start an
        import or classify a live rating pool.
        """

        _validate_text("player display name", self.display_name, required=True, maximum=200)
        _validate_text("Kamaitachi username", self.username, required=for_network, maximum=128)
        validate_badge_pack(self.badge_pack)

        if self.timezone != "UTC":
            try:
                ZoneInfo(self.timezone)
            except (ZoneInfoNotFoundError, ValueError) as exc:
                raise ConfigError(
                    f"Invalid or unavailable IANA timezone {self.timezone!r}; use a name "
                    "such as UTC, Europe/London, or Asia/Tokyo, and ensure your Python/OS "
                    "timezone database is installed."
                ) from exc

        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", self.game):
            raise ConfigError(
                "Invalid game identifier; use letters, digits, underscores, or hyphens "
                "(for example, maimaidx)."
            )
        if not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*",
            self.import_type,
        ):
            raise ConfigError("Invalid import type; expected a value such as api/myt-maimaidx.")

        seen_versions: set[str] = set()
        for version in self.current_version_display_names:
            _validate_text("current-version display name", version, required=True, maximum=300)
            if version in seen_versions:
                raise ConfigError(f"Duplicate current-version display name: {version!r}.")
            seen_versions.add(version)
        if for_network and not self.current_version_display_names:
            raise ConfigError(
                "No current-version display names are configured. Set "
                "report.current_version_display_names in config.toml before a live sync."
            )

        if not isinstance(self.support_enabled, bool):
            raise ConfigError("support.enabled must be true or false.")

        if self.output_dir.exists() and not self.output_dir.is_dir():
            raise ConfigError(f"Configured output directory is a file: {self.output_dir}")
        if isinstance(self.artifact_retention_days, bool) or not (
            1 <= self.artifact_retention_days <= 90
        ):
            raise ConfigError("Artifact retention must be an integer from 1 through 90 days.")
        if not isinstance(self.publishing_enabled, bool):
            raise ConfigError("publishing.enabled must be true or false.")

        _validate_text("publishing provider", self.publishing_provider, required=True, maximum=50)
        if (
            not self.report_path.startswith("/")
            or "?" in self.report_path
            or "#" in self.report_path
        ):
            raise ConfigError("publishing.report_path must be an absolute URL path without ? or #.")

        if for_publish:
            if not self.publishing_enabled:
                raise ConfigError(
                    "Publishing is disabled. Set publishing.enabled=true only when you intend "
                    "to run the separate manual publish workflow."
                )
            if self.publishing_provider != "cloudflare":
                raise ConfigError(
                    "The bundled deployment adapter supports publishing.provider=cloudflare."
                )
            required = {
                "Cloudflare account ID": self.cloudflare_account_id,
                "Cloudflare Worker name": self.cloudflare_worker_name,
            }
            missing = [label for label, value in required.items() if not value.strip()]
            if missing:
                raise ConfigError(
                    "Publishing configuration is incomplete; missing " + ", ".join(missing) + "."
                )
            has_custom_domain = bool(self.cloudflare_custom_domain.strip())
            has_route_pattern = bool(self.cloudflare_route_pattern.strip())
            if has_custom_domain == has_route_pattern:
                raise ConfigError(
                    "Configure exactly one Cloudflare routing mode: cloudflare_custom_domain "
                    "or cloudflare_route_pattern."
                )
            if has_route_pattern and not self.cloudflare_zone_id.strip():
                raise ConfigError("Cloudflare route mode requires cloudflare_zone_id.")


_TOML_LAYOUT: dict[str, dict[str, str]] = {
    "kamaitachi": {
        "username": "username",
        "game": "game",
        "import_type": "import_type",
    },
    "player": {
        "display_name": "display_name",
        "timezone": "timezone",
    },
    "report": {
        "current_version_display_names": "current_version_display_names",
        "output_dir": "output_dir",
        "badge_pack": "badge_pack",
    },
    "support": {"enabled": "support_enabled"},
    "actions": {"artifact_retention_days": "artifact_retention_days"},
    "publishing": {
        "enabled": "publishing_enabled",
        "provider": "publishing_provider",
        "cloudflare_account_id": "cloudflare_account_id",
        "cloudflare_zone_id": "cloudflare_zone_id",
        "cloudflare_worker_name": "cloudflare_worker_name",
        "cloudflare_custom_domain": "cloudflare_custom_domain",
        "cloudflare_route_pattern": "cloudflare_route_pattern",
        "report_path": "report_path",
    },
}

_ENVIRONMENT_FIELDS: tuple[tuple[str, str], ...] = (
    # Source-compatible aliases are read first; the documented MAIMAI_REPORT_*
    # names below win when both forms are present.
    ("KAMAITACHI_USERNAME", "username"),
    ("PLAYER_DISPLAY_NAME", "display_name"),
    ("PLAYER_TIMEZONE", "timezone"),
    ("MAIMAI_GAME", "game"),
    ("KAMAITACHI_GAME", "game"),
    ("KAMAITACHI_IMPORT_TYPE", "import_type"),
    ("MAIMAI_CURRENT_VERSION_DISPLAY_NAMES", "current_version_display_names"),
    ("MAIMAI_ARTIFACT_RETENTION_DAYS", "artifact_retention_days"),
    ("MAIMAI_PUBLISHING_ENABLED", "publishing_enabled"),
    ("MAIMAI_PUBLISHING_PROVIDER", "publishing_provider"),
    ("CLOUDFLARE_ACCOUNT_ID", "cloudflare_account_id"),
    ("CLOUDFLARE_ZONE_ID", "cloudflare_zone_id"),
    ("CLOUDFLARE_WORKER_NAME", "cloudflare_worker_name"),
    ("CLOUDFLARE_CUSTOM_DOMAIN", "cloudflare_custom_domain"),
    ("CLOUDFLARE_ROUTE", "cloudflare_route_pattern"),
    ("MAIMAI_REPORT_PATH", "report_path"),
    ("MAIMAI_REPORT_USERNAME", "username"),
    ("MAIMAI_REPORT_DISPLAY_NAME", "display_name"),
    ("MAIMAI_REPORT_TIMEZONE", "timezone"),
    ("MAIMAI_REPORT_GAME", "game"),
    ("MAIMAI_REPORT_IMPORT_TYPE", "import_type"),
    ("MAIMAI_REPORT_CURRENT_VERSION_DISPLAY_NAMES", "current_version_display_names"),
    ("MAIMAI_REPORT_OUTPUT_DIR", "output_dir"),
    ("MAIMAI_REPORT_BADGE_PACK", "badge_pack"),
    ("MAIMAI_REPORT_SUPPORT_ENABLED", "support_enabled"),
    ("MAIMAI_REPORT_ARTIFACT_RETENTION_DAYS", "artifact_retention_days"),
    ("MAIMAI_REPORT_PUBLISHING_ENABLED", "publishing_enabled"),
)

_FIELD_NAMES = {field.name for field in fields(AppConfig)}
_BOOLEAN_FIELDS = {"publishing_enabled", "support_enabled"}
_INTEGER_FIELDS = {"artifact_retention_days"}
_PATH_FIELDS = {"output_dir"}
_VERSION_FIELDS = {"current_version_display_names"}
_SECRET_KEY_NAMES = {
    "token",
    "api_token",
    "kamaitachi_api_token",
    "password",
    "access_code",
}


def load_config(
    config_path: Path | str | None = DEFAULT_CONFIG_PATH,
    *,
    cli_overrides: Mapping[str, object] | None = None,
    environ: Mapping[str, str] | None = None,
    require_file: bool = False,
) -> AppConfig:
    """Resolve CLI > environment > TOML > safe-default precedence."""

    values: dict[str, object] = {field.name: field.default for field in fields(AppConfig)}

    if config_path is not None:
        path = Path(config_path)
        values.update(_read_config_file(path, require_file=require_file))

    environment = os.environ if environ is None else environ
    for environment_name, field_name in _ENVIRONMENT_FIELDS:
        if environment_name in environment:
            values[field_name] = _coerce_value(
                field_name,
                environment[environment_name],
                source=f"environment variable {environment_name}",
            )

    if cli_overrides:
        unknown = sorted(set(cli_overrides) - _FIELD_NAMES)
        if unknown:
            raise ConfigError("Unknown CLI configuration option(s): " + ", ".join(unknown))
        for field_name, value in cli_overrides.items():
            if value is not None:
                values[field_name] = _coerce_value(field_name, value, source="CLI option")

    config = AppConfig(**values)
    config.validate()
    return config


def get_api_token(
    environ: Mapping[str, str] | None = None,
    *,
    required: bool = True,
) -> str | None:
    """Read the Kamaitachi token from its sole supported source without displaying it."""

    environment = os.environ if environ is None else environ
    value = environment.get(TOKEN_ENVIRONMENT_VARIABLE)
    token = value.strip() if isinstance(value, str) else ""
    if not token:
        if required:
            raise MissingTokenError(
                "KAMAITACHI_API_TOKEN is not configured. Set it in the current process "
                "environment (or as the GitHub Actions secret of that name); never put it "
                "in config.toml or a command-line argument."
            )
        return None
    return token


def _read_config_file(path: Path, *, require_file: bool) -> dict[str, object]:
    if not path.exists():
        if require_file:
            raise ConfigError(f"Configuration file does not exist: {path}")
        return {}
    if not path.is_file():
        raise ConfigError(f"Configuration path is not a file: {path}")

    try:
        with path.open("rb") as handle:
            document = tomllib.load(handle)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(
            f"Could not parse TOML configuration from {path}; correct its syntax and retry."
        ) from exc
    except OSError as exc:
        raise ConfigError(f"Could not read TOML configuration from {path}: {exc}") from exc

    return config_values(document, source=str(path))


def config_values(document: Mapping[str, object], *, source: str) -> dict[str, object]:
    """Parse the existing application tables for both standalone and hosted use."""
    secret_key = _find_secret_key(document)
    if secret_key is not None:
        raise ConfigError(
            f"Secret-bearing key {secret_key!r} is not allowed in {source}. "
            "Use KAMAITACHI_API_TOKEN in the process environment instead."
        )

    unknown_sections = sorted(set(document) - set(_TOML_LAYOUT))
    if unknown_sections:
        raise ConfigError("Unknown configuration section(s): " + ", ".join(unknown_sections))

    values: dict[str, object] = {}
    for section_name, section in document.items():
        if not isinstance(section, dict):
            raise ConfigError(f"Configuration section [{section_name}] must be a TOML table.")
        layout = _TOML_LAYOUT[section_name]
        unknown_keys = sorted(set(section) - set(layout))
        if unknown_keys:
            raise ConfigError(f"Unknown key(s) in [{section_name}]: " + ", ".join(unknown_keys))
        for key, value in section.items():
            field_name = layout[key]
            values[field_name] = _coerce_value(
                field_name,
                value,
                source=f"{source} [{section_name}].{key}",
            )
    return values


def _find_secret_key(value: object) -> str | None:
    if not isinstance(value, dict):
        return None
    for key, nested in value.items():
        normalized = str(key).strip().lower().replace("-", "_")
        if normalized in _SECRET_KEY_NAMES or normalized.endswith("_token"):
            return str(key)
        found = _find_secret_key(nested)
        if found is not None:
            return found
    return None


def _coerce_value(field_name: str, value: object, *, source: str) -> object:
    if field_name in _BOOLEAN_FIELDS:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"1", "true", "yes", "on"}:
                return True
            if lowered in {"0", "false", "no", "off"}:
                return False
        raise ConfigError(f"{source} must provide true or false for {field_name}.")

    if field_name in _INTEGER_FIELDS:
        if isinstance(value, bool):
            raise ConfigError(f"{source} must provide an integer for {field_name}.")
        try:
            return int(value)  # type: ignore[arg-type]
        except (TypeError, ValueError) as exc:
            raise ConfigError(f"{source} must provide an integer for {field_name}.") from exc

    if field_name in _PATH_FIELDS:
        if not isinstance(value, (str, os.PathLike)):
            raise ConfigError(f"{source} must provide a filesystem path for {field_name}.")
        return Path(value)

    if field_name in _VERSION_FIELDS:
        return _coerce_versions(value, source=source)

    if not isinstance(value, str):
        raise ConfigError(f"{source} must provide text for {field_name}.")
    return value.strip()


def _coerce_versions(value: object, *, source: str) -> tuple[str, ...]:
    parsed: object = value
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith("["):
            try:
                parsed = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ConfigError(
                    f"{source} must be a JSON array or comma-separated display-name list."
                ) from exc
        elif not stripped:
            parsed = []
        else:
            parsed = stripped.split(",")

    if not isinstance(parsed, (list, tuple)) or not all(isinstance(item, str) for item in parsed):
        raise ConfigError(f"{source} must provide a list of current-version display names.")
    normalized = tuple(item.strip() for item in parsed)
    if any(not item for item in normalized):
        raise ConfigError(f"{source} may not contain an empty display name.")
    return normalized


def _validate_text(
    label: str,
    value: str,
    *,
    required: bool,
    maximum: int,
) -> None:
    if not isinstance(value, str):
        raise ConfigError(f"{label.capitalize()} must be text.")
    if required and not value.strip():
        raise ConfigError(f"{label.capitalize()} is required.")
    if len(value) > maximum:
        raise ConfigError(f"{label.capitalize()} is too long (maximum {maximum} characters).")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ConfigError(f"{label.capitalize()} may not contain control characters.")
