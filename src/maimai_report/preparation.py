"""Prepare report-owned data before deterministic presentation assembly.

No provider, catalog or asset request is performed by this module.
"""

from __future__ import annotations

import base64
import re
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from ._party import player_data as player_core
from .party_recommendations import prepare as prepare_recommendations
from .player_capture import from_documents
from .report_data import enrich_report_data as enrich_report_data
from .report_data import support_enabled as support_enabled


@dataclass(frozen=True)
class PartyContext:
    """Explicit inputs owned by report export/catalog preparation."""

    dataset: Mapping[str, Any] | None = None
    catalog: Mapping[str, Any] | None = None
    enabled: bool = True
    latest_path: str | None = None

    @classmethod
    def from_legacy(cls, report: dict[str, Any]) -> PartyContext:
        """Compatibility alias; explicit callers supply PartyContext directly."""
        from .compatibility import extract_context

        return cls(*extract_context(report))


@dataclass(frozen=True)
class PreparedReport:
    """A detached presentation model plus its explicit handoff and policy flags."""

    data: dict[str, Any]
    party: dict[str, Any]
    support: bool
    hosted: bool


def prepare_report(
    report: Mapping[str, Any],
    *,
    context: PartyContext | None = None,
    party_enabled: bool | None = None,
    party_latest_path: str | None = None,
) -> PreparedReport:
    """Derive recommendations and handoff data without mutating caller inputs."""
    if not isinstance(report, Mapping):
        raise ValueError("Report must be an object")
    report_data = deepcopy(dict(report))
    if context is None:
        # Preserve the preparation API introduced before explicit caller migration.
        from .compatibility import extract_context

        context = PartyContext(*extract_context(report_data))
    elif any(key.startswith("_party") for key in report_data):
        raise ValueError("Explicit report data must not contain legacy context fields")
    dataset = context.dataset or from_documents(report_data)
    catalog = context.catalog
    prepared_enabled = context.enabled
    enabled = prepared_enabled if party_enabled is None else party_enabled
    if type(enabled) is not bool:
        raise ValueError("Personal handoff must be explicitly enabled or disabled")
    prepared_latest_path = context.latest_path
    party_latest_path = party_latest_path or prepared_latest_path
    if party_latest_path is not None and not re.fullmatch(
        r"/[A-Za-z0-9_-]+/party/latest\.json", party_latest_path
    ):
        raise ValueError("Player data endpoints must stay beneath the protected installation path")
    report_data["partyRecommendations"] = prepare_recommendations(
        dataset, catalog, report_data.get("session", {}).get("scores", [])
    )
    report_data["partyIntegration"] = {
        "enabled": enabled,
        "hosted": bool(enabled and party_latest_path),
    }
    chart_ids = set()

    def collect(value):
        if isinstance(value, dict):
            if isinstance(value.get("chartID"), str):
                chart_ids.add(value["chartID"])
            for child in value.values():
                collect(child)
        elif isinstance(value, list):
            for child in value:
                collect(child)

    collect(report_data)
    mapping = (catalog or {}).get("provider_mapping", {}).get("charts", {})
    party_settings = {
        "enabled": enabled,
        "latestPath": party_latest_path if enabled else None,
        "offer": player_core.offer(dataset) if enabled else None,
        "payload": base64.b64encode(player_core.encode(dataset)).decode() if enabled else None,
        "catalogVersion": (catalog or {}).get("catalog_version"),
        "mapping": {
            cid: {"chart_id": mapping[cid]["chart_id"], "source_hash": mapping[cid]["source_hash"]}
            for cid in chart_ids
            if cid in mapping
        },
    }
    support = support_enabled(report_data.get("support", True))
    report_data["support"] = support
    return PreparedReport(report_data, party_settings, support, bool(enabled and party_latest_path))
