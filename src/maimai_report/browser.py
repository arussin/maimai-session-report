"""Optional prepared recommendations; normal rendering needs no intelligence package."""

from __future__ import annotations

import datetime as dt
import math
import re
from collections.abc import Mapping
from urllib.parse import urlsplit


def export_browser_bundle(report, after_pbs, mapping, catalog, **options):
    """Export retained inputs using the separately installed, pinned shared engine."""
    try:
        from maimai_intelligence.bundles import export_report_bundle
    except ImportError as exc:
        raise RuntimeError(
            "Browser export requires the optional maimai-chart-intelligence package. "
            "Install its reviewed private release; ordinary reports do not need it."
        ) from exc
    return export_report_bundle(report, after_pbs, mapping, catalog, **options)


def _text(value, name):
    if not isinstance(value, str) or not value or len(value) > 2000:
        raise ValueError(f"Invalid prepared {name}")
    return value


def _number(value, name):
    if value is not None and (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value < 0
    ):
        raise ValueError(f"Invalid prepared {name}")
    return value


def prepared_view(bundle, report, browser_url=None):
    """Consume only a bounded presentation subset; never load a catalog or make requests."""
    if not isinstance(bundle, Mapping) or bundle.get("format") != "maimai-personal":
        raise ValueError("Expected a prepared maimai personal bundle")
    if bundle.get("schema_version") != "1.0.0" or bundle.get("engine_version") != "0.1.0":
        raise ValueError("Unsupported personal bundle or recommendation engine version")
    catalog = bundle.get("catalog", {})
    reference = {
        key: _text(catalog.get(key), "catalog " + key) for key in ("id", "version", "sha256")
    }
    if not re.fullmatch(r"[a-f0-9]{64}", reference["sha256"]):
        raise ValueError("Invalid prepared catalog digest")
    snapshot = _text(bundle.get("snapshot_id"), "snapshot identity")
    if not re.fullmatch(r"[a-f0-9]{64}", snapshot):
        raise ValueError("Invalid prepared snapshot identity")
    cutoff = bundle.get("cutoff_ms")
    if type(cutoff) is not int or not 0 <= cutoff < 8_640_000_000_000_000:
        raise ValueError("Invalid prepared cutoff")
    generated = dt.datetime.fromisoformat(report.get("generatedAt", "").replace("Z", "+00:00"))
    if generated.tzinfo is None or cutoff > int(generated.timestamp() * 1000):
        raise ValueError("Recommendations cannot postdate the retained report")
    browser = None
    if browser_url is not None:
        parsed = urlsplit(browser_url)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError(
                "Browser address must be an HTTPS site without credentials, query or fragment"
            )
        if not re.fullmatch(r"[A-Za-z0-9.-]+(?::[0-9]+)?", parsed.netloc) or not re.fullmatch(
            r"/[A-Za-z0-9_./%~-]*", parsed.path or "/"
        ):
            raise ValueError("Invalid browser host or path")
        browser = {"scheme": "https", "host": parsed.netloc, "path": parsed.path or "/"}
    summaries = bundle.get("chart_summaries")
    cards = bundle.get("recommendations", {}).get("cards")
    if (
        not isinstance(summaries, list)
        or len(summaries) > 60
        or not isinstance(cards, list)
        or len(cards) > 60
    ):
        raise ValueError(
            "Prepared recommendations must contain at most 60 cards and chart summaries"
        )
    by_id = {}
    for chart in summaries:
        if not isinstance(chart, dict):
            raise ValueError("Invalid prepared chart summary")
        cid = _text(chart.get("chart_id"), "chart identity")
        if cid in by_id:
            raise ValueError("Duplicate prepared chart identity")
        by_id[cid] = {
            key: _text(chart.get(key), key) for key in ("title", "difficulty", "format", "level")
        }
    result, seen = [], set()
    for card in cards:
        if not isinstance(card, dict):
            raise ValueError("Invalid prepared card")
        cid = card.get("chart_id")
        if (
            cid not in by_id
            or cid in seen
            or card.get("category") not in {"rating", "practice", "discovery"}
        ):
            raise ValueError("Invalid or duplicate recommendation chart")
        seen.add(cid)
        patterns = card.get("targeted_patterns", [])
        if (
            not isinstance(patterns, list)
            or len(patterns) > 100
            or any(not isinstance(p, str) for p in patterns)
        ):
            raise ValueError("Invalid prepared patterns")
        result.append(
            {
                **by_id[cid],
                "chart_id": cid,
                "category": card["category"],
                "patterns": patterns,
                "target": _number(card.get("target_achievement"), "target"),
                "gain": _number(card.get("gain_if_achieved"), "gain"),
                "previous": _number(card.get("previous_achievement"), "previous result"),
            }
        )
    return {
        "catalog": reference,
        "snapshot_id": snapshot,
        "cutoff_ms": cutoff,
        "engine_version": bundle["engine_version"],
        "browser": browser,
        "cards": result,
    }
