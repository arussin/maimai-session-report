"""Report-owned destination mapping; envelope validation is registry-owned.

This developer command is excluded from the installed runtime package. Its
validator is an exact, separately pinned copy of the registry authority.
"""

import hashlib
import json
from pathlib import Path

from scripts._contract_tool.contract_bundle import (  # noqa: F401 -- developer API re-exports
    FILES,
    SCHEMA,
    UPSTREAM,
    canonical,
    export_bundle,
    load_bundle,
    validate_bundle,
)

TARGETS = {
    "player_data.py": "_party/player_data.py",
    "public_matching.py": "_party/public_matching.py",
    "site-brand.html": "assets/party-site-brand.html",
    "site-brand.css": "assets/party-site-brand.css",
    "LICENSE": "_party/LICENSE",
}


def vendor_bundle(bundle: dict, revision: str, destination: Path, *, check: bool = False) -> None:
    raw_files = validate_bundle(bundle, revision)
    if check:
        provenance = json.loads((destination / "_party/PROVENANCE.json").read_text("utf-8"))
        if provenance.get("upstream_revision") != revision:
            raise ValueError("Vendored revision differs from the reviewed contract")
        for name, raw in raw_files.items():
            # Existing source is checked out with platform line endings; normalize only
            # this comparison. Exported provenance always hashes exact committed bytes.
            current = (destination / TARGETS[name]).read_bytes().replace(b"\r\n", b"\n")
            if current != raw.replace(b"\r\n", b"\n"):
                raise ValueError("Vendored file differs from its exact source revision: " + name)
        return
    # All payloads and paths are validated before any file is replaced. Source is
    # ordinary reviewable code, never a runtime refresh or an automatic copyback.
    for name, raw in raw_files.items():
        target = destination / TARGETS[name]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    provenance = {
        "upstream": UPSTREAM,
        "api_version": 1,
        "canonical_text": "UTF-8 with LF line endings",
        "license": "MIT",
        "upstream_revision": revision,
        "files": {
            name: hashlib.sha256(raw).hexdigest()
            for name, raw in raw_files.items()
            if name != "LICENSE"
        },
        "contract_bundle_sha256": hashlib.sha256(canonical(bundle)).hexdigest(),
    }
    (destination / "_party/PROVENANCE.json").write_text(
        json.dumps(provenance, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    (destination / "_party/__init__.py").write_text(
        '"""Pinned public maimai.party interfaces; see PROVENANCE.json."""\n',
        encoding="utf-8",
        newline="\n",
    )
