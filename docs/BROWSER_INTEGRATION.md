# Optional standalone browser integration

Ordinary reports need no additional dependency. To display a prepared
maimai-personal version 1.0.0 bundle, pass recommendation_bundle=bundle to
build_html or render_report. Optional browser_url="https://your-site/" adds
explicit chart links. It never enables background network access.

The renderer embeds a validated, compact presentation subset: catalog/snapshot
provenance and cards. It does not embed the complete catalog or private overlay.
It rejects unsupported engine/schema versions, conflicting chart identities and
recommendations later than the report cutoff. Empty cards retain existing Targets.
With cards, original session suggestions remain in an expandable section.

To calculate an export directly from retained inputs, install a reviewed, pinned
release of the separate maimai-chart-intelligence package, then call:

    from maimai_report.browser import export_browser_bundle

    bundle = export_browser_bundle(
        report, retained_after_pbs, reviewed_mapping, catalog,
        catalog_version="reviewed-release",
        attempts=retained_attempts,
        settings=recommendation_settings,
    )

Export is offline and does not trigger a Kamaitachi import or alter archives.
Missing optional installation produces an actionable export error while normal
report rendering and consuming prepared files continue to work.
While the browser repository is private, no default dependency points to it.
Public/private installed deployments adopt this adapter through their usual
separate release process. Existing historical reports need no backfill.
