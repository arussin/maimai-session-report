# My private maimai installation

This repository contains your configuration and workflows. The report, history,
B50 adapter and deployment tools come from the pinned shared product. Keep this
repository **private**. `instance.toml` is ordinary tracked configuration in this
private repository; credentials belong in GitHub Actions secrets.

Installed core: `__CORE_SHA__`.

1. Fill in `instance.toml`: player, exact current-version aliases, timezone, your
   Cloudflare origin/prefix, account/zone IDs, unique resource names and stable scope.
2. Follow the [installation guide](https://github.com/arussin/maimai-session-report/blob/__CORE_SHA__/docs/INSTALLATION.md)
   to configure Access and secrets. Account activation and login are owner steps.
3. Run **Validate installation**, then **Maintain hosted history → plan**. Review
   the named resources; setup and deployment are separate operations.
4. Run **setup** with explicit apply. Copy the two returned database IDs into the
   existing `[history]` table and rerun validation. Setup never changes DNS or Access.
5. Run **Maintain hosted history → verify-fresh** with apply on the empty resources.
   Inspect its private evidence and verified cleanup. This is a hosted synthetic
   test; it does not import scores or require a local database.
6. Verify Access, enable publishing deliberately, and run **bootstrap** with apply
   to create the empty protected site. It records no synthetic or real session.
7. Run **Refresh maimai session** when you want one score import. History is hosted
   in private R2/D1 with an independent hosted backup. Empty syncs preserve the last
   meaningful live report.

The guide includes the complete configuration and credential reference, retained
build retries, backup/recovery, upgrades, rollback, costs and diagnostics. You do
not need to implement a Worker or maintain a local database.

Refresh captures, archive results and deployment results are separate. If one
stage fails, resume that stage using its retained run; never rerun the sync job
to repair rendering, storage or deployment. Keep the last successful release's
private rollback artifact while upgrading.

All four workflows pin the same full core commit. Upgrade them together in a
reviewed pull request, follow that release's migration notes, and explicitly
deploy. Validation and pull requests never sync or deploy.
