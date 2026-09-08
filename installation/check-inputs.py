"""Validate workflow intent before installing tools, retrieving artifacts or using secrets."""

import os
import re

operation = os.environ.get("INSTANCE_OPERATION", "")
allowed = {
    "validate",
    "plan",
    "setup",
    "preflight",
    "verify-fresh",
    "sync",
    "render",
    "archive",
    "backup",
    "rebuild",
    "health",
    "release",
    "publish",
    "bootstrap",
    "rollback",
}
if operation not in allowed:
    raise SystemExit("Choose a documented installation operation")
if operation != "validate" and os.environ.get("INSTANCE_PRIVATE") != "true":
    raise SystemExit("Private installation operations require a private caller repository")
for key in ("INSTANCE_APPLY", "INSTANCE_PROMOTE", "INSTANCE_RECOVERY"):
    if os.environ.get(key, "false") not in {"true", "false"}:
        raise SystemExit("Operation flags must be true or false")
source_run = os.environ.get("INSTANCE_SOURCE_RUN", "")
if source_run and not re.fullmatch(r"[1-9][0-9]{0,19}", source_run):
    raise SystemExit("Select a numeric retained workflow run ID")
if operation == "sync":
    if source_run or os.environ.get("GITHUB_RUN_ATTEMPT", "1") != "1":
        raise SystemExit("A sync retry cannot start another import; resume from retained inputs")
if operation in {"setup", "verify-fresh", "release", "publish", "bootstrap", "rollback"}:
    if os.environ.get("INSTANCE_APPLY") != "true":
        raise SystemExit("This operation requires explicit apply intent")
if operation in {"render", "archive", "publish", "rollback"} and not source_run:
    raise SystemExit("Select the retained workflow run for this operation")

if os.environ.get("INSTANCE_RECOVERY") == "true" and operation not in {"rebuild", "health"}:
    raise SystemExit("Recovery selects the backup index only for rebuild or health")
if os.environ.get("INSTANCE_PROMOTE") == "true" and operation != "archive":
    raise SystemExit("Promotion applies only to retained archival")

if operation == "verify-fresh" and source_run:
    raise SystemExit("Fresh verification accepts synthetic fixtures only, never a retained capture")
