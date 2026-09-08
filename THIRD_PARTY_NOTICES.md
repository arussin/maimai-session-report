# Third-party notices

## License scope

The [MIT license](LICENSE) covers original maimai Session Report software and
documentation by arussin. It does not relicense third-party code, game artwork,
song covers, trademarks or user-supplied assets. The distribution is not wholly
MIT-licensed merely because its Python application code is MIT.

The built-in rating frames are identified as
`LicenseRef-SEGA-Game-Artwork` in package metadata. That is this project's local
identifier for the artwork notice below, **not** the name of a permission granted
by SEGA or a claim that the artwork is open-source.

## Tomomai code

Thanks to **shedaniel and the Tomomai contributors** for
[Tomomai / ともマイ](https://github.com/shedaniel/tomomai), the optional B50
image renderer used by this project.

- Immutable upstream revision:
  `7608b9c250f4a8778cdfd4768cdecb7628cd5889`.
- Upstream [license](https://github.com/shedaniel/tomomai/blob/7608b9c250f4a8778cdfd4768cdecb7628cd5889/LICENSE)
  and [README](https://github.com/shedaniel/tomomai/blob/7608b9c250f4a8778cdfd4768cdecb7628cd5889/README.md):
  GNU Affero General Public License, version 3.
- The unchanged full license is included at
  [adapters/tomomai/LICENSE](adapters/tomomai/LICENSE).
  Its Git blob checksum matches upstream:
  `2beb9e16309456b1f4244480f4fe6890324a5064`.
- Our adapter [render.ts](adapters/tomomai/render.ts) is licensed
  `AGPL-3.0-only`, not MIT. It imports upstream's
  `render-image.ts`, `catalog.ts`, `rating-calculator.ts`, `types.ts`
  and `render-route.ts` from `apps/render/src/`.
- The upstream checkout and its locked dependencies are fetched only for an
  explicitly enabled B50 build. Our wrapper adapts canonical Kamaitachi report
  records to that renderer; the original HTML pipeline does not execute Tomomai.
- Downstream modification, **2026-09-08**: the build applies the source-controlled
  [TLS-hardening patch](scripts/harden_tomomai.py) to the exact pinned
  `catalog.ts`, `render-image-server.ts` and `image_cacher.ts` in
  `apps/render/src/lib/`. Their catalogue, image-download and image-cache
  connections are changed to verify TLS certificates. All other upstream
  source is left unchanged. The patch checks every expected source checksum
  before modifying any file and rejects an unreviewed version.
- Upstream retains its authors' notices and history. The Free Software
  Foundation copyright at the top of the license applies to the license text;
  it is not a project authorship claim.

The upstream README also acknowledges SEGA, the
[dxrating project](https://github.com/gekichumai/dxrating) for internal-level
data, and [otoge-db](https://github.com/zvuc/otoge-db) for level data.
Their credit here does not assert that their code is included in the Python
application or that their licenses grant rights to SEGA images.

## Source and distribution obligations

Keep the adapter's AGPL notice, the upstream license and applicable dependency
notices with redistribution. Preserve and provide the relevant source,
including the adapter, exact upstream revision, downstream patch, build
instructions and applicable dependency source, when required. Merely linking
to upstream is not necessarily sufficient for a modified combined work.
A downloaded source checkout in a temporary build runner is not, by itself,
an offer of source to recipients.

If you offer a modified AGPL program for remote interaction, review section 13
and provide the required prominent source offer. A static report or image is
not automatically AGPL-covered solely because an AGPL tool produced it; the
output's actual content matters under section 2. Embedded third-party
artwork keeps its own rights considerations. These are implementation notes,
not a legal determination that this project's packaging arrangement resolves
every obligation. Consult the [complete AGPLv3 terms](adapters/tomomai/LICENSE),
especially sections 1, 2, 4–6 and 13, before distributing a combined build.

## SEGA rating-frame artwork

The twelve built-in rating-frame images originate from SEGA game-interface
graphics. They were obtained from Tomomai's public
[`apps/render/public/res/rating/` directory](https://github.com/shedaniel/tomomai/tree/7608b9c250f4a8778cdfd4768cdecb7628cd5889/apps/render/public/res/rating)
at the revision above and converted from PNG to lossless WebP for embedding.
[Full filenames, conversion notes and checksums](docs/RATING_ASSETS.md) identify
every source and packaged image.

These graphics are not original artwork by this project's author and are
excluded from the root MIT license. Their presence in an AGPL-licensed source
repository does not independently establish permission from the artwork
owner. **No separate SEGA redistribution grant has been verified.** Attribution
does not itself grant that permission. Public redistribution of packages,
repositories, screenshots or reports containing the graphics still requires
an artwork-rights decision by the publisher. This project is not endorsed by
SEGA or Tomomai.

The optional Tomomai renderer loads additional upstream game-interface assets
for its B50 output; the twelve-frame HTML pack does not inventory or relicense
that entire asset collection. Review the exact upstream build and any
additional resources before redistributing that output.

## Song covers and custom artwork

Optional song jackets come from the official public SEGA catalogue and
international DX-NET static image hosting, as documented in
[ARTWORK.md](docs/ARTWORK.md). They are not proprietary Mythos account data.
Public availability does not transfer ownership or authorize unrestricted
redistribution. The bundled demo's covers are locally generated fictional
tiles, not real song artwork.

Custom local packs and jackets remain subject to the rights and notices
supplied by their owners. Supplying a pack does not transfer its copyright to
this project or change its license.
