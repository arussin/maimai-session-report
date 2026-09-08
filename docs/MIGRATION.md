# Moving to the standalone CLI

This guide covers a clean start with the standalone CLI. For an existing hosted
installation, use [Reusable installation migration](INSTALLATION_MIGRATION.md).
Do not apply these clean-start instructions to an existing R2/D1 history archive.

This project began as a personal report workflow and was extracted into a standalone
application with fresh Git history. Account configuration and generated player data
are separate from the shared implementation.

## Shared behavior

- before/import/SSE/after synchronization with one import per explicit run;
- session-cutoff and changed-PB analysis;
- Old 35/New 15 rating pools driven by explicit version configuration;
- a self-contained HTML report with no runtime requests when optional support is disabled;
- a private-by-default local workflow and optional protected hosting adapter.

## Settings to supply yourself

- your Kamaitachi username, display name and timezone;
- the exact current-version display names for the New 15 pool;
- your Kamaitachi API token, through the environment only;
- if hosting: your private repository, destination, credentials and access controls.

No account data, secrets, deployment settings or historical workflow artifacts
are transferred by cloning this repository.

## Moving an owner to this project

1. Clone this repository and follow the [local setup guide](LOCAL.md).
2. Generate and inspect the bundled demo before supplying personal configuration.
3. Copy `config.example.toml` to ignored `config.toml` and enter only the new owner's non-secret identity/settings.
4. Confirm exact current Kamaitachi display-version names rather than copying an old release name.
5. Create a new least-capability Kamaitachi API key in the new owner's official account and inject it only through `KAMAITACHI_API_TOKEN`.
6. Configure the new owner's MYT integration only in the official Kamaitachi UI. Never migrate an access code through files or chat.
7. Run offline `doctor`, then `doctor --network` if desired, before the first explicit sync.
8. If using Actions, create new repository secrets/variables; forks and copies do not inherit them.
9. If publishing, build new owner-controlled protection and routing configuration and test unauthorized access before enabling the separate workflow.

Keep existing reports and API output in private storage outside Git. The
[render command](LOCAL.md#offline-and-local-rendering) can use compatible local inputs
without starting another import.

## Compatibility expectations

This is not a drop-in deployment migration. Use the documented configuration and
check the input schema before importing existing files. Local operation is the
default, publishing starts disabled, and deployment identifiers have no fallback
values. An existing hosted archive needs the separate installation migration guide.
