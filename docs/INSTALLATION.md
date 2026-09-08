# Install and maintain your private maimai report

The shared repository owns the report, history reader/writer, B50 adapter, deployment
code, migrations and tests. Each owner keeps a small **private installation
repository** containing seven files: one `instance.toml`, four workflows, a README
and a `.gitignore`. You do not need to write a Worker or run a local database.

`instance.toml` is tracked, non-secret configuration in that private repository.
It contains your player identity, hosted resource names and resolved account,
zone and database IDs. TOML is a file format, not encryption or access control.
Credentials belong only in GitHub Actions secrets. The shared example contains
fictional values; your completed file must never be copied into the product repo.

This guide describes the hosted installation interface. The standalone CLI and older
root, `render/`, `archive/` and `history/` actions remain compatible. Existing owners
should follow [the migration notes](INSTALLATION_MIGRATION.md), not bootstrap again.

**Only want an HTML report?** Use the [five-command demo](../README.md#five-command-offline-demo)
and [local setup](LOCAL.md) instead. This guide is for owners who want a continuing
protected website and hosted history; it requires configuring accounts, credentials
and a hostname. You can add it after you have a local report working.

## Requirements and installation files

- A private GitHub repository with Actions enabled. Create a `production`
  Environment for release/history jobs; configure available approval rules to suit
  your GitHub plan. Refresh remains an explicit manual operation.
- A Cloudflare account with Workers, R2 and D1 activated, plus a proxied hostname
  in a zone you control. Account activation, billing acceptance, DNS, Access login
  and tokens are owner steps; this project does not automate them.
- A Cloudflare Access application protecting your complete report prefix, including
  the bare prefix, history and downloads. Test it signed out before publishing.
- A working Kamaitachi/MYT integration if you want to capture new sessions. See
  the [account prerequisites](../README.md#account-and-myt-prerequisites).
- GitHub-hosted Linux runners use Python 3.13 and Node 22. Local report generation
  supports Python 3.11+. R2 operations install the pinned `history` extra; jacket
  preparation uses the `artwork` extra. The optional B50 adapter uses pinned
  Tomomai and pnpm dependencies.

Use the installation ZIP and SHA-256 checksum if attached to the selected
release, or download `maimai-installation-package` from its successful CI
run. From a source checkout whose CI passed,
`git rev-parse HEAD` prints the full SHA to use when building the same package:

```console
python scripts/package_installation.py --commit FULL_40_CHARACTER_CORE_SHA --output dist/maimai-installation.zip
```

Use the full tested commit SHA, not a branch name.
Extract the ZIP at the root of your new private repository, including its
`.github` directory, then commit those seven files. Do not use GitHub's repository
"Use this template" feature on the product repository: that would copy the entire
product instead of the small installation package.

Commit the workflows to the new installation's default branch before trying its
manual operations. GitHub requires a `workflow_dispatch` workflow on that branch;
adding it only to a new PR does not make **Run workflow** available.
See [GitHub's manual workflow instructions](https://docs.github.com/actions/managing-workflow-runs/manually-running-a-workflow).

All four workflows use the same full core SHA. There is no second version lockfile,
custom updater, or generated configuration to maintain. The product code may be
public while your installation repository stays private. If the selected product
version is still private, its action-sharing settings restrict who can use it. See
[GitHub's action-sharing settings](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/enabling-features-for-your-repository/managing-github-actions-settings-for-a-repository).

## First setup

1. Fill in the commented `instance.toml`. Choose unique resource names and a
   stable history scope. Enter exact current-version aliases from your chart data;
   there is deliberately no guessed current maimai version.
2. Configure Access for the whole hostname/prefix. The Worker rejects other
   origins, disables `workers.dev` and preview URLs, and uses strict private
   headers. These settings supplement Access; they do not replace it.
3. Add the secrets below. Initially the management token is enough for storage
   setup. R2 object credentials can be created after the two named buckets exist.
4. Run **Validate installation**. This is offline, needs no secrets, and checks
   configuration and all four pins. Blank IDs are allowed only while configuring.
5. Run **Maintain hosted history → plan**. Download its private operation artifact
   and inspect `plan-result.json`: exactly two private buckets and two databases.
   Plan performs no network request and changes nothing.
6. Run **setup** with **apply** selected. Setup creates missing named resources,
   checks existing resources, and applies the existing history migration. It
   refuses unrelated database tables, mismatched IDs, public bucket domains and
   lifecycle rules that expire completed captures. Repeating setup is safe after
   a partial failure. Copy the two IDs in `setup-result.toml` into the existing
   `[history]` table; do not add a duplicate table. Commit and validate again.
7. Add R2 credentials scoped to the two buckets. Run **Maintain hosted history →
   verify-fresh**, select **apply**, and leave the other inputs blank/false. Review
   the private verification results described below. This exercises only synthetic captures
   in empty storage and cleans them up. Leave publishing disabled until Access
   is configured and these checks pass.
8. Set `[publishing].enabled = true` and commit. Run **Release or recover retained
   report → bootstrap**, with **apply** selected. This creates an empty
   site. It rejects an existing Worker, occupied route or nonempty archive/index;
   it does not import scores or record a synthetic session.
9. Run **Maintain hosted history → preflight** to check storage credentials,
   migrations, Worker identity/bindings, disabled alternate domains and signed-out
   Access. Then run **Refresh maimai session** when you want one actual import.

The shipped workflows have no schedule and no push-triggered score import.
Validation on a push or PR never imports, provisions or deploys.

## Configuration reference

Keep every table from the shipped example. Unknown fields, credential-shaped
keys, malformed IDs and conflicting legacy environment overrides are rejected.
These are the values in the installation package; standalone `config.toml` has
its own backward-compatible defaults.

| Key | Type / shipped value | Meaning and requirement |
| --- | --- | --- |
| `schema_version` | integer, `1` | Required configuration schema. |
| `kamaitachi.username` | string, blank | Required before sync; one owner per installation. |
| `kamaitachi.game` | string, `maimaidx` | Hosted installation supports maimai DX. |
| `kamaitachi.import_type` | string, `api/myt-maimaidx` | The importer configured for your Kamaitachi account. |
| `player.display_name` | string, `Your player name` | Display identity, not a credential. |
| `player.timezone` | IANA string, `UTC` | Session/history display timezone. Preserve it when migrating. |
| `report.current_version_display_names` | string array, empty | Exact as-of aliases; nonempty before sync. Retained renders keep their recorded aliases. |
| `report.output_dir` | relative path, `output` | Private capture artifact directory; no absolute/traversal/source paths. |
| `report.badge_pack` | string, `builtin` | Original embedded 12-tier frames; `plain` omits game frames; a local manifest selects owner artwork. Custom files must be present in the private caller checkout. See [badge packs](BADGES.md). |
| `support.buy_me_a_coffee_id` | string, blank | Blank disables support; otherwise your BMC creator ID. |
| `support.label` | string, `Buy me a maimai credit` | Footer trigger text. |
| `support.description` | string, `Support this maimai report` | Checkout description. |
| `support.color` | hex string, `#5F7FFF` | Checkout accent. |
| `artwork.enabled` | boolean, `true` | Build-time public jacket preparation on explicit sync. Retained render reuses saved jackets without network. |
| `b50.mode` | enum, `optional` | `optional`, `required`, or `disabled`; see below. |
| `actions.artifact_retention_days` | integer, `14` | Capture artifact retention, 1–90 days; R2 history has no automatic expiry. |
| `publishing.enabled` | boolean, `false` | Enables meaningful refresh publication and explicit releases; setup does not change it. |
| `publishing.provider` | string, `cloudflare` | Supported hosted adapter. |
| `cloudflare.account_id` | 32 hex characters, blank | Account owning the Worker, zone and history resources. Required for hosted operations. |
| `cloudflare.zone_id` | 32 hex characters, blank | Zone owning the protected route. |
| `cloudflare.worker_name` | resource name, `maimai-report` | Dedicated Worker; unrelated routes/bindings stop a release. |
| `cloudflare.origin` | HTTPS origin, fictional | No path, credentials, query or port; replace before hosted operations. |
| `cloudflare.prefix` | single segment, `/maimai/` | Protected report path, including trailing slash. Route is derived from it. |
| `history.enabled` | boolean, `true` | Hosted reader/archive integration. Disabled archive jobs safely do no storage work. |
| `history.scope` | stable owner/game string | Never rename an existing archive's identity during migration. |
| `history.bucket` | resource name | Primary immutable R2 archive. |
| `history.backup_bucket` | distinct resource name | Independent hosted R2 copy. |
| `history.database_name` | resource name | Primary rebuildable D1 index. |
| `history.database_id` | UUID, blank | Resolved by explicit setup, then tracked in TOML. |
| `history.recovery_database_name` | distinct resource name | Independent D1 recovery target. |
| `history.recovery_database_id` | distinct UUID, blank | Resolved by setup; must differ from the primary. |

Resource names use lowercase letters, digits and hyphens (3–63 characters).
The scope accepts letters, digits, `_`, `.`, `:`, `-` (up to 160 characters).
Changing an origin, prefix, scope or resource identity is a migration, not a routine
version upgrade. Existing Worker compatibility flags/date and CPU limits are
preserved during a retained release. There is no generated Wrangler file to edit.

## Credentials and their scope

Use these names in **GitHub Actions secrets**. The workflows pass secrets as
composite-action inputs; only the selected sync/maintenance step receives them in
its process environment. Validation, report rendering, B50 dependency installation
and public artwork preparation do not receive account credentials.

| Secret | Used by | Required capabilities |
| --- | --- | --- |
| `KAMAITACHI_API_TOKEN` | Explicit sync only | Existing Kamaitachi API token with the import capability; never a card access code. |
| `CLOUDFLARE_API_TOKEN` | Worker preflight, release, publish, bootstrap, rollback | Account Workers Scripts Edit; zone Workers Routes Edit and Zone Read for the selected account/zone. Management reads also inspect Worker domains/settings/deployments. No DNS or Access writes. |
| `CLOUDFLARE_HISTORY_API_TOKEN` | Storage setup/check/verify-fresh/archive/backup/rebuild/health; retained release/bootstrap checks | Account D1 Edit and Workers R2 Storage Edit for the selected account. Setup creates only configured names. Provider management scopes may be broader than individual resources. |
| `MAIMAI_HISTORY_R2_ACCESS_KEY_ID` | Object checks/verify-fresh/archive/backup/rebuild/health; retained release/bootstrap checks | R2 S3 key scoped to both named buckets. |
| `MAIMAI_HISTORY_R2_SECRET_ACCESS_KEY` | Same R2 operations | Corresponding Object Read & Write credential, including deletion of this verifier's temporary objects. |

Refresh capture/archive jobs need repository-level secrets. Refresh publication
and release/history jobs use `production` and can use identically named Environment
secrets. A key scoped to production buckets does not automatically cover new test
buckets; use the test installation's own credentials. Do not duplicate
ordinary configuration as repository variables or put secrets into TOML, command
arguments, committed `.env` files, screenshots or issues. While creating tokens,
verify current permission labels and available resource restrictions in
[Cloudflare's token documentation](https://developers.cloudflare.com/fundamentals/api/get-started/create-token/)
and [R2 authentication](https://developers.cloudflare.com/r2/api/tokens/).

## Operations, retained retries and downloads

| Workflow / operation | What it does | Starts a score import? |
| --- | --- | --- |
| Validate | Offline settings and common full-SHA pin check | No |
| Refresh | Capture, render, retain, independently archive and publish a meaningful successful build | Once, on a new explicit run |
| History: plan / preflight / health | Plan, credential/privacy checks, or index/object-marker status | No |
| History: setup + apply | Create/reuse named resources and apply the history schema | No |
| History: verify-fresh + apply | Exercise empty hosted resources with temporary synthetic captures, verify recovery, clean up owned fixtures | No |
| History: archive + source run | Resume immutable archival of retained inputs; optional original promotion gate | No |
| History: backup | Verify/copy the primary archive into the backup bucket | No |
| History: rebuild | Reconstruct primary D1 from primary R2; select recovery for backup R2 → recovery D1 | No |
| Release: render + source run | Rebuild HTML from retained inputs; reuse saved B50/jackets, build a missing eligible B50 | No |
| Release: publish + source run + apply | Publish the selected meaningful retained report/B50 | No |
| Release: release + apply | Upgrade Worker code while preserving the current live report and B50 bytes | No |
| Release: bootstrap + apply | Create a first empty, protected site | No |
| Release: rollback + release run + apply | Restore the recorded prior Worker version after identity/drift checks | No |

A failed B50/render step still retains captured inputs, and archival can preserve
that incomplete capture without promoting it. Empty sessions remain archived but
cannot displace the meaningful latest pointer or live fallback. A manual archive's
`promote` flag asserts that the **original** capture's successful build/publication
gate passed; do not set it merely because an archive retry succeeded.

Never use GitHub's rerun button on the sync job to fix rendering, archive or
publication: the new action rejects sync attempts after attempt 1. Choose the
retained original run in the appropriate history/release workflow. Rerendering
produces a new private artifact while preserving original raw inputs and source
identity. Old captures without `render-provenance.json` require their original
40-character renderer commit when archiving/publishing directly. No command tries
to invent missing original visits from a later personal-best snapshot.

Capture artifacts are named `maimai-session-RUN_ID`; operations use
`maimai-operation-RUN_ID-OPERATION`; deployments retain
`maimai-release-RUN_ID` for 90 days. Operation artifacts contain private IDs,
retained HTML, hashes and rollback evidence; keep them private. GitHub artifacts
are retry/inspection material, not the durable history database.

`b50.mode = "optional"` allows incomplete pools and labels an unavailable B50.
`required` preserves the full Old 35/New 15 requirement and prevents publishing
without a complete image. `disabled` skips the optional adapter and keeps the
standalone print control. Existing archived reports download their own captured
image or say it was not retained; they never borrow the latest session's B50.
The B50 wrapper is an optional [separately licensed AGPL component](../adapters/tomomai/README.md).
Song jackets use the existing documented public artwork source at build time;
HTML embeds them. No browser-time jacket API, font CDN or analytics is added.

Support remains a footer-triggered on-page modal on the latest report, selected
historical reports and the history index. The isolated cross-origin BMC iframe
activates lazily; the parent page has no third-party BMC script. Browser tests mock
only the checkout container and never submit payments.

## Hosted backup and recovery

R2 stores original data, checksummed manifests, retained HTML and B50. D1 is a
rebuildable index.
Archive copies each captured object's immutable bytes to the backup bucket.
It does **not** silently rebuild recovery D1 after every session. Run **backup**
then **rebuild** with **recovery** selected, and check **health** with recovery
before a retained-code release that requires both latest pointers to agree.

### Verify a fresh hosted installation

Use **Maintain hosted history → verify-fresh**, with **apply** selected, in a new
private installation whose two buckets and two migrated databases are empty.
Keep source run and renderer inputs blank, and recovery/promotion unchecked.
The action uses its installed full core SHA for the synthetic renderer identity.
It needs only the history-management token and the two R2 credential secrets;
no Kamaitachi or Worker-deployment token is passed to this operation. Publishing
can remain disabled. All execution and durable storage are hosted.

Download `maimai-operation-RUN_ID-verify-fresh`. Require a successful workflow,
`verify-fresh/evidence.json` with `status: passed`, all four cleanup records
verified, and `verify-fresh-result.json` with `syntheticCleanupVerified: true`.
The private `verify-fresh/ownership.json` records the random scope, capture IDs,
object keys and hashes before fixture uploads, so a failed run remains reviewable.

For maintainers who prefer the installed CLI, the equivalent operation is:

```console
maimai-report instance verify-fresh --config /private/path/instance.toml --renderer-commit FULL_40_CHARACTER_CORE_SHA --workdir /private/path/verification --apply
```

This is an explicit hosted test with synthetic writes, not ordinary offline CI.
It refuses nonempty indexes/buckets, uses a unique synthetic scope/object prefix,
checks interruption repair, duplicate handling, incomplete finalization, empty
latest behavior, immutable conflicts and independent recovery, then removes only
its own synthetic records/objects. It does not deploy, import scores or alter
Access. Do not run it against an existing personal archive. Its success cannot
be inferred from local emulation; run it on a new owner's resources before launch.
For an existing-owner migration, use a separate private test installation with
distinct empty resources, not a temporary edit of the production TOML.

If verification fails, inspect the evidence phase and cleanup records before
retrying. Cleanup refuses unknown IDs, unexpected keys or changed object bytes.
A runner cancellation can interrupt cleanup; retain the ownership journal and
review those exact synthetic records before any manual repair. Do not empty a
bucket, delete a database or broaden cleanup to get a green result. The verifier
does not remove provider resources or change migrations, routes, DNS or Access.

For account loss, copy the immutable archive privately using an S3-compatible
client, configure new account resources, apply setup, and rebuild D1 from R2.
The portable manifest format and missing-input rules are in
[Hosted history](HOSTED_HISTORY.md). No local historical database is required.
Removing a workflow or rolling back a Worker does not delete the archive.

## Upgrades and rollback

1. Read the target commit's migration notes and inspect its tests. Update all four
   `uses:` pins together in a private PR; update the README's recorded version too.
   Leave player, scope, resource IDs, origin, prefix and version aliases unchanged.
2. Run validation and render a retained capture for review. Keep the last
   successful private release artifact. Changing the pin does not deploy the Worker;
   deployment requires an explicit release operation.
3. Before **release**, verify both hosted copies and recovery latest state.
   The operation checks live routes, bindings, Access and exact retained bytes,
   saves prior modules/settings/version information, stages the new shared Worker,
   and checks again for concurrent changes before an explicit Wrangler deployment.
4. After deployment, it verifies report/B50 hashes, bindings and privacy settings.
   Review the protected site in a browser. A failed verification is a failed
   release, even if Cloudflare accepted the upload; the private artifact includes
   observed state for recovery.
5. To restore, choose **rollback** and the release run that introduced the change.
   The action checks that no newer unrelated Worker has replaced it and restores
   its recorded prior 100% Worker version. A first bootstrap has no prior version.

[Cloudflare rollback](https://developers.cloudflare.com/workers/versions-and-deployments/rollbacks/)
restores Worker code, not R2/D1 data or deleted resources. Available versions and
resource compatibility constrain it. Storage migrations need their own reviewed
recovery procedure. Do not delete resources or substitute a new sync for rollback.

## Diagnostics and cost controls

Read the failed job and its private artifact first. Validation fails before account
access for invalid values or mixed pins. A 401/403 management error usually means
an absent/expired token or insufficient scope; do not broaden scopes blindly.
Signed-out report access must be an Access login or denial, not a generic redirect.
A deployment blocked by drift means live modules, routes, settings or resources
changed since preparation; inspect that change before trying again.

If a private shared action cannot be downloaded, check action-sharing permission
and that the exact SHA exists. Expired GitHub capture artifacts cannot be repaired
by rerunning an import: recover retained originals from your private R2 archive.
An incomplete B50 failure should be handled by the chosen B50 policy, not fabricated
charts or altered pool math.

Monitor GitHub Actions usage and Cloudflare Worker requests/CPU, D1 reads/writes/
storage and R2 operations/storage. This setup has no scheduler, stores immutable
captures, disables alternate public endpoints and preserves existing Worker CPU
limits. These are operational controls, not an account-wide monetary cap. Check
current [Worker limits](https://developers.cloudflare.com/workers/platform/limits/)
and your Cloudflare billing notifications; a CPU limit does not cap storage or
request charges. Stop new refreshes/publications while investigating unexpected
usage, without deleting the backup needed for recovery.
