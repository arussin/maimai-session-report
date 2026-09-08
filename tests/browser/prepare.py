"""Generate only fictional browser-test inputs; never inspect a private output path."""

from __future__ import annotations

import base64
import json
from copy import deepcopy
from pathlib import Path

from PIL import Image, ImageDraw

from maimai_report.fixtures import load_scenario
from maimai_report.render import build_html, enrich_report, render_demo

ROOT = Path(__file__).parent / "generated"
ROOT.mkdir(exist_ok=True)
render_demo(ROOT / "demo.html")
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
    report["support"] = {
        "provider": "buy_me_a_coffee",
        "id": "synthetic-test",
        "label": "Buy me a maimai credit",
        "description": "Synthetic checkout container test",
        "color": "#087d90",
    }
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
report["after"]["newPool"].append(
    {
        "songID": "synthetic-target",
        "chartID": "synthetic-target-chart",
        "title": "Synthetic uncounted target",
        "artist": "Test Artist",
        "difficulty": "DX MASTER",
        "level": "15",
        "levelNum": 15.2,
        "percent": 96.2,
        "grade": "AAA",
        "rate": 260,
        "displayVersion": "Synthetic Current",
    }
)
save("presentation", report)
print("Generated four explicitly synthetic browser fixtures and one test-only download.")
