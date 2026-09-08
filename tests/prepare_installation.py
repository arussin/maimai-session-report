"""Generate two fictional staged installations for the real Worker/browser tests."""

import json
import shutil
import sqlite3
import zipfile
from pathlib import Path

from maimai_report.history.storage import migration_sql
from maimai_report.installation.config import validate_workflow_pins
from maimai_report.installation.deployment import stage
from maimai_report.installation.operations import render_capture
from scripts.package_installation import package
from tests.installation_fixture import ROOT, WEBP, capture, instance_file


def create(destination: Path):
    if destination.exists():
        shutil.rmtree(destination)
    package(destination / "installation.zip", "a" * 40)
    with zipfile.ZipFile(destination / "installation.zip") as archive:
        archive.extractall(destination / "package")
    validate_workflow_pins(destination / "package/.github/workflows")
    template = (destination / "package/instance.toml").read_text()
    for owner in ("alpha", "beta"):
        config = destination / owner / "instance.toml"
        instance = instance_file(config, owner=owner, template=template)
        source = destination / owner / "capture"
        capture(source, instance)
        render_capture(instance, source)
        stage(
            instance,
            destination / owner / "staged",
            ROOT,
            (source / "maimai-report.html").read_bytes(),
            WEBP,
        )
        statements, statement = [], ""
        for line in migration_sql().splitlines(keepends=True):
            statement += line
            if sqlite3.complete_statement(statement):
                statements.append(statement)
                statement = ""
        (destination / owner / "schema.json").write_text(json.dumps(statements))


if __name__ == "__main__":
    import sys

    create(Path(sys.argv[1]))
