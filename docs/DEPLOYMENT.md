# Hosted deployment and the legacy static adapter

For the complete hosted product, follow the [installation guide](INSTALLATION.md).
It covers the private TOML, four shared-action workflows, R2/D1 history and backup,
fresh hosted verification, protected Worker bootstrap, retained release and rollback.
Owners do not need to write deployment code or maintain a local database.

The rest of this page describes the supported **legacy single-file adapter** and
its older artifact/publish workflows. Its repository variables and
`private-report-production` Environment are not the new installation's interface.
The shared installation uses `instance.toml` and `production` instead. Neither
path automates DNS or Access configuration. Setup, temporary hosted verification
and deployment are distinct operations; a PR or validation run performs none of them.

## Ordinary static hosting

`report.html` embeds CSS, JavaScript and report data. With support disabled, it
makes no runtime request. Optional support lazily loads only the isolated BMC
checkout iframe. A static host must protect every report and download request.

Before uploading, answer both questions:

1. Does the host require authentication for **every** request to this exact file/hostname?
2. Have you verified denial in a signed-out or private browser rather than relying on a hard-to-guess URL?

If either answer is no, treat the report as public. CSP, `noindex`, `no-store`, and robots headers reduce secondary risks; they do not authenticate a viewer. Configure equivalent headers where the host supports them:

- `Cache-Control: private, no-store, max-age=0`
- `Content-Security-Policy: default-src 'none'; base-uri 'none'; connect-src 'none'; font-src 'none'; form-action 'none'; frame-ancestors 'none'; img-src data:; manifest-src 'none'; media-src 'none'; object-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; worker-src 'none'`
- `Referrer-Policy: no-referrer`
- `X-Frame-Options: DENY`
- `X-Content-Type-Options: nosniff`
- `X-Robots-Tag: noindex, nofollow, noarchive`
- a restrictive `Permissions-Policy`

The CSP above is the no-support baseline. If support is enabled, use the shared
[support policy](SUPPORT.md) and adapter header implementation; do not add a
parent-page BMC script or broaden arbitrary frame/network origins.

## Bundled Cloudflare adapter

`deploy/cloudflare` wraps one generated HTML file in a small module Worker. It serves GET/HEAD only at `CLOUDFLARE_REPORT_PATH`, returns 404 elsewhere, sends the restrictive headers above, and neither logs nor fetches report data.

The generator creates ignored files under `deploy/cloudflare/.wrangler/` and enforces:

- `workers_dev: false`—no alternate `*.workers.dev` deployment URL;
- `preview_urls: false`—no version preview URL;
- Wrangler metrics and error reporting disabled through config/workflow environment;
- Worker observability, dependency instrumentation, and Logpush disabled;
- exactly one owner-supplied custom domain or route;
- no unexpected HTTP/HTTPS URL in the selected HTML; only the explicitly enabled support origin is allowed;
- no committed account, zone, route, hostname, or Worker name.

These settings follow Cloudflare's current [Wrangler configuration reference](https://developers.cloudflare.com/workers/wrangler/configuration/), [workers.dev controls](https://developers.cloudflare.com/workers/configuration/routing/workers-dev/), and [preview URL controls](https://developers.cloudflare.com/workers/versions-and-deployments/preview-urls/).

### Choose a routing mode

Use one, never both:

- **Custom Domain:** an exact lowercase hostname such as `report.example.invalid`; appropriate when the Worker is the origin for that hostname. See [Cloudflare Custom Domains](https://developers.cloudflare.com/workers/configuration/routing/custom-domains/).
- **Route:** a pattern such as `report.example.invalid/*` plus the matching 32-character zone ID; appropriate when a zone already has an origin/routing plan. See [Cloudflare Routes](https://developers.cloudflare.com/workers/configuration/routing/routes/).

The adapter rejects wildcard custom domains, schemes/paths in the custom-domain value, malformed routes, missing route zone IDs, and route patterns that do not cover the exact report path. Its report path is exact (`/` or, for example, `/private/report.html`). If the route is `report.example.invalid/private/*`, set `CLOUDFLARE_REPORT_PATH=/private/report.html` (or another exact path under that prefix). Ensure the Access application covers the actual hostname/path selected.

### Protect the hostname first

Create and test a Cloudflare Access self-hosted application/policy for the exact destination before any report deployment. Use the owner's chosen identity provider and least-access policy. Cloudflare documents Worker protection and the difference between preview and production protection in [Cloudflare Access for Workers](https://developers.cloudflare.com/workers/configuration/cloudflare-access/).

Do not enable a public bypass. Verify both an authorized session and denial from an unsigned/private browser. The workflow asks the operator to attest to this check, but it cannot inspect the meaning of an owner-created Access policy. That attestation is not a substitute for a test.

### Configure the production GitHub Environment

Create an Environment named exactly `private-report-production` before the first publish run. Add an environment protection/reviewer rule when the repository plan supports it, restrict deployments to the intended branch, and store `CLOUDFLARE_API_TOKEN` as an **Environment secret**, not a repository file or variable.

GitHub warns that referencing a nonexistent Environment can create it without protection. Configure it in advance and review it before every first deployment. Current plan limitation: required reviewers for private repositories require GitHub Enterprise; Free, Pro, and Team document required reviewers only for public repositories. Environment secrets on private repositories also require an eligible plan. See [GitHub deployment environments](https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments), [managing environments](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments), and [reviewing deployments](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/review-deployments).

If your plan cannot enforce a reviewer, the separate manual dispatch, boolean Access assertion, and typed confirmation still prevent accidental generation-to-deployment coupling, but they do not create independent human approval. Keep publishing disabled unless that tradeoff is acceptable.

### Create a narrowly scoped Cloudflare token

Follow Cloudflare's current CI instructions: from the account API-token page, create a custom token using **Edit Cloudflare Workers**, give it a distinct deployment-only name, and scope it to only the intended account and zone. Confirm the current dashboard-generated permissions before saving; routing products and permission names can evolve. Store only the resulting token as Environment secret `CLOUDFLARE_API_TOKEN`. Cloudflare's official steps are in [GitHub Actions for Workers](https://developers.cloudflare.com/workers/ci-cd/external-cicd/github-actions/).

Never use the Global API Key. Do not paste a token into `wrangler.json`, TOML, workflow YAML, `.dev.vars`, a command argument, an issue, or chat.

### Repository and Environment values

Configure these GitHub **repository variables**:

| Variable | Required | Value |
| --- | --- | --- |
| `MAIMAI_REPORT_PUBLISHING_ENABLED` | yes | Keep absent/`false`; set exactly `true` only after all protection is ready. |
| `CLOUDFLARE_ACCOUNT_ID` | yes | Owner's Cloudflare account ID. |
| `CLOUDFLARE_WORKER_NAME` | yes | New or owner-approved generic Worker name, lowercase/digits/dashes. |
| `CLOUDFLARE_CUSTOM_DOMAIN` | one routing mode | Exact protected hostname, no scheme/path/wildcard. |
| `CLOUDFLARE_ROUTE_PATTERN` | other routing mode | Exact route pattern. |
| `CLOUDFLARE_ZONE_ID` | with route | Zone ID matching the route. |
| `CLOUDFLARE_REPORT_PATH` | optional | Exact served path; default `/`. |

Configure this `private-report-production` **Environment secret**:

| Secret | Required | Value |
| --- | --- | --- |
| `CLOUDFLARE_API_TOKEN` | yes | Narrow deployment token described above. |

`KAMAITACHI_API_TOKEN` is unrelated and remains a repository Actions secret used only by the artifact workflow. The publish job does not receive it and cannot sync.

### Validate the adapter without publishing

Node.js 22 or newer is required only for this optional adapter. These commands generate synthetic output and perform a Wrangler dry-run; they do not contact Cloudflare to deploy a Worker.

PowerShell:

```powershell
maimai-report demo --output .\output\demo-report.html
Push-Location .\deploy\cloudflare
npm ci --ignore-scripts --no-audit --no-fund
$env:CLOUDFLARE_WORKER_NAME = 'fictional-private-report'
$env:CLOUDFLARE_CUSTOM_DOMAIN = 'report.example.invalid'
$env:CLOUDFLARE_REPORT_PATH = '/'
node .\scripts\generate-config.mjs --report ..\..\output\demo-report.html
npx --no-install wrangler deploy --dry-run --config .\.wrangler\wrangler.generated.jsonc --outdir .\.wrangler\dry-run
Pop-Location
```

macOS/Linux:

```bash
maimai-report demo --output ./output/demo-report.html
cd ./deploy/cloudflare
npm ci --ignore-scripts --no-audit --no-fund
export CLOUDFLARE_WORKER_NAME='fictional-private-report'
export CLOUDFLARE_CUSTOM_DOMAIN='report.example.invalid'
export CLOUDFLARE_REPORT_PATH='/'
node ./scripts/generate-config.mjs --report ../../output/demo-report.html
npx --no-install wrangler deploy --dry-run --config ./.wrangler/wrangler.generated.jsonc --outdir ./.wrangler/dry-run
cd ../..
```

The fictional `.invalid` hostname cannot be deployed as a real destination. Do not replace it and remove `--dry-run` during setup; production deployment belongs in the reviewed workflow.

### Manually publish a selected artifact

1. Manually run **Build private report artifact** and inspect its successful run.
2. Copy its numeric run ID from the run URL.
3. Confirm the exact destination denies an unsigned browser and permits the intended identity.
4. Set `MAIMAI_REPORT_PUBLISHING_ENABLED` exactly `true` only for the publishing period.
5. Manually run **Publish protected report to Cloudflare**.
6. Enter the run ID, check the Access-protection assertion, and type `PUBLISH PRIVATE REPORT` exactly.
7. Review/approve the `private-report-production` deployment if the plan enforces it.
8. After completion, test response headers and both authorized/unauthorized access again.

The workflow downloads only the named `maimai-report` artifact from the selected run, rejects a missing/external-URL report, installs the locked adapter, generates an ignored config, performs a dry bundle, then invokes one deployment. It never generates a report and never runs on a push.

## Disable, rotate, or remove publishing

To stop future publication immediately, remove or set `MAIMAI_REPORT_PUBLISHING_ENABLED` to anything other than exactly `true`, then disable the workflow if desired. Revoke the Cloudflare API token and delete the Environment secret when no longer needed.

Removing a deployed Worker, route/custom domain, DNS record, or Access application is deliberately outside automation. Perform those changes through your normal reviewed Cloudflare process and verify the hostname no longer serves the report. Do not remove Access before removing the protected content route.

For a content update, generate a new artifact and explicitly publish its run ID. For rollback, use the owner's reviewed Cloudflare deployment controls or republish a retained, trusted private artifact; do not commit HTML to create a rollback mechanism.

## Response-header verification

After an authorized deployment, inspect the main report response and 404/405 responses. All should have private/no-store caching, CSP, no-referrer, frame denial, nosniff, noindex, and restrictive Permissions Policy. The main document should have `text/html; charset=utf-8`; POST should return 405 with `Allow: GET, HEAD`.

The adapter test suite checks these behaviors locally. Cloudflare configuration and Access behavior must still be tested at the owner's destination because edge rules outside this repository can alter responses.
