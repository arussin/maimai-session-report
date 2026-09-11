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
- Share the compact chart rows between Scorecard's Play next and Targets. Retain
  chart identity, PB-to-S objective, conditional floor-aware gain, the existing
  session-based practice idea and level breakdown. Remove the longer coaching and
  repeated target prose; add no View action, dropdown or expandable writeup.

The selection/order of targets and the S-threshold calculation are unchanged.
Flow bars, named-pattern practice, similarity and Explore remain in Chart
Intelligence because they require its catalog and analysis evidence. This branch
does not create substitute pattern tags or infer personal weaknesses.

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

## Local evidence (2026-09-11)

- Python: 209 tests discovered, 208 passed, one Windows symbolic-link skip.
- Browser: 140 existing-report cases passed in Chromium at 1280, 768, 390 and
  320 pixels and WebKit at 390; ten compact-Targets cases also passed across
  those projects. These include missing/invalid score fields, repeated plays,
  keyboard focus, 200% text, automated accessibility and exact B50 image bytes.
- The initial combined run passed 145 cases and failed five copies of an incorrect
  new fixture expectation: an empty session still has prior PB targets. The corrected
  ten-case Targets run passed, exercising both retained targets with no new plays and
  an explicitly authored pool without eligible candidates. Product code did not
  change to satisfy that fixture correction.
- The Windows managed-server shutdown stalled after two earlier 140-case runs.
  The completed run used the same loopback fixture server started separately;
  no browser assertions, retries or timeouts were relaxed.
- Ruff lint and format checks passed. Offline doctor and sealed fictional rendering
  passed; no external URL was present in the sealed output. Desktop, mobile and
  Scores/Targets screenshots were inspected. This is automated browser coverage,
  not a manual screen-reader audit or a hosted installation test.

The final diff uses LF for the imported browser fixtures; their line-ending cleanup
does not change behavior. No history was rewritten. All generated test evidence
remains ignored under `output/` or the existing synthetic test folders.
