# Optional Buy Me a Coffee checkout

The report can show an optional support control at the bottom of the active report view. Support is disabled by default. With no Buy Me a Coffee ID configured, the generated report remains fully sealed: it contains no external URL, permits no frames, and makes no runtime request.

## Configuration

In `config.toml`:

```toml
[support]
buy_me_a_coffee_id = "your-creator-id"
label = "Buy me a maimai credit"
description = "Support me on Buy me a coffee!"
color = "#5F7FFF"
```

Equivalent environment variables:

```text
MAIMAI_REPORT_BUY_ME_A_COFFEE_ID=your-creator-id
MAIMAI_REPORT_SUPPORT_LABEL=Buy me a maimai credit
MAIMAI_REPORT_SUPPORT_DESCRIPTION=Support me on Buy me a coffee!
MAIMAI_REPORT_SUPPORT_COLOR=#5F7FFF
```

Replace `your-creator-id` with your own public creator ID. The ID and display values are public configuration, not credentials. Do not add a Stripe key, Buy Me a Coffee login, bank information, or any payment secret to the report or repository.

## Browser behavior

When support is enabled, the report renders a small footer card immediately above its metadata footer. No request to Buy Me a Coffee occurs merely because the report loads. The first click opens an accessible modal and assigns the Buy Me a Coffee widget-page URL to a cross-origin iframe.

The iframe starts at Buy Me a Coffee's canonical `https://buymeacoffee.com` origin. This is deliberate: the `www` widget URL currently redirects to the no-`www` origin, which can be blocked by a strict single-origin `frame-src` policy. Using the canonical origin avoids that redirect while keeping the allowlist narrow.

The iframe is isolated from the parent page by the browser's same-origin policy. The report does not load Buy Me a Coffee's parent-page widget script, remote fonts, icons, analytics code, or other third-party assets. A separate link to the public creator page is available as a fallback.

The iframe uses `allow="payment *"` so payment delegation survives any internal Buy Me a Coffee navigation. This does not grant arbitrary sites payment capability because the parent HTTP `Permissions-Policy` still limits payment to the exact Buy Me a Coffee origin.

The checkout is hidden from print output. Desktop uses a narrow modal; mobile uses the full viewport so the payment interface is not compressed.

## Security policy change

The default policy remains:

```text
frame-src 'none'
payment=()
```

A support-enabled report changes only those capabilities needed by the checkout:

```text
frame-src https://buymeacoffee.com
payment=(self "https://buymeacoffee.com")
```

All other report restrictions remain in force, including `connect-src 'none'`, `form-action 'none'`, `font-src 'none'`, `object-src 'none'`, `Referrer-Policy: no-referrer`, and frame denial for the report itself.

The renderer and Cloudflare adapter fail closed. A support-enabled generated file may contain only the exact Buy Me a Coffee frame origin as an external HTTP(S) URL. Any additional origin is rejected before publishing.

## Testing

Automated browser tests use a fictional checkout page to check the modal,
keyboard focus and mobile layout. They do not contact the payment provider or
submit payments. Verify your own creator page and checkout after enabling support.

## Hosting requirement

A host that supplies its own response headers must make the same conditional `frame-src` and `Permissions-Policy` allowance. A stricter response header overrides the report's meta policy and will prevent checkout from loading.

The checkout endpoint and payment methods remain controlled by Buy Me a Coffee. Test the live account's checkout after any upstream widget change. Do not claim a particular wallet or cryptocurrency method unless it is actually offered for the creator and supporter accounts involved.
