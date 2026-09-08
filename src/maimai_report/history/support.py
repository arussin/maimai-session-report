"""Package the existing optional checkout for the history index at build time."""

from __future__ import annotations

from importlib import resources

from maimai_report.render import ASSET_PACKAGE, _support_data, json_for_html

from .bundle import report_data


def history_support(report_html: bytes) -> dict[str, str]:
    """Reuse only validated support settings, never scores or player data.

    The caller supplies its retained report when staging the Worker. Both pages
    use the exact same local CSS and lazy iframe controller; no storage read or
    provider request is needed to display the footer.
    """
    support = _support_data(report_data(report_html).get("support"))
    if support is None:
        return {}
    assets = resources.files(ASSET_PACKAGE)
    return {
        "css": assets.joinpath("support.css").read_text(encoding="utf-8"),
        "html": '<script id="report-data" type="application/json">'
        + json_for_html({"support": support})
        + "</script><script>"
        + assets.joinpath("support.js").read_text(encoding="utf-8")
        + "</script>",
    }
