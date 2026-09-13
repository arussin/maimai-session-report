import test from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {readFile} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {Miniflare,convertV4MiniflareOptions} from 'miniflare';
import {privateHeadersFor} from '../src/security.js';

test('personal handoff changes only the intended browser isolation and connection policy',()=>{
  const report=flags=>'<script id="report-data" type="application/json">'+JSON.stringify({support:false,partyIntegration:flags})+'</script>';
  for(const enabled of [false,true]) {
    const h=privateHeadersFor(report({enabled,hosted:enabled}));
    assert.equal(h.get('Cross-Origin-Opener-Policy'),enabled?'same-origin-allow-popups':'same-origin');
    assert.match(h.get('Content-Security-Policy'),enabled?/connect-src 'self'/:/connect-src 'none'/);
    assert.equal(h.get('Cross-Origin-Resource-Policy'),'same-origin');
    assert.equal(h.get('Referrer-Policy'),'no-referrer');
    assert.match(h.get('Cache-Control'),/no-store/);
  }
});

test('protected player revisions stream immutable objects from real D1 and R2',async t=>{
  const root=fileURLToPath(new URL('../src/',import.meta.url));
  const source=await readFile(path.join(root,'player-data.js'),'utf8');
  const wrapper=`${source}\nexport default {fetch(request,env){return handlePlayerData(request,env,x=>({'Cache-Control':'private, no-store','Cross-Origin-Resource-Policy':'same-origin',...x}));}};`;
  const mf=new Miniflare(convertV4MiniflareOptions({cf:false,modules:true,script:wrapper,compatibilityDate:'2026-08-31',d1Databases:{HISTORY_DB:'player-test'},r2Buckets:['HISTORY_OBJECTS'],bindings:{HISTORY_PREFIX:'/private/',HISTORY_ORIGIN:'https://fixture.invalid',HISTORY_SCOPE:'synthetic:player'}}));
  t.after(()=>mf.dispose());
  const db=await mf.getD1Database('HISTORY_DB'),bucket=await mf.getR2Bucket('HISTORY_OBJECTS');
  await db.exec('CREATE TABLE player_state(scope TEXT PRIMARY KEY,revision TEXT); CREATE TABLE player_revisions(scope TEXT,revision TEXT,metadata TEXT);');
  const get=p=>mf.dispatchFetch('https://fixture.invalid/private/party/'+p);
  assert.equal((await get('latest.json')).status,404);
  const raw=Buffer.from('synthetic opaque gzip bytes'),hash=createHash('sha256').update(raw).digest('hex'),revision='a'.repeat(64);
  const meta={scope:'synthetic:player',revision,sha256:hash,key:'objects/sha256/'+hash,bytes:raw.length,offer:{revision,capturedAt:1234,player:{key:'synthetic'}}};
  await bucket.put(meta.key,raw,{customMetadata:{sha256:hash}});
  await db.prepare('INSERT INTO player_revisions VALUES(?,?,?)').bind(meta.scope,revision,JSON.stringify(meta)).run();
  await db.prepare('INSERT INTO player_state VALUES(?,?)').bind(meta.scope,revision).run();
  const latest=await get('latest.json');assert.equal(latest.status,200);const offered=await latest.json();assert.equal(offered.capturedAt,1234);
  const response=await get('data/'+hash+'.gz');assert.equal(response.status,200);assert.deepEqual(Buffer.from(await response.arrayBuffer()),raw);assert.match(response.headers.get('Content-Disposition'),/player.maimai.json.gz/);
  assert.equal((await mf.dispatchFetch('https://other.invalid/private/party/latest.json')).status,404);
  assert.equal((await get('data/'+'b'.repeat(64)+'.gz')).status,404);
  await bucket.delete(meta.key);assert.equal((await get('data/'+hash+'.gz')).status,503);
  assert.equal((await (await get('latest.json')).json()).capturedAt,1234);
});
