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

for(const publicImports of [false,true])test(`player revisions stream exact immutable bytes; public imports ${publicImports}`,async t=>{
  const root=fileURLToPath(new URL('../src/',import.meta.url));
  const source=await readFile(path.join(root,'player-data.js'),'utf8');
  const wrapper=`${source}\nexport default {fetch(request,env){return handlePlayerData(request,env,x=>({'Cache-Control':'private, no-store','Cross-Origin-Resource-Policy':'same-origin',...x}),${publicImports});}};`;
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
  for(const origin of ['https://maimai.party','https://maimai.party.evil.invalid','https://preview.maimai.party','http://localhost:8897','null']) {
    for(const method of ['GET','HEAD']) {
      for(const endpoint of ['latest.json','data/'+hash+'.gz']) {
        const r=await mf.dispatchFetch('https://fixture.invalid/private/party/'+endpoint,{method,headers:{Origin:origin}});
        assert.equal(r.status,200);
        assert.equal(r.headers.get('Access-Control-Allow-Origin'),publicImports&&origin==='https://maimai.party'?origin:null);
        assert.equal(r.headers.get('Access-Control-Allow-Credentials'),null);
        assert.match(r.headers.get('Cache-Control'),/no-store/);
        assert.equal(r.headers.get('Vary'),publicImports?'Origin':null);
        if(method==='HEAD')assert.equal(await r.text(),'');
      }
    }
  }
  for(const endpoint of ['unknown.json','data/not-a-sha.gz']) {
    const r=await mf.dispatchFetch('https://fixture.invalid/private/party/'+endpoint,{headers:{Origin:'https://maimai.party'}});
    assert.equal(r.status,404);assert.equal(r.headers.get('Access-Control-Allow-Origin'),null);
  }
  for(const method of ['POST','OPTIONS']) {
    const r=await mf.dispatchFetch('https://fixture.invalid/private/party/latest.json',{method,headers:{Origin:'https://maimai.party'}});
    assert.equal(r.status,405);assert.equal(r.headers.get('Access-Control-Allow-Origin'),null);
  }
  assert.equal((await mf.dispatchFetch('https://other.invalid/private/party/latest.json')).status,404);
  assert.equal((await get('data/'+'b'.repeat(64)+'.gz')).status,404);
  await bucket.delete(meta.key);assert.equal((await get('data/'+hash+'.gz')).status,503);
  const failed=await mf.dispatchFetch('https://fixture.invalid/private/party/data/'+hash+'.gz',{headers:{Origin:'https://maimai.party'}});
  assert.equal(failed.status,503);assert.equal(failed.headers.get('Access-Control-Allow-Origin'),publicImports?'https://maimai.party':null);
  assert.equal((await (await get('latest.json')).json()).capturedAt,1234);
});
