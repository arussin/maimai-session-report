# Optional Tomomai B50 adapter

This build-time adapter consumes the canonical report's Old 35 and New 15 records.
It preserves the existing difficulty normalization, chart-constant unit conversion,
achievement conversion, rating total and pool assignment. It does not import scores
or use public catalogue versions to reclassify a canonical pool.

The installation action fetches `shedaniel/tomomai` at
`7608b9c250f4a8778cdfd4768cdecb7628cd5889`, uses its committed pnpm lockfile and
pnpm 11.2.2, and installs only the render workspace. Source and dependencies stay
in the build runner. The report receives only the resulting WebP.

The adapter is a separate optional AGPL-3.0-only component. Its imports link to
Tomomai's AGPLv3 render modules; see `LICENSE` and the pinned upstream source.
The core Python wheel and private-installation ZIP do not embed this component or
the upstream renderer. Enabling B50 downloads builds the optional component from
the pinned source checkout. This boundary does not remove applicable AGPL source
and notice obligations. The project-wide public-distribution and asset-rights
review remains required before publication.

Jackets use the existing public catalogue at build time and the renderer's neutral
fallback when unavailable. No score data is submitted to an external rendering API.
`mode = "disabled"` skips it; `optional` keeps partial-pool reports usable;
`required` fails the build if a complete, valid B50 cannot be produced.

The original renderer's decorative profile defaults and date/catalogue behavior
are preserved. They are not additional measured player statistics. Any future
correction to those upstream presentation fields is a separate change.
