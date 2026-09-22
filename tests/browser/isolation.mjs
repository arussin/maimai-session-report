/** Local-only browser fixtures. No production origin is ever passed to the network. */
import http from 'node:http';
import net from 'node:net';

// Only the disposable Playwright profile is affected. Never allow updater traffic.
const firefoxUserPrefs = {'app.update.disabledForTesting':true, 'app.update.auto':false,
  'app.update.enabled':false, 'app.update.background.scheduling.enabled':false,
  'app.update.url':'', 'app.update.url.override':'', 'media.gmp-manager.updateEnabled':false, 'media.gmp-manager.url':'',
  'media.gmp-manager.url.override':'', 'media.gmp-provider.enabled':false};

function originSet(origins) {
  return new Set(origins.map(value => {
    const url = new URL(value);
    if (!['http:', 'https:'].includes(url.protocol) || !['127.0.0.1', 'localhost', '[::1]'].includes(url.hostname)
        || url.username || url.password || url.pathname !== '/' || url.search || url.hash) {
      throw new Error(`Fixture origin must be an exact HTTP(S) loopback origin: ${value}`);
    }
    return url.origin;
  }));
}

export async function startIsolationProxy({origins}) {
  const allowed = originSet(origins), unexpected = [], blockedTransports = [], syntheticOrigins = new Set();
  const deny = (kind, target) => unexpected.push({kind, target});
  const server = http.createServer((request, response) => {
    let target;
    try { target = new URL(request.url); } catch { response.writeHead(400).end(); return; }
    if (!allowed.has(target.origin)) {
      deny('proxy', target.origin); response.writeHead(403).end('Synthetic fixture network blocked'); return;
    }
    const headers = {...request.headers};
    delete headers['proxy-connection']; delete headers['proxy-authorization'];
    const upstream = http.request(target, {method: request.method, headers}, result => {
      response.writeHead(result.statusCode, result.headers); result.pipe(response);
    });
    upstream.on('error', () => { if (!response.headersSent) response.writeHead(502); response.end(); });
    request.pipe(upstream);
  });
  server.on('clientError', (_error, socket) => socket.destroy());
  server.on('connect', (request, socket, head) => {
    socket.on('error', () => socket.destroy());
    let target;
    try { target = new URL('https://' + request.url); } catch { socket.destroy(); return; }
    if (!allowed.has(target.origin) && !allowed.has('http://' + target.host)) {
      if (syntheticOrigins.has(target.origin)) blockedTransports.push({kind:'CONNECT',target:request.url});
      else deny('CONNECT', request.url); socket.end('HTTP/1.1 403 Forbidden\r\nConnection: close\r\n\r\n'); return;
    }
    // Playwright APIRequestContext also tunnels HTTP through CONNECT. Restrict
    // both forms to the exact allocated loopback authority; never another port.
    const upstream = net.connect(Number(target.port || 443), target.hostname.replace(/^\[|\]$/g, ''), () => {
      socket.write('HTTP/1.1 200 Connection Established\r\n\r\n');
      if (head.length) upstream.write(head);
      upstream.pipe(socket); socket.pipe(upstream);
    });
    upstream.on('error', () => socket.destroy()); socket.on('error', () => upstream.destroy());
    socket.on('close', () => upstream.destroy());
  });
  server.on('upgrade', (request, socket) => {
    deny('upgrade', request.url); socket.end();
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  return {
    server: `http://127.0.0.1:${server.address().port}`, unexpected, allowed, syntheticOrigins, blockedTransports,
    declareSynthetic: origin => {
      const url = new URL(origin);
      if (url.protocol !== 'https:' || url.origin !== origin) throw new Error('Declare an exact synthetic HTTPS origin');
      // Transports may be created after a context closes. Retain this deny-only
      // classification for the proxy lifetime; it never grants network access.
      syntheticOrigins.add(origin); return () => {};
    },
    allowOrigin: origin => { const value = [...originSet([origin])][0]; allowed.add(value); return () => allowed.delete(value); },
    close: async () => { server.closeAllConnections(); await new Promise(resolve => server.close(resolve)); },
  };
}

function guardRoutes(surface, {allowed, unexpected}) {
  const original = surface.route.bind(surface), remove = surface.unroute.bind(surface), handlers = new WeakMap();
  surface.route = async (pattern, handler, options) => {
    const wrapped = async (route, request) => {
      const guarded = new Proxy(route, {get(target, key) {
        const value = Reflect.get(target, key);
        if (key === 'continue' || key === 'fetch') return async options => {
          const url = new URL(options?.url || request.url());
          if (!allowed.has(url.origin)) {
            unexpected.push({kind:'route-' + key, target:url.origin, method:request.method()});
            if (key === 'continue') return target.abort('blockedbyclient');
            throw new Error('Fixture route.fetch denied non-loopback destination');
          }
          return value.call(target, options);
        };
        return typeof value === 'function' ? value.bind(target) : value;
      }});
      return handler(guarded, request);
    };
    handlers.set(handler, wrapped);
    return original(pattern, wrapped, options);
  };
  surface.unroute = (pattern, handler) => remove(pattern, handler && (handlers.get(handler) || handler));
}

export async function isolateContext(context, {origins, handlers = [], unexpected = [], allowed = originSet(origins)}) {
  const options = {allowed, unexpected};
  guardRoutes(context, options);
  context.on('page', page => guardRoutes(page, options));
  for (const page of context.pages()) guardRoutes(page, options);
  await context.route('**/*', async route => {
    const request = route.request();
    for (const handler of handlers) if (await handler(route, request)) return;
    const url = new URL(request.url());
    if (allowed.has(url.origin)) return route.continue();
    unexpected.push({kind: request.resourceType(), target: url.origin});
    await route.abort('blockedbyclient');
  });
  return unexpected;
}

export async function launchIsolated(browserType, {origins, handlers = [], launch = {}, context = {}}) {
  const proxy = await startIsolationProxy({origins});
  let browser;
  try {
    browser = await browserType.launch({...launch, firefoxUserPrefs:{...firefoxUserPrefs,...launch.firefoxUserPrefs}, proxy: {server: proxy.server}});
    const isolated = await browser.newContext({...context, serviceWorkers: 'block'});
    await isolateContext(isolated, {origins, handlers, unexpected: proxy.unexpected, allowed: proxy.allowed, syntheticOrigins: proxy.syntheticOrigins});
    return {browser, context: isolated, unexpected: proxy.unexpected,
      blockedTransports: proxy.blockedTransports, synthetic: proxy.declareSynthetic,
      close: async () => { await browser.close(); await proxy.close(); }};
  } catch (error) {
    await browser?.close(); await proxy.close(); throw error;
  }
}

/** Extend Playwright once; the proxy also covers page routes that call continue(). */
export function isolatedTest(base, {origins}) {
  return base.extend({
    _networkProxy: [async ({}, use) => {
      const proxy = await startIsolationProxy({origins});
      try { await use(proxy); } finally { await proxy.close(); }
    }, {scope: 'worker'}],
    launchOptions: [async ({_networkProxy}, use) => {
      await use({proxy: {server: _networkProxy.server}, firefoxUserPrefs});
    }, {scope: 'worker'}],
    serviceWorkers: 'block',
    fixtureOrigins: async ({_networkProxy}, use) => {
      const releases=[];
      const scoped = register => value => { const release=register(value); releases.push(release); return release; };
      try { await use({allow:scoped(_networkProxy.allowOrigin),synthetic:scoped(_networkProxy.declareSynthetic)}); }
      finally { for (const release of releases) release(); }
    },
    browser: [async ({browser, _networkProxy}, use) => {
      const original = browser.newContext.bind(browser);
      browser.newContext = async options => {
        const context = await original({...options, serviceWorkers: 'block'});
        await isolateContext(context, {origins, unexpected: _networkProxy.unexpected, allowed: _networkProxy.allowed, syntheticOrigins: _networkProxy.syntheticOrigins});
        return context;
      };
      try { await use(browser); } finally { browser.newContext = original; }
    }, {scope: 'worker'}],
    _networkCheck: [async ({_networkProxy, fixtureOrigins, browser}, use, testInfo) => {
      const start = _networkProxy.unexpected.length, transportStart = _networkProxy.blockedTransports.length;
      await use();
      // Finish each context before examining its ledger or releasing allocated origins.
      await Promise.all(browser.contexts().map(context => context.close()));
      const denied = _networkProxy.blockedTransports.slice(transportStart);
      if (denied.length) await testInfo.attach('denied-synthetic-transports', {body:JSON.stringify(denied),contentType:'application/json'});
      const blocked = _networkProxy.unexpected.slice(start);
      if (blocked.length) throw new Error(`Unexpected fixture network requests: ${JSON.stringify(blocked)}`);
    }, {auto: true}],
  });
}
