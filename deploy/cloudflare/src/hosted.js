import {privateHeadersFor} from "./security.js";
import { handleHistory, withHistoryNavigation } from './history-reader.js';

// The generated entry supplies retained bytes and validated installation settings.
export function createHostedWorker(report, b50, support, installation) {
  const headers = (extra = {}) => privateHeadersFor(report, extra);
  const text = (value, status, method) => new Response(method === 'HEAD' ? null : value, {
    status, headers: headers({'Content-Type':'text/plain; charset=utf-8'}),
  });
  return {async fetch(request, env = {}) {
    const url = new URL(request.url), prefix = installation.prefix;
    if (url.origin !== installation.origin) return text('Not found', 404, request.method);
    if (!['GET','HEAD'].includes(request.method)) {
      const response = text('Method not allowed', 405, request.method);
      response.headers.set('Allow', 'GET, HEAD'); return response;
    }
    if (installation.historyEnabled) {
      if (env.HISTORY_ORIGIN !== installation.origin || env.HISTORY_PREFIX !== prefix || env.HISTORY_SCOPE !== installation.scope) {
        return text('Installation configuration mismatch', 503, request.method);
      }
      const archived = await handleHistory(request, env, headers, support);
      if (archived) return archived;
    }
    if (url.pathname === prefix.slice(0, -1)) {
      return new Response(null, {status:308, headers:headers({Location:installation.origin + prefix})});
    }
    if (url.pathname === prefix + 'b50.webp') {
      if (!b50) return text('B50 unavailable', 404, request.method);
      return new Response(request.method === 'HEAD' ? null : b50, {status:200, headers:headers({
        'Content-Type':'image/webp', 'Content-Disposition':'attachment; filename="maimai-b50.webp"',
      })});
    }
    if (![prefix, prefix + 'index.html'].includes(url.pathname)) return text('Not found', 404, request.method);
    const html = installation.historyEnabled ? withHistoryNavigation(report, {prefix}) : report;
    return new Response(request.method === 'HEAD' ? null : html, {status:200, headers:headers({'Content-Type':'text/html; charset=utf-8'})});
  }};
}
