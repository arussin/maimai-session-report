# Public API boundary

This project is a downstream client of Kamaitachi. It does not implement a MYT
client, discover a private server, or provide access to another service. Live use
assumes the owner has already configured the integration in Kamaitachi.

The following facts were verified against the public `zkldi/Tachi` repository on
2026-09-07, at commit `8f4b6b41e08d2d059f9fde62edbf16d147bfaadc`:

- Kamaitachi's public [MYT integration component](https://github.com/zkldi/Tachi/blob/8f4b6b41e08d2d059f9fde62edbf16d147bfaadc/typescript/client/src/components/imports/MYTIntegrationPage.tsx)
  offers the integration and submits an `importType` to `/import/from-api`.
- The maimai identifier is `api/myt-maimaidx`. This is an existing upstream
  importer identifier, not a private service endpoint disclosed by this project.
- Integration setup and any card credentials belong in Kamaitachi's UI. The
  report application has no card-code setting and does not read integration
  credentials back from Kamaitachi.

The report application's network contract is deliberately small: read existing
PBs and recent scores, start one import with the owner's Kamaitachi API token,
wait for completion through one SSE stream, then read the updated scores once.
See [architecture](ARCHITECTURE.md) for pinned API/stream references and
[local setup](LOCAL.md) for using your own account.

Documentation here covers only that public integration surface. It does not
describe service signup, invitations, hosting, game-network configuration,
private protocols or credential recovery. Availability and current UI steps must
be confirmed in the account and integration the owner already uses.

Import failures produce a local, actionable message. Raw upstream failure
descriptions are not printed: even a short server message can contain account or
integration details. Consult the account's own import status before another run.

Public upstream code is evidence of the documented behavior, not a guarantee that
an external API will never change. Automated tests mock it; they do not start a
live import.
