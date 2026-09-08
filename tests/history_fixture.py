"""Generate a bounded, explicitly fictional archive for real D1/R2 and browser tests."""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

from maimai_report.fixtures import load_scenario
from maimai_report.history.bundle import canonical, prepare_capture
from maimai_report.history.storage import archive, migration_sql
from maimai_report.history.support import history_support
from maimai_report.render import build_html, enrich_report
from tests.test_history import MemoryObjects


class RecordingDatabase:
    def __init__(self):
        self.statements = []

    def query(self, sql, params=()):
        if not sql.startswith("SELECT"):
            self.statements.append({"sql": sql, "params": list(params)})
        return []


def create(destination: Path, count: int = 23) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    objects, database = MemoryObjects(), RecordingDatabase()
    statement = ""
    migrations = []
    for line in migration_sql().splitlines(keepends=True):
        statement += line
        if sqlite3.complete_statement(statement):
            migrations.append(statement)
            statement = ""
    for i in range(count):
        report, pbs = load_scenario("empty" if i == count - 1 else "complete")
        report["player"]["displayName"] = "Synthetic History Player"
        report["support"] = {
            "provider": "buy_me_a_coffee",
            "id": "synthetic-test",
            "label": "Buy me a maimai credit",
            "description": "Synthetic checkout container",
            "color": "#007887",
        }
        # IDs, dates and version labels are deliberately fictional and isolated from real captures.
        for score in report["session"]["scores"]:
            score["timeAchieved"] += i * 86400000
        if i > 16:
            report["currentNewDisplayVersions"] = ["Synthetic rollover version"]
        source = destination / "sources" / str(i)
        source.mkdir(parents=True, exist_ok=True)
        (source / "report-input.json").write_bytes(canonical(report))
        (source / "metadata.json").write_bytes(
            canonical(
                {
                    "syncCompleted": True,
                    "importID": f"synthetic-import-{i}",
                    "sessionScoreCount": report["session"]["scoreCount"],
                    "changedPBCount": report["session"]["changedPBCount"],
                }
            )
        )
        if i != 3:
            (source / "after-pbs.json").write_bytes(canonical(pbs))
        html = build_html(enrich_report(report, pbs)).replace(
            '<body class="clean-checkpoint">',
            '<body class="clean-checkpoint"><aside aria-label="Synthetic fixture" '
            'style="padding:8px 20px;background:#fff1c2;color:#493900;font:14px system-ui">'
            "SYNTHETIC TEST DATA · fictional archive</aside>",
        )
        (source / "maimai-report.html").write_text(html, encoding="utf-8")
        if i % 2:
            # Tiny but valid, explicit test download. No claim that this is song artwork.
            import base64

            (source / "maimai-b50.webp").write_bytes(
                base64.b64decode("UklGRiIAAABXRUJQVlA4IBYAAAAwAQCdASoBAAEADsD+JaQAA3AAAAAA")
            )
        bundle = prepare_capture(
            source,
            scope="synthetic:maimaidx",
            timezone="America/New_York",
            source_id=f"synthetic-{i}",
            renderer_commit="a" * 40,
            rendered_html=source / "maimai-report.html",
            promote=True,
        )
        archive(bundle, objects, database)
    for key, raw in objects.data.items():
        path = destination / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    (destination / "fixture.json").write_text(
        json.dumps(
            {
                "synthetic": True,
                "support": history_support(
                    (destination / "sources/21/maimai-report.html").read_bytes()
                ),
                "migrations": migrations,
                "statements": database.statements,
                "objects": list(objects.data),
                "latestHTML": "sources/21/maimai-report.html",
            }
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    create(parser.parse_args().output)
