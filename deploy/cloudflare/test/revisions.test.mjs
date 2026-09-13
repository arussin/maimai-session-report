import test from 'node:test';
import assert from 'node:assert/strict';
import {createHash, webcrypto} from 'node:crypto';
import {handleHistory} from '../src/history.js';
if (!globalThis.crypto) globalThis.crypto = webcrypto;
const hash = raw => createHash('sha256').update(raw).digest('hex');
const json = value => Buffer.from(JSON.stringify(value));
const html = (label, data={session:{scores:[{chartID:'fictional',rate:200}]},before:{rating:100},after:{rating:105}}) => `<html><head></head><body><h1>${label}</h1><script id="report-data" type="application/json">${JSON.stringify(data)}</script><script id="download-data" type="application/json">{}</script></body></html>`;
function fixture(change = () => {}) {
  const id='a'.repeat(64),scope='synthetic:maimaidx',renderer='c'.repeat(40);
  const objects=new Map(),reads=[];
  const add=raw=>{raw=Buffer.from(raw);const sha256=hash(raw),key=`objects/sha256/${sha256}`;objects.set(key,raw);return {key,sha256,bytes:raw.length};};
  const report=add(html('Original fictional report')),b50=add('fictional-image-bytes');
  const original={schemaVersion:1,captureID:id,scope,inputHash:'b'.repeat(64),meaningful:true,scoreCount:1,rendererCommit:'d'.repeat(40),files:{'original.html':report,'selected-b50.webp':b50},report,b50};
  const originalRaw=json(original);objects.set(`captures/${id}/published.json`,originalRaw);
  const revised=add(html('Corrected fictional report'));
  const revision={...structuredClone(original),rendererCommit:renderer,report:revised,presentationRevision:{schemaVersion:1,reason:'corrected-session-rating-contributions',originalPublishedManifestSha256:hash(originalRaw),originalReportSha256:report.sha256}};
  revision.files[`renders/${renderer}/report.html`]=revised;
  change(revision,objects,add);
  const revisionRaw=json(revision),digest=hash(revisionRaw),manifestKey=`captures/${id}/sources/${digest}.json`;
  objects.set(manifestKey,revisionRaw);
  const capture={id,scope,report_key:report.key,report_hash:report.sha256,b50_key:b50.key,b50_hash:b50.sha256,sort_ms:1780000000000,timezone:'UTC',score_count:1};
  const env={HISTORY_PREFIX:'/maimai/',HISTORY_ORIGIN:'https://synthetic.test',HISTORY_SCOPE:scope,HISTORY_OBJECTS:{get:async key=>{reads.push(key);const raw=objects.get(key);return raw?{size:raw.length,arrayBuffer:async()=>Uint8Array.from(raw).buffer}:null;}},HISTORY_DB:{prepare(sql){assert.match(sql,/^SELECT /);return {bind(owner,cid){assert.equal(owner,scope);return {first:async()=>cid===id?capture:null};}};}}};
  const revisions={[id]:digest};
  const request=(suffix='',method='GET',selected=revisions)=>handleHistory(new Request(`https://synthetic.test/maimai/history/c/${id}/${suffix}`,{method}),env,extra=>({'Cache-Control':'private, no-store, max-age=0',...extra}),{},selected);
  return {request,objects,reads,capture,manifestKey,revision,revisions};
}
test('default selects approved corrected bytes and offers original; GETs only',async()=>{const f=fixture(),r=await f.request();assert.equal(r.status,200);const text=await r.text();assert.match(text,/Corrected fictional report/);assert.match(text,/Original report<\/a>/);assert.match(text,/Original scores preserved/);assert.equal(r.headers.get('cache-control'),'private, no-store, max-age=0');});
test('original is independent of missing selected revision',async()=>{const f=fixture();f.objects.delete(f.manifestKey);const r=await f.request('?view=original');assert.match(await r.text(),/Original fictional report/);assert.ok(!f.reads.includes(f.manifestKey));});
test('missing revision falls back with explicit warning',async()=>{const f=fixture();f.objects.delete(f.manifestKey);const r=await f.request();assert.equal(r.status,200);const text=await r.text();assert.match(text,/Original fictional report/);assert.match(text,/Corrected version unavailable/);});
test('damaged corrected HTML cannot be served',async()=>{const f=fixture();f.objects.set(f.revision.report.key,Buffer.from('damaged'));assert.match(await (await f.request()).text(),/Corrected version unavailable/);});
test('damaged source manifest cannot be served',async()=>{const f=fixture();f.objects.set(f.manifestKey,Buffer.from('{}'));assert.match(await (await f.request()).text(),/Corrected version unavailable/);});
for (const [name,change] of [
 ['foreign scope',r=>{r.scope='foreign';}],['foreign capture',r=>{r.captureID='f'.repeat(64);}],
 ['different original manifest',r=>{r.presentationRevision.originalPublishedManifestSha256='e'.repeat(64);}],
 ['different original report',r=>{r.presentationRevision.originalReportSha256='e'.repeat(64);}],
 ['changed B50',r=>{r.b50=null;}],['changed score count',r=>{r.scoreCount=3;}],
 ['changed original reference',r=>{r.files['original.html'].bytes++;}],
 ['changed retained data',(r,objects,add)=>{const entry=add(html('Unapproved modified data',{session:{scores:[]}}));r.report=entry;r.files[`renders/${r.rendererCommit}/report.html`]=entry;}],
 ['extra reference',r=>{r.files.extra=r.report;}],['invalid renderer',r=>{r.rendererCommit='../../';}],
 ['wrong revised length',r=>{r.report.bytes++;}],
]) test(`${name} refuses corrected selection`,async()=>{const f=fixture(change);assert.match(await (await f.request()).text(),/Corrected version unavailable/);});
test('original corruption fails closed instead of hiding behind correction',async()=>{const f=fixture();f.objects.set(f.capture.report_key,Buffer.from('bad original'));assert.equal((await f.request()).status,503);});
test('B50 uses original independently verified bytes',async()=>{const f=fixture();assert.equal(await (await f.request('b50.webp')).text(),'fictional-image-bytes');assert.ok(!f.reads.includes(f.manifestKey));});
test('invalid or duplicate view and write methods are refused',async()=>{const f=fixture();assert.equal((await f.request('?view=other')).status,400);assert.equal((await f.request('?view=original&view=corrected')).status,400);assert.equal((await f.request('','POST')).status,405);});
test('HEAD returns headers and no body',async()=>{const f=fixture(),r=await f.request('','HEAD');assert.equal(r.status,200);assert.equal(await r.text(),'');});
test('selection leaves the entire object set byte-identical',async()=>{const f=fixture(),before=[...f.objects].map(([k,v])=>[k,hash(v)]);await f.request();await f.request('?view=original');assert.deepEqual([...f.objects].map(([k,v])=>[k,hash(v)]),before);});
