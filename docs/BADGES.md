# Rating artwork packs

The report includes all **12 original rating frames**, embedded locally. This is
independent of song covers and the optional Tomomai B50 image export. No account,
network request, image download, Node.js installation or sync is needed for badges.

## Choose a pack

In `config.toml` (standalone CLI) or `instance.toml` (private installation):

```toml
[report]
badge_pack = "builtin"
```

Use `builtin` for the original frames, `plain` for the CSS-only alternative, or
`artwork/badges.toml` for your own local pack. CLI options override
`MAIMAI_REPORT_BADGE_PACK`, which overrides standalone TOML. The hosted installation
keeps `instance.toml` as its single source and rejects conflicting environment values.
Manifest paths resolve from the command's working directory (the caller checkout
in Actions). Image paths resolve from the manifest's own directory.

Preview either built-in choice without credentials:

```console
maimai-report demo --badge-pack builtin --output output/original-badges.html
maimai-report demo --badge-pack plain --output output/plain-badges.html
```

The offline demo never reads personal TOML; it accepts only the explicit badge
option or its environment variable, while keeping all score data fictional.

## Start an editable pack

These commands work in PowerShell, macOS and Linux after activating your venv:

```console
maimai-report export-badges --output-dir artwork
maimai-report demo --badge-pack artwork/badges.toml --output output/custom-badges.html
```

The first command creates 12 WebP images, `badges.toml` and an artwork notice.
It refuses to overwrite an existing directory. Change the images or replace their
paths in the manifest, then set `report.badge_pack` to that manifest for real reports.
Preserve the notice when retaining the original images. `artwork/` is Git-ignored
in the application repository; store a private backup of your custom pack.

The exported manifest covers every supported tier:

```toml
version = 1

[frames]
white = "white.webp"
blue = "blue.webp"
green = "green.webp"
yellow = "yellow.webp"
red = "red.webp"
purple = "purple.webp"
bronze = "bronze.webp"
silver = "silver.webp"
gold = "gold.webp"
platinum = "platinum.webp"
rainbow = "rainbow.webp"
rainbow-ex = "rainbow-ex.webp"
```

The highest tier (`rainbow-ex`, 16000+) uses the distinct upstream `kiwami.png`
artwork. Do not silently substitute the ordinary rainbow frame.

To override only selected tiers, explicitly choose the fallback for every other tier:

```toml
version = 1
fallback = "builtin" # or "plain" to use CSS for all unspecified tiers

[frames]
gold = "my-gold-frame.png"
rainbow-ex = "my-highest-frame.webp"
```

Without a fallback, all 12 entries are required. A typo, missing image or malformed
pack fails before any live sync request; run `maimai-report doctor` to check first.

## Artwork requirements and layout

- Local PNG, JPEG or WebP only; maximum 512 KiB per image and 4096 pixels per axis.
- Files must stay inside the manifest directory, including after symlink resolution.
  URLs, network shares, absolute image paths and traversal paths are rejected.
- No SVG, scripts, arbitrary CSS or HTML can be supplied by a pack.
- Design frames for the original **296:86** aspect ratio. The five HTML digit slots
  stay on the right (left 41.55%, right 5%, top 18.6%, bottom 23.25%). Leave that
  region readable; decorations are backgrounds, not baked-in player numbers.
- Player name, numeric rating, tier classification and accessibility labels remain
  application text. Packs do not alter rating calculations or import behavior.
- Images are embedded into the generated HTML. Moving or sharing that HTML does
  not require the pack files, and viewing it makes no artwork requests.

## Private Actions use

Set `report.badge_pack` in the private caller's `instance.toml`. Include the manifest
and its images in that **private caller checkout**, outside the generated capture
directory, so each dispatched run can read them. The older reusable action can
instead receive `MAIMAI_REPORT_BADGE_PACK`. No new secret is needed.

Retained HTML remains self-contained. Re-rendering JSON intentionally applies the
currently selected pack; keep the pack in version control in your private caller
if you need to reproduce a specific presentation. No existing runner is upgraded
or repinned by installing this project.

## Ownership and attribution

The bundled frames are SEGA game artwork obtained through the pinned Tomomai
source, not original MIT-licensed illustrations. Choosing `plain` omits them from
that generated HTML; it does not remove them from the installed distribution.
Your own artwork can use a complete custom pack with no built-in image fallback.
Only supply artwork you are entitled to use. Attribution alone is not permission
to redistribute it. See [exact provenance](RATING_ASSETS.md) and
[third-party notices](../THIRD_PARTY_NOTICES.md).
