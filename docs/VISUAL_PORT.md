# Visual compatibility and sample reports

The four-view layout, spacing, system fonts, navigation, difficulty and grade
styling, tables, dialogs, filters, print rules, mobile navigation and reduced-motion
rules preserve the interface from the original standalone report.
`tests/test_presentation_port.py` checks the preserved presentation assets without
fetching anything. The footer now uses the shared maimai.party button styling
and separate checkout window; its behavior has dedicated privacy and browser tests.

## Artwork and sample data

The personal-data integration places the compact maimai.party link below the
main wordmark, groups the player-file download with B50/print actions, and shows
the selected practice chart's jacket alongside its identity. The presentation
snapshot is updated for these reviewed refinements; the four report views and
project links use the shared maimai.party support flow.

| Element | Release behavior |
| --- | --- |
| Rating badge | The default `builtin` pack includes all 12 original embedded game frames, including the distinct 16000+ kiwami frame. Compact right-hand digits, font, five slots and 296:86 proportions are preserved. Select `plain` for CSS-only styling or supply a local artwork pack. |
| Demo song covers | Original geometric tiles marked **DEMO**, attached only to fictional fixture songs. These are not authentic maimai jackets. Live/local jacket embedding remains unchanged; missing real art still shows the original `NO ART` placeholder. |
| Demo scores | Entirely fictional. Before/after pools, deltas and target recommendations are computed through the same model used for live reports. |
| Browser title / project name | Uses “maimai Session Report.” The report's existing maimai DX text wordmark remains unchanged. |
| Developer support | Matching project buttons appear near the footer; shared Stripe checkout opens separately after activation. Use `--no-support` to hide the links. |
| Hosted extras | The standalone demo has no account history shell or B50 download. These remain optional installation features, not removed report features. Enabling them has separate dependencies and privacy implications. |

See [rating assets](RATING_ASSETS.md) for provenance and ownership, and
[local artwork packs](BADGES.md) for customization.

## Actual browser previews

The README images are Chromium screenshots of `docs/sample-report.html`, generated
by the installed renderer from the bundled demo. The sample is the same interface
produced by `maimai-report demo`.

The contributor script `tests/browser/capture-readme.mjs` regenerates
the HTML, opens it in Chromium, blocks external requests, checks for page errors
and overflow, then captures all four desktop views and the mobile Scorecard. It
makes no sync or publishing requests. Browser tests also visit all four views at 1280, 768,
390 and 320 pixels plus mobile WebKit, including empty/incomplete fixtures.

Existing installations keep their own immutable code pins. This release does not
update any existing runner, site, artwork selection or deployment configuration.
