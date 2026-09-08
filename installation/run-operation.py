"""Execute a selected operation with argument arrays, never interpolated shell code."""

import json
import os
import subprocess
import sys
from pathlib import Path

root = Path(os.environ["INSTANCE_ACTION_PATH"]).resolve().parent
operation = os.environ["INSTANCE_OPERATION"]
base = [sys.executable, "-m", "maimai_report", "instance"]
common = [
    "--config",
    os.environ["INSTANCE_CONFIG"],
    "--source",
    os.environ["INSTANCE_CAPTURE"],
    "--core",
    str(root),
]


def run(name, *extra):
    subprocess.run([*base, name, *common, *extra], check=True)  # noqa: S603 -- fixed CLI plus separate validated arguments


if operation in {"release", "publish", "bootstrap", "rollback"}:
    if os.environ["INSTANCE_APPLY"] != "true":
        raise SystemExit("Explicit deployment intent is required")
    tools = root / "deploy/cloudflare"
    subprocess.run(  # noqa: S603,S607 -- fixed command, committed lockfile
        ["npm", "ci", "--ignore-scripts", "--no-audit", "--no-fund"],  # noqa: S607 -- fixed executable
        cwd=tools,
        check=True,
    )  # noqa: S603,S607 -- fixed command, committed lockfile
    wrangler = ["node", str(tools / "node_modules/wrangler/bin/wrangler.js")]
    if operation == "rollback":
        run("rollback-plan")
        result = json.loads(Path(".maimai/rollback-plan-result.json").read_bytes())
        config = Path(".maimai/rollback-source/release/staged/wrangler.generated.json").resolve()
        subprocess.run(  # noqa: S603 -- validated saved UUID and separate arguments
            [
                *wrangler,
                "rollback",
                result["version"],
                "--config",
                str(config),
                "--message",
                "Restore reviewed retained installation release",
                "--yes",
            ],
            check=True,
        )  # noqa: S603 -- validated saved UUID
        run("verify-rollback")
    else:
        if operation == "bootstrap":
            run("bootstrap")
        elif operation == "publish":
            run("prepare-publish", "--renderer-commit", os.environ.get("INSTANCE_RENDERER", ""))
        else:
            run("prepare-release")
        run("recheck")
        config = Path(".maimai/release/staged/wrangler.generated.json").resolve()
        subprocess.run([*wrangler, "deploy", "--config", str(config)], check=True)  # noqa: S603 -- generated and rechecked private deployment config
        run("verify-release")
else:
    flags = []
    for env_key, flag in (
        ("INSTANCE_APPLY", "--apply"),
        ("INSTANCE_PROMOTE", "--promote"),
        ("INSTANCE_RECOVERY", "--recovery"),
    ):
        if os.environ.get(env_key) == "true":
            flags.append(flag)
    run(
        operation,
        "--renderer-commit",
        os.environ.get("INSTANCE_RENDERER", ""),
        "--source-id",
        "github-run-" + os.environ["INSTANCE_SOURCE_RUN"],
        *flags,
    )
