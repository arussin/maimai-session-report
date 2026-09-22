"""Run the report's fictional compatibility corpus against a pinned registry bundle."""

import argparse
import importlib.util
import tempfile
from copy import deepcopy
from pathlib import Path

from maimai_report._party import player_data, public_matching
from maimai_report.contract_vendor import load_bundle, validate_bundle
from maimai_report.fixtures import SCENARIOS, load_scenario
from maimai_report.party import from_documents
from maimai_report.render import enrich_report


def check_bundle(bundle, revision):
    """Execute only the explicitly reviewed bundle in an offline acceptance harness."""
    raw_files = validate_bundle(bundle, revision)
    with tempfile.TemporaryDirectory() as directory:
        modules = {}
        for name in ("player_data", "public_matching"):
            path = Path(directory) / (name + ".py")
            path.write_bytes(raw_files[name + ".py"])
            spec = importlib.util.spec_from_file_location("candidate_" + name, path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            modules[name] = module
        candidate = modules["player_data"]
        for scenario in SCENARIOS:
            report, pbs = load_scenario(scenario)
            data = from_documents(enrich_report(report, pbs), pbs)
            if (
                candidate.validate(deepcopy(data)) != data
                or candidate.encode(data) != player_data.encode(data)
                or candidate.current(data) != player_data.current(data)
                or candidate.merge(data, data) != player_data.merge(data, data)
            ):
                raise ValueError("Player contract changed for synthetic scenario " + scenario)
        profiles = [
            {
                "chart_id": name,
                "song_family": family,
                "source_hash": "a" * 64,
                "version": "challenge-profile-1-experimental",
                "demand": {group: {"measure": value} for group in public_matching.GROUPS},
            }
            for name, family, value in (
                ("anchor", "first", 1),
                ("sibling", "first", 2),
                ("near", "second", 2),
                ("far", "third", 5),
            )
        ]
        # The incomplete profile must never gain a fabricated structural match.
        profiles.append(
            {
                **profiles[0],
                "chart_id": "unknown",
                "song_family": "fourth",
                "demand": {"cadence": {"measure": 2}},
            }
        )
        expected = public_matching.ComparisonIndex(profiles)
        actual = modules["public_matching"].ComparisonIndex(profiles)
        for left in profiles:
            identifier = left["chart_id"]
            for right in profiles:
                other = right["chart_id"]
                if actual.compare(identifier, other) != expected.compare(
                    identifier, other
                ) or actual.pattern_compare(identifier, other) != expected.pattern_compare(
                    identifier, other
                ):
                    raise ValueError("Public comparison contract changed")
            for patterns in (True, False):
                for eligible in (None, ["near", "unknown"]):
                    if actual.similar(identifier, patterns=patterns, eligible_ids=eligible) != (
                        expected.similar(identifier, patterns=patterns, eligible_ids=eligible)
                    ):
                        raise ValueError("Public ranking contract changed")
    return {"report_scenarios": len(SCENARIOS), "comparison_profiles": len(profiles)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--bundle-sha256", required=True)
    args = parser.parse_args()
    bundle = load_bundle(args.bundle, args.revision, args.bundle_sha256)
    result = check_bundle(bundle, args.revision)
    print(f"Public contracts compatible: {result}")


if __name__ == "__main__":
    main()
