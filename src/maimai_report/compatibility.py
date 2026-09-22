"""Legacy dictionary adapters. New producers pass explicit preparation context.

Only this module knows the historical in-process keys. These facades preserve
existing integrations while detached report data carries no hidden context.
"""

from collections.abc import Mapping, Sequence
from copy import deepcopy
from typing import Any


def extract_context(report):
    return (
        report.pop("_partyData", None),
        report.pop("_partyCatalog", None),
        report.pop("_partyEnabled", True),
        report.pop("_partyLatestPath", None),
    )


def enrich_report(
    report: dict[str, Any],
    after_payload: dict[str, Any] | None = None,
    *,
    player: Mapping[str, str] | None = None,
    current_version_display_names: Sequence[str] | None = None,
    support: bool | None = None,
) -> dict[str, Any]:
    from .player_capture import from_documents
    from .report_data import enrich_report_data

    result = enrich_report_data(
        report,
        after_payload,
        player=player,
        current_version_display_names=current_version_display_names,
        support=support,
    )
    result["_partyData"] = from_documents(result, after_payload)
    return result


def prepare_player(report, *, source=None, history=(), player_file=None):
    from .player_capture import prepare_dataset

    result = prepare_dataset(
        report,
        source=source,
        history=history,
        player_file=player_file,
        dataset=report.get("_partyData"),
    )
    report["_partyData"] = result
    return result


def artwork_data(report):
    """Retain the old dictionary artwork API without affecting explicit producers."""
    if (
        report.get("partyRecommendations") is None
        and report.get("_partyData")
        and report.get("_partyCatalog")
    ):
        from .party_recommendations import prepare

        report = deepcopy(report)
        report["partyRecommendations"] = prepare(
            report["_partyData"],
            report["_partyCatalog"],
            report.get("session", {}).get("scores", []),
        )
    return report
