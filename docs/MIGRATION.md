# Migration from a personalized workflow

This is the earlier migration to the standalone CLI. For the current hosted
installation, use [Reusable installation migration](INSTALLATION_MIGRATION.md).
Do not apply these clean-start instructions to an existing R2/D1 history archive.

This repository is a generic, standalone project derived from the useful behavior of a personalized private report workflow. It has fresh history and is not a historical fork. Only reviewed implementation ideas and sanitized presentation behavior belong here.

## What was deliberately retained

- before/import/SSE/after synchronization with one import per explicit run;
- session-cutoff and changed-PB analysis;
- Old 35/New 15 rating pools driven by explicit version configuration;
- a polished, self-contained, zero-runtime-request HTML report;
- a private-by-default local workflow and optional protected hosting adapter.

## What was deliberately removed

- player identity, score records, raw responses, generated reports, tokens, cookies, and access codes;
- personal domain, Cloudflare account/zone/route/Worker data, email, and access-policy assumptions;
- a fixed current-release assumption;
- push-triggered deployment and any coupling between generation and publication;
- original commit history, repository settings, Actions artifacts, and secrets.

## Moving an owner to this project

1. Clone this standalone repository; do not transplant `.git` or workflow history.
2. Generate and inspect the bundled demo before supplying personal configuration.
3. Copy `config.example.toml` to ignored `config.toml` and enter only the new owner's non-secret identity/settings.
4. Confirm exact current Kamaitachi display-version names rather than copying an old release name.
5. Create a new least-capability Kamaitachi API key in the new owner's official account and inject it only through `KAMAITACHI_API_TOKEN`.
6. Configure the new owner's MYT integration only in the official Kamaitachi UI. Never migrate an access code through files or chat.
7. Run offline `doctor`, then `doctor --network` if desired, before the first explicit sync.
8. If using Actions, create new repository secrets/variables; forks and copies do not inherit them.
9. If publishing, build new owner-controlled protection and routing configuration and test unauthorized access before enabling the separate workflow.

Do not copy old output or an old artifact merely to seed this project. If historical comparisons are important, keep them in private archival storage outside Git and transform only the minimum necessary data through a reviewed, local process.

## Compatibility expectations

This is not a drop-in deployment migration. Configuration names, output schemas, and safety gates are intentionally explicit. The default path is local, publishing remains false, and deployment identifiers have no fallback values. Treat a future importer/API/schema change as a reviewed application change with new mocked fixtures—not as an opportunity to reuse a private response.
