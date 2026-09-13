"""Verified public catalog refresh with an atomic last-valid local cache."""

import hashlib
import json
import re
import urllib.request
from pathlib import Path

from ._party.public_matching import ComparisonIndex
from .io import atomic_write_text

ORIGIN = "https://maimai.party"
MAX_BYTES = 32 * 1024 * 1024


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Public catalog redirects are not accepted")


def fetch(path, maximum):
    if not re.fullmatch(r"manifest\.json|integration/[a-f0-9]{64}\.json", path):
        raise ValueError("Invalid public catalog path")
    request = urllib.request.Request(  # noqa: S310 -- fixed HTTPS origin plus validated public path
        ORIGIN + "/" + path, headers={"User-Agent": "maimai-session-report/party-v1"}
    )
    with urllib.request.build_opener(NoRedirect()).open(request, timeout=10) as response:
        raw = response.read(maximum + 1)
    if len(raw) > maximum:
        raise ValueError("Public catalog exceeds size limit")
    return raw


def validate(data):
    if (
        not isinstance(data, dict)
        or data.get("schema_version") != "maimai-public-integration-1"
        or data.get("matching_version") != 1
        or not isinstance(data.get("catalog_version"), str)
    ):
        raise ValueError("Incompatible public matching catalog")
    profiles = data.get("catalog")
    if not isinstance(profiles, list) or len(profiles) > 50000:
        raise ValueError("Invalid public chart catalog")
    by_id = {c["chart_id"]: c for c in profiles}
    mapping = data.get("provider_mapping")
    if (
        not isinstance(mapping, dict)
        or mapping.get("schema_version") != "provider-mapping-1"
        or mapping.get("provider") != "kamaitachi"
        or mapping.get("game") != "maimaidx"
        or not isinstance(mapping.get("charts"), dict)
    ):
        raise ValueError("Incompatible public provider mapping")
    for ref in mapping["charts"].values():
        if not isinstance(ref, dict):
            raise ValueError("Invalid public chart reference")
        c = by_id.get(ref.get("chart_id"))
        if (
            not c
            or c["source_hash"] != ref.get("source_hash")
            or (c["format"], c["difficulty"].upper()) != (ref.get("format"), ref.get("difficulty"))
        ):
            raise ValueError("Public chart mapping revision mismatch")
    ComparisonIndex(profiles, data.get("analysis"))
    return data


def load(cache, *, refresh=False):
    cache = Path(cache)
    warning = None
    if refresh:
        try:
            manifest = json.loads(fetch("manifest.json", 1024 * 1024))
            entry = next(r for r in manifest["releases"] if r["version"] == manifest["default"])
            ref = entry["integration"]
            if (
                ref["path"] != f"integration/{ref['sha256']}.json"
                or not isinstance(ref["bytes"], int)
                or not 0 < ref["bytes"] <= MAX_BYTES
            ):
                raise ValueError("Invalid integration catalog reference")
            raw = fetch(ref["path"], ref["bytes"])
            if len(raw) != ref["bytes"] or hashlib.sha256(raw).hexdigest() != ref["sha256"]:
                raise ValueError("Public catalog integrity mismatch")
            data = validate(json.loads(raw))
            if data["catalog_version"] != entry["version"]:
                raise ValueError("Public catalog version mismatch")
            envelope = {"sha256": ref["sha256"], "data": raw.decode("utf-8")}
            atomic_write_text(cache, json.dumps(envelope, ensure_ascii=False))
            return data, None
        except (OSError, ValueError, KeyError, IndexError, StopIteration, TypeError):
            warning = (
                "Public chart refresh unavailable; using the last verified catalog if present."
            )
    if cache.is_file():
        if cache.stat().st_size > MAX_BYTES * 2:
            raise ValueError("Public catalog cache exceeds limit")
        envelope = json.loads(cache.read_text("utf-8"))
        raw = envelope["data"].encode("utf-8")
        if hashlib.sha256(raw).hexdigest() != envelope["sha256"]:
            raise ValueError("Cached public catalog integrity mismatch")
        return validate(json.loads(raw)), warning
    return (
        None,
        warning or "No prepared public catalog; exact links and similarity are unavailable.",
    )
