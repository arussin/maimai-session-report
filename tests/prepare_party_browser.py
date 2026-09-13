# ruff: noqa: E402 -- test-only cross-repository imports follow explicit source selection
"""Synthetic cross-repository browser fixture; never used by either application."""

import argparse
import json
import sys
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--party-source", type=Path, required=True)
parser.add_argument("--output", type=Path, default=Path("output/party-browser"))
args = parser.parse_args()
sys.path[:0] = [str(args.party_source / "src"), str(args.party_source)]
from maimai_intelligence.lab import build_lab
from maimai_intelligence.provider_mapping import build_mapping, integration_catalog
from maimai_intelligence.public_release import build_public_release
from maimai_intelligence.snapshots import canonical

from maimai_report._party import player_data as core
from maimai_report.fixtures import load_scenario
from maimai_report.party import from_documents
from maimai_report.render import build_html, enrich_report
from tests.lab_fixture import write_package

out = args.output.resolve()
out.mkdir(parents=True, exist_ok=True)
package = write_package(out / "package", grouped=True, constants=True)
page = build_lab(package, out / "lab", catalog_version="player-fixture-1")
manifest = json.loads((page.parent / "manifest.json").read_bytes())
entry = manifest["releases"][0]
data = json.loads((page.parent / entry["path"]).read_bytes())
c = data["catalog"][0]
provider = "synthetic-personal-chart"
mapping = build_mapping(
    data["catalog"],
    [
        {
            "chartID": provider,
            "songID": "synthetic-personal-song",
            "difficulty": ("DX " if c["format"] == "DX" else "") + c["difficulty"],
            "levelNum": 13,
            "level": "13",
            "data": {"displayVersion": "PRiSM"},
            "versions": ["prism"],
        }
    ],
    [{"id": "synthetic-personal-song", "title": c["title"], "artist": c["artist"]}],
)
data["provider_mapping"] = mapping
import hashlib

raw = canonical(data)
digest = hashlib.sha256(raw).hexdigest()
entry.update(path=f"catalogs/{digest}.json", sha256=digest)
(page.parent / entry["path"]).write_bytes(raw)
integration = integration_catalog(data, entry["version"])
raw = canonical(integration)
digest = hashlib.sha256(raw).hexdigest()
entry["integration"] = {"path": f"integration/{digest}.json", "sha256": digest, "bytes": len(raw)}
(page.parent / entry["integration"]["path"]).write_bytes(raw)
(page.parent / "manifest.json").write_bytes(canonical(manifest))
build_public_release(page.parent, out / "site")
report, payload = load_scenario("complete")
report = enrich_report(report, payload)
row = {
    **report["session"]["scores"][0],
    "chartID": provider,
    "songID": "synthetic-personal-song",
    "title": c["title"],
    "artist": c["artist"],
    "difficulty": ("DX " if c["format"] == "DX" else "") + c["difficulty"],
    "levelNum": 13,
    "percent": 98.25,
    "rate": 259,
    "grade": "S+",
    "lamp": "CLEAR",
    "scoreID": "synthetic-play-1",
}


def player(when, achievement, username="synthetic-player"):
    score = {**row, "percent": achievement, "grade": "SS" if achievement >= 99 else "S+"}
    model = {
        "player": {"username": username, "displayName": "Synthetic Player"},
        "generatedAt": when,
        "currentNewDisplayVersions": ["PRiSM"],
        "after": {"old35": [score]},
        "session": {"scores": [score]},
        "capture": {"kind": "session", "sessionID": "synthetic-session-1"},
    }
    return from_documents(model)


old = player("2026-08-20T12:00:00Z", 98.25)
new = player("2026-08-30T12:00:00Z", 99.2)
for name, value in [
    ("player", old),
    ("newer", new),
    ("different", player("2026-08-30T12:00:00Z", 99.2, "another-player")),
]:
    core.write(out / (name + ".maimai.json.gz"), value)
report["_partyData"] = old
report["_partyCatalog"] = integration
report["session"]["scores"][0] = row
(out / "local.html").write_text(build_html(report), encoding="utf-8")
(out / "hosted.html").write_text(
    build_html(report, party_latest_path="/private/party/latest.json"), encoding="utf-8"
)
(out / "disabled.html").write_text(build_html(report, party_enabled=False), encoding="utf-8")
report["_partyData"] = player("2026-08-30T12:00:00Z", 99.2, "another-player")
(out / "different.html").write_text(build_html(report), encoding="utf-8")
(out / "expected.json").write_bytes(
    canonical(
        {
            "provider": provider,
            "chart": c["chart_id"],
            "version": entry["version"],
            "revision": old["revision"],
            "offer": core.offer(old),
            "newOffer": core.offer(new),
            "newHash": hashlib.sha256(core.encode(new)).hexdigest(),
            "newBytes": len(core.encode(new)),
        }
    )
)
print("Synthetic browser fixture ready:", out)
