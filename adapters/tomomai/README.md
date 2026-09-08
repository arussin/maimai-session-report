# Optional Tomomai B50 adapter

This is an adapter to the **Tomomai / ともマイ renderer by shedaniel and its
contributors**, not an original B50 rendering engine. Thank you to the upstream
project. See the project-wide [third-party notices](../../THIRD_PARTY_NOTICES.md)
for credits, license scope, source obligations and artwork caveats.

## What is used

The installation action fetches
[`shedaniel/tomomai`](https://github.com/shedaniel/tomomai/tree/7608b9c250f4a8778cdfd4768cdecb7628cd5889)
at `7608b9c250f4a8778cdfd4768cdecb7628cd5889`. It uses the committed pnpm
lockfile, pnpm 11.2.2 and only the render workspace.

Our `render.ts` directly imports these modules from that checkout:

| Upstream module under `apps/render/src/` | Used for |
|---|---|
| `lib/render-image.ts` | B50 canvas layout and drawing |
| `lib/catalog.ts` | Public catalogue metadata for drawing |
| `lib/rating-calculator.ts` | Upstream renderer's split and rating representation |
| `lib/types.ts` | Renderer input types |
| `render-route.ts` | Snapshot resources and WebP generation |

The wrapper consumes the canonical report's Old 35 and New 15 records. It
preserves difficulty normalization, chart-constant unit conversion, achievement
conversion, rating total and pool assignment. It does not import scores or use
public catalogue versions to reclassify a canonical pool. Its supplied
`addedVersion` values encode the report's existing pool membership.

**Downstream change dated 2026-09-08:** the build applies
[`scripts/harden_tomomai.py`](../../scripts/harden_tomomai.py) to the pinned
`catalog.ts`, `render-image-server.ts` and `image_cacher.ts` modules in
`apps/render/src/lib/`. It changes `rejectUnauthorized: false` to `true` for
catalogue, image-download and image-cache connections. Exact source hashes for
all three files must match before any file is patched. Other upstream source
is unchanged. A remote resource with an invalid certificate can now fail;
do not disable validation to work around that failure.
The adapter itself supplies the local JSON input mapping and build-time
orchestration. It is not represented as an unmodified upstream program.

## Modes and data flow

In a private installation's `instance.toml`:

```toml
[b50]
mode = "optional"
```

- `disabled`: skip the optional renderer.
- `optional`: allow reports with partial pools without a B50 image.
- `required`: fail when a complete valid B50 cannot be produced.

Source and dependencies stay in the build runner. Score records are rendered
there, not uploaded to an external rendering API. Public catalogue and cover
resources are fetched at build time; the report receives the resulting WebP.
No third-party image request is needed when viewing that embedded result.

The B50 renderer's decorative profile defaults and date/catalogue presentation
are preserved. They are not additional measured player statistics. A future
correction to those upstream fields is a separate change.

The HTML report's twelve built-in [rating frames](../../docs/RATING_ASSETS.md)
are a separate feature. They do not require enabling B50 or downloading Tomomai.

## License and source availability

Upstream's pinned [README](https://github.com/shedaniel/tomomai/blob/7608b9c250f4a8778cdfd4768cdecb7628cd5889/README.md)
and [LICENSE](https://github.com/shedaniel/tomomai/blob/7608b9c250f4a8778cdfd4768cdecb7628cd5889/LICENSE)
state AGPLv3. The unchanged license text is included in [LICENSE](LICENSE).
This adapter is explicitly **AGPL-3.0-only**, not covered by the root MIT grant.

The core Python wheel and private-installation ZIP do not contain this adapter
or the upstream renderer. An enabled B50 build fetches the separate source.
That packaging boundary does **not** by itself decide the license of a combined
work or remove source, notice or network-interaction obligations.

When distributing an affected combined build, keep the applicable notices and
make the required corresponding source available, including this adapter,
the exact upstream source, the TLS patch and necessary build/dependency
material. Retaining source only in a temporary private Actions workspace does
not provide it to recipients. Review AGPLv3 sections 4–6 for distribution and
section 13 if operating a modified remotely interactive service. Do not assume
that an upstream link alone covers local changes or all dependency source.

Code licensing and game-artwork rights are separate questions. The upstream
renderer includes SEGA interface art and other resources whose public
availability is not a verified redistribution grant from their owners.
See [THIRD_PARTY_NOTICES.md](../../THIRD_PARTY_NOTICES.md) before publication.
