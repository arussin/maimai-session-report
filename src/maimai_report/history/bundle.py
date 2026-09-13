"""Create portable, immutable capture manifests without changing report calculations."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

SCHEMA_VERSION = 1
RAW_NAMES = (
    "report-input.json",
    "metadata.json",
    "before-pbs.json",
    "after-pbs.json",
    "before-recent-scores.json",
    "after-recent-scores.json",
)
OPTIONAL_NAMES = (
    "maimai-report.html",
    "maimai-b50.webp",
    "baseline.json",
    "kamaitachi-session.json",
)
MAX_FILE_BYTES = 20 * 1024 * 1024
SCOPE_PATTERN = r"[a-zA-Z0-9_.:-]{1,160}"
DIGEST_PATTERN = r"[0-9a-f]{64}"


class ArchiveError(ValueError):
    """The archive cannot safely accept the supplied capture."""


def canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode()


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def load_json(raw: bytes) -> dict:
    try:
        result = json.loads(raw)
    except (ValueError, UnicodeError) as exc:
        raise ArchiveError("Invalid retained JSON") from exc
    if not isinstance(result, dict):
        raise ArchiveError("Retained JSON must be an object")
    return result


def integer(value: Any, *, optional: bool = False) -> int | None:
    if optional and value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool) or abs(value) > 2**53 - 1:
        raise ArchiveError("Expected a finite safe integer in the retained summary")
    return value


def timestamp(value: Any) -> int:
    if not isinstance(value, str):
        raise ArchiveError("Capture timestamp is missing")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("timezone missing")
        return int(parsed.timestamp() * 1000)
    except (ValueError, OverflowError) as exc:
        raise ArchiveError("Capture timestamp must include its timezone") from exc


def report_data(html: bytes) -> dict:
    match = re.search(rb'<script[^>]+id=["\']report-data["\'][^>]*>(.*?)</script>', html, re.S)
    if match is None:
        raise ArchiveError("Rendered report data is missing")
    return load_json(match[1])


def rating_snapshot(value: Any) -> dict:
    if not isinstance(value, dict):
        raise ArchiveError("Before/after rating snapshot is missing")
    keys = (
        "reconstructedRating",
        "naiveRating",
        "old35Rating",
        "new15Rating",
        "old35Floor",
        "new15Floor",
        "pbCount",
        "newSlotsFilled",
        "newPoolPlayed",
    )
    output = {key: integer(value.get(key), optional=True) for key in keys}
    for name in ("old35", "new15"):
        if not isinstance(value.get(name), list):
            raise ArchiveError("Complete counted-pool arrays must be retained")
    output["oldSlotsFilled"] = len(value["old35"])
    return output


@dataclass(frozen=True)
class CaptureBundle:
    manifest: dict
    objects: dict[str, bytes]

    @property
    def manifest_bytes(self) -> bytes:
        return canonical(self.manifest)

    @property
    def capture_id(self) -> str:
        return self.manifest["captureID"]

    def write(self, destination: Path) -> None:
        destination.mkdir(parents=True, exist_ok=True)
        (destination / "manifest.json").write_bytes(self.manifest_bytes)
        for key, raw in self.objects.items():
            path = destination / key
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)


def prepare_capture(
    source: Path,
    *,
    scope: str,
    timezone: str,
    source_id: str,
    renderer_commit: str,
    rendered_html: Path | None = None,
    retained_b50: Path | None = None,
    b50_provenance: str | None = None,
    promote: bool = False,
    source_revision: str | None = None,
) -> CaptureBundle:
    if not re.fullmatch(r"[a-zA-Z0-9_.:-]{1,160}", scope):
        raise ArchiveError("Scope must identify one owner and game")
    if not re.fullmatch(r"[a-zA-Z0-9_.:-]{1,160}", source_id):
        raise ArchiveError("A stable source identifier is required")
    if not re.fullmatch(r"[0-9a-f]{40}", renderer_commit):
        raise ArchiveError("The renderer must be pinned to a complete commit SHA")
    try:
        ZoneInfo(timezone)
    except (ValueError, ZoneInfoNotFoundError) as exc:
        raise ArchiveError("Invalid capture timezone") from exc
    files: dict[str, bytes] = {}
    for name in RAW_NAMES + OPTIONAL_NAMES:
        path = source / name
        if path.is_symlink():
            raise ArchiveError("Capture inputs may not be symlinks")
        if path.is_file():
            if path.stat().st_size > MAX_FILE_BYTES:
                raise ArchiveError("Capture file is too large")
            files[name] = path.read_bytes()
    if any(name not in files for name in RAW_NAMES[:2]):
        raise ArchiveError("report-input.json and metadata.json are required")
    report = load_json(files["report-input.json"])
    metadata = load_json(files["metadata.json"])
    if metadata.get("syncCompleted") is not True:
        raise ArchiveError("Capture must confirm sync completion")
    session = report.get("session")
    if not isinstance(session, dict):
        raise ArchiveError("Session summary is missing")
    for count, entries in (("scoreCount", "scores"), ("changedPBCount", "changedPBs")):
        if not isinstance(session.get(entries), list) or integer(session.get(count)) != len(
            session[entries]
        ):
            raise ArchiveError("Session counts disagree with the retained records")
    if (
        metadata.get("sessionScoreCount") != session["scoreCount"]
        or metadata.get("changedPBCount") != session["changedPBCount"]
    ):
        raise ArchiveError("Metadata disagrees with the retained session")
    versions = report.get("currentNewDisplayVersions")
    if (
        not isinstance(versions, list)
        or not versions
        or not all(isinstance(v, str) and v for v in versions)
    ):
        raise ArchiveError("As-of game-version assumptions must be retained")
    captured_at = timestamp(report.get("generatedAt"))
    times = [
        integer(s["timeAchieved"]) for s in session["scores"] if s.get("timeAchieved") is not None
    ]
    meaningful = session["scoreCount"] > 0 or session["changedPBCount"] > 0
    before, after = rating_snapshot(report.get("before")), rating_snapshot(report.get("after"))
    identity_inputs = {"report": {k: v for k, v in report.items() if k != "generatedAt"}}
    for name in RAW_NAMES[2:]:
        if name in files:
            value = load_json(files[name])
            identity_inputs[name] = value.get("body", value)
    input_hash = sha256(canonical(identity_inputs))
    import_id = metadata.get("importID")
    if import_id is not None and (not isinstance(import_id, str) or not import_id):
        raise ArchiveError("Invalid upstream import identity")
    capture_id = sha256(
        canonical(
            {
                "scope": scope,
                "identity": import_id or input_hash,
                "kind": "import" if import_id else "retained-input",
            }
        )
    )
    missing = [name for name in RAW_NAMES if name not in files]
    objects: dict[str, bytes] = {}
    references: dict[str, dict] = {}

    def add(name: str, raw: bytes) -> dict:
        if not raw or len(raw) > MAX_FILE_BYTES:
            raise ArchiveError("Archive object is empty or too large")
        digest = sha256(raw)
        key = f"objects/sha256/{digest}"
        objects[key] = raw
        value = {"key": key, "sha256": digest, "bytes": len(raw)}
        references[name] = value
        return value

    for name, raw in files.items():
        add(name, raw)
    view = None
    if rendered_html is not None:
        html = rendered_html.read_bytes()
        presented = report_data(html)
        # Enrichment may add display data, but cannot alter retained analysis.
        for section in ("before", "after", "delta", "session", "capture", "comparison"):
            original = report.get(section, {})
            if any(presented.get(section, {}).get(k) != v for k, v in original.items()):
                raise ArchiveError("Historical rendering changed the retained analysis")
        if presented.get("currentNewDisplayVersions") != versions:
            raise ArchiveError("Historical rendering changed the as-of version")
        if re.search(rb"<script[^>]+src\s*=", html, re.I):
            raise ArchiveError("Historical presentation cannot load parent-page remote scripts")
        view = add(f"renders/{renderer_commit}/report.html", html)
    elif "maimai-report.html" in files:
        # Original bytes remain archival evidence; use a fresh validated render for serving.
        missing.append("validated-render")
    image = None
    if retained_b50 is not None:
        if not b50_provenance:
            raise ArchiveError("A supplied historical B50 needs explicit provenance")
        raw_b50 = retained_b50.read_bytes()
    else:
        raw_b50 = files.get("maimai-b50.webp")
    if raw_b50 is not None:
        if raw_b50[:4] != b"RIFF" or raw_b50[8:12] != b"WEBP":
            raise ArchiveError("Retained B50 is not WebP")
        image = add("selected-b50.webp", raw_b50)
    manifest = {
        "schemaVersion": SCHEMA_VERSION,
        "captureID": capture_id,
        "scope": scope,
        "inputHash": input_hash,
        "identityQuality": "upstream-import" if import_id else "retained-input-hash",
        "importID": import_id,
        "capturedAtMs": captured_at,
        "startMs": min(times) if times else None,
        "endMs": max(times) if times else None,
        # Existing-session reads pair historical plays with PBs at capture time.
        "sortMs": (
            captured_at
            if report.get("capture", {}).get("source") == "kamaitachi" or not times
            else max(times)
        ),
        "cutoffMs": integer(session.get("cutoffTimeAchieved"), optional=True),
        "timezone": timezone,
        "versions": versions,
        "ratingModel": report.get("ratingVersionAssumption"),
        "meaningful": meaningful,
        "promote": bool(promote and meaningful and view),
        "scoreCount": session["scoreCount"],
        "changedPBCount": session["changedPBCount"],
        "before": before,
        "after": after,
        "delta": report.get("delta", {}),
        "missing": missing,
        "source": {"id": source_id, "revision": source_revision},
        "rendererCommit": renderer_commit,
        "files": references,
        "report": view,
        "b50": image,
        "b50Provenance": b50_provenance or ("original capture" if image else "not retained"),
    }
    validate_manifest(manifest)
    return CaptureBundle(manifest, objects)


def validate_manifest(manifest: dict) -> None:
    """Validate the portable boundary before paths, SQL or hosted writes use it."""
    if manifest.get("schemaVersion") != SCHEMA_VERSION:
        raise ArchiveError("Unsupported capture schema")
    for key in ("captureID", "inputHash"):
        if not re.fullmatch(DIGEST_PATTERN, str(manifest.get(key))):
            raise ArchiveError("Invalid capture identity")
    if not re.fullmatch(SCOPE_PATTERN, str(manifest.get("scope"))):
        raise ArchiveError("Invalid capture scope")
    source = manifest.get("source", {})
    if not isinstance(source, dict) or not re.fullmatch(SCOPE_PATTERN, str(source.get("id"))):
        raise ArchiveError("Invalid capture source")
    if not re.fullmatch(r"[0-9a-f]{40}", str(manifest.get("rendererCommit"))):
        raise ArchiveError("Invalid renderer revision")
    try:
        ZoneInfo(manifest["timezone"])
    except (KeyError, TypeError, ValueError, ZoneInfoNotFoundError) as exc:
        raise ArchiveError("Invalid capture timezone") from exc
    for key in ("capturedAtMs", "sortMs", "scoreCount", "changedPBCount"):
        if integer(manifest.get(key)) < 0:
            raise ArchiveError("Negative capture counter or timestamp")
    for key in ("startMs", "endMs", "cutoffMs"):
        integer(manifest.get(key), optional=True)
    for key in ("meaningful", "promote"):
        if not isinstance(manifest.get(key), bool):
            raise ArchiveError("Invalid publication flag")
    meaningful = manifest["scoreCount"] > 0 or manifest["changedPBCount"] > 0
    if manifest["meaningful"] != meaningful or (manifest["promote"] and not meaningful):
        raise ArchiveError("Publication flags disagree with capture counts")
    for phase in ("before", "after"):
        snapshot = manifest.get(phase)
        if not isinstance(snapshot, dict):
            raise ArchiveError("Missing rating snapshot")
        for key in (
            "reconstructedRating",
            "naiveRating",
            "old35Rating",
            "new15Rating",
            "old35Floor",
            "new15Floor",
            "pbCount",
            "oldSlotsFilled",
            "newSlotsFilled",
            "newPoolPlayed",
        ):
            integer(snapshot.get(key), optional=True)
    versions = manifest.get("versions")
    if (
        not isinstance(versions, list)
        or not versions
        or not all(isinstance(v, str) and v for v in versions)
    ):
        raise ArchiveError("Missing as-of versions")
    if not isinstance(manifest.get("missing"), list) or not all(
        isinstance(v, str) for v in manifest["missing"]
    ):
        raise ArchiveError("Invalid missing-data annotation")
    files = manifest.get("files")
    if not isinstance(files, dict) or not all(name in files for name in RAW_NAMES[:2]):
        raise ArchiveError("Missing capture input references")
    for entry in files.values():
        if not isinstance(entry, dict) or not re.fullmatch(
            DIGEST_PATTERN, str(entry.get("sha256"))
        ):
            raise ArchiveError("Invalid object digest")
        if entry.get("key") != f"objects/sha256/{entry['sha256']}":
            raise ArchiveError("Unsafe object path in capture manifest")
        if not 0 < integer(entry.get("bytes")) <= MAX_FILE_BYTES:
            raise ArchiveError("Invalid object size")
    for key in ("report", "b50"):
        if manifest.get(key) is not None and manifest[key] not in files.values():
            raise ArchiveError("Presentation reference is not in the capture manifest")
    if manifest["promote"] and manifest.get("report") is None:
        raise ArchiveError("Cannot promote a capture without its validated report")
    if not isinstance(manifest.get("b50Provenance"), str):
        raise ArchiveError("Missing B50 provenance")
    canonical(manifest)  # Reject non-finite or non-serializable values anywhere.


def read_bundle(directory: Path) -> CaptureBundle:
    manifest = load_json((directory / "manifest.json").read_bytes())
    validate_manifest(manifest)
    objects = {}
    for entry in manifest["files"].values():
        key = entry.get("key", "")
        if key != f"objects/sha256/{entry.get('sha256')}" or not re.fullmatch(
            r"objects/sha256/[0-9a-f]{64}", key
        ):
            raise ArchiveError("Unsafe object path in capture manifest")
        path = directory / key
        if path.is_symlink() or path.resolve().is_relative_to(directory.resolve()) is False:
            raise ArchiveError("Unsafe local archive path")
        if path.stat().st_size > MAX_FILE_BYTES:
            raise ArchiveError("Oversized archive object")
        raw = path.read_bytes()
        if len(raw) != entry["bytes"] or sha256(raw) != entry["sha256"]:
            raise ArchiveError("Archive object hash or length mismatch")
        objects[key] = raw
    bundle = CaptureBundle(manifest, objects)
    validate_capture_contents(bundle)
    return bundle


def validate_capture_contents(bundle: CaptureBundle) -> None:
    """Indexed summaries must match retained inputs, not merely self-consistent checksums."""
    manifest = bundle.manifest
    report = load_json(bundle.objects[manifest["files"]["report-input.json"]["key"]])
    metadata = load_json(bundle.objects[manifest["files"]["metadata.json"]["key"]])
    session = report.get("session", {})
    if metadata.get("syncCompleted") is not True:
        raise ArchiveError("Original capture did not complete")
    for key, metadata_key in (
        ("scoreCount", "sessionScoreCount"),
        ("changedPBCount", "changedPBCount"),
    ):
        if manifest[key] != session.get(key) or manifest[key] != metadata.get(metadata_key):
            raise ArchiveError("Manifest count differs from the original capture")
    for phase in ("before", "after"):
        if manifest[phase] != rating_snapshot(report.get(phase)):
            raise ArchiveError("Indexed rating differs from the original capture")
    if manifest["versions"] != report.get("currentNewDisplayVersions"):
        raise ArchiveError("Manifest changed the original game-version assumptions")
    if manifest["delta"] != report.get("delta", {}):
        raise ArchiveError("Manifest changed the original rating delta")
    if manifest["capturedAtMs"] != timestamp(report.get("generatedAt")):
        raise ArchiveError("Manifest changed the original capture timestamp")
    times = [
        integer(s["timeAchieved"]) for s in session["scores"] if s.get("timeAchieved") is not None
    ]
    if (manifest["startMs"], manifest["endMs"], manifest["sortMs"], manifest["cutoffMs"]) != (
        min(times) if times else None,
        max(times) if times else None,
        (
            manifest["capturedAtMs"]
            if report.get("capture", {}).get("source") == "kamaitachi" or not times
            else max(times)
        ),
        session.get("cutoffTimeAchieved"),
    ):
        raise ArchiveError("Manifest changed the original capture interval")
    identity_inputs = {"report": {k: v for k, v in report.items() if k != "generatedAt"}}
    for name in RAW_NAMES[2:]:
        if name in manifest["files"]:
            value = load_json(bundle.objects[manifest["files"][name]["key"]])
            identity_inputs[name] = value.get("body", value)
    expected_hash = sha256(canonical(identity_inputs))
    import_id = metadata.get("importID")
    expected_id = sha256(
        canonical(
            {
                "scope": manifest["scope"],
                "identity": import_id or expected_hash,
                "kind": "import" if import_id else "retained-input",
            }
        )
    )
    if (manifest["inputHash"], manifest["captureID"], manifest["importID"]) != (
        expected_hash,
        expected_id,
        import_id,
    ):
        raise ArchiveError("Manifest identity differs from its retained inputs")
    if manifest.get("report"):
        html = bundle.objects[manifest["report"]["key"]]
        presented = report_data(html)
        for section in ("before", "after", "delta", "session", "capture", "comparison"):
            if any(
                presented.get(section, {}).get(k) != v for k, v in report.get(section, {}).items()
            ):
                raise ArchiveError("Archived presentation changed the retained analysis")
        if presented.get("currentNewDisplayVersions") != manifest["versions"]:
            raise ArchiveError("Archived presentation changed the as-of versions")
        if re.search(rb"<script[^>]+src\s*=", html, re.I):
            raise ArchiveError("Archived presentation includes a parent-page remote script")
