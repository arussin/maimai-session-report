# Security policy

This project processes credentials and personal play data. Treat security and privacy regressions as product failures, even when they do not enable code execution.

## Supported version

Security fixes are applied to the current default branch. There is no long-term-support release line yet.

## Report a vulnerability privately

Use this repository's **Security → Report a vulnerability** private advisory flow if it is enabled. Include the affected commit/version, impact, reproduction using synthetic data, and a proposed mitigation if known.

Never put any of the following in an issue, pull request, fixture, test log, screenshot, patch, or chat:

- Kamaitachi bearer/API tokens or authorization headers;
- MYT/maimai card access codes, cookies, or credentials;
- raw API responses or generated reports from a real player;
- Cloudflare API tokens, account/zone identifiers tied to a private deployment, or Access assertions;
- GitHub Actions artifact contents from a live run.

If private advisories are unavailable, request a private contact channel from the repository owner without disclosing the vulnerability or any secret in the public request. Revoke an exposed credential first; do not wait for triage.

## Security invariants

- `KAMAITACHI_API_TOKEN` is the only supported Kamaitachi token source. It is not a CLI option or TOML field.
- Configuration is fully validated before a live command's first network request.
- Each explicit live invocation starts at most one import and waits through SSE; there is no retry/polling loop.
- Upstream import failure bodies are never relayed to CLI or Actions logs.
- Installation, module import, tests, demo, render, serve, offline doctor, push, and pull request events never sync.
- Reports embed their data, styles, scripts and artwork. No remote fonts, analytics or telemetry are allowed. The sole optional runtime service is the footer-activated, isolated BMC checkout iframe; its parent-page script is prohibited.
- Embedded JSON cannot terminate its script-data element through `</script>` or HTML-special input.
- Generated JSON/HTML and local deployment state are ignored and must never be committed.
- The local server allows only the selected Host header, logs no request target, and rejects wildcard binds.
- The artifact and publish workflows refuse to process a report unless the repository is private.
- Publishing is disabled by default. Explicit release operations require apply intent; an owner-enabled refresh may publish only its successful meaningful capture, with production Environment controls.
- The Worker disables `workers.dev`, preview URLs, metrics/error reporting, observability, and cache storage in generated configuration.

Automated tests mock every API and SSE interaction and must remain network-free. A contribution that needs a real account response for a test is not acceptable; reduce the behavior to a synthetic schema fixture.

## Operational response

If a Kamaitachi token may have leaked:

1. Delete/revoke it in the current official Kamaitachi API-key UI.
2. Remove it from GitHub secrets and the local process environment.
3. Replace it with a new least-capability key only after the leak path is fixed.
4. Purge affected logs, artifacts, caches, and history through the relevant provider's incident process; deleting a current file alone does not remove Git history.

If a report was publicly exposed, disable the route/host first, then review host/CDN logs and caches under your own incident policy. A no-store header reduces caching but cannot retract a file already downloaded.

If Cloudflare publishing credentials leaked, revoke the API token, disable the publish workflow/repository flag, review account audit activity, and rotate any related credential. The project never changes Access or DNS automatically, so restore those through a separate reviewed change.

## Scope notes

The local server is intended for `127.0.0.1` and rejects wildcard binds. Selecting one exact non-loopback interface creates a new exposure boundary. Static HTML privacy depends on file permissions and host access control, not on obfuscation, CSP, noindex, or a difficult URL.

Third-party service security, account recovery, and the behavior of owner-created Access policies are outside this repository's control. Keep dependencies/actions pinned, review upstream API changes, and use the smallest provider permissions that current official documentation supports.

## Installation configuration

Owner `instance.toml` is tracked only in the private installation repository. Account,
zone and database IDs are non-secret configuration; they still identify a private
deployment and do not belong in public fixtures. Credentials enter only the relevant
composite-action step through GitHub secrets. R2 buckets, Worker alternate domains,
Access and exact binding identities are verified before a retained release.

The installation ZIP uses an explicit seven-file allowlist. Do not add generated
Wrangler output, private operation artifacts or real report evidence to it. Public
source code and private operation are separate: the caller's privacy check uses
the caller repository's visibility, not that of this product repository.

Before a private repository becomes public, review all reachable branches, tags,
PR discussions and Actions history, not just the current tree. Deleted files can
remain in commits and closed PRs. Preserve immutable commits used by private
callers; a clean current diff does not authorize exposing historical personal data.
See [GitHub's visibility consequences](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/managing-repository-settings/setting-repository-visibility).

`verify-fresh` is an explicit exception for temporary synthetic writes and cleanup.
It requires apply intent and empty primary/backup buckets and indexes before any
fixture write. Deletion is restricted to recorded capture IDs in a random synthetic
scope and unchanged, hash-recorded objects under that run's synthetic prefix.
Each resource is cleaned independently if another cleanup fails. Unknown or changed
data stops deletion; the operation never deletes a bucket, database or schema.
Its ownership journal and evidence contain private resource identities and must
remain in private operation artifacts, including after cancellation or failure.
