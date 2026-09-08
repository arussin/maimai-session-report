const BUY_ME_A_COFFEE_ORIGIN = "https://buymeacoffee.com";
const BUY_ME_A_COFFEE_MARKER = '"provider":"buy_me_a_coffee"';

function buyMeACoffeeEnabled(html) {
  return html.includes(BUY_ME_A_COFFEE_MARKER);
}

export function contentSecurityPolicyFor(html) {
  const supportEnabled = buyMeACoffeeEnabled(html);
  return [
    "default-src 'none'",
    "base-uri 'none'",
    "connect-src 'none'",
    "font-src 'none'",
    "form-action 'none'",
    "frame-ancestors 'none'",
    `frame-src ${supportEnabled ? BUY_ME_A_COFFEE_ORIGIN : "'none'"}`,
    "img-src data:",
    "manifest-src 'none'",
    "media-src 'none'",
    "object-src 'none'",
    "script-src 'unsafe-inline'",
    "style-src 'unsafe-inline'",
    "worker-src 'none'",
  ].join("; ");
}

export function permissionsPolicyFor(html) {
  const supportEnabled = buyMeACoffeeEnabled(html);
  return [
    "accelerometer=()",
    "autoplay=()",
    "camera=()",
    "display-capture=()",
    "encrypted-media=()",
    "fullscreen=()",
    "geolocation=()",
    "gyroscope=()",
    "magnetometer=()",
    "microphone=()",
    "midi=()",
    supportEnabled ? `payment=(self "${BUY_ME_A_COFFEE_ORIGIN}")` : "payment=()",
    "picture-in-picture=()",
    "publickey-credentials-get=()",
    "screen-wake-lock=()",
    "serial=()",
    "usb=()",
    "web-share=()",
    "xr-spatial-tracking=()",
  ].join(", ");
}

export function privateHeadersFor(reportHtml, extra = {}) {
  return new Headers({
  "Cache-Control": "private, no-store, max-age=0",
  "CDN-Cache-Control": "no-store",
  "Cloudflare-CDN-Cache-Control": "no-store",
  "Content-Security-Policy": contentSecurityPolicyFor(reportHtml),
  "Cross-Origin-Opener-Policy": "same-origin",
  "Cross-Origin-Resource-Policy": "same-origin",
  Expires: "0",
  "Permissions-Policy": permissionsPolicyFor(reportHtml),
  Pragma: "no-cache",
  "Referrer-Policy": "no-referrer",
  "X-Content-Type-Options": "nosniff",
  "X-Frame-Options": "DENY",
  "X-Robots-Tag": "noindex, nofollow, noarchive",
    ...extra,
  });
}
