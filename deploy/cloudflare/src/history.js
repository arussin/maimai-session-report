/* Hosted history reader. All data access stays in the Worker; navigation is ordinary GET. */
const PAGE_SIZE = 20;
const MAX_BYTES = 20 * 1024 * 1024;
const ID = /^[a-f0-9]{64}$/;
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const number = value => Number.isSafeInteger(value) ? value.toLocaleString('en-US') : '—';
const change = (before, after) => Number.isSafeInteger(before) && Number.isSafeInteger(after) ? after - before : null;
const signed = value => value === null ? '—' : `${value > 0 ? '+' : ''}${number(value)}`;
function date(ms, timezone, options = {}) {
  return new Intl.DateTimeFormat('en-US', {timeZone: timezone, month:'short', day:'numeric', year:'numeric', ...options}).format(new Date(ms));
}
const NAV_CSS = `.history-nav{box-sizing:border-box;max-width:1184px;margin:0 auto;padding:12px 24px;display:flex;gap:4px;align-items:center;border-bottom:1px solid #dce7e9;font:600 14px/1.4 system-ui;color:#183b43}.history-nav a{display:inline-flex;min-height:44px;box-sizing:border-box;align-items:center;padding:8px 14px;text-decoration:none;border-radius:6px;color:#44616a}.history-nav a[aria-current]{color:#006b7a;background:#e6f8fa}.history-nav a:focus-visible{outline:3px solid #007887;outline-offset:3px}.history-context{max-width:1136px;margin:12px auto 0;padding:10px 24px;font:14px/1.6 system-ui;color:#44616a}.history-context strong{color:#183b43}.history-context p{margin:0}.history-unavailable{color:#546b71;cursor:default}@media(max-width:600px){.history-nav{padding:6px 16px}.history-context{padding:8px 20px;margin:4px 0 0}}`;
const CSS = `${NAV_CSS}
:root{color-scheme:light;--ink:#183b43;--ink-2:#183b43;--muted:#52676d;--line:#dce7e9;--aqua:#08aebe;--aqua-deep:#007887;--pink:#ba2f69;--paper-2:#f2fafb;--text-label:.875rem}button{font:inherit;cursor:pointer}button,a{touch-action:manipulation}[hidden]{display:none!important}.support-card+.footer{margin-top:0;border-top:0}*{box-sizing:border-box}body{margin:0;background:#fff;color:#183b43;font:16px/1.55 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}a{color:#007887}a:focus-visible{outline:3px solid #007887;outline-offset:4px}h1,h2,p{margin:0}main{max-width:1184px;margin:auto;padding:36px 24px 64px}main>header{margin-bottom:28px}.brand{font-style:italic;font-weight:800;font-size:20px;letter-spacing:-.6px;color:#007887}.brand b{font-size:12px;background:#fff1b8;padding:3px 5px;border-radius:3px;font-style:normal;letter-spacing:0}h1{font-size:36px;letter-spacing:-1px;line-height:1.2;margin-top:20px}main>header p{color:#526b72;margin-top:10px;max-width:660px}.history-summary{display:grid;grid-template-columns:2fr 1fr;gap:32px;align-items:start;padding:24px 28px;border:1px solid #d4e6e9;border-top:3px solid #08aebe;border-radius:10px;background:#f8fcfc;margin-bottom:36px}h2{font-size:18px;font-weight:650;letter-spacing:-.3px}.trend-plot{display:grid;grid-template-columns:48px minmax(0,1fr);margin-top:10px}.trend-axis{position:relative;font-size:12px;color:#526b72;font-variant-numeric:tabular-nums}.trend-axis span{position:absolute;right:4px;transform:translateY(-50%)}.trend-axis span:first-child{top:27.027%}.trend-axis span:last-child{top:86.486%}.trend-plot .trend{margin:0}.trend-dates{display:flex;justify-content:space-between;margin-left:58px;font-size:12px;color:#526b72}.trend-caption{font-size:14px;color:#526b72;margin-top:4px}.trend{display:block;width:100%;height:150px;margin-top:10px;overflow:visible}.history-stat{font-size:40px;font-weight:700;line-height:1.2;letter-spacing:-1px}.coverage{border-left:1px solid #d4e6e9;padding-left:28px}.coverage p{font-size:14px;color:#526b72;margin-top:12px}.coverage .history-stat{color:#183b43;font-size:32px;margin-top:4px}.coverage .stat-label{font-weight:600;color:#183b43}.capture-list{list-style:none;padding:0;margin:16px 0 0;border-top:1px solid #d4e6e9}.capture{display:grid;grid-template-columns:1.3fr 1.2fr 1.4fr 28px;gap:24px;align-items:center;padding:23px 4px;border-bottom:1px solid #d4e6e9;color:inherit;text-decoration:none}.capture:hover{background:#f6fbfc}.capture h3{font-size:17px;font-weight:650;margin:0 0 3px}.capture small{display:block;color:#526b72;font-size:13px;line-height:1.6}.rating{display:flex;align-items:baseline;gap:12px;flex-wrap:wrap;font-variant-numeric:tabular-nums}.rating strong{font-size:25px;font-weight:700;letter-spacing:-.6px}.gain{display:inline-block;min-width:54px;color:#006b65;font-size:16px;font-weight:700;letter-spacing:0}.gain.negative{color:#a92858}.pools{display:grid;grid-template-columns:1fr 1fr;gap:20px}.pool-value{display:block;font-size:16px;font-weight:650;font-variant-numeric:tabular-nums}.old-label,.new-label{display:flex;align-items:center;gap:6px;font-size:13px;color:#526b72}.old-label::before,.new-label::before{content:"";width:7px;height:7px;border-radius:50%;background:#007887}.new-label::before{background:#8954c2}.arrow{font-size:24px;color:#007887}.capture-note{display:block;margin-top:5px;color:#755b09;font-size:13px}.list-heading{display:flex;align-items:baseline;justify-content:space-between;gap:16px}.list-heading p{font-size:14px;color:#526b72}.pagination{display:flex;justify-content:space-between;align-items:center;margin-top:24px;gap:12px}.pagination a,.empty a{padding:10px 14px;min-height:44px;border:1px solid #b8cfd4;border-radius:6px;text-decoration:none;font-size:14px;font-weight:600}.archive-note{font-size:13px;color:#526b72;max-width:840px;margin:28px 0 0}.empty{padding:30px 0}.empty p{margin:12px 0 24px;color:#526b72}.footer{border-top:1px solid #dce7e9;padding-top:20px;margin-top:48px;font-size:13px;color:#526b72}.sr-only{position:absolute;width:1px;height:1px;padding:0;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}
@media(max-width:760px){main{padding:28px 20px 40px}h1{font-size:30px}.trend{height:110px}.history-summary{grid-template-columns:1fr;gap:18px;padding:20px;margin-bottom:28px}.coverage{border-left:0;border-top:1px solid #d4e6e9;padding:16px 0 0;display:grid;grid-template-columns:1fr 1fr;gap:12px}.coverage p{margin:0}.coverage .history-stat{font-size:20px}.coverage{display:block;padding-top:12px}.coverage>div{display:flex;align-items:baseline;justify-content:space-between;gap:12px}.coverage .stat-label{font-size:14px}.coverage>p{display:none}.capture{grid-template-columns:1fr 1fr;gap:12px 18px;padding:20px 0;position:relative}.capture .pools{grid-column:1/-1;gap:18px}.capture .arrow{position:absolute;right:0;top:16px;font-size:20px}.capture .identity{padding-right:12px}.capture .rating{padding-right:14px;gap:3px 8px;justify-content:flex-end}.capture .rating small{width:100%;text-align:right}.capture .rating strong{font-size:23px}.capture .gain{min-width:0;font-size:15px}.capture h3{font-size:16px}.pool-value{font-size:15px}.list-heading p{max-width:140px;text-align:right;font-size:13px}.trend-caption{font-size:13px}.capture-note{max-width:170px}.archive-note{font-size:13px}.footer{margin-top:32px}}
@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto!important;transition:none!important}}`;

function nav(prefix, selected) {
  return `<nav class="history-nav" aria-label="Report archive"><a href="${esc(prefix)}"${selected ? '' : ' aria-current="page"'}>Latest session</a><a href="${esc(prefix)}history"${selected ? ' aria-current="page"' : ''}>History</a></nav>`;
}

export function withHistoryNavigation(html, {prefix = '/maimai/', capture = null} = {}) {
  const context = capture ? `<aside class="history-context" aria-label="Selected historical capture"><p><strong>Archived session · ${esc(date(capture.start_ms ?? capture.sort_ms, capture.timezone))}</strong> · ${number(capture.score_count)} plays</p>${!capture.b50_key ? '<p>B50 image was not retained for this capture.</p>' : ''}</aside>` : '';
  html = html.replace('</head>', `<style>${NAV_CSS}</style></head>`).replace(/(<body\b[^>]*>)/i, `$1${nav(prefix, Boolean(capture))}${context}`);
  if (capture) {
    if (html.includes('<script id="download-data"')) {
      const download = {href: capture.b50_key ? `${prefix}history/c/${capture.id}/b50.webp` : null, unavailable: !capture.b50_key, unavailableLabel: "B50 not retained", filename: `maimai-b50-${capture.id.slice(0,12)}.webp`};
      html = html.replace(/(<script id="download-data"[^>]*>)[\s\S]*?(<\/script>)/, (_, start, end) => start + JSON.stringify(download).replaceAll('<', '\\u003c') + end);
      return html;
    }
    const control = capture.b50_key
      ? `<a id="download-b50" class="action-button" href="${prefix}history/c/${capture.id}/b50.webp" download="maimai-b50-${capture.id.slice(0, 12)}.webp">Download B50</a>`
      : '<span id="historical-b50-unavailable" class="action-button history-unavailable" aria-disabled="true">B50 not retained</span>';
    html = html.replace(/<a id="download-b50"[^>]*>Download B50<\/a>|<button id="print-report" class="action-button">Print \/ Save PDF<\/button>/, control);
  }
  return html;
}

function trend(rows) {
  const points = rows.slice().reverse().filter(r => Number.isSafeInteger(r.after_rating));
  if (!points.length) return '<p class="trend-caption">A trend will appear when a capture has a retained rating.</p>';
  const values = points.map(r => r.after_rating);
  const min = Math.min(...values), max = Math.max(...values), span = Math.max(max - min, 100);
  const x = i => points.length === 1 ? 330 : 60 + (i * 555 / (points.length - 1));
  const y = v => 160 - (v - min) * 110 / span;
  let lines = '', dots = '';
  points.forEach((p, i) => {
    if (i && p.versions === points[i-1].versions) lines += `<path d="M${x(i-1)},${y(values[i-1])}L${x(i)},${y(values[i])}"/>`;
    dots += `<circle cx="${x(i)}" cy="${y(values[i])}" r="4"><title>${esc(date(p.sort_ms,p.timezone))}: ${number(p.after_rating)}</title></circle>`;
  });
  return `<div class="trend-plot"><div class="trend-axis" aria-hidden="true"><span>${number(min+span)}</span><span>${number(min)}</span></div><svg class="trend" role="img" aria-labelledby="trend-title trend-desc" viewBox="50 0 600 185" preserveAspectRatio="none"><title id="trend-title">Reconstructed rating after each shown capture</title><desc id="trend-desc">${points.map(p => `${esc(date(p.sort_ms,p.timezone))}: ${number(p.after_rating)}`).join('; ')}. Points are spaced by capture; game version changes break the line.</desc><g stroke="#d4e6e9"><path d="M60 50H630M60 160H630"/></g><g fill="none" stroke="#007887" stroke-width="3" stroke-linecap="round">${lines}</g><g fill="#007887" stroke="white" stroke-width="2">${dots}</g></svg></div><div class="trend-dates" aria-hidden="true"><span>${esc(date(points[0].sort_ms,points[0].timezone,{year:undefined}))}</span><span>${points.length>1?esc(date(points.at(-1).sort_ms,points.at(-1).timezone,{year:undefined})):""}</span></div>`;
}

export function historyPage({rows, total, cursor = '', hasMore = false, prefix = '/maimai/', support = {}}) {
  const body = rows.length ? `<section class="history-summary" aria-label="History summary"><div><h2>Rating over time</h2><p class="trend-caption">After each shown capture · Reconstructed Old 35 + New 15</p>${trend(rows)}</div><div class="coverage"><div><span class="stat-label">Retained sessions</span><p class="history-stat">${number(total)}</p></div><p>Open a date for its full scorecard, plays, rating pools and targets.</p></div></section><div class="list-heading"><h2>Session archive</h2><p>Newest first · ${rows.length} shown</p></div><ol class="capture-list">${rows.map((r,i) => {
    const delta = change(r.before_rating,r.after_rating);
    const versionChange = rows[i+1] && r.versions !== rows[i+1].versions;
    const missing = JSON.parse(r.missing || '[]');
    return `<li><a class="capture" href="${esc(prefix)}history/c/${r.id}/"><div class="identity"><h3>${esc(date(r.start_ms ?? r.sort_ms,r.timezone))}</h3><small>${number(r.score_count)} plays · ${number(r.pb_count)} PB changes</small>${versionChange ? '<span class="capture-note">Game version changed</span>' : ''}${missing.length ? '<span class="capture-note">Some original inputs unavailable</span>' : ''}</div><div class="rating"><small>Rating ${number(r.before_rating)} →</small><strong>${number(r.after_rating)}</strong><span class="gain${delta < 0 ? ' negative' : ''}">${signed(delta)}</span></div><div class="pools"><div><span class="old-label">Old 35</span><span class="pool-value">${number(r.after_old)}</span><small>${signed(change(r.before_old,r.after_old))} this capture</small></div><div><span class="new-label">New 15</span><span class="pool-value">${number(r.after_new)}</span><small>${signed(change(r.before_new,r.after_new))} this capture</small></div></div><span class="arrow" aria-hidden="true">›</span></a></li>`;
  }).join('')}</ol><nav class="pagination" aria-label="History pages">${cursor ? `<a href="${esc(prefix)}history">Newest sessions</a>` : '<span></span>'}${hasMore ? `<a rel="next" href="${esc(prefix)}history?before=${rows.at(-1).sort_ms}.${rows.at(-1).id}">Older sessions →</a>` : ''}</nav><p class="archive-note">Earlier sessions may be missing, and one capture can span several visits. Changes in game version break the rating trend.</p>` : '<section class="empty"><h2>No archived sessions yet</h2><p>Completed captures will appear here after they have been saved and verified. Your latest report remains available.</p><a href="'+esc(prefix)+'">Open latest session</a></section>';
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow,noarchive"><title>Session history · maimai DX</title><style>${CSS}</style>${support.css ? `<style>${support.css}</style>` : ''}</head><body class="clean-checkpoint">${nav(prefix,true)}<main><header><span class="brand">maimai <b>DX</b></span><h1>Session history</h1><p>Choose a date to reopen its complete session report.</p></header>${body}<footer class="footer">Independent maimai companion · Private session archive</footer></main>${support.html || ''}</body></html>`;
}

const COLUMNS = `c.*,b.reconstructed before_rating,a.reconstructed after_rating,b.old_rating before_old,a.old_rating after_old,b.new_rating before_new,a.new_rating after_new`;
const JOINS = `FROM captures c JOIN rating_snapshots b ON b.capture_id=c.id AND b.phase='before' JOIN rating_snapshots a ON a.capture_id=c.id AND a.phase='after'`;

async function verifiedObject(env, key, hash) {
  if (!ID.test(hash || '') || key !== `objects/sha256/${hash}`) throw Error('Invalid archive reference');
  const object = await env.HISTORY_OBJECTS.get(key);
  if (!object || object.size > MAX_BYTES) throw Error('Archived object unavailable');
  const raw = await object.arrayBuffer();
  const digest = [...new Uint8Array(await crypto.subtle.digest('SHA-256',raw))].map(b=>b.toString(16).padStart(2,'0')).join('');
  if (digest !== hash) throw Error('Archived object verification failed');
  return raw;
}

export async function handleHistory(request, env, makeHeaders, support = {}) {
  const prefix = env.HISTORY_PREFIX || '/maimai/';
  const url = new URL(request.url);
  if (!url.pathname.startsWith(`${prefix}history`)) return null;
  const respond = (body,status=200,type='text/html; charset=utf-8',extra={}) => new Response(request.method === 'HEAD' ? null : body,{status,headers:makeHeaders({'Content-Type':type,...extra})});
  if (!/^\/[a-zA-Z0-9_-]+\/$/.test(prefix) || url.origin !== env.HISTORY_ORIGIN) return respond('Not found',404,'text/plain');
  if (!['GET','HEAD'].includes(request.method)) return respond('Method not allowed',405,'text/plain',{Allow:'GET, HEAD'});
  if (!env.HISTORY_DB || !env.HISTORY_OBJECTS || !env.HISTORY_SCOPE) return respond('History storage is not configured. Your latest report remains available.',503,'text/plain');
  try {
    if ([`${prefix}history`,`${prefix}history/`].includes(url.pathname)) {
      const cursor = url.searchParams.get('before') || '';
      if (cursor && !/^\d{1,16}\.[a-f0-9]{64}$/.test(cursor)) return respond('Invalid history cursor',400,'text/plain');
      const [time,id] = cursor.split('.');
      if (cursor && !Number.isSafeInteger(Number(time))) return respond('Invalid history cursor',400,'text/plain');
      const condition = cursor ? ' AND (c.sort_ms,c.id)<(?,?)' : '';
      const values = cursor ? [env.HISTORY_SCOPE,Number(time),id,PAGE_SIZE+1] : [env.HISTORY_SCOPE,PAGE_SIZE+1];
      const [{results}, count] = await Promise.all([
        env.HISTORY_DB.prepare(`SELECT ${COLUMNS} ${JOINS} WHERE c.scope=? AND c.state='ready' AND c.meaningful=1${condition} ORDER BY c.sort_ms DESC,c.id DESC LIMIT ?`).bind(...values).all(),
        env.HISTORY_DB.prepare("SELECT COUNT(*) total FROM captures WHERE scope=? AND state='ready' AND meaningful=1").bind(env.HISTORY_SCOPE).first(),
      ]);
      return respond(historyPage({rows:results.slice(0,PAGE_SIZE),total:count.total,cursor,hasMore:results.length>PAGE_SIZE,prefix,support}));
    }
    const relative = url.pathname.slice(`${prefix}history/c/`.length);
    const match = /^([a-f0-9]{64})\/(b50\.webp)?$/.exec(relative);
    if (!url.pathname.startsWith(`${prefix}history/c/`) || !match) return respond('Not found',404,'text/plain');
    const capture = await env.HISTORY_DB.prepare("SELECT * FROM captures WHERE scope=? AND id=? AND state='ready' AND meaningful=1").bind(env.HISTORY_SCOPE,match[1]).first();
    if (!capture) return respond('Capture not found',404,'text/plain');
    if (match[2]) {
      if (!capture.b50_key) return respond('B50 image was not retained for this capture.',404,'text/plain');
      return respond(await verifiedObject(env,capture.b50_key,capture.b50_hash),200,'image/webp',{'Content-Disposition':`attachment; filename="maimai-b50-${capture.id.slice(0,12)}.webp"`});
    }
    const html = new TextDecoder().decode(await verifiedObject(env,capture.report_key,capture.report_hash));
    return respond(withHistoryNavigation(html,{prefix,capture}));
  } catch {
    // Do not log score data or provider error bodies. The static latest report is independent.
    return respond('History is temporarily unavailable. Your latest report remains available.',503,'text/plain');
  }
}
