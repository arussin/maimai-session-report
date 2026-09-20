export function developerSupportEnabled(html) {
  if (html && typeof html === 'object') return html.flags?.support === true;
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

export function partyIntegration(html) {
  if (html && typeof html === 'object') return html.flags?.party || {};
  const blocks = [...html.matchAll(/<script id="report-data" type="application\/json">([\s\S]*?)<\/script>/gu)];
  try { return blocks.length === 1 ? JSON.parse(blocks[0][1]).partyIntegration || {} : {}; }
  catch { return {}; }
}

export function contentSecurityPolicyFor(html) {
  const support = developerSupportEnabled(html);
  return [
    "default-src 'none'",
    "base-uri 'none'",
    `connect-src ${support ? (partyIntegration(html).hosted === true ? "'self' " : '') + 'https://maimai.party https://api.stripe.com https://checkout.stripe.com https://link.com https://*.link.com' : partyIntegration(html).hosted === true ? "'self'" : "'none'"}`,
    "font-src 'none'",
    "form-action 'none'",
    "frame-ancestors 'none'",
    support ? "frame-src https://js.stripe.com https://*.js.stripe.com https://hooks.stripe.com https://checkout.stripe.com https://link.com https://*.link.com" : "frame-src 'none'",
    support ? "img-src data: https://*.stripe.com https://*.link.com" : "img-src data:",
    "manifest-src 'none'",
    "media-src 'none'",
    "object-src 'none'",
    support ? "script-src 'unsafe-inline' https://js.stripe.com https://*.js.stripe.com https://checkout.stripe.com" : "script-src 'unsafe-inline'",
    "style-src 'unsafe-inline'",
    "worker-src 'none'",
  ].join("; ");
}

// The renderer's deterministic meta policy, independently checked at publication.
export function reportMetaPolicy(html) {
  const headers = contentSecurityPolicyFor(html).split('; ');
  return ['default-src', 'script-src', 'style-src', 'img-src', 'connect-src', 'font-src',
    'media-src', 'object-src', 'frame-src', 'base-uri', 'form-action']
    .map(name => headers.find(value => value.startsWith(name + ' '))).join('; ');
}

export function permissionsPolicyFor(html) {
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
    developerSupportEnabled(html) ? 'payment=(self "https://js.stripe.com" "https://checkout.stripe.com" "https://hooks.stripe.com")' : "payment=()",
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
  "Cross-Origin-Opener-Policy": partyIntegration(reportHtml).enabled === true ? "same-origin-allow-popups" : "same-origin",
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
