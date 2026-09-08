"""Private local JSON and text I/O helpers."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from .errors import OutputError


def ensure_output_directory(path: Path | str) -> Path:
    """Create an output directory and verify that a private temporary file is writable."""

    directory = Path(path)
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise OutputError(f"Could not create output directory {directory}: {exc}") from exc
    if not directory.is_dir():
        raise OutputError(f"Output path is not a directory: {directory}")

    temporary_path: Path | None = None
    try:
        descriptor, name = tempfile.mkstemp(prefix=".maimai-write-check-", dir=directory)
        temporary_path = Path(name)
        os.close(descriptor)
        _restrict_permissions(temporary_path)
    except OSError as exc:
        raise OutputError(f"Output directory is not writable: {directory}") from exc
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass
    return directory


def read_json_object(path: Path | str) -> dict[str, Any]:
    source = Path(path)
    try:
        value = json.loads(source.read_text(encoding="utf-8"))
    except OSError as exc:
        raise OutputError(f"Could not read JSON input {source}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise OutputError(f"JSON input is invalid at {source}: {exc}") from exc
    if not isinstance(value, dict):
        raise OutputError(f"Expected a JSON object in {source}.")
    return value


def write_json(path: Path | str, value: object) -> Path:
    destination = Path(path)
    text = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    atomic_write_text(destination, text)
    return destination


def atomic_write_text(path: Path | str, text: str) -> Path:
    """Replace one exact output file atomically, with owner-only mode where supported."""

    destination = Path(path)
    directory = ensure_output_directory(destination.parent)
    temporary_path: Path | None = None
    descriptor: int | None = None
    try:
        descriptor, name = tempfile.mkstemp(
            prefix=f".{destination.name}.",
            suffix=".tmp",
            dir=directory,
        )
        temporary_path = Path(name)
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            descriptor = None
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        _restrict_permissions(temporary_path)
        os.replace(temporary_path, destination)
        temporary_path = None
        _restrict_permissions(destination)
    except OSError as exc:
        raise OutputError(f"Could not write private output {destination}: {exc}") from exc
    finally:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                pass
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass
    return destination


def _restrict_permissions(path: Path) -> None:
    try:
        path.chmod(0o600)
    except OSError:
        # Windows ACLs and some network filesystems do not implement POSIX modes.
        pass
