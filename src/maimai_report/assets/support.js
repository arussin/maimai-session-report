(function initializeProjectLinks() {
  "use strict";
  let data;
  try { data = JSON.parse(document.getElementById("report-data")?.textContent || "{}"); }
  catch { return; }
  if (data?.support !== true || document.querySelector(".support-card")) return;
  const footer = document.querySelector(".footer");
  if (!footer) return;

  // Shared checkout has its own availability switch; no payment state lives here.
  const supportAvailable = true;
  const checkoutUrl = "https://maimai.party/support.html";
  const repositoryUrl = "https://github.com/arussin/maimai-session-report";
  function link(label, url, className, icon) {
    const anchor = document.createElement("a");
    anchor.className = "project-action " + className;
    anchor.href = url; anchor.target = "_blank";
    anchor.rel = "noopener noreferrer"; anchor.referrerPolicy = "no-referrer";
    // Only bundled, constant SVG markup enters this template.
    anchor.innerHTML = icon;
    const text = document.createElement("span"); text.textContent = label; anchor.append(text);
    return anchor;
  }
  const card = document.createElement("aside");
  card.className = "support-card"; card.setAttribute("aria-label", "Project links");
  card.append(link("View on GitHub", repositoryUrl, "github-button", "<svg width=\"22\" height=\"22\" viewBox=\"0 0 16 16\" fill=\"currentColor\" aria-hidden=\"true\"><path d=\"M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82a7.65 7.65 0 0 1 2-.27c.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8Z\"/></svg>"));
  if (supportAvailable) {
    const group = document.createElement("div"); group.className = "support-button-group";
    const support = link("Support maimai.party", checkoutUrl, "creator-support-link", "<svg class=\"creator-support-heart\" width=\"22\" height=\"22\" viewBox=\"0 0 24 24\" aria-hidden=\"true\">\n<defs><linearGradient id=\"creator-support-heart-gradient\" x1=\"0\" y1=\"0\" x2=\"1\" y2=\"0\"><stop offset=\"0\" stop-color=\"#ed5053\"/><stop offset=\".24\" stop-color=\"#ed5053\"/><stop offset=\".24\" stop-color=\"#f39835\"/><stop offset=\".42\" stop-color=\"#f39835\"/><stop offset=\".42\" stop-color=\"#f2c62e\"/><stop offset=\".48\" stop-color=\"#f2c62e\"/><stop offset=\".48\" stop-color=\"#8aba3d\"/><stop offset=\".70\" stop-color=\"#8aba3d\"/><stop offset=\".70\" stop-color=\"#27a9e0\"/><stop offset=\"1\" stop-color=\"#27a9e0\"/></linearGradient></defs>\n<path fill=\"url(#creator-support-heart-gradient)\" d=\"M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8L12 21l8.8-8.6a5.5 5.5 0 0 0 0-7.8Z\"/></svg>");
    // Unconfigured hosts use the shared checkout in the current tab.
    support.removeAttribute("target"); support.id = "support-open";
    const provider = document.createElement("span"); provider.className = "support-button-provider";
    provider.append(document.createTextNode("Powered by "));
    const logo = document.createElement("img"); logo.alt = "Stripe";
    logo.width = 35; logo.height = 15; logo.src = "data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMzYwIiBoZWlnaHQ9IjE1MSIgdmlld0JveD0iMCAwIDM2MCAxNTEiIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+CjxwYXRoIGZpbGwtcnVsZT0iZXZlbm9kZCIgY2xpcC1ydWxlPSJldmVub2RkIiBkPSJNMzYwIDc4LjIwMDFDMzYwIDUyLjYwMDEgMzQ3LjYgMzIuNDAwMSAzMjMuOSAzMi40MDAxQzMwMC4xIDMyLjQwMDEgMjg1LjcgNTIuNjAwMSAyODUuNyA3OC4wMDAxQzI4NS43IDEwOC4xIDMwMi43IDEyMy4zIDMyNy4xIDEyMy4zQzMzOSAxMjMuMyAzNDggMTIwLjYgMzU0LjggMTE2LjhWOTYuODAwMUMzNDggMTAwLjIgMzQwLjIgMTAyLjMgMzMwLjMgMTAyLjNDMzIwLjYgMTAyLjMgMzEyIDk4LjkwMDIgMzEwLjkgODcuMTAwMkgzNTkuOEMzNTkuOCA4NS44MDAyIDM2MCA4MC42MDAyIDM2MCA3OC4yMDAxWk0zMTAuNiA2OC43MDAxQzMxMC42IDU3LjQwMDIgMzE3LjUgNTIuNzAwMSAzMjMuOCA1Mi43MDAxQzMyOS45IDUyLjcwMDEgMzM2LjQgNTcuNDAwMiAzMzYuNCA2OC43MDAxSDMxMC42WiIgZmlsbD0iIzA2MUIzMSIvPgo8cGF0aCBmaWxsLXJ1bGU9ImV2ZW5vZGQiIGNsaXAtcnVsZT0iZXZlbm9kZCIgZD0iTTI0Ny4xIDMyLjQwMDFDMjM3LjMgMzIuNDAwMSAyMzEgMzcuMDAwMSAyMjcuNSA0MC4yMDAxTDIyNi4yIDM0LjAwMDFIMjA0LjJWMTUwLjZMMjI5LjIgMTQ1LjNMMjI5LjMgMTE3QzIzMi45IDExOS42IDIzOC4yIDEyMy4zIDI0NyAxMjMuM0MyNjQuOSAxMjMuMyAyODEuMiAxMDguOSAyODEuMiA3Ny4yMDAxQzI4MS4xIDQ4LjIwMDEgMjY0LjYgMzIuNDAwMSAyNDcuMSAzMi40MDAxWk0yNDEuMSAxMDEuM0MyMzUuMiAxMDEuMyAyMzEuNyA5OS4yMDAxIDIyOS4zIDk2LjYwMDJMMjI5LjIgNTkuNTAwMUMyMzEuOCA1Ni42MDAxIDIzNS40IDU0LjYwMDIgMjQxLjEgNTQuNjAwMkMyNTAuMiA1NC42MDAyIDI1Ni41IDY0LjgwMDEgMjU2LjUgNzcuOTAwMUMyNTYuNSA5MS4zMDAxIDI1MC4zIDEwMS4zIDI0MS4xIDEwMS4zWiIgZmlsbD0iIzA2MUIzMSIvPgo8cGF0aCBmaWxsLXJ1bGU9ImV2ZW5vZGQiIGNsaXAtcnVsZT0iZXZlbm9kZCIgZD0iTTE2OS44IDI2LjVMMTk0LjkgMjEuMVYwLjgwMDA0OUwxNjkuOCA2LjEwMDA1VjI2LjVaIiBmaWxsPSIjMDYxQjMxIi8+CjxwYXRoIGQ9Ik0xOTQuOSAzNC4xMDAxSDE2OS44VjEyMS42SDE5NC45VjM0LjEwMDFaIiBmaWxsPSIjMDYxQjMxIi8+CjxwYXRoIGZpbGwtcnVsZT0iZXZlbm9kZCIgY2xpcC1ydWxlPSJldmVub2RkIiBkPSJNMTQyLjkgNDEuNTAwMUwxNDEuMyAzNC4xMDAxSDExOS43VjEyMS42SDE0NC43VjYyLjMwMDFDMTUwLjYgNTQuNjAwMSAxNjAuNiA1Ni4wMDAxIDE2My43IDU3LjEwMDFWMzQuMTAwMUMxNjAuNSAzMi45MDAxIDE0OC44IDMwLjcwMDEgMTQyLjkgNDEuNTAwMVoiIGZpbGw9IiMwNjFCMzEiLz4KPHBhdGggZmlsbC1ydWxlPSJldmVub2RkIiBjbGlwLXJ1bGU9ImV2ZW5vZGQiIGQ9Ik05Mi44OTk5IDEyLjQwMDFMNjguNDk5OSAxNy42MDAxTDY4LjM5OTkgOTcuNzAwMUM2OC4zOTk5IDExMi41IDc5LjQ5OTkgMTIzLjQgOTQuMjk5OSAxMjMuNEMxMDIuNSAxMjMuNCAxMDguNSAxMjEuOSAxMTEuOCAxMjAuMVY5OS44MDAxQzEwOC42IDEwMS4xIDkyLjc5OTkgMTA1LjcgOTIuNzk5OSA5MC45MDAxVjU1LjQwMDFIMTExLjhWMzQuMTAwMkg5Mi43OTk5TDkyLjg5OTkgMTIuNDAwMVoiIGZpbGw9IiMwNjFCMzEiLz4KPHBhdGggZmlsbC1ydWxlPSJldmVub2RkIiBjbGlwLXJ1bGU9ImV2ZW5vZGQiIGQ9Ik0yNS4zIDU5LjUwMDFDMjUuMyA1NS42MDAxIDI4LjUgNTQuMTAwMiAzMy44IDU0LjEwMDJDNDEuNCA1NC4xMDAyIDUxIDU2LjQwMDEgNTguNiA2MC41MDAxVjM3LjAwMDFDNTAuMyAzMy43MDAxIDQyLjEgMzIuNDAwMSAzMy44IDMyLjQwMDFDMTMuNSAzMi40MDAxIDAgNDMuMDAwMSAwIDYwLjcwMDFDMCA4OC4zMDAxIDM4IDgzLjkwMDEgMzggOTUuODAwMUMzOCAxMDAuNCAzNCAxMDEuOSAyOC40IDEwMS45QzIwLjEgMTAxLjkgOS41IDk4LjUwMDIgMS4xIDkzLjkwMDJWMTE3LjdDMTAuNCAxMjEuNyAxOS44IDEyMy40IDI4LjQgMTIzLjRDNDkuMiAxMjMuNCA2My41IDExMy4xIDYzLjUgOTUuMjAwMUM2My40IDY1LjQwMDEgMjUuMyA3MC43MDAxIDI1LjMgNTkuNTAwMVoiIGZpbGw9IiMwNjFCMzEiLz4KPC9zdmc+Cg==";
    provider.append(logo); group.append(support, provider); card.append(group);
  }
  footer.before(card);
})();

/* Native checkout UI shared with maimai.party. Keep the two bundled modules below
   byte-identical to support-client.js and support-stripe.js in that repository. */
(() => {
  if (!document.getElementById('support-open') ||
      location.origin !== 'https://adamrussin.com' &&
      !['localhost', '127.0.0.1'].includes(location.hostname)) return;
  window.maimaiSupportConfig = Object.freeze({
    enabled: true, origin: location.origin, apiOrigin: 'https://maimai.party',
    publishableKey: 'pk_live_51UHZZ0DrG9Tq0ch5XoqgrhrxG5r6Jjjw29sQGhvZvbvfjmalBZ1iakVWY2AAVXh0VZo3PKbA01abE2vUR4BnkTnu00TEYDhcmj',
    project: 'session-report', returnHash: '#support-return',
    title: 'Support maimai.party',
    invitation: 'maimai.party is free for everyone. If you’d like to help with hosting and domain costs, a few dollars is more than enough.',
    thanks: 'Thank you for supporting maimai.party!',
  });
  const brand = document.createElement('span'); brand.className = 'party-brand'; brand.hidden = true;
  brand.innerHTML = '<span aria-hidden="true">maimai<span class="party-suffix"><span class="party-dot">.</span><span class="party-red">p</span><span class="party-orange">a</span><span class="party-yellow">r</span><span class="party-green">t</span><span class="party-blue">y</span></span></span>';
  document.querySelector('.support-card').append(brand);
})();

/* Payment-only state shared with the return page. Never reads player storage or URLs. */
(() => {
  'use strict';
  if (window.maimaiSupportClient) return;
  const config = window.maimaiSupportConfig;
  if (!config || (location.protocol !== 'https:' && !['localhost', '127.0.0.1'].includes(location.hostname)) || location.origin !== config.origin ||
      !/^pk_(test|live)_[A-Za-z0-9]+$/.test(config.publishableKey)) return;
  const key = 'support.checkout.v2.' + config.project;
  const uuid = /^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$/;
  const clear = () => { try { sessionStorage.removeItem(key); } catch { /* No state. */ } };
  const save = value => {
    // Redirect methods need this tab's state; do not start a payment if it cannot persist.
    sessionStorage.setItem(key, JSON.stringify(value));
  };
  const read = () => {
    try {
      const value = JSON.parse(sessionStorage.getItem(key));
      if (!value || !uuid.test(value.attempt) ||
          (value.entry !== undefined && !['site', 'support'].includes(value.entry)) ||
          !Number.isFinite(value.created) || value.created > Date.now() ||
          Date.now() - value.created > 23 * 3600000 ||
          (value.session && !/^cs_(test|live)_[a-zA-Z0-9]{10,200}$/.test(value.session))) return null;
      return value;
    } catch { return null; }
  };
  async function request(action, value) {
    const response = await fetch((config.apiOrigin || '') + '/api/support/' + action, {method: 'POST',
      headers: {'Content-Type': 'application/json'}, credentials: 'omit', cache: 'no-store',
      referrerPolicy: 'no-referrer', redirect: 'error', signal: AbortSignal.timeout(20000),
      body: JSON.stringify({project: config.project, attempt: value.attempt,
        ...(value.session ? {session: value.session} : {})})});
    if (!response.ok) throw new Error(response.status === 429 ? 'Please wait a minute and try again.' :
      'Checkout is unavailable. Please try again.');
    const data = await response.json();
    if (!['open', 'paid', 'pending', 'expired'].includes(data.status)) throw new Error('Invalid checkout response.');
    return data;
  }
  window.maimaiSupportClient = Object.freeze({config, read, save, clear, request});
})();

(() => {
  'use strict';
  const client = window.maimaiSupportClient, opener = document.getElementById('support-open');
  if (!client?.config.enabled || !opener || opener.dataset.checkoutReady ||
      typeof HTMLDialogElement === 'undefined' || !HTMLDialogElement.prototype.showModal) return;
  const {config, read, save, clear, request} = client;
  const element = (tag, className, text) => {
    const node = document.createElement(tag); node.className = className;
    if (text) node.textContent = text; return node;
  };
  const event = name => window.dispatchEvent(new CustomEvent('maimai:support', {detail: name}));
  const dialog = element('dialog', 'support-dialog support-stripe-dialog');
  dialog.dataset.stage = 'checkout';
  dialog.id = 'support-checkout-dialog'; dialog.setAttribute('aria-labelledby', 'support-dialog-title');
  const header = element('div', 'support-dialog-header');
  const title = element('h2', 'support-dialog-title', config.title); title.id = 'support-dialog-title';
  const brand = document.querySelector('.party-brand > span');
  if (brand) {
    title.replaceChildren(brand.cloneNode(true)); title.classList.add('party-brand');
    title.setAttribute('aria-label', config.title);
  }
  const close = element('button', 'support-dialog-close', '×'); close.type = 'button';
  close.setAttribute('aria-label', 'Close support checkout'); header.append(title, close);
  const body = element('div', 'support-stripe-body');
  const message = element('p', 'support-stripe-status'); message.setAttribute('role', 'status');
  const invitation = element('p', 'support-invitation', config.invitation);
  const mount = element('div', 'support-stripe-mount'); mount.id = 'support-stripe-mount';
  const retry = element('button', 'support-primary', 'Try again'); retry.type = 'button'; retry.hidden = true;
  const again = element('button', 'support-secondary', 'Start a new checkout'); again.type = 'button'; again.hidden = true;
  body.append(invitation, message, mount, retry, again);
  dialog.append(header, body); document.body.append(dialog);
  opener.dataset.checkoutReady = 'stripe'; opener.setAttribute('aria-haspopup', 'dialog');
  const provider = opener.parentElement.querySelector('.support-button-provider');
  if (provider) provider.hidden = false;
  opener.parentElement.hidden = false;
  opener.setAttribute('aria-controls', dialog.id);
  opener.querySelector('span:last-child').textContent = config.title;
  let instance = null, generation = 0, busy = false, scriptPromise = null;
  const destroy = () => { instance?.destroy(); instance = null; mount.replaceChildren(); };
  function loadStripe() {
    if (window.Stripe) return Promise.resolve();
    if (scriptPromise) return scriptPromise;
    scriptPromise = new Promise((resolve, reject) => {
      const script = element('script', ''); script.async = true;
      script.src = 'https://js.stripe.com/dahlia/stripe.js'; script.referrerPolicy = 'no-referrer';
      const fail = () => { clearTimeout(timer); script.remove(); scriptPromise = null;
        reject(new Error('Stripe could not load. Please try again.')); };
      const timer = setTimeout(fail, 15000);
      script.onerror = fail;
      script.onload = () => { clearTimeout(timer); if (window.Stripe) resolve(); else fail(); };
      document.head.append(script);
    });
    return scriptPromise;
  }
  function result(status, value) {
    if (status === 'open') return false;
    dialog.dataset.stage = 'result';
    destroy(); invitation.hidden = true; retry.hidden = true; again.hidden = status === 'pending';
    if (status === 'paid') {
      message.textContent = config.thanks;
      again.textContent = 'Support again';
      if (!value.successTracked) { value.successTracked = true; save(value); event('support_success_return'); }
    } else if (status === 'pending') {
      message.textContent = 'Your payment is still processing. Please check its status before trying another payment.';
      retry.textContent = 'Check payment status'; retry.hidden = false;
    } else {
      message.textContent = 'This checkout has expired. You can start a new checkout.';
      again.textContent = 'Start a new checkout';
    }
    return true;
  }
  function errorMessage(error) {
    const safeMessages = ['Please wait a minute and try again.', 'Checkout is unavailable. Please try again.',
      'Stripe could not load. Please try again.',
      'Checkout is taking too long. Try again to resume the same payment.'];
    return error?.name === 'QuotaExceededError' || error?.name === 'SecurityError' ?
      'Checkout needs temporary storage in this tab to return safely from a wallet. Please allow it and try again.' :
      error?.name === 'TimeoutError' || error?.name === 'AbortError' ?
        'Checkout is taking too long. Try again to resume the same payment.' :
        error instanceof TypeError ? 'Checkout could not connect. Try again to resume the same payment.' :
          safeMessages.includes(error?.message) ? error.message : 'Checkout could not start. Try again to resume the same payment.';
  }
  async function start() {
    if (busy) return;
    let value = read();
    if (!value) value = {attempt: crypto.randomUUID(), created: Date.now(),
      entry: /^\/support(?:\.html)?$/.test(location.pathname) ? 'support' : 'site'};
    const token = ++generation;
    dialog.dataset.stage = 'checkout';
    busy = true; invitation.hidden = false; retry.hidden = true; again.hidden = true;
    destroy(); message.textContent = value.session ? 'Checking your checkout…' : 'Opening secure checkout…';
    try {
      save(value);
      if (value.session) {
        const checked = await request('status', value);
        if (token !== generation) return;
        if (result(checked.status, value)) return;
      }
      await loadStripe(); if (token !== generation) return;
      const data = await request('checkout', value); if (token !== generation) return;
      if (!/^cs_(test|live)_[a-zA-Z0-9]{10,200}$/.test(data.session)) throw new Error('Invalid checkout response.');
      value.session = data.session; save(value);
      if (result(data.status, value)) return;
      if (typeof data.clientSecret !== 'string') throw new Error('Invalid checkout response.');
      let abandoned = false, initializationTimer;
      const initializing = window.Stripe(config.publishableKey).createEmbeddedCheckoutPage({
        fetchClientSecret: async () => data.clientSecret,
        onComplete: () => {
          if (abandoned || token !== generation) return;
          // A client callback is not proof of payment: retrieve paid status on the server.
          busy = false; void start();
        },
      }).then(checkout => {
        if (abandoned || token !== generation) { checkout.destroy(); return null; }
        return checkout;
      });
      let checkout;
      try {
        checkout = await Promise.race([initializing, new Promise((_, reject) => {
          initializationTimer = setTimeout(() => { abandoned = true;
            reject(new Error('Checkout is taking too long. Try again to resume the same payment.'));
          }, 20000);
        })]);
      } finally { clearTimeout(initializationTimer); }
      if (!checkout) return;
      if (token !== generation) { checkout.destroy(); return; }
      instance = checkout; checkout.mount(mount); message.textContent = '';
      if (!value.startedTracked) { value.startedTracked = true; save(value); event('support_checkout_started'); }
    } catch (error) {
      if (token !== generation) return;
      destroy(); dialog.dataset.stage = 'result'; message.textContent = errorMessage(error);
      retry.textContent = 'Try again'; retry.hidden = false;
    } finally { if (token === generation) busy = false; }
  }
  function open() {
    if (dialog.open) return;
    dialog.showModal(); document.body.classList.add('support-dialog-open'); close.focus();
    event('support_opened');
    void start();
  }
  retry.onclick = () => { void start(); };
  again.onclick = () => { clear(); close.focus(); void start(); };
  opener.addEventListener('click', e => {
    if (e.button || e.ctrlKey || e.metaKey || e.shiftKey || e.altKey) return;
    e.preventDefault(); open();
  });
  close.onclick = () => dialog.close();
  dialog.addEventListener('click', e => { if (e.target === dialog) {
    const box = dialog.getBoundingClientRect();
    if (e.clientX < box.left || e.clientX > box.right || e.clientY < box.top || e.clientY > box.bottom) dialog.close();
  } });
  dialog.addEventListener('close', () => {
    generation++; busy = false; destroy(); document.body.classList.remove('support-dialog-open'); opener.focus();
  });
  // Only an explicit return-page action resumes automatically. Ordinary reloads wait for a click.
  const returning = read();
  if (config.returnHash && location.hash === config.returnHash) {
    history.replaceState(null, '', location.pathname + location.search);
    if (returning?.session) { returning.resume = true; save(returning); }
  }
  if (returning?.resume) { delete returning.resume; save(returning); open(); }
})();
