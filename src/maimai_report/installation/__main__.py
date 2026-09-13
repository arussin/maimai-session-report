"""Configure, build and maintain one private hosted installation."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

from ..errors import MaimaiReportError
from ..history.bundle import ArchiveError, canonical
from . import deployment, operations, verification
from .config import load_instance, validate_workflow_pins


def outputs(values: dict) -> None:
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with Path(path).open("a", encoding="utf-8") as handle:
            for key, value in values.items():
                if isinstance(value, bool):
                    value = str(value).lower()
                if (
                    not re.fullmatch(r"[a-z][a-z0-9_-]*", key)
                    or "\n" in str(value)
                    or "\r" in str(value)
                ):
                    raise ArchiveError("Invalid workflow output")
                handle.write(f"{key}={value}\n")


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument(
        "operation",
        choices=[
            "validate",
            "plan",
            "setup",
            "preflight",
            "verify-fresh",
            "sync",
            "capture",
            "b50-ready",
            "render",
            "inspect",
            "receipt",
            "archive",
            "backup",
            "rebuild",
            "health",
            "stage",
            "prepare-release",
            "prepare-publish",
            "recheck",
            "verify-release",
            "bootstrap",
            "rollback-plan",
            "verify-rollback",
        ],
    )
    result.add_argument("--config", type=Path, default=Path("instance.toml"))
    result.add_argument("--workdir", type=Path, default=Path(".maimai"))
    result.add_argument("--source", type=Path, default=Path("output"))
    result.add_argument("--core", type=Path, default=Path(os.environ.get("MAIMAI_CORE_ROOT", ".")))
    result.add_argument("--source-id", default="retained-review")
    result.add_argument(
        "--session-id", default="", help="Kamaitachi session ID, latest, or pb-snapshot"
    )
    result.add_argument("--baseline", type=Path, help="Saved pre-session baseline.json")
    result.add_argument("--renderer-commit", default="")
    result.add_argument(
        "--apply",
        action="store_true",
        help="Explicitly authorize setup or temporary verification writes",
    )
    result.add_argument(
        "--promote", action="store_true", help="The original publication gate passed"
    )
    result.add_argument("--recovery", action="store_true", help="Use hosted backup and recovery D1")
    result.add_argument(
        "--fetch-artwork", action="store_true", help="Allow build-time public artwork reads"
    )
    result.add_argument("--storage-only", action="store_true")
    result.add_argument("--workflows", type=Path, help="Check the four installed workflow pins")
    return result


def run(args: argparse.Namespace) -> dict:
    instance = load_instance(args.config, operation=args.operation, environ=dict(os.environ))
    if args.operation == "validate":
        revision = validate_workflow_pins(args.workflows) if args.workflows else ""
        outputs(
            {
                "core-revision": revision,
                "history-enabled": instance.history_enabled,
                "publishing-enabled": instance.app.publishing_enabled,
                "b50-mode": instance.b50_mode,
                "retention-days": instance.app.artifact_retention_days,
                "account-id": instance.account_id,
                "display-name": instance.app.display_name,
                "capture-path": str(instance.app.output_dir),
            }
        )
        return {"configurationValid": True, "scoreImportStarted": False, "networkAccessed": False}
    if args.operation in {"plan", "setup", "archive", "backup", "rebuild", "health"}:
        return operations.storage(
            instance,
            args.operation,
            args.workdir,
            source=args.source,
            source_id=args.source_id,
            renderer=args.renderer_commit,
            promote=args.promote,
            recovery=args.recovery,
            apply=args.apply,
        )
    if args.operation == "verify-fresh":
        return verification.verify_fresh(
            instance, args.workdir / "verify-fresh", args.renderer_commit, apply=args.apply
        )
    if args.operation == "preflight":
        return operations.preflight(instance, storage_only=args.storage_only)
    if args.operation == "sync":
        operations.sync(instance, args.source)
        return {"captureSaved": True, "meaningful": operations.meaningful(args.source)}
    if args.operation == "capture":
        operations.capture(instance, args.source, args.session_id, args.baseline)
        return {
            "captureSaved": True,
            "scoreImportStarted": False,
            "meaningful": operations.meaningful(args.source),
        }
    if args.operation == "b50-ready":
        ready = operations.b50_ready(instance, args.source)
        outputs({"ready": ready and not (args.source / "maimai-b50.webp").is_file()})
        return {"b50Ready": ready}
    if args.operation == "render":
        return operations.render_capture(instance, args.source, fetch_artwork=args.fetch_artwork)
    if args.operation == "receipt":
        deployment.check(
            re.fullmatch(r"[0-9a-f]{40}", args.renderer_commit), "Record the exact renderer commit"
        )
        receipt = {
            "schemaVersion": 1,
            "rendererCommit": args.renderer_commit,
            "sourceID": args.source_id,
        }
        (args.source / "render-provenance.json").write_bytes(canonical(receipt))
        return {"renderProvenanceSaved": True}
    if args.operation == "inspect":
        bundle = operations.validate_capture(instance, args.source, args.renderer_commit)
        operations.retained_report_matches(args.source)
        outputs({"meaningful": bundle.manifest["meaningful"], "capture-id": bundle.capture_id})
        return {"meaningful": bundle.manifest["meaningful"], "captureValidated": True}
    if args.operation == "stage":
        b50 = args.source / "maimai-b50.webp"
        return deployment.stage(
            instance,
            args.workdir / "staged",
            args.core,
            (args.source / "maimai-report.html").read_bytes(),
            b50.read_bytes() if b50.is_file() else None,
        )
    if args.operation in {"prepare-release", "prepare-publish"}:
        source = None
        if args.operation == "prepare-publish":
            operations.validate_capture(instance, args.source, args.renderer_commit)
            operations.retained_report_matches(args.source)
            deployment.check(
                operations.meaningful(args.source),
                "An empty capture cannot replace the live report",
            )
            source = args.source
        return deployment.prepare_release(
            instance, args.workdir / "release", args.core, source=source
        )
    if args.operation == "recheck":
        deployment.recheck(instance, args.workdir / "release")
        return {"readyForExplicitDeployment": True}
    if args.operation == "verify-release":
        deployment.verify_release(instance, args.workdir / "release")
        return {"deploymentVerified": True, "scoreImportStarted": False}
    if args.operation == "bootstrap":
        return deployment.bootstrap(instance, args.workdir / "release", args.core)
    if args.operation == "rollback-plan":
        return deployment.rollback_plan(
            instance, args.workdir / "rollback-source/release", args.workdir
        )
    if args.operation == "verify-rollback":
        deployment.verify_rollback(instance, args.workdir)
        return {"rollbackVerified": True, "scoreImportStarted": False}
    raise AssertionError("Unknown installation operation")


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        result = run(args)
        args.workdir.mkdir(parents=True, exist_ok=True)
        (args.workdir / (args.operation + "-result.json")).write_bytes(canonical(result))
        # Reports, resource identifiers and provider response bodies stay in private artifacts.
        print(json.dumps({"operation": args.operation, "completed": True}))
        return 0
    except (MaimaiReportError, ArchiveError) as exc:
        print(f"{args.operation} stopped: {exc}", file=sys.stderr)
        return 1
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(
            f"{args.operation} stopped ({type(exc).__name__}); "
            "inspect the private operation artifact",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
