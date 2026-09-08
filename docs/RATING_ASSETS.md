# Rating-frame artwork and provenance

The built-in badge pack contains the original twelve rating-frame images used
by the direct port, including the distinct 16,000+ frame. These are **SEGA
game-interface graphics**, obtained from the public
[shedaniel/tomomai rating assets](https://github.com/shedaniel/tomomai/tree/7608b9c250f4a8778cdfd4768cdecb7628cd5889/apps/render/public/res/rating)
at the immutable revision
`7608b9c250f4a8778cdfd4768cdecb7628cd5889`.

This is not an original CSS imitation. The packaged
`src/maimai_report/assets/rating-frames.css` embeds lossless WebP versions of the
original PNGs. The original conversion was verified against decoded RGBA
pixels. The tables below identify both original source files and packaged
images; encoding changes can change a file checksum without changing pixels.

## Use and accessibility

`[report] badge_pack = "builtin"` selects these frames by default. Use
`"plain"` for the image-free display, or a local badge-pack manifest to supply
your own decorations. See the [artwork guide](ARTWORK.md) and
[configuration reference](CONFIGURATION.md) for the exact interface.

No Tomomai checkout, account, network request, Node installation or optional B50
export is needed for these bundled frames. They are embedded in the HTML;
viewing a report makes no image requests. The rating digits and player name
remain real HTML text, and the complete rating has an accessible label.
No avatar, title, class rank, stars or achievement is invented by these frames.

The tier names and thresholds are presentation metadata, not a change to
Old 35/New 15 calculations. The current visual mapping includes the 16,000+
frame; it does not reproduce every historical game's version-specific frame
selection. Upstream's pinned graphics selector uses `kiwami` from game version
13 onward. New 15 version configuration and badge styling remain separate.
The small original images can appear slightly soft when enlarged; the digits
use system fonts. See [visual-port notes](VISUAL_PORT.md).

## Ownership and redistribution

The root MIT license covers this project's original software, **not SEGA's
artwork**. Tomomai's code is distributed under AGPLv3, but its public asset
directory is not independent proof that SEGA granted redistribution permission.
No separate grant from the artwork owner has been verified for this project.
These provenance records and credits are not a clearance opinion.

Before making an artwork-containing repository, package, screenshot or report
public, the publisher must resolve the artwork rights question. Selecting
`plain` avoids including these frames in that generated report; it does not
remove the bundled frames from a source checkout or installed package.
User-supplied artwork likewise remains subject to its owner's terms.
See [third-party notices](../THIRD_PARTY_NOTICES.md).

The [optional B50 adapter](../adapters/tomomai/README.md) uses additional upstream
decorative assets during its separate build. Those assets are not this
twelve-frame pack. [Song jackets](ARTWORK.md) have separate provenance and are
not bundled as real song data in the demo. Fictional DEMO cover tiles are
generated locally.

## Original PNG checksums

All source filenames below are relative to
`apps/render/public/res/rating/` at the pinned Tomomai revision.

| Presentation tier | Source | Original PNG SHA-256 |
|---|---|---|
| white | `normal.png` | `3b163004f1c3e86291d16d90273a382b27e05c6d9ed7b39988504c0c26d07c0c` |
| blue | `blue.png` | `0d0304254fe54cd7a88c26c696ebad9c5e32b25a3ce756ff2f956cedc94bcd6b` |
| green | `green.png` | `32a321a1289131e2c0ae8813ac5186029019669889d0a0fc1cfacf33c59c0597` |
| yellow | `orange.png` | `b597b6a56a97970e6ba46df8fa08edb689453db1dbce900177c27d5b74e1dfb4` |
| red | `red.png` | `6e799aa2d22d334a1427ac2be293d50d007596d1b58ab3405ab65224f636e7e0` |
| purple | `purple.png` | `d4824289345e224adb6cc397ef4141e334e930ef138245a18236cdcc7ec90589` |
| bronze | `bronze.png` | `d407fd69d2c922bc006f95c05ad6213067c48776c46f5440562c792bfae5fe00` |
| silver | `silver.png` | `32d6553f189304e319d4be9bdee02f6e5d07ae265a3894dc7123b933db7f5183` |
| gold | `gold.png` | `62970a734ca15ed234f73e42746ecef2ee8a5f1df97f46ce285f69676eb69ce6` |
| platinum | `platinum.png` | `f84159dcca3cfd4022fa93fb2621e886c19c50dbdc36c34ba10c835ecb3cda8d` |
| rainbow | `rainbow.png` | `59432ba044b40fc0d5d19488b621ff0bce991b575a0565af217139668749e228` |
| rainbow-ex | `kiwami.png` | `804acca3df0cf981685dc61590194b1b43fd52737829b3048017f3f1f0348414` |

## Packaged lossless WebP checksums

These hashes cover the decoded base64 file bytes, not the CSS text.

| Presentation tier | Packaged WebP SHA-256 |
|---|---|
| white | `a44293cb7c59aca7a672a1e3b07de19c388afba6dce49cc2471a150ea327d0f0` |
| blue | `b37ca0e12985ab56d78f40bb3cfa26e3f9457424d809aa455527bf740bcdf335` |
| green | `e8de5db2ba8eafc45cf3989d1d7070210e79791b97e7fe5c1b6ddd941a35aea7` |
| yellow | `a40ae1ccd1682bfdb4bc3aab2aa23e6c0127c18e5ea06b527acca9a57a6f2e78` |
| red | `c030aad53c7935d083292e067589ec1801cd160d16a0197c9cd1eaaef4be0a24` |
| purple | `2f42fad88d31d955076beee74663cc8aa6b27241265e1dbfc880906dcce415b4` |
| bronze | `82bf0534e122bf5e89f8a221ed202fe0dd283f0ef49812ca427b45ba94e623b2` |
| silver | `2d2798d39abf3292da61139ea69a02a6605caa559d917ca2088e5f734aca7da3` |
| gold | `a20ccf89093200bf20a5b66db8ca2dcedc16a86bd53cbdb897fa353c8da382dc` |
| platinum | `67ca9dc00621a2ff4f3eca80bcb1a56e999bcd117dd1fe2cbbac4269072f41ed` |
| rainbow | `f0e3c997ce12b57457e5fbef9801cb5fefef5b7140b2a5f8c50cd2ec463045dc` |
| rainbow-ex | `48491ddf896f057b5e25516734828690087816f79f9228d049caf36169c149f7` |
