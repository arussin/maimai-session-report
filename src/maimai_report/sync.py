"""Explicit one-import synchronization orchestration."""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from .api import KamaitachiClient, validate_score_payload
from .calculations import build_report_input
from .config import AppConfig, get_api_token
from .io import ensure_output_directory, write_json

JSONDict = dict[str, Any]


class SyncClient(Protocol):
    """Narrow client surface used to keep all sync tests offline."""

    def get_pbs(self, username: str, game: str) -> JSONDict: ...

    def get_recent_scores(self, username: str, game: str) -> JSONDict: ...

    def start_import(self, import_type: str) -> str: ...

    def wait_for_import(self, import_id: str) -> None: ...


@dataclass(frozen=True, slots=True)
class SyncResult:
    before_pbs_payload: JSONDict
    before_scores_payload: JSONDict
    after_pbs_payload: JSONDict
    after_scores_payload: JSONDict
    report_input: JSONDict
    metadata: JSONDict

    @property
    def before_pbs(self) -> JSONDict:
        return self.before_pbs_payload

    @property
    def before_scores(self) -> JSONDict:
        return self.before_scores_payload

    @property
    def after_pbs(self) -> JSONDict:
        return self.after_pbs_payload

    @property
    def after_scores(self) -> JSONDict:
        return self.after_scores_payload


def synchronize(
    config: AppConfig,
    *,
    environ: Mapping[str, str] | None = None,
    client: SyncClient | None = None,
    generated_at: dt.datetime | None = None,
) -> SyncResult:
    """Perform one before/import/SSE/after sequence, with no retry or polling."""

    # These checks happen before the first possible client call.
    config.validate(for_network=True)
    token = get_api_token(environ)
    active_client: SyncClient = KamaitachiClient(token) if client is None else client

    before_pbs_payload = active_client.get_pbs(config.username, config.game)
    before_pbs = validate_score_payload(before_pbs_payload, "pbs")

    before_scores_payload = active_client.get_recent_scores(config.username, config.game)
    before_scores = validate_score_payload(before_scores_payload, "scores")

    import_id = active_client.start_import(config.import_type)
    active_client.wait_for_import(import_id)

    after_pbs_payload = active_client.get_pbs(config.username, config.game)
    after_pbs = validate_score_payload(after_pbs_payload, "pbs")

    after_scores_payload = active_client.get_recent_scores(config.username, config.game)
    after_scores = validate_score_payload(after_scores_payload, "scores")

    report_input = build_report_input(
        before_pbs,
        before_scores,
        after_pbs,
        after_scores,
        config.current_version_display_names,
        generated_at=generated_at,
    )
    metadata: JSONDict = {
        "syncCompleted": True,
        "importID": import_id,
        "fetchedAt": report_input["generatedAt"],
        "beforePBCount": report_input["before"]["pbCount"],
        "afterPBCount": report_input["after"]["pbCount"],
        "sessionScoreCount": report_input["session"]["scoreCount"],
        "changedPBCount": report_input["session"]["changedPBCount"],
    }
    return SyncResult(
        before_pbs_payload=before_pbs_payload,
        before_scores_payload=before_scores_payload,
        after_pbs_payload=after_pbs_payload,
        after_scores_payload=after_scores_payload,
        report_input=report_input,
        metadata=metadata,
    )


def write_sync_result(result: SyncResult, output_dir: Path | str) -> dict[str, Path]:
    """Write the audited six private JSON outputs without committing or publishing them."""

    directory = ensure_output_directory(output_dir)
    values: tuple[tuple[str, object], ...] = (
        ("before-pbs.json", result.before_pbs_payload),
        ("after-pbs.json", result.after_pbs_payload),
        ("before-recent-scores.json", result.before_scores_payload),
        ("after-recent-scores.json", result.after_scores_payload),
        ("report-input.json", result.report_input),
        ("metadata.json", result.metadata),
    )
    outputs: dict[str, Path] = {}
    for filename, value in values:
        outputs[filename] = write_json(directory / filename, value)
    return outputs
