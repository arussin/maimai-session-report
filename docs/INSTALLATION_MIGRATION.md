# Migration to the reusable installation interface

Use this guide to move an existing installation from the lower-level actions to
the shared `installation` action and one `instance.toml`. The seven-file package
provides four workflows for validation, refresh, history and releases. Migration
preserves rating calculations, target estimates, grade logic, import behavior,
the history schema and capture IDs.

## Existing installation mapping

| Existing setting or implementation | New destination |
| --- | --- |
| Refresh workflow player/game/timezone/version environment settings | `instance.toml`: kamaitachi, player, report |
| Footer BMC environment settings | `instance.toml`: support |
| Publication JSON and history-enabled repository variable | `publishing.enabled` and `history.enabled` in TOML |
| History JSON resource names, scope and resolved IDs | `instance.toml`: history + cloudflare |
| Worker account, route and zone | `instance.toml`: cloudflare; route generated from origin/prefix |
| Handwritten Worker/history wiring and release scripts | Shared `installation` action and `deploy/cloudflare/src/hosted.js` |
| Custom B50 wrapper | Shared optional `adapters/tomomai` wrapper and renderer download-data contract |
| Repeated workflow shell/Python build/archive/release code | Four pinned validate, refresh, history and release workflows |
| GitHub secrets | Existing secret names retained; passed to scoped action inputs |
| Custom recovery/backfill scripts and logs | Keep private until cutover and rollback are verified |

Take values from the actual deployed installation. Do not copy the example IDs or
change scope, route, database IDs, current version assumptions or B50 requirement.
A retained release preserves the existing Worker compatibility settings/CPU limits
and exact meaningful report/B50 bytes. It refuses unexpected bindings/routes,
public alternate domains and disagreement between the two hosted latest copies.

The migration PR must not change a trigger file, run a fresh import, point the
reader at a new archive, or silently replace a meaningful report with an empty
artifact. An existing intentional trigger-file integration may remain in the
private refresh workflow. Fresh template installations remain manual-only.

## Upgrade checklist

1. Review the core and private-caller PRs with their exact full SHA pins. Verify the
   private TOML against the existing source settings and retained report identity.
2. Run Python, adapter and browser CI, including the package's two-owner tests. Test
   retained private data locally. No private fixture or screenshot belongs in CI.
3. For an existing installation, verify its populated primary archive and independent
   backup/recovery index in place. Preserve all resource identities and the meaningful
   live report. A fresh empty installation is a separate bootstrap/distribution test,
   not a prerequisite for this existing-owner migration. Never run `verify-fresh`
   against a personal archive or delete history to make it pass.
4. Merge the installation's pin update when ready to use that version for future
   operations. A pin update does not itself deploy the Worker.
5. Before an explicit retained release, refresh the independent backup/recovery
   index and review signed-out Access, routes, bindings and preserved module hashes.
6. Verify the deployed protected report/history/downloads/support container. Retain
   rollback evidence. Only then retire the private legacy workflow/script copies.

An in-place upgrade and a fresh installation use different verification paths.
For a new owner's empty resources, follow
[fresh installation verification](INSTALLATION.md#verify-a-fresh-hosted-installation).
For an existing archive, keep the data in place and test the upgraded capture path
on the next session you actually want to import.

Legacy root/render/archive/history action entry points remain compatible. The
private caller can keep its existing recovery tools until the new workflow has
passed live verification. New installations need only the packaged workflows.

The `scripts/verify_hosted_installation.py` entry point accepts `instance.toml` and
requires `--apply`. It is for empty resources only. A populated-resource refusal
is a protective stop, not a reason to delete history and try again.

## Licensing and deployment boundaries

A source-code release never changes an existing runner's visibility or pin.
The product's original Python code is MIT-licensed. The
optional Tomomai adapter has its own AGPL-3.0-only notice/license and upstream pin;
it is excluded from the MIT wheel/source package and the seven-file caller ZIP.
Its presence in a repository requires preserving its notice and upstream terms.

The optional renderer's license does not establish redistribution rights to game
artwork. See [artwork provenance and ownership](RATING_ASSETS.md). Installing the
package does not create a host, database resource or score import.
