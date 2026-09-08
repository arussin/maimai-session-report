"""Explicitly fictional, self-contained installation inputs for offline tests."""

import base64
from pathlib import Path

from maimai_report.fixtures import load_scenario
from maimai_report.history.bundle import canonical
from maimai_report.installation.config import load_instance

ROOT = Path(__file__).resolve().parents[1]
WEBP = base64.b64decode("UklGRiIAAABXRUJQVlA4IBYAAAAwAQCdASoBAAEADsD+JaQAA3AAAAAA")


def instance_file(
    destination: Path, *, owner: str = "alpha", mode: str = "optional", template: str | None = None
):
    text = template or (ROOT / "templates/private-caller/instance.toml").read_text()
    substitutions = {
        'username = ""': f'username = "synthetic-{owner}"',
        'display_name = "Your player name"': f'display_name = "SYNTHETIC {owner.upper()}"',
        "current_version_display_names = []": (
            'current_version_display_names = ["maimai DX Synthetic Current"]'
        ),
        'mode = "optional"': f'mode = "{mode}"',
        "enabled = false": "enabled = true",
        'account_id = ""': 'account_id = "' + "1" * 32 + '"',
        'zone_id = ""': 'zone_id = "' + "2" * 32 + '"',
        'worker_name = "maimai-report"': f'worker_name = "synthetic-{owner}"',
        'origin = "https://report.example.invalid"': f'origin = "https://{owner}.example.invalid"',
        'prefix = "/maimai/"': f'prefix = "/{owner}/"',
        "example-owner:maimaidx": f"synthetic-{owner}:maimaidx",
        "maimai-history-example": f"synthetic-history-{owner}",
        'database_id = ""': 'database_id = "11111111-1111-4111-8111-111111111111"',
        'recovery_database_id = ""': (
            'recovery_database_id = "22222222-2222-4222-8222-222222222222"'
        ),
    }
    # Longer field names first so the primary-ID replacement cannot consume recovery.
    for before in sorted(substitutions, key=len, reverse=True):
        text = text.replace(before, substitutions[before])
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text)
    return load_instance(destination)


def capture(destination: Path, instance, scenario: str = "complete", *, b50: bool = True):
    report, pbs = load_scenario(scenario)
    report["player"]["username"] = instance.app.username
    report["player"]["displayName"] = instance.app.display_name
    metadata = {
        "syncCompleted": True,
        "importID": f"synthetic-{instance.scope}-{scenario}",
        "sessionScoreCount": report["session"]["scoreCount"],
        "changedPBCount": report["session"]["changedPBCount"],
    }
    destination.mkdir(parents=True, exist_ok=True)
    files = {
        "report-input.json": report,
        "after-pbs.json": pbs,
        "before-pbs.json": pbs,
        "metadata.json": metadata,
        "before-recent-scores.json": {"body": {"scores": []}},
        "after-recent-scores.json": {"body": {"scores": report["session"]["scores"]}},
    }
    for name, value in files.items():
        (destination / name).write_bytes(canonical(value))
    if b50:
        (destination / "maimai-b50.webp").write_bytes(WEBP)
    return report
