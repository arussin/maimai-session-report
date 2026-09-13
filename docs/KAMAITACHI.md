# Official-network Kamaitachi reports

Use this path for maimai DX plays already imported into Kamaitachi. MYT
integration and a score-submission token are not needed by the report. It reads
your existing session and never submits scores or logs into maimai DX NET.

## Import your plays

Install the community [maimai DX NET importer](https://github.com/j1nxie/kt-maimaidx-site-importer)
linked by Kamaitachi. Log into maimai DX NET and follow its account-linking
instructions. Import **recent scores first**. During initial setup, backfill all
PBs afterward so the report has your full rating pool. After playing, repeat the
recent-score import while the plays are still in the website's recent history.
The importer supports the international and Japanese websites.

The initial supported route is this importer's recent-play mode. It supplies
achievement, clear/combo lamp, timestamps, fast/slow and judgement totals.
Other producers may work after Kamaitachi normalizes their records, but are not
separately certified. PB-only imports lack individual play history.

## Generate locally

Follow [local installation](LOCAL.md), then set your username, timezone and exact
current-version display names in `config.toml`. Release settings must match your
intended game version. Existing-session mode supports `maimaidx` only.

List the latest 100 session summaries:

```sh
maimai-report sessions
```

Use an ID from that list or a Kamaitachi session URL:

```sh
maimai-report from-kamaitachi --session-id YOUR_SESSION_ID --output-dir output/visit-01 --output output/visit-01/report.html
```

Use `--latest` instead of `--session-id YOUR_SESSION_ID` to explicitly select the
newest session. An exact ID can also select older sessions outside the list.
The complete session endpoint supplies the plays, including repeated plays of a
chart and sessions larger than 100 scores. Incomplete or inconsistent membership
stops capture instead of silently generating a partial session.

Public Kamaitachi read access to the configured account is required. Failed
reads never trigger an import. Each run needs a new, empty capture directory.
Keep the entire output directory private; the HTML can be opened locally.

## Rating comparisons

The selected session supplies **plays**. The PB endpoint supplies **current
account PBs at capture time**, potentially including later sessions or backfills.
Selecting an old session does not reconstruct its historical rating pools.
The history chart dates these ratings at capture time and retains the selected
session's play date separately.

Without a baseline, the report shows current rating, pools, targets and session
plays, but marks PB changes and rating gain unavailable. It does not interpret
missing comparisons as zero gain or as first-ever PBs.

After initial backfill and before your next play session, save a baseline:

```sh
maimai-report snapshot --output reports/start.baseline.json
```

After your next recent-score import:

```sh
maimai-report from-kamaitachi --latest --baseline reports/start.baseline.json --output-dir output/visit-02 --output output/visit-02/report.html
```

The baseline must belong to the same username, game and configured release and
predate the selected session. Wrong or too-new baselines cause an error.
Comparisons are labeled **since baseline**, because they may include other
sessions or backfills. They are not presented as gains from only the selected
session. Every capture also saves `baseline.json` for your next visit. The
snapshot command never overwrites an existing baseline.

To inspect only PBs and create a baseline without selecting a session:

```sh
maimai-report from-kamaitachi --pb-snapshot --output-dir output/pb-check --output output/pb-check/report.html
```

An optional earlier `--baseline` enables PB comparisons. Total plays, duration,
timing and session difficulty profiles are not inferred from PB records.

## GitHub Actions and hosted installations

In **Build private report artifact**, choose `source: kamaitachi` and enter a
session ID, `latest`, or `pb-snapshot`. Leave `baseline-run` blank on the first
run. Download the private report artifact. For later visits, `baseline-run` may
select an earlier report run containing `baseline.json`. The capture step does
not receive an MYT token.

For a packaged private installation, update the core pin and installed workflow
files through the normal [installation upgrade](INSTALLATION.md) process. In
**Refresh maimai session**, choose the same source and session selection.
`baseline-run` selects an earlier `maimai-session-<run-id>` artifact. Expired
artifacts or older releases without `baseline.json` cannot supply a baseline;
leave the field blank to generate with unavailable comparisons.

The reusable root action accepts `source: kamaitachi`, `session-id`, and an
optional `baseline` path already downloaded by the caller. The installation
action accepts `operation: capture`, `session-id`, and optional `baseline-run`.
The usual private-artifact, archive and publication gates apply. A PB snapshot
without known changes is downloadable but does not automatically replace the
live report. Existing installations must be upgraded to receive this workflow.

## Detail coverage and retained evidence

Missing per-play details display dashes. Timing counts only plays with both
fast and slow values and reports unavailable or partial coverage. Grade and
difficulty summaries use actual plays. Lamp-only PB changes are counted even
when achievement and rating are unchanged.

Raw `kamaitachi-session.json`, normalized scores, current PBs, comparison inputs
and the next baseline are retained beside the report. A complete Kamaitachi
session is not proof that the source website retained every play from a visit.

API behavior was checked against Tachi commit
`f08148f8644e40de9b178445df4bd59da712d3de`: [session retrieval](https://github.com/zkldi/Tachi/blob/f08148f8644e40de9b178445df4bd59da712d3de/typescript/server/src/server/router/api/v1/sessions/_sessionID/router.ts)
and [complete session scores](https://github.com/zkldi/Tachi/blob/f08148f8644e40de9b178445df4bd59da712d3de/typescript/server/src/utils/queries/sessions.ts).
Tests use fictional normalized payloads and do not perform a live official-network import.
