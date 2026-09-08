# Migration to the reusable installation interface

This change moves owner-independent deployment, B50 and maintenance code into the
shared product. It introduces one validated `instance.toml`, a composite action,
four thin installation workflows and a deterministic seven-file ZIP. It does not
change rating calculations, target estimates, grade logic, score-import semantics,
the history schema, immutable capture IDs, or the approved visual system.

## Existing installation mapping

| Existing setting or implementation | New destination |
| --- | --- |
| Refresh workflow player/game/timezone/version environment settings | `instance.toml`: kamaitachi, player, report |
| Footer BMC environment settings | `instance.toml`: support |
| Publication JSON and history-enabled repository variable | `publishing.enabled` and `history.enabled` in TOML |
| History JSON resource names, scope and resolved IDs | `instance.toml`: history + cloudflare |
| Worker account, route and zone | `instance.toml`: cloudflare; route generated from origin/prefix |
| Handwritten Worker/history wiring and release scripts | Shared `installation` action and `deploy/cloudflare/src/hosted.js` |
| Personal B50 wrapper and literal HTML substitution | Shared optional `adapters/tomomai` wrapper and renderer download-data contract |
| Repeated workflow shell/Python build/archive/release code | Four pinned validate, refresh, history and release workflows |
| GitHub secrets | Existing secret names retained; passed to scoped action inputs |
| Personal recovery/backfill receipts and one-off scripts | Keep private as migration evidence until cutover and rollback are verified |

Take values from the actual deployed installation. Do not copy the example IDs or
change scope, route, database IDs, current version assumptions or B50 requirement.
A retained release preserves the existing Worker compatibility settings/CPU limits
and exact meaningful report/B50 bytes. It refuses unexpected bindings/routes,
public alternate domains and disagreement between the two hosted latest copies.

The migration PR must not change a trigger file, run a fresh import, point the
reader at a new archive, or silently replace a meaningful report with an empty
artifact. An existing intentional trigger-file integration may remain in the
private refresh workflow. Fresh template installations remain manual-only.

## Cutover gates

1. Review the core and private-caller PRs with their exact full SHA pins. Verify the
   private TOML against the existing source settings and retained report identity.
2. Run canonical Python/adapter/browser CI and the package's two-owner tests. Test
   retained private data locally. No private fixture or screenshot belongs in CI.
3. For an existing installation, verify its populated primary archive and independent
   backup/recovery index in place. Preserve all resource identities and the meaningful
   live report. A fresh empty installation is a separate bootstrap/distribution test,
   not a prerequisite for this existing-owner migration. Never run `verify-fresh`
   against a personal archive or delete history to make it pass.
4. Approve merge/live pin changes separately. Merging the caller changes future
   operations, so do not merge it as a casual documentation update.
5. Before an explicit retained release, refresh the independent backup/recovery
   index and review signed-out Access, routes, bindings and preserved module hashes.
6. Verify the deployed protected report/history/downloads/support container. Retain
   rollback evidence. Only then retire the private legacy workflow/script copies.

An in-place release proves the upgrade path with retained real history. It does
not prove new-account provisioning or a fresh import: verify a new owner's empty
resources separately with **Maintain hosted history → verify-fresh** and explicit
apply before claiming the installer is ready for unrelated owners. Review its
private success evidence and all four cleanup records. Exercise the upgraded
capture path on the owner's next explicitly requested session, never by starting
an import solely to test migration.

Legacy root/render/archive/history action entry points remain compatible. The
private caller migration can therefore keep its old manual recovery tools intact
until the new workflow has passed live verification. They are migration evidence,
not files shipped to new owners or a second maintained implementation.

Fresh verification now belongs to the shared package and the existing history
workflow; it adds no fifth workflow, database schema or config file. The standalone
`scripts/verify_hosted_installation.py` entry point accepts `instance.toml` and now
requires `--apply`. An existing private legacy JSON-based verification script is
not replaced by this change. A populated-resource refusal is a protective stop,
not a reason to delete history and try again.

## Public distribution is a separate gate

A source-code release never changes an existing runner's visibility or pin.
This standalone repository has fresh history. A public launch requires a complete
tracked-file and Git-history privacy audit, licensing and asset review, clean
synthetic CI artifacts, a verified unrelated-owner install, and an explicit
visibility/release decision. The product's pure-Python package remains MIT. The
optional Tomomai adapter has its own AGPL-3.0-only notice/license and upstream pin;
it is excluded from the MIT wheel/source package and the seven-file caller ZIP.
Its presence in a repository requires preserving its notice and upstream terms.

Do not imply that the optional renderer's license grants redistribution rights to
all game artwork. The existing artwork provenance and honest fallbacks remain in
place. This refactor creates no new public host, remote runtime dependency,
analytics, checkout script, database resource or score import by itself.
