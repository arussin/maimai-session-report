"""Pin the small upstream public interfaces without a runtime network dependency."""

import argparse
import hashlib
import json
import re
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--source", type=Path, required=True)
parser.add_argument("--revision", help="Reviewed full upstream commit SHA for provenance")
args = parser.parse_args()
if args.revision and not re.fullmatch(r"[a-f0-9]{40}", args.revision):
    parser.error("--revision requires a full lowercase commit SHA")
source = args.source.resolve() / "src/maimai_intelligence"
root = Path(__file__).resolve().parents[1] / "src/maimai_report"
destination = root / "_party"
destination.mkdir(exist_ok=True)
(destination / "__init__.py").write_text(
    '"""Pinned public maimai.party interfaces; see PROVENANCE.json."""\n'
)
provenance = {
    "upstream": "https://github.com/arussin/maimai-chart-browser",
    "api_version": 1,
    "canonical_text": "UTF-8 with LF line endings",
    "license": "MIT",
    "files": {},
}
if args.revision:
    provenance["upstream_revision"] = args.revision
for name in ("player_data.py", "public_matching.py"):
    raw = (source / name).read_text("utf-8").encode("utf-8")
    (destination / name).write_bytes(raw)
    provenance["files"][name] = hashlib.sha256(raw).hexdigest()
for name in ("site-brand.html", "site-brand.css"):
    raw = (source / "assets" / name).read_text("utf-8").encode("utf-8")
    (root / "assets" / ("party-" + name)).write_bytes(raw)
    provenance["files"][name] = hashlib.sha256(raw).hexdigest()
(destination / "LICENSE").write_bytes((args.source / "LICENSE").read_text("utf-8").encode("utf-8"))
(destination / "PROVENANCE.json").write_text(json.dumps(provenance, indent=2) + "\n")
print("Pinned public player format, comparison interface and original wordmark")
