"""Deterministic downstream contracts read from exact Git objects, never dirty files."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

SCHEMA = "maimai-public-contract-bundle-1"
UPSTREAM = "https://github.com/arussin/maimai-chart-browser"
FILES = {
    "player_data.py": "src/maimai_intelligence/player_data.py",
    "public_matching.py": "src/maimai_intelligence/public_matching.py",
    "site-brand.html": "src/maimai_intelligence/assets/site-brand.html",
    "site-brand.css": "src/maimai_intelligence/assets/site-brand.css",
    "LICENSE": "LICENSE",
}
MAX_FILE_BYTES = 1024 * 1024


def canonical(value: object) -> bytes:
    return (
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        )
        + "\n"
    ).encode()


def git_bytes(source: Path, *arguments: str) -> bytes:
    git = shutil.which("git")
    if git is None:
        raise ValueError("Git is required to verify the contract source revision")
    result = subprocess.run(  # noqa: S603 -- resolved Git executable, explicit argument list
        [git, "--no-optional-locks", "-C", str(source), *arguments],
        capture_output=True,
        check=False,
    )
    if result.returncode:
        raise ValueError("Cannot read the requested contract from the source Git database")
    return result.stdout


def export_bundle(source: Path, revision: str) -> dict:
    """Export only the public allowlist at one full, resolved commit SHA."""
    if not re.fullmatch(r"[a-f0-9]{40}", revision):
        raise ValueError("A full lowercase Git commit SHA is required")
    source = source.resolve(strict=True)
    resolved = git_bytes(source, "rev-parse", "--verify", revision + "^{commit}").decode().strip()
    if resolved != revision:
        raise ValueError("Contract revision must resolve to the requested commit")
    entries = {}
    for name, path in FILES.items():
        raw = git_bytes(source, "show", revision + ":" + path)
        if not 0 < len(raw) <= MAX_FILE_BYTES:
            raise ValueError("Public contract file is empty or exceeds its limit")
        raw.decode("utf-8")  # Preserve exact committed bytes, but require portable text.
        entries[name] = {
            "source_path": path,
            "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "content_base64": base64.b64encode(raw).decode("ascii"),
        }
    return {
        "schema_version": SCHEMA,
        "upstream": UPSTREAM,
        "upstream_revision": revision,
        "api_version": 1,
        "contracts": {"player_data": "maimai-player-data-1", "matching": "public-matching-1"},
        "files": entries,
    }


def validate_bundle(bundle: dict, revision: str) -> dict[str, bytes]:
    """Validate the closed contract envelope before any destination write."""
    if not re.fullmatch(r"[a-f0-9]{40}", revision):
        raise ValueError("A full lowercase Git commit SHA is required")
    expected = {
        "schema_version",
        "upstream",
        "upstream_revision",
        "api_version",
        "contracts",
        "files",
    }
    if (
        not isinstance(bundle, dict)
        or set(bundle) != expected
        or bundle["schema_version"] != SCHEMA
        or bundle["upstream"] != UPSTREAM
        or bundle["upstream_revision"] != revision
        or type(bundle["api_version"]) is not int
        or bundle["api_version"] != 1
        or bundle["contracts"]
        != {"player_data": "maimai-player-data-1", "matching": "public-matching-1"}
        or not isinstance(bundle["files"], dict)
        or set(bundle["files"]) != set(FILES)
    ):
        raise ValueError("Incompatible public contract bundle")
    result = {}
    for name, entry in bundle["files"].items():
        if (
            not isinstance(entry, dict)
            or set(entry) != {"source_path", "bytes", "sha256", "content_base64"}
            or entry["source_path"] != FILES[name]
            or type(entry["bytes"]) is not int
            or not 0 < entry["bytes"] <= MAX_FILE_BYTES
            or not isinstance(entry["content_base64"], str)
            or len(entry["content_base64"]) > MAX_FILE_BYTES * 2
        ):
            raise ValueError("Invalid public contract file")
        try:
            raw = base64.b64decode(entry["content_base64"], validate=True)
            raw.decode("utf-8")
        except (ValueError, UnicodeError, binascii.Error) as exc:
            raise ValueError("Invalid public contract encoding") from exc
        if len(raw) != entry["bytes"] or hashlib.sha256(raw).hexdigest() != entry["sha256"]:
            raise ValueError("Public contract integrity mismatch")
        result[name] = raw
    return result


def load_bundle(path: Path, revision: str, expected_sha256: str) -> dict:
    if not re.fullmatch(r"[a-f0-9]{64}", expected_sha256):
        raise ValueError("The reviewed contract bundle SHA256 is required")
    if path.stat().st_size > MAX_FILE_BYTES * len(FILES) * 2:
        raise ValueError("Contract bundle exceeds its size limit")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("Contract bundle SHA256 mismatch")
    bundle = json.loads(raw, object_pairs_hook=_unique_object)
    validate_bundle(bundle, revision)
    return bundle


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate public contract key: " + key)
        result[key] = value
    return result
