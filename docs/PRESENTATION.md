# Report presentation

The report has four views: Scorecard, Rating pools, Scores and Targets. This guide
maps its data and controls to those views. See [visual compatibility](VISUAL_PORT.md)
for artwork choices and the fictional sample report.

## Data and behavior destinations

| Feature | Destination |
|---|---|
| Player, date, local time, duration; reconstructed rating and change | Scorecard namecard and session receipt |
| Rating tier and next-tier progress | All 12 original embedded tier frames (or an explicit local/CSS pack); HTML digits and accessible progress bar |
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
| Print/B50 integration | Print control or optional B50 image download, according to the installation's configuration |
| Footer checkout | Lazy isolated cross-origin iframe with keyboard focus handling |
| Empty/incomplete reports | Same renderer; fictional fixtures in offline tests and browser CI |

## Implementation and dependencies

Presentation stays HTML, CSS and vanilla JavaScript. Native selects and dialogs
provide normal keyboard behavior; native modal dialogs keep focus out of the
background. CSS handles reflow, system fonts and reduced motion. There is no
frontend framework, remote font, runtime API, tracker or third-party parent script.

The optional build-time `artwork` extra adds pinned Pillow. It downloads only
public static catalogue/artwork files, matches normalized title **and artist**
exactly, rejects ambiguous filenames/redirects, bounds downloads and decoding,
and embeds small raster data URLs. Rendering without an explicit artwork flag
remains offline. Missing art remains a marked placeholder, never fabricated art.
See [ARTWORK.md](ARTWORK.md) and [RATING_ASSETS.md](RATING_ASSETS.md).

## Presentation regression tests

The existing Scores column headings toggle ascending and descending order for
Song, Chart, Achievement, Grade, Rating, PB gain and Fast / Slow. The Sort menu
stays synchronized and supplies the same choices on narrow-screen cards. Missing
values stay last, equal values retain source order, and repeated plays open their
own retained details. PB gain sorting is available only for PB changes. Chart
order uses difficulty, displayed level (including plus bands), retained constant,
then STD/DX; it does not invent missing constants.

The published original playercard frames remain in use, with print-color and
high-contrast fallbacks. Supplied B50 image downloads remain unchanged. No analyzer
or catalog package is needed for these report fixes. A focused local gate runs
with `npx playwright test --config report-fixes.config.js` from `tests/browser`
after generating the ordinary fictional fixtures.

`tests/browser` uses pinned Playwright and axe-core with Chromium at 1280, 768,
390 and 320 CSS pixels, plus WebKit at 390. Complete, empty and incomplete fixtures
visit every view. A separate explicitly fictional presentation fixture exercises
Advanced 9 versus Expert 9, absent judgements and an uncounted target.

Assertions check actual visible values and outcomes: sorted grades/scores,
combined filters, complete before/after pools, PB comparisons, direct target
navigation, dialog closure/focus, keyboard tabs, reduced motion, 200% text reflow,
page overflow, WCAG A/AA automated checks and exact B50 download bytes. The BMC
origin is intercepted with a synthetic cross-origin page; provider payments are
never exercised. Screenshots support visual review; automated checks do not replace
a manual accessibility audit.

Browser CI builds and uploads only fictional reports and screenshots. Do not add
real reports or private snapshots to its inputs.

After the [development setup](../CONTRIBUTING.md#development-environment), run:

```console
ruff check .
ruff format --check .
python -m unittest discover -s tests -v
python tests/browser/prepare.py
npm ci --ignore-scripts --prefix tests/browser
cd tests/browser
npx playwright install --with-deps chromium webkit
npm test
```

## Analytical limitations

Scorecard's Play next and Targets share the same compact chart-row component:
identity, PB-to-S objective and conditional rating gain. The short gain note
states that the New 15 floor is included. Chart titles still open retained score
details; there is no extra View action or recommendation writeup control. The
practice idea remains based on this session's observed level bands, with the
sample scope stated alongside it. This presentation cleanup adds no detector,
training claim or new recommendation ranking.

- Difficulty-band averages aggregate retained plays across chart types and
  versions; the existing exploration quest recommends current-version charts
  from that sample. The UI explains this scope.
- Raw PB chart gains are not net account gains: counted-pool replacement matters.
- The bundled synthetic demo computes its summaries from invented before/after
  inputs using the production model; its totals, grades and pool rows agree.
- The optional B50 renderer uses retained pools, a pinned Tomomai implementation
  and its public catalogue. It is separate from the HTML report renderer.
