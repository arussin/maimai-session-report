# Public API boundary

This project uses Kamaitachi's public API, not a direct MYT connection. Live use
requires an integration you have already configured in Kamaitachi.

The following facts were verified against the public `zkldi/Tachi` repository on
2026-09-07, at commit `8f4b6b41e08d2d059f9fde62edbf16d147bfaadc`:

- Kamaitachi's public [MYT integration component](https://github.com/zkldi/Tachi/blob/8f4b6b41e08d2d059f9fde62edbf16d147bfaadc/typescript/client/src/components/imports/MYTIntegrationPage.tsx)
  offers the integration and submits an `importType` to `/import/from-api`.
- The maimai identifier is `api/myt-maimaidx`. This is an existing upstream
  importer identifier in the public upstream source.
- Integration setup and any card credentials belong in Kamaitachi's UI. The
  report application has no card-code setting and does not read integration
  credentials back from Kamaitachi.

The report application's network contract is deliberately small: read existing
PBs and recent scores, start one import with the owner's Kamaitachi API token,
wait for completion through one SSE stream, then read the updated scores once.
See [architecture](ARCHITECTURE.md) for pinned API/stream references and
[local setup](LOCAL.md) for using your own account.

These docs cover the Kamaitachi integration only. For account access, availability
and current setup steps, use the service and integration you already have.

Import failures produce a local, actionable message. Raw upstream failure
descriptions are not printed: even a short server message can contain account or
integration details. Consult the account's own import status before another run.

Public upstream code is evidence of the documented behavior, not a guarantee that
an external API will never change. Automated tests mock it; they do not start a
live import.
