# Selecting corrected historical presentations

The hosted installation supports an optional `[history.presentation_revisions]`
TOML table mapping existing capture SHA-256 IDs to approved immutable source-manifest
SHA-256 hashes. There is no automatic newest-revision discovery. At most 256 selections
are allowed, and history must be enabled. Keep private capture IDs in the owner's
private installation, never in shared examples or public previews.

A selected historical page defaults to its corrected report and offers **Original
report** (`?view=original`). The original view does not depend on availability of the
revision. Both versions use the same original B50 endpoint. No score import, capture
creation, database update, archive overwrite, or latest-pointer change is involved.

The Worker verifies the selected manifest hash, capture/scope identity, original
publication manifest hash, all original metadata and file references, the corrected
HTML hash/length, and equality of the embedded report data. Invalid/missing corrections
fall back to a checksum-verified original with an explicit warning. An invalid original
fails closed. The selection never accepts an arbitrary manifest hash from a URL.

Selections are compiled into the staged Worker from the owner's versioned TOML.
They are deliberately excluded from archive resource identity, backup formats, and
recovery index reconstruction. Stage validation nevertheless detects selection drift.
Future syncs retain the configured selections. Removing a selection and redeploying
returns that session to its original default. A saved Worker-version rollback also
restores the preceding presentation behavior without changing archive data.

## Release gates

Before applying selections, verify all selected manifests and HTML in primary and
independent backup storage. Compare original archive objects, index rows, ordering and
latest pointers before and after deployment. Preserve and verify the latest static
report/B50; this feature does not require rerendering them. Exercise both corrected and
original routes plus downloads and private access checks. Keep prior Worker settings,
modules and deployment version as rollback evidence.

Already-retained alternate HTML can differ from an original publication, so the strict
code-only `release` live-versus-original-archive guard may correctly refuse a previously
rerendered latest report. Do not relax that guard or overwrite the original publication.
Use the existing retained `publish` path with exact current live bytes and original
provenance, checking drift and both archival copies separately.

Synthetic coverage includes bad hashes, missing objects, foreign capture/scope,
changed metadata/data/references, original fallback, B50 identity, HEAD, invalid queries,
configuration bounds, staging drift, and correction/original context accessibility
across the existing viewport/browser matrix. Existing D1/R2 and full report browser
regression tests continue to run as part of repository CI.
