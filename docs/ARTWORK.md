# Optional embedded song artwork

The normal `render` command remains offline. Supply a previously prepared local
mapping using `--jackets path/to/jackets.json`, or explicitly prepare artwork
from retained inputs without starting an import:

```console
python -m pip install ".[artwork]"
maimai-report prepare-jackets --report-input output/report-input.json --after-pbs output/after-pbs.json --jacket-cache output/artwork-cache --output output/jackets.json
maimai-report render --report-input output/report-input.json --after-pbs output/after-pbs.json --jackets output/jackets.json --output output/report.html
```

For a single build, `render --prepare-jackets` prepares and embeds artwork. The
same option is available on an explicitly requested `sync-and-render`, after its
existing single import has completed. Never run a sync just to acquire artwork.

Use `--offline-artwork` to restrict preparation to saved files, and
`--artwork-catalogue path/to/catalogue.json` for a saved official catalogue.
`--jacket-cache` overrides the default `<output_dir>/artwork-cache`. The mapping
and provenance identify songs present in the report and should remain private.

The reusable action's `artwork` input defaults to `true`; it installs pinned
Pillow and prepares embedded artwork during the existing build. Set
`artwork: "false"` to retain the dependency-free, artwork-free action behavior.
No request is made by the report browser. Network or ambiguous-match failures
leave a clear NO ART placeholder and do not stop analytical report generation.

## Sources and matching

- Official public song catalogue: [SEGA song data](https://maimai.sega.jp/data/maimai_songs.json).
- Public jacket files: the catalogue's raster filename under
  `https://maimaidx-eng.com/maimai-mobile/img/Music/`.
- Match normalized Unicode title **and artist** exactly. Multiple matching
  filenames, missing metadata and filenames outside the narrow raster pattern
  are omitted. No fuzzy matching or invented substitute song jacket is used.
- Requests use fixed HTTPS sources with no authorization header and no player
  data. Redirects are rejected. Downloads are limited to 4 MiB; decoded images
  to 16 million pixels. Pillow creates a maximum 112×112 WebP for embedding.
- Only validated raster data URLs enter the HTML. Its CSP is unchanged.

Public availability is not a transfer of artwork ownership. Song artwork and
upstream game-interface graphics remain the property of their respective owners; the
repository's software license does not relicense them. A future public
redistribution of an artwork collection requires a separate rights review.
The standalone report and fictional preview include the original third-party
[rating frames](RATING_ASSETS.md). Select `report.badge_pack = "plain"` to omit
those images from a generated report. [Local rating artwork packs](BADGES.md)
are independent of both song covers and the optional Tomomai B50 renderer.

The cache is optional and rebuildable. It is not a score archive or historical
database. Unmatched songs remain distinguishable by their full title, artist,
chart type, level and DX/STD label.
