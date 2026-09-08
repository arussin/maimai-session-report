# Rating-display artwork

The standalone report's rating display is an original CSS-only design shipped in
`src/maimai_report/assets/rating-frames.css` under the project's MIT software
license. It uses system fonts, text, borders and gradients. No SEGA rating-frame
images, copied game UI textures, remote fonts or bundled third-party artwork are
required by the default report or its fictional sample.

Tier names and numerical thresholds are presentation metadata, separate from the
unchanged Old 35 / New 15 calculations. Color always has an accompanying label.
The displayed rating remains text, with the complete number in its accessible
label. Print, reduced-motion and forced-color environments need no image assets.

This repository starts with a reviewed source snapshot and fresh Git history.
Old game-interface images, prior development branches, PRs and workflow artifacts
were not imported. The sample and README screenshots use the CSS-only display.
Existing installations in other repositories retain their own immutable pins and
artwork; this release does not modify or relicense them.

The [optional Tomomai adapter](../adapters/tomomai/README.md) still has its separate
AGPL and upstream asset considerations. [Optional song jackets](ARTWORK.md) are
not bundled with the core or sample. An owner's choice to fetch or redistribute
third-party artwork requires that owner's rights review.
