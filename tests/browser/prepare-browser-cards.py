"""Prepare optional cards without installing the shared intelligence package."""

from pathlib import Path

from maimai_report.fixtures import load_scenario
from maimai_report.render import build_html
from tests.test_browser_integration import fixture

root = Path(__file__).parent / "generated"
root.mkdir(exist_ok=True)
report, _payload = load_scenario("complete")
report["support"] = False
bundle = fixture()
for suffix, options in (
    ("links", {"browser_url": "https://charts.example.test/browser/"}),
    ("offline", {}),
):
    (root / f"browser-cards-{suffix}.html").write_text(
        build_html(report, recommendation_bundle=bundle, **options), encoding="utf-8"
    )
