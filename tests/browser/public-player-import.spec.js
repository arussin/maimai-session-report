import {test,expect} from './fixtures.js';
import {publicImportFixture} from '../../deploy/cloudflare/test/public-import-fixture.mjs';

// Only this test uses Miniflare's local certificate and local-network grant.
// Actual HTTP responses reach the browser: route.fulfill bypasses CORS checks.
test.use({ignoreHTTPSErrors:true});
test('public exports are readable by Party only after owner opt-in',async({page,context,browserName,fixtureOrigins})=>{
  if(browserName==='chromium')await context.grantPermissions(['local-network-access']);
  await context.route('https://maimai.party/**',route=>route.fulfill({contentType:'text/html',body:'<!doctype html><title>Synthetic Party import</title>'}));
  await context.route('https://other.example.test/**',route=>route.fulfill({contentType:'text/html',body:'<!doctype html><title>Unrelated origin</title>'}));
  const read=origin=>page.evaluate(async origin=>{
    try {
      const manifest=await fetch(origin+'/maimai/party/latest.json',{credentials:'omit',referrerPolicy:'no-referrer'}).then(r=>r.json());
      const response=await fetch(origin+manifest.object.path,{credentials:'omit',referrerPolicy:'no-referrer'});
      const bytes=await response.arrayBuffer();
      const sha=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),x=>x.toString(16).padStart(2,'0')).join('');
      return {ok:true,integrity:sha===manifest.object.sha256&&bytes.byteLength===manifest.object.bytes};
    } catch {return {ok:false};}
  },origin);
  const sent=[];
  page.on('request',r=>{if(new URL(r.url()).hostname==='127.0.0.1')sent.push(r)});
  for(const enabled of [false,true]) {
    const {mf,origin}=await publicImportFixture(enabled);
    const releaseOrigin=fixtureOrigins.allow(origin);
    try {
      await page.goto('https://maimai.party/');
      expect(await read(origin)).toEqual(enabled?{ok:true,integrity:true}:{ok:false});
      await page.goto('https://other.example.test/');
      expect(await read(origin)).toEqual({ok:false});
    } finally {releaseOrigin();await mf.dispose();}
  }
  expect(sent.length).toBeGreaterThanOrEqual(5);
  for(const request of sent) {
    const headers=await request.allHeaders();
    expect(headers.cookie||headers.authorization||headers.referer).toBeUndefined();
  }
});
