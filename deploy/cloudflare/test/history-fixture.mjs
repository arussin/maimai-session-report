import {readFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import {Miniflare, convertV4MiniflareOptions} from 'miniflare';

export const headersSource = `const headers = extra => ({'Cache-Control':'private, no-store, max-age=0','Content-Security-Policy':"default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; connect-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'; frame-src https://buymeacoffee.com; frame-ancestors 'none'",'Permissions-Policy':'camera=(), microphone=(), geolocation=(), payment=(self "https://buymeacoffee.com")','Referrer-Policy':'no-referrer','X-Content-Type-Options':'nosniff','X-Frame-Options':'DENY','X-Robots-Tag':'noindex, nofollow, noarchive',...extra});`;

export async function fixture(directory, origin = 'https://synthetic.test') {
  const source = await readFile(fileURLToPath(new URL('../src/history.js',import.meta.url)),'utf8');
  const config = JSON.parse(await readFile(path.join(directory,'fixture.json'),'utf8'));
  if (config.synthetic !== true) throw Error('CI only accepts the explicitly synthetic archive');
  const latest = await readFile(path.join(directory,config.latestHTML),'utf8');
  const worker = source.replaceAll('export ','') + `\n${headersSource}\nexport default {async fetch(request,env){if(new URL(request.url).searchParams.get('fixture')==='empty')env={...env,HISTORY_SCOPE:'synthetic:empty'};const response=await handleHistory(request,env,headers,${JSON.stringify(config.support || {})});if(response)return response; const pathname=new URL(request.url).pathname;if(pathname==='/maimai/'||pathname==='/maimai/index.html')return new Response(withHistoryNavigation(${JSON.stringify(latest)}),{headers:headers({'Content-Type':'text/html;charset=utf-8'})});return new Response('Not found',{status:404,headers:headers({'Content-Type':'text/plain'})})}};`;
  const mf = new Miniflare(convertV4MiniflareOptions({
    cf:false,
    modules:true, script:worker, compatibilityDate:'2026-08-31',
    d1Databases:{HISTORY_DB:'synthetic-history'}, r2Buckets:['HISTORY_OBJECTS'],
    bindings:{HISTORY_SCOPE:'synthetic:maimaidx',HISTORY_ORIGIN:origin,HISTORY_PREFIX:'/maimai/'},
  }));
  try {
    const db = await mf.getD1Database('HISTORY_DB');
    const bucket = await mf.getR2Bucket('HISTORY_OBJECTS');
    for (const sql of config.migrations) await db.prepare(sql).run();
    for (const key of config.objects) await bucket.put(key,await readFile(path.join(directory,key)));
    // Replay the actual Python writer's prepared statements against real D1 bindings.
    for (let i=0;i<config.statements.length;i+=50) await db.batch(config.statements.slice(i,i+50).map(s=>db.prepare(s.sql).bind(...s.params)));
    return {mf,db,bucket};
  } catch(error) {await mf.dispose();throw error;}
}
