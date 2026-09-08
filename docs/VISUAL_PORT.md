# Visual compatibility and sample reports

The four-view layout, spacing, system fonts, navigation, difficulty and grade
styling, tables, dialogs, filters, print rules, mobile navigation and reduced-motion
rules preserve the interface from the original standalone report.
`tests/test_presentation_port.py` checks the exact original Git blob hashes of
`styles.css`, `app.js`, `support.css` and `support.js` without fetching anything.

## Artwork and sample data

| Element | Release behavior |
| --- | --- |
| Rating badge | The default `builtin` pack includes all 12 original embedded game frames, including the distinct 16000+ kiwami frame. Compact right-hand digits, font, five slots and 296:86 proportions are preserved. Select `plain` for CSS-only styling or supply a local artwork pack. |
| Demo song covers | Original geometric tiles marked **DEMO**, attached only to fictional fixture songs. These are not authentic maimai jackets. Live/local jacket embedding remains unchanged; missing real art still shows the original `NO ART` placeholder. |
| Demo scores | Entirely fictional. Before/after pools, deltas and target recommendations are computed through the same model used for live reports. |
| Browser title / project name | Uses “maimai Session Report.” The report's existing maimai DX text wordmark remains unchanged. |
| Hosted extras | The standalone demo has no account history shell, B50 download, or support checkout. These remain optional installation features, not removed report features. Enabling them has separate dependencies and privacy implications. |

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
