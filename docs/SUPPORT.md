# Project links and optional support

The footer contains **View on GitHub**, linking to the Session Report repository.
**Support maimai.party** appears beside
it with a filled logo-color heart and the official Stripe wordmark. It opens the
same native Stripe dialog as maimai.party on the configured hosted report at
adamrussin.com. Closing it restores focus to the button without navigating or opening
a window. Other, unregistered hosts keep a normal link to the shared checkout in
the current tab. No player name, scores, report URL or query string is sent to the
checkout API. The native Stripe SDK loads only after a click.

The shared dialog uses maimai.party branding and native Stripe amounts and methods.
It says: “maimai.party is free for everyone. If you’d like to help with hosting and
domain costs, a few dollars is more than enough.” There is no alternate provider.
Stripe localization, amount/currency selection and payment confirmation belong to
the shared checkout. The report never constructs amounts or stores payment state.

## Availability and configuration

The release switch `supportAvailable` in the bundled controller is enabled for the
reviewed shared live checkout release. Its restricted credential, live customer-chosen
Price, branding, payment domain and unpaid session create/status checks were verified.
Some payment methods remain subject to Stripe approval. The public site has its own
availability switch. Disabled or unconfigured payment service must not advertise a
working Support button. Runtime errors in an active checkout offer retry.

Owner configuration remains a single boolean, enabled by default:

```toml
[support]
enabled = false
```

This hides both footer project links. `MAIMAI_REPORT_SUPPORT_ENABLED=false` and
`--no-support` provide the same override. The setting does not change scores,
artwork, history, exports, or the separate optional Party integration.

## Isolation and validation

Enabled reports allow specific Stripe script/frame/payment origins and the
maimai.party checkout API. Disabled reports retain `frame-src 'none'` and `payment=()`.
Existing private access, no-cache headers and Party integration policies remain in force. Logos are
embedded. Only the exact bundled controllers may contain approved project URLs;
placing an allowed URL in player data or unrelated markup still fails validation.
The report makes no payment-service requests on load or while switching views.
API requests omit credentials and referrers and contain only the fixed project ID,
random checkout attempt and optional Stripe session ID. The payment Worker permits
only the exact configured report origin, with no wildcard CORS. Wallet returns use
the fixed `/maimai/#support-return` address and resume the same tab's payment-only
session state; server status is required before showing a successful payment.

The native dialog and payment client bundled in `support.js` are shared verbatim
with maimai.party's `support-stripe.js` and `support-client.js`. Keep those modules
in sync when changing payment behavior. Host registration and Stripe payment-domain
registration are required before enabling native checkout on another report origin.

Automated tests use synthetic reports, payment API responses and a mock Stripe SDK.
They check idle isolation, keyboard activation, no new windows, empty referrers,
preserved report data and URL, close/reopen, history navigation, B50 bytes,
accessibility and narrow screens.
Actual Stripe methods are verified separately in the shared site's sandbox.

## Updating an existing publication

Use the currently installed renderer and its retained source inputs. Keep original
captures/publications immutable, preserve approved historical presentation selections,
and compare all embedded report, player, jacket and download data before publication.
Do not start a score import, create a new session, change dates, advance a latest
pointer, or bulk rerender history for a footer change. Preserve original B50 bytes.

Retain the previous Worker version/settings and use the established drift-checked
retained publish operation. Verify primary and backup manifests, history counts,
ordering, selected revision hashes, original routes, downloads and private access
before and after. A Worker-only release preserves HTML and therefore does not, by
itself, replace an embedded footer. See [historical presentation revisions](HISTORICAL_PRESENTATION_REVISIONS.md)
and [installation upgrades](INSTALLATION.md#upgrades-and-rollback).
