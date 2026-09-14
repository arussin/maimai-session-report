# Session rating contributions

The scorecard's Session highlights rank charts by their contribution to the
session's reconstructed Old 35 + New 15 rating gain, not by the raw increase in a
chart's personal-best rating. The existing chart-rating values, headline rating
and PB-change table remain unchanged.

## Attribution

Start with the before snapshot's counted pools. Include the previous PB of every
changed chart, including previously uncounted PBs. Replay retained session plays
in increasing recorded timestamp order. Only an achievement improvement updates
a chart's PB. After each update, select the highest 35 legacy and 15 configured
current-version chart ratings. Attribute the difference in the combined pool
total to that chart, and combine repeated plays of the same chart.

Only positive contributions are highlighted. Rank by contribution descending,
then final chart rating descending, then chart ID for a deterministic tie-break.
The top-four subtotal is shown separately from the complete session gain. The
raw previous and final PB chart ratings remain secondary information, with the
same distinction available in the score-detail dialog.

For example, a first PB worth 210 replacing a 200-point floor contributes 10,
not 210. Improving an already-counted 300-point PB to 321 contributes 21 and
ranks ahead of that first PB. An uncounted improvement contributes zero. Filling
an empty slot can legitimately contribute the whole chart rating.

This is chronological attribution, not final-pool membership or a counterfactual
leave-one-chart-out calculation. A score can increase rating early in a session
and later be displaced. Its earlier contribution is retained; a later replacing
score receives only its additional gain.

## Reconciliation and incomplete data

The compact starting state is sufficient for monotonic PB improvements: an
unchanged, uncounted chart cannot enter a pool while that pool's floor only rises.
The implementation verifies the serialized before and after pool totals,
individual changed-PB endpoints, final counted records, both pool deltas, and the
overall session delta before exposing the ranking.

Missing snapshots, malformed values, missing changed-PB endpoints, inconsistent
chart metadata, rate corrections, negative steps, or ambiguous cross-chart
timestamps make attribution unavailable. In that case the UI explicitly says so
and leaves the original PB records accessible; it never falls back to presenting
raw PB gains as rating contributions. A verified zero-gain session gets a distinct
empty state.

Reconciliation establishes consistency with the retained report inputs and the
configured version model. It does not independently prove that upstream retained
every intermediate play, verify cabinet rating rules, or repair incorrect chart
metadata. Attribution depends on recorded play order.

No new network requests, imports, credentials, or personal-data fields are needed.
Existing retained reports can use this calculation when rerendered with the new
frontend. Already-generated HTML remains unchanged until explicitly rerendered.

## Regression coverage

`tests/browser/contributions.spec.js` exercises the production calculation with
fictional scores: pool replacements, separate pools, empty slots, previously
uncounted PBs, repeat plays, chronology, subsequent displacement, zero gains,
missing history, corrections, ties, invalid values and input immutability.
Browser checks cover the visible ranking, PB comparisons, unavailable/zero states,
escaping, and viewport fit through the existing browser project matrix.
