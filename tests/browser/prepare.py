"""Generate only fictional browser-test inputs; never inspect a private output path."""

from __future__ import annotations

import base64
import hashlib
import json
import runpy
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image, ImageDraw

from maimai_report.badges import export_badge_pack
from maimai_report.fixtures import load_scenario
from maimai_report.fixtures.synthetic import CURRENT_VERSION, _raw_record
from maimai_report.party_recommendations import rating
from maimai_report.render import build_html, enrich_report, render_demo

ROOT = Path(__file__).parent / "generated"
ROOT.mkdir(exist_ok=True)
render_demo(ROOT / "demo.html")
render_demo(ROOT / "sealed-demo.html", support=False)
with TemporaryDirectory() as directory:
    pack = export_badge_pack(Path(directory) / "pack")
    render_demo(ROOT / "custom-badges.html", badge_pack=pack)
image = Image.new("RGB", (400, 240), "#e4f7f9")
ImageDraw.Draw(image).text((30, 90), "SYNTHETIC B50 DOWNLOAD TEST", fill="#183c42")
image.save(ROOT / "synthetic-b50.webp", format="WEBP", lossless=True)
(ROOT / "b50.webp").write_bytes((ROOT / "synthetic-b50.webp").read_bytes())
art = (
    "data:image/webp;base64,"
    + base64.b64encode((ROOT / "synthetic-b50.webp").read_bytes()).decode()
)


def save(name: str, report: dict) -> None:
    report = deepcopy(report)
    report["player"]["displayName"] = "Synthetic Test Player"
    report["support"] = True
    html = build_html(report, jackets={"synthetic-song-old-00": art}, b50_path="b50.webp")
    html = html.replace(
        '<body class="clean-checkpoint">',
        '<body class="clean-checkpoint"><aside aria-label="Synthetic fixture" '
        'style="padding:8px 16px;background:#fff3cf;color:#493300;font-size:14px">'
        "SYNTHETIC TEST DATA · fictional scores and test artwork</aside>",
    )
    (ROOT / f"{name}.html").write_text(html, encoding="utf-8")
    (ROOT / f"{name}.json").write_text(json.dumps(report), encoding="utf-8")


for scenario in ("complete", "empty", "incomplete"):
    source, pbs = load_scenario(scenario)
    save(scenario, enrich_report(source, pbs))

source, pbs = load_scenario("complete")
report = enrich_report(source, pbs)
for item, difficulty, percent, grade in zip(
    report["session"]["scores"][:2],
    ("Advanced", "DX Expert"),
    (98.0, 99.0),
    ("S+", "SS"),
    strict=True,
):
    item.update(
        title="Synthetic same-level song",
        difficulty=difficulty,
        level="9",
        levelNum=9.0,
        percent=percent,
        grade=grade,
        rate=180,
        lamp="FULL COMBO",
    )
report["session"]["scores"][0].update(
    fast=None, slow=None, pcrit=None, perfect=None, great=None, good=None, miss=None
)
# A fictional, uncounted threshold candidate exercises direct target navigation.
target = {
    **report["after"]["newPool"][0],
    "songID": "synthetic-target",
    "chartID": "synthetic-target-chart",
    "title": "Synthetic uncounted target",
    "artist": "Test Artist",
    "difficulty": "DX MASTER",
    "level": "15",
    "levelNum": 15.2,
    "percent": 96.2,
    "grade": "AAA",
    "rate": rating(962000, 152, "CLEAR"),
    "lamp": "CLEAR",
    "displayVersion": CURRENT_VERSION,
}
pb, chart, song = _raw_record(target)
for key, row in (("pbs", pb), ("charts", chart), ("songs", song)):
    pbs["body"][key].append(row)
report = enrich_report(report, pbs)
save("presentation", report)
runpy.run_path(str(Path(__file__).with_name("prepare-score-sort.py")), run_name="__main__")
runpy.run_path(str(Path(__file__).with_name("prepare-kamaitachi.py")))["generate"](save)
print("Generated explicitly synthetic browser fixtures and a test-only download.")

# The preview runner serves only these exact generated fictional bytes.
(ROOT / "preview-manifest.json").write_text(
    json.dumps(
        {
            "schema": "maimai-synthetic-preview-1",
            "files": {
                path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                for path in sorted(ROOT.iterdir())
                if path.is_file() and path.suffix in {".html", ".webp"}
            },
        },
        sort_keys=True,
    ),
    encoding="utf-8",
)
