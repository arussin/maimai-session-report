import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {execFileSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {fixture} from './history-fixture.mjs';

test('hosted reader uses real D1/R2 bindings and immutable Python publications', async t => {
  const directory=await mkdtemp(path.join(tmpdir(),'maimai-synthetic-history-'));
  t.after(()=>rm(directory,{recursive:true,force:true}));
  const root=fileURLToPath(new URL('../../../',import.meta.url));
  execFileSync('python',['-m','tests.history_fixture',directory],{cwd:root,env:{...process.env,PYTHONPATH:`${root}/src:${root}`}});
  const {mf,db,bucket}=await fixture(directory);
  t.after(()=>mf.dispose());
  const get=path=>mf.dispatchFetch(`https://synthetic.test${path}`);
  await t.test('default page is bounded and excludes the empty refresh',async()=>{
    const response=await get('/maimai/history');
    assert.equal(response.status,200);
    const html=await response.text();
    assert.equal((html.match(/class="capture"/g)||[]).length,20);
    assert.match(html,/22<\/p>/);
    assert.match(html,/rel="next"/);
    assert.equal(response.headers.get('cache-control'),'private, no-store, max-age=0');
    assert.match(response.headers.get('content-security-policy'),/connect-src 'none'/);
    const cursor=/before=([0-9a-f.]+)/.exec(html)[1];
    const older=await (await get('/maimai/history?before='+cursor)).text();
    assert.equal((older.match(/class="capture"/g)||[]).length,2);
    assert.doesNotMatch(older,/rel="next"/);
  });
  await t.test('all four selected report views share one retained capture',async()=>{
    const row=await db.prepare("SELECT * FROM captures WHERE meaningful=1 AND b50_key IS NOT NULL ORDER BY sort_ms DESC LIMIT 1").first();
    const response=await get(`/maimai/history/c/${row.id}/`);
    assert.equal(response.status,200);
    const html=await response.text();
    assert.match(html,/Synthetic History Player/);
    assert.ok(html.includes(`/maimai/history/c/${row.id}/b50.webp`));
    assert.doesNotMatch(html,/<script[^>]+src\s*=/i);
    const b50=await get(`/maimai/history/c/${row.id}/b50.webp`);
    assert.equal(b50.status,200);
    assert.equal(b50.headers.get('content-type'),'image/webp');
    assert.deepEqual(new Uint8Array(await b50.arrayBuffer()),new Uint8Array(await (await bucket.get(row.b50_key)).arrayBuffer()));
    const head=await mf.dispatchFetch(`https://synthetic.test/maimai/history/c/${row.id}/`,{method:'HEAD'});
    assert.equal(head.status,200);assert.equal(await head.text(),'');
  });
  await t.test('missing historical B50 never points at the latest B50',async()=>{
    const row=await db.prepare("SELECT * FROM captures WHERE meaningful=1 AND b50_key IS NULL LIMIT 1").first();
    const html=await (await get(`/maimai/history/c/${row.id}/`)).text();
    assert.match(html,/B50 not retained/);
    assert.equal((await get(`/maimai/history/c/${row.id}/b50.webp`)).status,404);
  });
  await t.test('bad cursors, raw object paths, origins and methods fail closed',async()=>{
    assert.equal((await get('/maimai/history?before=bad')).status,400);
    assert.equal((await get('/maimai/history/objects/private.json')).status,404);
    assert.equal((await mf.dispatchFetch('https://preview.invalid/maimai/history')).status,404);
    assert.equal((await mf.dispatchFetch('https://synthetic.test/maimai/history',{method:'POST'})).status,405);
    assert.equal((await get('/maimai/history/c/'+'0'.repeat(64)+'/')).status,404);
  });
  await t.test('missing or corrupt archived bytes fail while the static latest stays available',async()=>{
    const row=await db.prepare("SELECT * FROM captures WHERE meaningful=1 LIMIT 1").first();
    await bucket.put(row.report_key,'corrupt test bytes');
    assert.equal((await get(`/maimai/history/c/${row.id}/`)).status,503);
    assert.equal((await get('/maimai/')).status,200);
  });
  await t.test('D1 finalization triggers preserve the meaningful latest pointer',async()=>{
    const pointer=await db.prepare('SELECT latest_id FROM archive_state').first();
    const newest=await db.prepare("SELECT id FROM captures WHERE meaningful=1 ORDER BY sort_ms DESC,id DESC LIMIT 1").first();
    assert.equal(pointer.latest_id,newest.id);
    await assert.rejects(db.prepare('UPDATE captures SET sort_ms=0 WHERE id=?').bind(newest.id).run());
  });
});
