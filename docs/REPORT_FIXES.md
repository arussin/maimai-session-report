# Existing report fixes, separate from Chart Intelligence

This branch starts at public `arussin/maimai-session-report` main
`75645ca9ecf2b5c7cc1225dccb037010c1f10aa6`, verified on GitHub on
2026-09-11. No competing open pull request was present. It extracts report fixes
from the private Chart Intelligence work without importing that branch's history,
analyzer, catalog, experimental recommendations, chart sources or generated corpus.

## Scope

- Sort the existing Scores headers; retain the native Sort menu for mobile cards.
  Missing values remain last, ties preserve source order, and repeated plays keep
  their own score-detail identity. PB gains with missing comparisons display a dash.
- Preserve the original playercard frames already restored in public `4f60099`.
  Carry forward print-color and high-contrast fallbacks with twelve-tier coverage.
- Preserve B50 downloads. The missing download in the Chart Intelligence preview
  was a preview with no supplied image, not a removal of the public download path.
  The existing browser test downloads and compares the exact fictional image bytes.

The earlier playercard regression was in the private release-cleanup commit
`0b399713b75507e0da07f0008c8825d48b810960`; that cleanup replaced the frames
with a CSS plaque. Reapplying the whole restoration to public main would overwrite
already-correct artwork and licensing work, so this branch retains those assets.

## Separation and verification

The renderer, rating model, sync, history/correction selector, installation files,
dependency pins, artwork bytes and support settings are outside this change.
Historical originals are never regenerated. All fixtures and documentation previews
are authored fictional data. The private research branch remains intact.

`tests/browser/report-fixes.config.js` runs the ordinary report, Scores sorting,
playercard and artwork checks without a catalog or installation server. The default
browser CI also includes these tests. The fixture server retains its loopback binding
and path allowlist while allowing idle browser connections without blocking requests.

Presentation asset hashes are intentionally updated for the reviewed changes;
support hashes remain fixed. Full asset hashes are supplemented by behavioral
tests of sorting, details, B50 bytes, before/after values and responsive layouts.
