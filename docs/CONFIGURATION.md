# Standalone CLI and legacy-action configuration

For the hosted installation, use the [instance configuration reference](INSTALLATION.md#configuration-reference).
Its tracked private `instance.toml` is the single source of owner settings; conflicting
legacy environment overrides are rejected. It does not use the precedence below
or require a second `config.toml` or a parallel set of repository variables.

This page documents the supported standalone CLI and older action entry points.

Configuration contains identity and behavior but never credentials. Copy `config.example.toml` to ignored `config.toml`, restrict access as appropriate for your system, and keep the Kamaitachi token only in `KAMAITACHI_API_TOKEN`.

Values resolve in this order, highest priority first:

1. Explicit command options.
2. Canonical environment variables.
3. The selected TOML file.
4. Safe generic defaults.

The loader validates all resolved values. Live operations perform stricter validation before constructing a network client: a username, at least one exact current-version display name, a valid output directory, and a nonempty token must all be available.

## TOML fields

| TOML key | Type | Default | Meaning |
| --- | --- | --- | --- |
| `kamaitachi.username` | string | empty | Exact Kamaitachi username; required for network mode. |
| `kamaitachi.game` | string | `maimaidx` | Kamaitachi game identifier. |
| `kamaitachi.import_type` | string | `api/myt-maimaidx` | From-API importer started once per explicit live run. |
| `player.display_name` | string | `Player` | Label embedded in the private report. |
| `player.timezone` | string | `UTC` | IANA timezone used for display/session timing. |
| `report.current_version_display_names` | string array | empty | Exact Kamaitachi `chart.data.displayVersion` values included in New 15. Required for live mode. |
| `report.output_dir` | path | `output` | Directory for the six private JSON files written by `sync`. |
| `actions.artifact_retention_days` | integer | `7` | Requested Actions retention, 1–90 in the application; the bundled workflow deliberately limits it to 1–30. |
| `publishing.enabled` | boolean | `false` | Intent flag only. It does not publish anything by itself. |
| `publishing.provider` | string | `cloudflare` | Adapter identifier. |
| `publishing.cloudflare_account_id` | string | empty | Owner's account ID for optional Cloudflare publishing. |
| `publishing.cloudflare_worker_name` | string | empty | Optional local metadata; the publish workflow uses its repository variable instead. |
| `publishing.cloudflare_custom_domain` | string | empty | Exact owner-controlled hostname for custom-domain routing. |
| `publishing.cloudflare_route_pattern` | string | empty | Owner-controlled Worker route pattern; alternative to a custom domain. |
| `publishing.cloudflare_zone_id` | string | empty | Owner's zone ID when a route pattern is used. |
| `publishing.report_path` | string | `/` | Exact URL path the adapter serves. |

The optional workflow receives these deployment settings from repository variables and the API token from an Environment secret. Local TOML deployment fields are owner-supplied metadata only; setting them never triggers a deployment.

Example:

```toml
[kamaitachi]
username = "your-kamaitachi-username"
game = "maimaidx"
import_type = "api/myt-maimaidx"

[player]
display_name = "Your display name"
timezone = "Europe/London"

[report]
current_version_display_names = ["Exact Version A", "Exact Version B"]
output_dir = "output"

[actions]
artifact_retention_days = 7

[publishing]
enabled = false
provider = "cloudflare"
cloudflare_account_id = ""
cloudflare_worker_name = ""
cloudflare_custom_domain = ""
cloudflare_route_pattern = ""
cloudflare_zone_id = ""
report_path = "/"
```

`config.toml` is ignored, but Git ignore rules are not encryption. Do not commit it if the identity itself is sensitive.

## Canonical environment variables

| Environment variable | Corresponding value | Format |
| --- | --- | --- |
| `MAIMAI_REPORT_USERNAME` | username | text |
| `MAIMAI_REPORT_DISPLAY_NAME` | display name | text |
| `MAIMAI_REPORT_TIMEZONE` | timezone | IANA name |
| `MAIMAI_REPORT_GAME` | game | identifier text |
| `MAIMAI_REPORT_IMPORT_TYPE` | import type | `family/name` text |
| `MAIMAI_REPORT_CURRENT_VERSION_DISPLAY_NAMES` | current versions | JSON array of nonempty strings |
| `MAIMAI_REPORT_OUTPUT_DIR` | private output directory | filesystem path |
| `MAIMAI_REPORT_ARTIFACT_RETENTION_DAYS` | artifact retention | integer text |
| `MAIMAI_REPORT_PUBLISHING_ENABLED` | publish intent | `true` or `false` |

The only application secret is:

| Secret environment variable | Source | Never accepted from |
| --- | --- | --- |
| `KAMAITACHI_API_TOKEN` | current process or identically named Actions secret | TOML, CLI argument, fixture, generated report |

The current-version environment value is JSON. Quote it as required by the shell:

```powershell
$env:MAIMAI_REPORT_CURRENT_VERSION_DISPLAY_NAMES = '["Exact Version A","Exact Version B"]'
```

```bash
export MAIMAI_REPORT_CURRENT_VERSION_DISPLAY_NAMES='["Exact Version A","Exact Version B"]'
```

Do not document or depend on undocumented aliases; the canonical names above are the portable interface used by the workflows.

## Command options

Configuration options are attached to each command that needs them and therefore appear after the command name:

```text
--config PATH
--username USERNAME
--display-name NAME
--timezone IANA_NAME
--game IDENTIFIER
--import-type FAMILY/NAME
--current-version DISPLAY_NAME   (repeat for aliases)
--output-dir PATH
```

For example, this command overrides the file's username and New 15 names without modifying it:

```console
maimai-report doctor --config config.toml --username fictional-player --current-version "Exact Version A" --current-version "Exact Version B"
```

Command-specific paths are separate:

- `demo --output PATH [--scenario complete|empty|incomplete]`
- `render --report-input PATH --after-pbs PATH --output PATH`
- `sync --output-dir PATH`
- `sync-and-render --output PATH`
- `serve --file PATH [--host 127.0.0.1] [--port 8000]`

`demo` never reads live configuration. `serve` only reads the selected HTML. `render` reads local JSON plus non-secret display/classification configuration. Only `doctor --network`, `sync`, and `sync-and-render` can make network requests; `doctor --network` never starts an import.

## Validation rules

- Python must be 3.11 or newer.
- Timezone must resolve as an IANA timezone on the host. `UTC` has a built-in fallback; Windows users choosing another zone can install `.[timezone]`.
- Game/import identifiers accept a narrow identifier syntax; whitespace and URLs are rejected.
- Each current-version name must be nonempty, unique, and exact.
- The output path must be or be creatable as a directory and must be writable.
- Artifact retention is 1–90 in local configuration and 1–30 in the short-lived artifact workflow.
- Publishing remains false by default.
- TOML rejects token/password/access-code-like keys, including unknown nested sections.

An error reports the field and next action without printing a token, authorization header, secret-bearing environment value, or server response body.

## Finding current-version names

Classification uses the exact `displayVersion` value attached to each Kamaitachi chart. The project deliberately does not guess the current maimai release. Confirm names against current Kamaitachi data when initially configuring the account and after every version transition. Multiple exact values are supported for aliases or transition periods.

If the values are wrong, the total PB data is still present but Old 35/New 15 classification can be wrong. Run the incomplete demo to understand how a genuinely short New 15 pool should look before diagnosing configuration.
