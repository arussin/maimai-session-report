# Reproduction and isolated previews

`requirements-dev.lock` pins and hashes every transitive test dependency. CI first
acquires wheel-only files, then installs with `--no-index --find-links ...
--require-hashes --only-binary=:all:`. Npm dependency trees use the committed locks;
acquisition precedes verification, and unnecessary lifecycle scripts stay disabled.
The installed report and its Python build backend do not require Node.

The registry owns `scripts/verify_reproducible_build.py`. Invoke it from the full
registry revision in `config/compatibility.json`, passing `--source` for this report
checkout and a new external `--output` directory. It compares two independent wheel
and source archives, rebuilds the wheel from the source archive, records every wheel
member hash, and verifies unchanged source. Python build sockets are denied. The
canonical Linux command, `scripts/run_canonical_reproduction.py`, acquires the
manifest-pinned official Python image and checksum-pinned Node distribution, then
runs that same verifier with Docker networking disabled. It never installs Docker.
Windows proof is separate; CI compares portable wheel contents across both systems.
A configured job is not a completed Linux or cross-OS proof: retained receipts must
show successful execution. All local environments and artifacts belong in DevCache.

## Browser network boundary

Every functional browser test imports `tests/browser/fixtures.js`. Context routing
allows only the fixture servers, service workers are blocked, and a deny-all proxy
backs up page routing. An allocated local HTTP or TLS server can be registered with
`fixtureOrigins.allow(origin)` and must be released after use. Arbitrary ports or
external origins remain blocked. Explicit synthetic-origin routes run locally; the
real local Worker CORS tests still use actual HTTP responses rather than route
fulfillment. The same context/proxy guard covers popups, frames, beacons and redirects.
The standalone helper probes verify those cases in Chromium, Firefox and WebKit.

After generating fictional inputs in a disposable test workspace and installing
its locked browser tools, run `node tests/browser/preview.mjs` there for a human
preview. It serves only the hash-bound generated fixture manifest and opens an
isolated browser. Support checkout and Party import destinations are explicit
synthetic responders; the latter transfers bytes only after its accept button.
The command accepts no private report path, account state or credentials. Close the
browser to finish. It does not change report CSP, production origins or policy.

The ordinary CLI localhost server retains its existing production-capable support
and explicit Party handoff semantics. Use the isolated synthetic preview runner
for testing those flows; an unguarded localhost preview is not an isolation proof.

Python CI uses `scripts/run_offline_tests.py`: non-loopback DNS and socket attempts
are denied and make the run fail even if application fallback catches the error.
No test is skipped to obtain an offline result. Network acquisition is a separate step.

Firefox is included in the functional matrix. Its preexisting custom-badge
background resampling differs from the built-in frame at fractional CSS widths.
Both generated variants remain byte-identical to commit 5a1a7b8, and their decoded
source artwork and geometry match; exact cross-pack screenshots remain enforced
on Chromium and WebKit. This scoped historical Firefox difference is recorded,
not changed by the refactor. All screenshots compare decoded pixels after readiness.
