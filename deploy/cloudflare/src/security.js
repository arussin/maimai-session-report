const BUY_ME_A_COFFEE_ORIGIN = "https://buymeacoffee.com";

export function developerSupportEnabled(html) {
  // Read only the renderer's data block; incidental page text grants no permissions.
  const blocks = [...html.matchAll(
    /<script id="report-data" type="application\/json">([\s\S]*?)<\/script>/gu,
  )];
  if (blocks.length !== 1) return false;
  try {
    const data = JSON.parse(blocks[0][1]);
    return data !== null && typeof data === "object" && !Array.isArray(data) && data.support === true;
  } catch {
    return false;
  }
}

export function contentSecurityPolicyFor(html) {
  const supportEnabled = developerSupportEnabled(html);
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
  const supportEnabled = developerSupportEnabled(html);
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
