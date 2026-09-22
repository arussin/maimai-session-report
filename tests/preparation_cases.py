"""Fictional mapped-catalog, retained-history and artwork characterization inputs."""

from copy import deepcopy

from maimai_report._party import player_data
from maimai_report.fixtures import load_scenario
from maimai_report.fixtures.artwork import demo_jackets
from maimai_report.party import from_documents
from maimai_report.render import enrich_report


def mapped_cases():
    report, pbs = load_scenario("incomplete")
    score = {
        "chartID": "anchor",
        "songID": "anchor",
        "title": "Anchor",
        "artist": "Synthetic",
        "difficulty": "DX MASTER",
        "levelNum": 13,
        "percent": 97,
        "rate": 252,
        "lamp": "CLEAR",
        "displayVersion": "PRiSM",
        "timeAchieved": 1000,
    }
    report.update(
        player={"username": "fixture"},
        generatedAt="2026-08-30T12:00:00Z",
        currentNewDisplayVersions=["PRiSM"],
        capture={"kind": "pb-snapshot"},
    )
    report["session"]["scores"] = [score]
    report["after"].update(old35=[], new15=[score], newPool=[score])
    report = enrich_report(report)
    dataset = from_documents(report, {"pbs": [score]})
    groups = ("cadence", "rhythm", "coordination", "holds", "slides", "spatial")
    rows = []
    refs = {}
    for cid, constant, family in (
        ("anchor", 13, "anchor"),
        ("sibling", 13.1, "anchor"),
        ("harder", 13.3, "other"),
    ):
        rows.append(
            {
                "chart_id": cid,
                "source_hash": "a" * 64,
                "version": "challenge-profile-1-experimental",
                "song_family": family,
                "demand": {g: {"measure": constant} for g in groups},
            }
        )
        refs[cid] = {
            "chart_id": cid,
            "source_hash": "a" * 64,
            "constant": constant,
            "versions": ["prism"],
            "displayVersion": "PRiSM",
            "songID": family,
            "title": cid,
            "artist": "Synthetic",
            "format": "DX",
            "difficulty": "MASTER",
            "level": "13",
        }
    catalog = {
        "catalog_version": "synthetic-pinned-catalog",
        "catalog": rows,
        "provider_mapping": {"charts": refs},
    }
    report["_partyData"] = dataset
    report["_partyCatalog"] = catalog
    jacket = next(iter(demo_jackets(pbs).values()))
    yield "mapped", deepcopy(report), {"other": jacket}
    older = deepcopy(report)
    older["generatedAt"] = "2025-01-01T00:00:00Z"
    old_dataset = from_documents(older, {"pbs": [score]})
    report["_partyData"] = player_data.merge(old_dataset, dataset)
    report["_partyLatestPath"] = "/maimai/party/latest.json"
    yield "retained-hosted", deepcopy(report), {"other": jacket}
    report["_partyEnabled"] = False
    yield "disabled-with-catalog", deepcopy(report), {"other": jacket}
