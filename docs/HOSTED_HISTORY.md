# Hosted session history

For a new installation, use the [single-TOML installation guide](INSTALLATION.md).
The shared action generates Worker bindings and handles maintenance; the lower-level
JSON commands and wiring below remain a supported compatibility/architecture reference.


The hosted foundation and dated reader are part of the shared product. New owners
run **Maintain hosted history → verify-fresh** with explicit apply on empty resources;
see [hosted verification and its private evidence](INSTALLATION.md#verify-a-fresh-hosted-installation).
Offline CI exercises the same recovery/cleanup protocol with test doubles. It does
not establish that a real account's credentials, R2 or D1 are configured correctly.

## Owner-managed resources

Each installation uses its own Cloudflare account and private repository. The
existing Worker keeps its current report and B50 as an independent fallback.
History uses a private R2 bucket and D1 index; an independent R2 backup bucket
and recovery D1 prove that history survives the loss of the primary index.
No report data is committed to source. No public buckets, presigned URLs, new
Worker origins, browser APIs, fonts, analytics or payment scripts are added.

For the lower-level legacy actions only, copy `deploy/cloudflare/history.example.json` into the private caller and set
the account, names, scope, timezone, existing HTTPS origin and protected prefix.
The configuration contains resource identifiers, never credentials. Provisioning
does not deploy the Worker or change Cloudflare Access. No capture expiration
rules are created. The provider's default cleanup of unfinished multipart uploads
is allowed and left unchanged; enabled rules that expire or transition completed
objects are rejected. Storage and requests are billed under the owner's Cloudflare
plan; backups store a second copy of the retained objects.

GitHub Actions secrets:

| Secret | Purpose |
|---|---|
| `CLOUDFLARE_HISTORY_API_TOKEN` | Account-scoped **D1: Edit** and **Workers R2 Storage: Edit** for resource setup, privacy checks and D1 queries |
| `MAIMAI_HISTORY_R2_ACCESS_KEY_ID` | R2 S3 access key, scoped to the archive and backup buckets |
| `MAIMAI_HISTORY_R2_SECRET_ACCESS_KEY` | Corresponding R2 secret with Object Read & Write for those two buckets |

Keep the existing Worker deployment token separate. Create R2 credentials in
Cloudflare's R2 token panel after creating the named buckets; do not paste secrets
in issues, logs, reports or chat. The writer uses the documented S3 interface via
pinned boto3, including conditional create and paginated listing. It does not
generate public presigned URLs. [R2 authentication](https://developers.cloudflare.com/r2/api/tokens/)
[R2 S3 compatibility](https://developers.cloudflare.com/r2/api/s3/api/)

## Installation and recovery

These commands run in GitHub Actions with the pinned `history` composite action,
or with `python -m pip install '.[history]'`. A workstation is not needed for
production installation, writing, reading, backups or repair.

```sh
# Read and display the exact resource plan. No network or credentials needed.
python -m maimai_report.history setup --config cloudflare/history.json

# Create only missing resources; verify public domains and lifecycle rules;
# migrate the two named databases. Never delete/reconfigure existing resources.
python -m maimai_report.history setup --config cloudflare/history.json \
  --apply --output output/history.generated.json

# Prepare an already completed capture; never starts an import.
python -m maimai_report.history prepare output/capture output/bundle \
  --scope my-installation:maimaidx --timezone UTC \
  --source-id original-run-123 --renderer-commit FULL_CANONICAL_COMMIT_SHA \
  --rendered-html output/capture/maimai-report.html --promote
python -m maimai_report.history archive output/bundle \
  --config output/history.generated.json

# Full hosted backup, then index reconstruction directly from the independent
# hosted backup. The normal archive command backs up only its own capture.
python -m maimai_report.history backup --config output/history.generated.json
python -m maimai_report.history rebuild --recovery --config output/history.generated.json
python -m maimai_report.history health --recovery --config output/history.generated.json
```

Use `--promote` only after the caller's existing successful-publication gate, or
when explicitly accepting a retained successful capture for backfill. An empty
capture is always excluded from the visible session list and latest pointer.
An incomplete publication remains retained and can be repaired by rerunning
archival work against its original inputs, with no score sync. Missing original
files are annotated. Do not reconstruct uncaptured visits from PB snapshots.

The setup output includes a binding fragment. Merge its `HISTORY_OBJECTS`,
`HISTORY_DB`, `HISTORY_SCOPE`, `HISTORY_PREFIX` and `HISTORY_ORIGIN` into a staged
Worker configuration. Keep `workers_dev: false`, `preview_urls: false`, and the
existing protected route and security headers. Import `handleHistory` and
`withHistoryNavigation` from the pinned `deploy/cloudflare/src/history.js`.
`handleHistory` handles only `<prefix>history` and selected capture/B50 paths;
other requests fall through to the working static report. Reuse the existing
security-header function. No CSP relaxation is needed.

## Preservation and write protocol

R2 stores original bytes under content hashes, the first manifest under
`captures/<id>/manifest.json`, every source variant under `sources/<hash>.json`,
and the first accepted complete publication under `published.json`. Conditional
S3 creates prevent overwriting existing bytes. A conflicting upstream import ID
fails closed. Old captures without an upstream import ID use a normalized input
hash; regenerated timestamps and workflow retries do not create extra sessions.
Raw envelopes retain score IDs and duplicate-looking attempts unchanged. New
sync metadata adds the existing upstream import ID without changing the import
sequence, recent-score cutoff or any rating calculation.

The D1 schema has captures, before/after rating snapshots, latest state and a
migration ledger. HTML, raw data and B50 stay in R2. Objects are verified before
SQL staging. A trigger finalizes readiness and latest selection atomically;
partially indexed captures are invisible. Finalized indexed values are immutable.
The migration keeps trigger `BEGIN`/`END` on separate lines and avoids a nested
`CASE ... END` in the completeness check so the hosted D1 statement parser can
apply the same rule verified locally.
Original pool arrays, plays, PB changes, timing, targets and model assumptions
remain in each capture's four-view report. Re-rendering validates that retained
analytical fields and as-of versions did not change. Original HTML remains stored
as evidence; only validated presentation HTML is served.

The hosted backup is portable: standard JSON manifests and content-addressed
objects, without a provider-specific data encoding. `rebuild` reconstructs D1
from published manifests and verifies every original object. To restore into
another account, copy these objects privately with an S3 client, configure that
account's scope/resources, apply the migration, and run `rebuild`. Full SQL exports
and a cross-account transfer wizard are follow-up conveniences, not required for
reconstructing the index. Rebuilding never reads a local historical database.

## Verification and launch gates

Run canonical Python, adapter and browser CI. Tests include duplicate/empty/
incomplete captures, interrupted writes, checksum conflicts, independent backup
reconstruction, D1/R2 bindings, cursor pagination, selected B50 bytes, four-view
navigation, keyboard access and the isolated checkout container.

Before enabling history in production, use synthetic data to verify a fresh
hosted install and restore in the recovery database, then verify the retained
private backfill. Confirm signed-out requests to history, selected reports and
B50 are blocked by Access. Confirm r2.dev/custom bucket domains and Worker preview
URLs are disabled. Verify the real reader in a browser under the protected route.
Payment tests cover only the checkout container; never submit a payment.

Rollback keeps the existing static Worker entry point and its retained report/B50.
Disable history integration and redeploy that known-good static build without
deleting R2 or D1. The separate archive writer can continue retaining future
captures. Do not run another score import to repair an archival failure.

First release intentionally has no cross-session chart search, visit splitting,
comparative coaching or retroactive rating recalculation. Existing captures and
their full reports are the source for future indexing work.
