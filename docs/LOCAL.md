# Local use and command reference

Use this guide after the [project quickstart](../README.md). The local workflow needs only Python 3.11+ and, for live sync, your own configured Kamaitachi account. Hosted history and deployment are optional; see [installation](INSTALLATION.md).

## Five-command offline demo

Cloning is the only command here that needs network access. Installation, `doctor`, report generation, and serving work offline and require no secrets.

### Windows PowerShell

```powershell
git clone https://github.com/arussin/maimai-session-report.git
py -3 -m venv .\maimai-session-report\.venv
& .\maimai-session-report\.venv\Scripts\python.exe -m pip install --no-deps .\maimai-session-report
& .\maimai-session-report\.venv\Scripts\maimai-report.exe demo --output .\maimai-session-report\output\demo-report.html
& .\maimai-session-report\.venv\Scripts\maimai-report.exe serve --file .\maimai-session-report\output\demo-report.html
```

### macOS

```bash
git clone https://github.com/arussin/maimai-session-report.git
python3 -m venv maimai-session-report/.venv
maimai-session-report/.venv/bin/python -m pip install --no-deps ./maimai-session-report
maimai-session-report/.venv/bin/maimai-report demo --output maimai-session-report/output/demo-report.html
maimai-session-report/.venv/bin/maimai-report serve --file maimai-session-report/output/demo-report.html
```

### Linux

```bash
git clone https://github.com/arussin/maimai-session-report.git
python3 -m venv maimai-session-report/.venv
maimai-session-report/.venv/bin/python -m pip install --no-deps ./maimai-session-report
maimai-session-report/.venv/bin/maimai-report demo --output maimai-session-report/output/demo-report.html
maimai-session-report/.venv/bin/maimai-report serve --file maimai-session-report/output/demo-report.html
```

Open the localhost URL printed by the fifth command and press Ctrl+C when finished. You can also open the HTML file directly. The `complete` demo exercises Old 35/New 15 pools, gains, new and improved PBs, session timing, fast/slow counts, multiple difficulties and grades, and Japanese/Unicode text. Use `--scenario empty` or `--scenario incomplete` for the no-change and incomplete-New-15 states.

Every console command also works as `python -m maimai_report ...` from the installed environment.

## Local development setup

After cloning, enter the repository and create an isolated environment:

```powershell
# Windows PowerShell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --no-deps -e .
```

```bash
# macOS or Linux
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --no-deps -e .
```

For development, install `requirements-dev.txt` before running `python -m unittest discover -s tests -v`; the full suite includes artwork/history tests and needs timezone data on Windows. See [CONTRIBUTING.md](../CONTRIBUTING.md). Stock Windows works with the generic `UTC` default. If a chosen non-UTC IANA zone is unavailable, install the optional timezone data with `python -m pip install ".[timezone]"`; `doctor` will report the problem before a network request.

## Offline and local rendering

Generate all bundled demo states without reading configuration or credentials:

```console
maimai-report demo --scenario complete --output output/demo-report.html
maimai-report demo --scenario empty --output output/empty-report.html
maimai-report demo --scenario incomplete --output output/incomplete-report.html
```

Render previously saved local inputs without network access:

```console
maimai-report render --config config.toml --report-input output/report-input.json --after-pbs output/after-pbs.json --output output/report.html
```

`report-input.json` is the calculated session document written by `sync`; `after-pbs.json` is the matching Kamaitachi response used to enrich song/chart details. Both are private. Rendering embeds CSS, JavaScript, and escaped report JSON in one file. It adds no analytics, fonts, CDN resources, or other external URLs.

Song jackets can be embedded from a prepared local mapping with `render --jackets output/jackets.json`. Optional public artwork preparation is explicit on the CLI and enabled by the reusable action’s `artwork` input (set `"false"` to disable). See [artwork preparation](ARTWORK.md). It adds no browser requests.

Serve a generated file only on the local machine:

```console
maimai-report serve --file output/report.html
```

The default bind address is `127.0.0.1`. Wildcard binds such as `0.0.0.0` are rejected for private reports. If you deliberately need LAN access, pass one exact interface address and account for the resulting exposure and Host-header restriction.

## Account and MYT prerequisites

Live mode needs an existing Kamaitachi account whose MYT integration is already configured and usable. Current upstream Kamaitachi source exposes the integration page under `/u/<username>/integrations`, labels its API-key area “API Keys,” and offers “Create new API Key” and “Delete Key.” UI wording can change; verify the page before following these instructions. [Current integration-page source](https://github.com/zkldi/Tachi/blob/8f4b6b41e08d2d059f9fde62edbf16d147bfaadc/typescript/client/src/app/pages/dashboard/users/UserIntegrationsPage.tsx)

Configure the existing MYT integration in Kamaitachi itself, following that UI. This application only requests its published `api/myt-maimaidx` importer and does not need, accept, or store a card access code. Do not put integration credentials in this project or in GitHub. See the [public-source boundary](UPSTREAM.md) for the upstream references.

MYT account access and integration availability are prerequisites, not something this project provisions. Confirm them in the service you already use.

## Create and store a Kamaitachi API token safely

In the current Kamaitachi integration UI, create an API key and grant only the capability needed for the import. The implementation's audited upstream revision checks the `submit_score` permission for `/import/from-api`; API-key permissions are immutable, so revoke/delete and replace an over-privileged key. The current UI can reveal existing keys, so do not assume a token is shown only once. [Import route source](https://github.com/zkldi/Tachi/blob/4f6048aaac4d0033e614401b0692a3785b78e149/typescript/server/src/server/router/api/v1/import/router.ts)

The CLI accepts the token only through `KAMAITACHI_API_TOKEN`. Do not put it in `config.toml`, `.env`, a command argument, shell profile, screenshot, or issue. Read it interactively for the current shell so it is absent from command history:

```powershell
# Windows PowerShell
$privateToken = Read-Host 'Kamaitachi API token' -AsSecureString
$env:KAMAITACHI_API_TOKEN = [System.Net.NetworkCredential]::new('', $privateToken).Password
Remove-Variable privateToken
```

```zsh
# macOS (default zsh)
read -rs 'KAMAITACHI_API_TOKEN?Kamaitachi API token: '
printf '\n'
export KAMAITACHI_API_TOKEN
```

```bash
# Linux (Bash)
read -rsp 'Kamaitachi API token: ' KAMAITACHI_API_TOKEN
printf '\n'
export KAMAITACHI_API_TOKEN
```

Close the shell or run `Remove-Item Env:KAMAITACHI_API_TOKEN` (PowerShell) / `unset KAMAITACHI_API_TOKEN` (macOS/Linux) when finished. A password manager is appropriate for long-term storage; inject the value into a process only when needed.

## Personalize `config.toml`

Copy the non-secret example:

```powershell
Copy-Item .\config.example.toml .\config.toml
```

```bash
cp ./config.example.toml ./config.toml
```

Edit username, display name, IANA timezone, and the exact current-version display names. `config.toml` is ignored by Git and rejects token-like keys, but it can still identify you; keep it private. The committed defaults are generic: game `maimaidx`, import type `api/myt-maimaidx`, timezone `UTC`, output directory `output`, seven-day artifact retention, and publishing off.

Values resolve in this order: command options, environment variables, `config.toml`, then safe defaults. Commands that use configuration place `--config` after the command, for example `maimai-report doctor --config private/settings.toml`. See [the configuration reference](CONFIGURATION.md) for every field and canonical environment variable.

### Updating the current version / New 15 pool

`report.current_version_display_names` must contain the exact `chart.data.displayVersion` strings that Kamaitachi uses for charts in the current version. This project intentionally has no release-specific default. Confirm the values against current Kamaitachi data whenever the game rolls over; during a transition, include every exact alias that should count as current. Incorrect names silently misclassify Old 35/New 15 membership, so do not guess.

Environment-based configuration uses a JSON array, not a comma list:

```text
MAIMAI_REPORT_CURRENT_VERSION_DISPLAY_NAMES=["Exact Version A","Exact Version B"]
```

## Validate with `doctor`

Offline validation checks Python, parsed configuration, timezone availability, current-version settings, and output-directory permissions. It never starts an import:

```console
maimai-report doctor --config config.toml
```

Add `--network` only when you explicitly want one API-readiness request. It still never starts an import or opens the SSE stream:

```console
maimai-report doctor --config config.toml --network
```

Offline `doctor` is safe for a fresh clone with generic defaults. Live commands perform stricter validation—username, current-version values, output path, and token—before their first network request.

## Perform one local live sync

Configure the account, set the token in the current process, then choose exactly one explicit command.

Save six private JSON files without rendering:

```console
maimai-report sync --config config.toml --output-dir output
```

The directory receives `before-pbs.json`, `after-pbs.json`, `before-recent-scores.json`, `after-recent-scores.json`, `report-input.json`, and `metadata.json`.

Sync and generate local HTML in one command:

```console
maimai-report sync-and-render --config config.toml --output output/report.html
```

Each invocation reads PBs and recent scores, starts **exactly one** authenticated from-API import, waits for completion through SSE (no rapid polling), then reads PBs and recent scores once more. Do not run a second sync merely because an SSE connection failed: first check the import's status in Kamaitachi, because the first import may still have completed. The recent-score endpoint is currently limited to 100 results, so a session with more than 100 newly imported scores may be truncated in the report. [Audited recent-score route source](https://github.com/zkldi/Tachi/blob/4f6048aaac4d0033e614401b0692a3785b78e149/typescript/server/src/server/router/api/v1/users/_userID/games/_game/_playtype/scores/router.ts)

Nothing publishes as a consequence of either command.

## Reuse from another private repository

GitHub can consume this package as a composite action from a private caller;
the caller does not need a copied implementation. When the product repository
is public, any owner's private runner can use its pinned actions. If the product
is still private, the owner must configure eligible private-action sharing first;
that is a temporary distribution restriction, not a new user's normal setup.
See [GitHub's private-action sharing documentation](https://docs.github.com/actions/creating-actions/sharing-actions-and-workflows-from-your-private-repository).

A caller supplies its existing Kamaitachi secret and non-secret player configuration:

```yaml
- name: Run one sync with the canonical implementation
  uses: arussin/maimai-session-report@REPLACE_WITH_REVIEWED_40_CHARACTER_COMMIT_SHA
  with:
    output: output/maimai-report.html
  env:
    KAMAITACHI_API_TOKEN: ${{ secrets.KAMAITACHI_API_TOKEN }}
    MAIMAI_REPORT_USERNAME: player
    MAIMAI_REPORT_DISPLAY_NAME: Player
    MAIMAI_REPORT_TIMEZONE: UTC
    MAIMAI_REPORT_GAME: maimaidx
    MAIMAI_REPORT_IMPORT_TYPE: api/myt-maimaidx
    MAIMAI_REPORT_CURRENT_VERSION_DISPLAY_NAMES: '["Exact current display version"]'
    MAIMAI_REPORT_OUTPUT_DIR: output
```

Replace the placeholder with a reviewed full 40-character commit SHA from this repository whose CI passed; it is not a runnable default. Do not assume that a release tag exists. The action fails closed for public callers, validates configuration before installation, runs offline `doctor`, and then starts exactly one import before rendering. It does not upload, deploy, publish, schedule, or retain anything; those remain explicit caller responsibilities.

## GitHub Actions private artifact mode

The **Build private report artifact** workflow runs only from an explicit `workflow_dispatch`; it has no push, pull-request, or schedule trigger. It refuses to sync or upload an artifact unless GitHub reports that the repository is private. GitHub documents manual workflow runs [here](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow). Its concurrency group prevents overlapping imports, the job has a 15-minute timeout, and it uploads output without committing it.

For this mode, create a new **private repository** and push a clone of the product
there using your own remote. A public fork is not private storage. Run the copied
workflow in your private repository, not in the public product repository.
Alternatively, use the small private caller described above. Public repository
visibility makes Actions logs visible too; an artifact name containing "private"
does not protect it.

A copied or forked repository receives no secrets. In **Settings → Secrets and variables → Actions**, create:

- Secret `KAMAITACHI_API_TOKEN`.
- Required variables `MAIMAI_REPORT_USERNAME`, `MAIMAI_REPORT_DISPLAY_NAME`, `MAIMAI_REPORT_TIMEZONE`, and `MAIMAI_REPORT_CURRENT_VERSION_DISPLAY_NAMES` (a nonempty JSON string array).
- Optional variables `MAIMAI_REPORT_GAME` (default `maimaidx`), `MAIMAI_REPORT_IMPORT_TYPE` (default `api/myt-maimaidx`), and `MAIMAI_REPORT_ARTIFACT_RETENTION_DAYS` (default `7`, workflow range `1`–`30`).

Do not create Cloudflare values for artifact mode. From **Actions**, choose the workflow, use **Run workflow**, and wait for the single run. Required configuration is checked before installation or sync, and missing names are reported without displaying secret values.

To download, open that authenticated workflow run and select the `maimai-report` artifact in its Artifacts section. GitHub artifacts from a private repository remain subject to repository access; the ZIP contains personal HTML and raw JSON, so move it to private storage and delete local downloads when finished. [GitHub artifact documentation](https://docs.github.com/en/actions/how-tos/writing-workflows/choosing-what-your-workflow-does/storing-and-sharing-data-from-a-workflow)

## Optional hosting and protected Cloudflare publishing

The generated HTML is ordinary static content and can be served by any static host. The file does not call home, but **static hosting is not access control**. Unless a host is configured to authenticate viewers, assume the report is public. Prefer local use or a private authenticated service.

The isolated adapter under `deploy/cloudflare/` provides a generic Cloudflare Worker with private/no-store caching, a restrictive CSP and Permissions Policy, noindex, no-referrer, frame denial, and nosniff. Publishing is separate from sync and disabled unless all of these are true:

- repository variable `MAIMAI_REPORT_PUBLISHING_ENABLED` is exactly `true`;
- a previously generated artifact run ID is selected;
- the operator checks that the exact hostname is already protected by their Cloudflare Access policy;
- the operator types `PUBLISH PRIVATE REPORT`;
- the `private-report-production` GitHub Environment permits the job; and
- all owner-specific Cloudflare variables and the environment-scoped API token are configured.

The generated Wrangler configuration sets `workers_dev = false` and `preview_urls = false`; it has no committed account, zone, domain, route, or Worker value. Do not run the publish workflow until the destination and Access policy exist and have been tested with an unauthorized browser. See [the deployment guide](DEPLOYMENT.md).

GitHub required-reviewer protection has plan limitations: GitHub currently documents required reviewers for **public** repositories on Free, Pro, and Team; enforcing them for a **private** repository requires GitHub Enterprise. Environment secrets in private repositories also require an eligible paid plan. If the plan cannot enforce reviewers, the manual dispatch and typed confirmation still operate but are not an independent approval boundary. [Deployment and environment rules](https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments)

## Troubleshooting

- **Missing token:** set `KAMAITACHI_API_TOKEN` in the current process or the exact Actions secret. Never add it to TOML or pass it on the command line.
- **401/403 or import rejected:** confirm the key is current and the official integration UI grants the currently required from-API capability (`submit_score` in the audited upstream source). Revoke and replace rather than broadening unrelated permissions.
- **Unknown username / empty payload:** confirm the configured Kamaitachi username, game identifier, account visibility/current API behavior, and that the configured MYT integration belongs to that account.
- **Invalid current-version JSON:** Actions/environment values must look like `["Exact Version"]`; the outer value is JSON and every element is a nonempty string.
- **Timezone not found:** use a valid IANA name. Stock Windows supports this project's `UTC` fallback; for another zone install the optional database with `python -m pip install ".[timezone]"`, or use a Python distribution/system that supplies IANA data.
- **SSE failed or ended before `done`:** do not immediately retry. Check Kamaitachi's import status first; network loss does not prove the server-side import stopped. A later explicit run starts one new import.
- **SSE timeout:** the client waits up to 650 seconds while upstream currently applies a ten-minute stream timeout. Check account integration/import status before deciding whether to invoke another run.
- **Output denied or path is a file:** choose a writable directory and run offline `doctor`; Windows ACLs and managed folders can override ordinary permissions.
- **Empty session:** this is valid when no post-cutoff score or PB change appears. Generate `demo --scenario empty` to compare the intended UI.
- **Incomplete New 15:** this is valid for an account without 15 qualifying current-version PBs. Recheck the exact version-name configuration before interpreting it.
- **Report has an external URL:** generation or deployment validation will reject it. Do not weaken that check; investigate newly added template content.
- **Artifact cannot be downloaded:** verify the run ID, workflow success, artifact retention window, and your access to the private repository.
- **Cloudflare publish is blocked:** keep publishing off while checking the Environment, token, account ID, exactly one routing mode, zone ID for routes, and Access protection. Artifact and local modes do not depend on Cloudflare.

## Remove private output, revoke access, or stop publishing

Close the local server before cleanup. Review the exact path, then remove the ignored output directory:

```powershell
# Windows PowerShell
Resolve-Path -LiteralPath .\output
Remove-Item -LiteralPath .\output -Recurse -Force
Remove-Item Env:KAMAITACHI_API_TOKEN -ErrorAction SilentlyContinue
```

```bash
# macOS or Linux
realpath ./output
rm -rf -- ./output
unset KAMAITACHI_API_TOKEN
```

This is permanent unless your filesystem provides recovery. Also delete any extracted Actions ZIP and empty the relevant trash/recycle location if required by your threat model.

To revoke API access, use the current Kamaitachi API-key UI to delete the key, then remove the Actions secret. To disable publishing, set or delete `MAIMAI_REPORT_PUBLISHING_ENABLED` so it is no longer exactly `true`, disable the publish workflow if desired, revoke the Cloudflare API token, and remove the Worker route/custom domain and Access application through your own Cloudflare change process. Removing infrastructure is not automated by this repository.

## More documentation

- [Configuration reference](CONFIGURATION.md)
- [Architecture and data flow](ARCHITECTURE.md)
- [Report presentation and browser tests](PRESENTATION.md)
- [Optional embedded artwork](ARTWORK.md)
- [Hosted session history](HOSTED_HISTORY.md)
- [Deployment guide](DEPLOYMENT.md)
- [Standalone-project migration note](MIGRATION.md)
- [Security policy](../SECURITY.md)
- [Contributing](../CONTRIBUTING.md)

The project is licensed under the [MIT License](../LICENSE).
