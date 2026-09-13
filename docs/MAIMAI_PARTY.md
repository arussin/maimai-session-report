# maimai.party integration

New reports keep the four existing views and add Open in maimai.party using its original wordmark. Every chart detail dialog includes exact song details and similar-chart links when the prepared public mapping resolves it. Unmapped records have a labeled title-search fallback.

The local result is one HTML file plus an optional cumulative `player.maimai.json.gz`. Both use the same normalized player dataset. Opening an HTML report makes no personal-data request or transfer. Clicking a maimai.party link opens a new tab, offers the player and capture date, and transfers the compressed data only after acceptance.

## Local commands

The following options work on `render`, `sync-and-render`, and `from-kamaitachi`:

| Option | Behavior |
| --- | --- |
| `--export-party-data [PATH]` | Create/update the cumulative file; without PATH, use `player.maimai.json.gz` beside the HTML |
| `--party-history PATH` | Add retained history; repeat for more sources |
| `--no-party-data` | Omit embedded personal handoff data and download; keep public song links |
| `--party-catalog-cache PATH` | Choose the verified public integration cache |
| `--offline-party` | Use prepared/cached public inputs without refreshing |

For example:

```console
maimai-report render --config config.toml --report-input output/report-input.json --after-pbs output/after-pbs.json --output output/report.html --export-party-data --party-history saved-captures
```

`render` is explicitly offline for public catalog access. Normal live generation refreshes the public manifest and compatible matching artifact; an unavailable refresh retains the last verified cache and prints a warning. No compatible cache means labeled search links and the existing general practice insight instead of fabricated structural matches.

Automatic cumulative export can be configured:

```toml
[party]
enabled = true
data_file = "output/player.maimai.json.gz"
catalog_cache = "output/maimai-party-catalog.json"
```

The opt-out controls embedded handoff data; an explicitly configured/requested player file can still be exported. Paths follow the existing configuration path rules.

History inputs accept a player file, a completed raw capture directory containing report-input.json and metadata.json, a portable archive directory containing manifest.json and its verified objects, or a directory of those capture/archive directories. Extract portable archive packages first. Symlinks and incomplete/invalid inputs are rejected.

Existing player files are validated, checked against the source player, merged under an exclusive adjacent lock and atomically replaced. Repeated source plays/captures do not multiply. Older imports do not downgrade current results. If a process is forcibly killed while holding the lock, verify that it is no longer running before removing the adjacent `.lock` and retrying. The previous player file remains usable.

The export preserves the full available PB collection, original play/source/session identities, capture associations and all retained PB observations. A PB-only report does not invent plays. Missing baselines or a partial archive remain explicitly incomplete. Capture-only observations are labeled separately from real plays.

## Personal mode in maimai.party

Import the file from Settings or accept a report handoff. Both go through the same validator and merge logic. The site reads the file in the browser; no score account or upload service is created.

Remember on this device is optional. Otherwise the dataset lasts for the current tab session, including refreshes. Storage failures do not replace existing data. A different player switches the active player without mixing records. Refusing a report offer opens the generic destination without deleting remembered data.

PB percentage, grade, recorded chart rating and available clear/sync badges appear beside the selected chart variant. Personal filters and sorting work on that variant before song grouping. Details show retained plays, dated PB observations and achievement progress.

See the upstream [format, matching and browser contract](https://github.com/arussin/maimai-chart-browser/blob/codex/player-data-integration/docs/PLAYER_DATA.md). The pinned modules and original wordmark retain their upstream license and hashes in `src/maimai_report/_party/PROVENANCE.json`. Refresh them intentionally with `python scripts/sync_party_library.py --source PATH_TO_CHART_BROWSER`. There is no runtime dependency in the reverse direction.

## Recommendations

Targets retain two rating opportunities, pool-floor context and one specific practice choice when evidence supports it.

Rating candidates come from the complete eligible PB collection across Old 35 and New 15. They target the next S-through-SSS+ boundary within 2.5 percentage points, require positive marginal pool gain, and rank by gain, similarity to successful session charts, then achievement gap with song diversity. Each estimate is conditional on achieving that target, considered separately.

The versioned policy `kamaitachi-maimaidx-f08148f-v1` follows the provider's [published calculation](https://github.com/zkldi/Tachi/blob/f08148f8644e40de9b178445df4bd59da712d3de/typescript/rg-stats/src/algorithms/maimaidx-rate.ts), including special one-tick boundaries, truncation, the 100.5% cap and AP bonus. Recorded ratings are preserved. Numerical estimates are omitted when the snapshot is incomplete, version groups are missing, or recorded ratings disagree with the policy.

Practice uses up to three distinct recent successful session charts at S or better, falling back to retained plays and dated PBs. It searches other song families 0.1–0.5 constant points harder in the configured version's available charts, including charts without a PB. Conditional rating upside is preferred, then structural similarity. It never proposes an already exceeded achievement target. Insufficient evidence retains the general practice insight. maimai.party continues to offer only general chart comparison.

## Hosted upgrade and data lifecycle

The installation's raw archive remains the source of retained history. Dataset revisions are materialized during archive processing and have their own publication pointer, separate from the latest session report. A PB-only capture can advance personal data without replacing the published report.

Upgrade in dependency order:

1. Publish the chart-browser mapping/matching artifact and personal importer/navigation.
2. Update the report installation's pinned core and caller workflow templates together. Refresh publication now waits for successful archive processing; capture/render and publish receive the existing scoped history/R2 credentials.
3. Run `maimai-report instance setup --config instance.toml --apply` to apply additive migration 0002 to the existing primary and recovery databases. Preserve all resource names, scopes, routes and raw captures.
4. Run `maimai-report instance player-backfill --config instance.toml` once for existing retained captures, then the normal backup operation. First archive processing also backfills automatically if no dataset exists.
5. Explicitly regenerate a retained report, or generate the next wanted report, archive its exact HTML/B50 in both private buckets, and publish using the existing protected release workflow.

There is no need to resync scores or replace the raw archive. Existing historical report HTML keeps its original analysis. Retained releases can keep the current HTML; new integration features appear only in newly generated or explicitly regenerated reports.

Protected, same-origin endpoints beneath the installation prefix are `party/latest.json` and `party/data/<sha256>.gz`. Old connected reports check the latest metadata only when clicked and fetch the selected immutable payload only after acceptance. A failed refresh explicitly offers the report's embedded snapshot and its original date. The download recovery button likewise identifies the saved snapshot.

The process validates retained inputs, encodes and verifies the full dataset, writes immutable data and revision metadata, then advances a D1 pointer with compare-and-swap. Concurrent publishers reload/merge the winner before retrying. Failed writes preserve the previous head and capture date. Raw archive backfill fails explicitly on incomplete or corrupt retained objects; it never silently skips history.

Growing player objects and generated report HTML live in existing private R2 archive storage. The Worker carries a small report reference and streams verified objects, rather than bundling all personal history into executable modules. Exact report objects must exist in both archives before publication. Legacy smaller HTML objects without verification metadata use the existing bounded checksum fallback.

The handoff changes only a connected report's opener policy to `same-origin-allow-popups` and allows same-origin refresh requests when configured. Existing Access protection, no-store behavior, no-referrer policy, anti-indexing and other security headers remain. See the [browser policy reference](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Cross-Origin-Opener-Policy).

## Limits and recovery

- Player file: 32 MiB compressed / 128 MiB expanded; one million entries per collection.
- Hosted revision metadata: 1 MiB.
- Individual raw capture input: 20 MiB; generated archived HTML: 64 MiB.
- Browser tab/device storage has its own quota. A quota failure offers an explicit error; choose device storage or free space and retry.
- No limit silently omits history. Existing files, remembered data and published dataset revisions remain usable after failed updates.
- Download/import recovers blocked popups or interrupted messaging. Player data never appears in URL parameters or analytics.
- Existing archive backup/recovery includes immutable player artifacts; rebuilding from validated raw captures can rematerialize them.

## Acceptance checks

Python tests cover full-PB exports, equivalent embedded/file bytes, repeated histories, player isolation, PB-only data, incomplete coverage, corruption/size/atomic failures, concurrent revision updates, archive backfill, provider boundaries and pool floors, practice choices and verified catalog fallback. Upstream parity tests cover measurement and pattern ranking.

`tests/prepare_party_browser.py --party-source PATH` builds fictional fixtures. `tests/party_browser.cjs` runs Chrome, Edge, Firefox and WebKit against local files, local serving and protected pages. It checks import/transfer equivalence, consent, retained/newer data, rejection, storage conflicts, interrupted refresh/payloads, exact details/similarity, reload/Back, keyboard access, personal sorting and mobile overflow. The Worker tests use real local D1/R2 emulation. No acceptance fixture contains real player data.

Implementation and local testing do not deploy either site or change an existing installation pin.
