# Contributing

## README previews

The committed sample HTML and screenshots contain only the bundled fictional
demo. After the browser development setup below, regenerate them with
`node tests/browser/capture-readme.mjs` from the repository root. The script uses
the active Python interpreter and a local Chromium browser, blocks HTTP requests,
and never starts a sync. The unit suite verifies the sample against `render_demo`
byte-for-byte after UTF-8 decoding. Never substitute a real report or screenshot.

Changes are welcome when they preserve the private-by-default contract and remain useful to an unrelated new owner. Never use a real account, token, response, report, Actions artifact, access code, or deployment value while developing or reviewing a change.

## Development environment

Use Python 3.11 or newer. Create the environment, then activate it **before**
installing tools:

```powershell
# Windows PowerShell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --no-deps -e .
python -m pip install -r requirements-dev.txt
```

```bash
# macOS / Linux
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --no-deps -e .
python -m pip install -r requirements-dev.txt
```

The normal CLI and demo have no third-party runtime dependency. The full test
suite also covers optional artwork and hosted history; its pinned development
tools include those dependencies and an IANA timezone database for Windows.
Installing tools needs a network or a prepared wheel cache. Tests themselves
never use a live account or service.

Before submitting a change, run:

```console
ruff check .
ruff format --check .
python -m unittest discover -s tests -v
maimai-report doctor
maimai-report demo --output output/demo-report.html
```

Verify the generated file has no external HTTP/HTTPS URL. In PowerShell:

```powershell
if (Select-String -Path .\output\demo-report.html -Pattern 'https?://') { throw 'external URL found' }
```

On macOS/Linux:

```bash
! grep -Ein 'https?://' ./output/demo-report.html
```

For adapter changes, also run Node.js 22 or newer checks:

```console
cd deploy/cloudflare
npm ci --ignore-scripts --no-audit --no-fund
npm run check
```

`npm ci` uses the committed lock file. Do not commit `node_modules`, `.wrangler`, a generated report module, or generated Wrangler configuration.

## Test rules

- Mock all HTTP and SSE operations. Tests must pass with outbound network disabled.
- Use only intentionally synthetic names/songs/scores and reserved `.invalid` or `.test` domains; mock all management/network calls.
- Cover success, explicit failure, timeout/EOF behavior, and malformed service responses.
- Preserve one import-start call per explicit sync. Never add automatic retry around import start.
- Exercise complete, empty, and incomplete pool/session states.
- Test hostile strings containing HTML metacharacters, Unicode, and `</script>`.
- Assert local-only commands and offline `doctor` do not construct or call a network client.
- Keep deterministic rendering and the external-URL check.
- Publishing changes must retain manual-only triggers, explicit enablement/confirmation, production Environment usage, and disabled alternate URLs.

If an upstream schema detail is uncertain, cite current official documentation or pinned upstream source in the change. Do not derive fixtures from a private Actions download.

## Change hygiene

Keep implementation, documentation, tests, and example configuration aligned. Do not weaken `.gitignore` coverage for generated data. Inspect `git status` and search the complete diff for tokens, authorization headers, access codes, real identities, domains, and raw responses before committing.

Use concise commits. Do not rewrite another contributor's unrelated working-tree changes. Security-sensitive findings should follow [SECURITY.md](SECURITY.md), not a public issue.

## Documentation claims

Kamaitachi, MYT, Cloudflare, and GitHub UI labels and plan behavior change. Link to primary sources and distinguish current verified behavior from steps the owner must confirm. Never invent token permissions, account-menu names, regional availability, approval guarantees, or an assumed current maimai version.

## Installation changes

Keep `templates/private-caller`, the configuration reference and the composite
action aligned. Run the existing Python and Worker checks, then the browser suite:

```console
python -m pip install ".[history,artwork]"
npm ci --ignore-scripts --no-audit --no-fund --prefix tests/browser
npm ci --ignore-scripts --no-audit --no-fund --prefix deploy/cloudflare
cd tests/browser
npx playwright install --with-deps chromium webkit
cd ../..
python tests/browser/prepare.py
python -m tests.history_fixture tests/browser/generated/history
python -m tests.prepare_installation tests/browser/generated/installations
npm test --prefix tests/browser
```

The package tests consume the actual ZIP, check common workflow pins, and stage two
fictional owners through the shared Worker. Browser evidence contains synthetic
data only and covers desktop, tablet, 390px, 320px and mobile WebKit. Checkout tests
exercise the isolated container and focus behavior, not provider payments.

Run actionlint against product and expanded caller workflows. Keep actions on full
commit pins and install tools from their committed lockfiles. New capture/release
operations must preserve retained raw bytes, publication gates and import identity;
never fix a failed downstream step by starting a new score import. Hosted fresh
installation verification is a separate explicit test against empty resources.
The packaged **History → verify-fresh** operation and its cleanup/ownership journal
are tested offline in `tests/test_hosted_verification.py`, including the real CLI
dispatch, partial failures and populated-resource refusal. These tests receive no
provider credentials. Hosted evidence is a separate installation gate; CI success
does not prove real R2/D1 access. Update the packaged README, installation guide,
migration notes and operation inputs together when this path changes.
