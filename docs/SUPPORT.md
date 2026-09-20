# Project links and optional support

The footer contains **View on GitHub**, linking to the Session Report repository.
**Support maimai.party** appears beside
it with a filled logo-color heart and the official Stripe wordmark. It opens the
fixed `https://maimai.party/support.html` address in a separate browser window;
mobile browsers may use a new tab. No player name, scores, report URL, query string,
referrer, or window opener is passed to checkout. No payment code runs in the report.

The shared page uses maimai.party branding and native Stripe amounts and methods.
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

Report frame and payment policies are always `frame-src 'none'` and `payment=()`.
Existing private headers and Party integration policies remain in force. Logos are
embedded. Only the exact bundled controllers may contain approved project URLs;
placing an allowed URL in player data or unrelated markup still fails validation.
The report makes no payment-service requests on load or while switching views.
Popup navigation uses `noopener,noreferrer` and a fixed URL with no return parameter.

Automated tests use synthetic reports and a mock destination. They check the hidden
state, keyboard activation, exact destination, empty referrer, null opener, preserved
report data and URL, history navigation, B50 bytes, accessibility and narrow screens.
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
