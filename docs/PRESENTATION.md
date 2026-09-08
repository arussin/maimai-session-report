# Completed report presentation

The compact scorecard is the presentation system for all four views.
The rating calculations remain authoritative. This guide describes the shipped
interface; internal design checkpoints are not part of the release. See
[visual compatibility](VISUAL_PORT.md) for the exact preserved assets and the
deliberate rating-frame/demo-artwork differences.

## Data and behavior destinations

| Retained feature | Destination |
|---|---|
| Player, date, local time, duration; reconstructed rating and change | Scorecard namecard and session receipt |
| Rating tier and next-tier progress | Original CSS rating display; HTML digits and accessible progress bar |
| Old 35 / New 15 session contributions | Scorecard; full before/after table in Rating pools |
| Reconstructed and Kama Naive before/after/delta; Naive gap and model assumption | Rating pools comparison and adjacent model explanation |
| Both floors, occupancy, recorded PB count, current-version charts played | Rating pools before/after summary |
| Every counted Old 35 and New 15 entry | Rating pools, After/Before snapshot selector; search covers title, artist, difficulty, level, grade |
| Session interpretation | Rating pools, beside the actual breakdown |
| All session plays and every PB change | Scores, explicit scope selector; counts and separate PB gain column |
| Achievement, grade, chart rating, PB prior achievement/rating, raw chart gain | Score rows and native score-detail dialog |
| Song, artist, difficulty, level, DX/STD, lamp, chart constant, time, version | Rows and score details |
| FAST/SLOW and five judgement fields | Rows, session timing analysis, complete score details; missing detail fields display a dash |
| Grade distribution | Scores, canonical highest-to-lowest order |
| Achievement/rating/latest sorting and combined difficulty/text filtering | Scores; visible result counts, keyboard-accessible controls |
| Difficulty bands, play counts, average achievement/rating, FAST/SLOW, sweet spot | Targets, with explicit chart-type breakdown inside each original numeric band |
| Threshold targets, estimates, floor and exploration quests | Targets; top opportunities also on Scorecard; uncounted targets open directly |
| Coaching | Timing guidance beside timing; model guidance beside pools; practice guidance beside difficulty analysis |
| Four views, linked overview actions, keyboard tabs | Persistent desktop tabs and mobile bottom navigation; arrow, Home and End keys |
| Print/B50 caller integration | Exact original button and handler replacement literals preserved |
| Footer checkout | Existing support.js/support.css; lazy isolated cross-origin iframe, original attributes and focus behavior |
| Empty/incomplete reports | Same renderer; fictional fixtures in offline tests and browser CI |

## Implementation and dependencies

Presentation stays HTML, CSS and vanilla JavaScript. Native selects and dialogs
provide normal keyboard behavior; native modal dialogs keep focus out of the
background. CSS handles reflow, system fonts and reduced motion. There is no
frontend framework, remote font, runtime API, tracker or third-party parent script.
A frontend framework would not itself improve the hierarchy and would add a
bundling dependency to this self-contained report.

The optional build-time `artwork` extra adds pinned Pillow. It downloads only
public static catalogue/artwork files, matches normalized title **and artist**
exactly, rejects ambiguous filenames/redirects, bounds downloads and decoding,
and embeds small raster data URLs. Rendering without an explicit artwork flag
remains offline. Missing art remains a marked placeholder, never fabricated art.
See [ARTWORK.md](ARTWORK.md) and [RATING_ASSETS.md](RATING_ASSETS.md).

## Presentation regression tests

`tests/browser` uses pinned Playwright and axe-core with Chromium at 1280, 768,
390 and 320 CSS pixels, plus WebKit at 390. Complete, empty and incomplete fixtures
visit every view. A separate explicitly fictional presentation fixture exercises
Advanced 9 versus Expert 9, absent judgements and an uncounted target.

Assertions check actual visible values and outcomes: sorted grades/scores,
combined filters, complete before/after pools, PB comparisons, direct target
navigation, dialog closure/focus, keyboard tabs, reduced motion, 200% text reflow,
page overflow, WCAG A/AA automated checks and exact B50 download bytes. The BMC
origin is intercepted with a synthetic cross-origin page; provider payments are
never exercised. Screenshots are captured for review. They are **not** a claim
of pixel-golden regression coverage or a complete manual accessibility audit.

Browser CI builds its own allowlisted fictional files. It cannot read retained
private snapshots and uploads only its synthetic result directory. Retained real
reports and their screenshots are reviewed separately and stay outside source.

To run the contributor gates:

```console
python -m pip install ".[artwork]" ruff==0.16.5
ruff check .
ruff format --check .
python -m unittest discover -s tests -v
python tests/browser/prepare.py
npm ci --ignore-scripts --prefix tests/browser
cd tests/browser
npx playwright install --with-deps chromium webkit
npm test
```

## Known analytical limitations, unchanged

- Difficulty-band averages aggregate retained plays across chart types and
  versions; the existing exploration quest recommends current-version charts
  from that sample. The UI explains this scope. Recommendation logic is unchanged.
- Raw PB chart gains are not net account gains: counted-pool replacement matters.
- The bundled synthetic demo computes its summaries from invented before/after
  inputs using the production model; its totals, grades and pool rows agree.
- The existing caller B50 renderer re-renders retained pools using its pinned
  Tomomai implementation and public catalogue. It is not changed by this redesign.

No report data, caller pin, deployment, Access policy, checkout code, rating
calculation, target formula or score-import sequence is changed by this work.
The action gains optional public artwork preparation after its existing import.
