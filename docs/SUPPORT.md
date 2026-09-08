# Developer support

Reports include a small **Enjoying maimai Session Report?** footer with a
**Buy the developer a maimai credit** button. Contributions go to the project's
developer through [Buy Me a Coffee](https://buymeacoffee.com/russin). No payment
account or payment credentials are needed to generate your report.

## Show or hide the footer

Developer support is enabled by default. To remove it, use this in `config.toml`
or a hosted installation's private `instance.toml`:

```toml
[support]
enabled = false
```

For the standalone CLI, `MAIMAI_REPORT_SUPPORT_ENABLED=false` provides the same
setting. `--support` and `--no-support` explicitly override it when generating a
report. For example:

```console
maimai-report demo --no-support --output output/demo-report.html
```

This is the only support setting. It does not affect scores, artwork, hosting,
or any report feature. A disabled report contains no external HTTP(S) URL,
permits no frames, and makes no runtime request.

## In-page checkout

The footer appears immediately above the metadata footer in every active report
view. Loading the report or changing views makes no request to Buy Me a Coffee.
Only clicking the button opens the checkout popup and loads the provider's
cross-origin iframe. The report does not send player data to the provider.

The popup stays inside the report. **Open separately** is available as a fallback;
the provider may also require a separate window for payment verification.
Checkout needs an internet connection and is controlled by Buy Me a Coffee.

The iframe uses the canonical `https://buymeacoffee.com` origin, a no-referrer
policy and payment delegation. The report does not load the provider's
parent-page widget script, remote fonts, icons or analytics. The browser's
same-origin policy separates the payment form from report data. Once you open
checkout, the provider's own privacy and payment terms apply.

Desktop uses a narrow popup; mobile uses the full viewport. The checkout and
support footer are hidden in print output.

## Hosting and security policy

Support-enabled reports permit only the provider's frame origin:

```text
frame-src https://buymeacoffee.com
payment=(self "https://buymeacoffee.com")
```

With support disabled, those policies become:

```text
frame-src 'none'
payment=()
```

All other report restrictions remain in force: `connect-src 'none'`,
`form-action 'none'`, `font-src 'none'`, `object-src 'none'`,
`Referrer-Policy: no-referrer` and frame denial for the report itself.
The renderer and deployment adapter reject unexpected external URLs. The only
HTTP(S) URL permitted in a support-enabled file is the exact provider origin in
the matching content security policy and fixed footer script. Payment links are
created locally by that script; disabled reports omit it entirely.

A host supplying its own response headers must make the same conditional frame
and payment allowance. A stricter response header overrides the report's meta
policy and can prevent checkout from loading. Do not loosen unrelated policies.

## Testing

Automated browser tests substitute a fictional checkout page. They verify the
fixed destination, lazy loading, keyboard focus, mobile layout and disabled state
without contacting the provider or submitting a payment. Actual payment methods
and verification requirements depend on Buy Me a Coffee and the supporter.
