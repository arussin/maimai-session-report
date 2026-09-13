"""Render fictional official-network-shaped records through the real capture path."""

import runpy
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from maimai_report.capture import capture_existing, make_baseline
from maimai_report.config import AppConfig
from maimai_report.io import write_json
from maimai_report.render import enrich_report

# Resolve the test helper independently of whether the project root is on sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
try:
    helpers = runpy.run_path(str(Path(__file__).parents[1] / "test_capture.py"))
finally:
    sys.path.pop(0)
Reader, NOW, BEFORE = (helpers[key] for key in ("Reader", "NOW", "BEFORE"))
config = AppConfig(username="test-player", current_version_display_names=("Current",))


def generate(save):
    for name in ("kama-missing", "kama-partial", "kama-snapshot", "kama-lamp"):
        reader = Reader(150 if name == "kama-missing" else 3)
        for record in reader.session["body"]["scores"]:
            record["scoreData"].pop("optional")
            record["scoreData"].pop("judgements")
        if name == "kama-partial":
            reader.session["body"]["scores"][0]["scoreData"]["optional"] = {"fast": 0, "slow": 4}
        with TemporaryDirectory() as directory:
            baseline = None
            if name == "kama-lamp":
                baseline = Path(directory) / "baseline.json"
                write_json(baseline, make_baseline(config, reader.pbs, BEFORE))
                reader.pbs["body"]["pbs"][0]["scoreData"]["lamp"] = "FULL COMBO"
            selectors = (
                {"pb_snapshot": True}
                if name in {"kama-snapshot", "kama-lamp"}
                else {"session_id": "external-session"}
            )
            result = capture_existing(
                config, client=reader, generated_at=NOW, baseline_path=baseline, **selectors
            )[0]
            save(name, enrich_report(result.report_input, result.after_pbs))
