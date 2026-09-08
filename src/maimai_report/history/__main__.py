"""Hosted history CLI. These commands never import or contact Kamaitachi."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .bundle import ArchiveError, prepare_capture, read_bundle
from .cloudflare import D1, R2, Cloudflare, required
from .setup import (
    bindings,
    config_file,
    provision,
    resource_plan,
    save_config,
    verify_private_bucket,
)
from .storage import archive, backup, backup_capture, rebuild


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prepare = sub.add_parser(
        "prepare", help="Validate retained inputs into a portable upload bundle"
    )
    prepare.add_argument("source", type=Path)
    prepare.add_argument("output", type=Path)
    for name in ("scope", "timezone", "source-id", "renderer-commit"):
        prepare.add_argument("--" + name, required=True)
    prepare.add_argument("--rendered-html", type=Path)
    prepare.add_argument("--retained-b50", type=Path)
    prepare.add_argument("--b50-provenance")
    prepare.add_argument("--source-revision")
    prepare.add_argument(
        "--promote", action="store_true", help="The original publication gate passed"
    )
    for name in ("setup", "archive", "rebuild", "backup", "health"):
        item = sub.add_parser(name)
        item.add_argument("--config", type=Path, required=True)
        if name == "setup":
            item.add_argument("--apply", action="store_true")
            item.add_argument("--output", type=Path)
        elif name == "archive":
            item.add_argument("bundle", type=Path)
        elif name in ("rebuild", "health"):
            item.add_argument(
                "--recovery",
                action="store_true",
                help="Use the independent backup bucket and recovery D1",
            )
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            values = vars(args).copy()
            source, output = values.pop("source"), values.pop("output")
            values.pop("command")
            bundle = prepare_capture(source, **values)
            bundle.write(output)
            result = {
                "captureID": bundle.capture_id,
                "meaningful": bundle.manifest["meaningful"],
                "missing": bundle.manifest["missing"],
                "objects": len(bundle.objects),
            }
        else:
            config = config_file(args.config)
            if args.command == "setup" and not args.apply:
                print(json.dumps(resource_plan(config), indent=2))
                return 0
            api = Cloudflare(
                config["accountId"], required(os.environ, "CLOUDFLARE_HISTORY_API_TOKEN")
            )
            if args.command == "setup":
                if args.output is None:
                    raise ArchiveError("Supply --output for the provisioned configuration")
                configured = provision(api, config)
                save_config(args.output, configured)
                save_config(
                    args.output.with_name("history-bindings.generated.json"), bindings(configured)
                )
                result = {"resourcesReady": True, "workerDeployed": False}
            else:
                recovery = getattr(args, "recovery", False)
                bucket = config["backupBucket" if recovery else "bucket"]
                database_id = config.get("recoveryDatabaseId" if recovery else "databaseId", "")
                verify_private_bucket(api, bucket)
                objects = R2(config["accountId"], bucket)
                database = D1(api, database_id)
                if args.command == "archive":
                    bundle = read_bundle(args.bundle)
                    if bundle.manifest["scope"] != config["scope"]:
                        raise ArchiveError("Bundle belongs to another installation")
                    result = archive(bundle, objects, database)
                    verify_private_bucket(api, config["backupBucket"])
                    result["backup"] = backup_capture(
                        objects,
                        R2(config["accountId"], config["backupBucket"]),
                        config["scope"],
                        bundle.capture_id,
                    )
                elif args.command == "rebuild":
                    result = rebuild(objects, database, config["scope"])
                elif args.command == "backup":
                    verify_private_bucket(api, config["backupBucket"])
                    target = R2(config["accountId"], config["backupBucket"])
                    result = backup(objects, target, config["scope"])
                else:
                    result = {
                        "index": database.query(
                            "SELECT state,meaningful,COUNT(*) count FROM captures "
                            "WHERE scope=? GROUP BY state,meaningful",
                            (config["scope"],),
                        ),
                        "latest": database.query(
                            "SELECT latest_id FROM archive_state WHERE scope=?", (config["scope"],)
                        ),
                        "privateBucketVerified": True,
                        "archiveMarkerPresent": objects.get("installation.json") is not None,
                    }
        print(json.dumps(result, indent=2))
        return 0
    except (ArchiveError, OSError) as exc:
        parser.exit(1, f"History operation stopped: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
