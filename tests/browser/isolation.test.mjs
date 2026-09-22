import test from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import {chromium, firefox, webkit} from '@playwright/test';
import {launchIsolated, startIsolationProxy} from './isolation.mjs';

for (const [name, engine] of Object.entries({chromium, firefox, webkit})) {
  test(`${name}: popup, iframe, beacon, redirect and route escape cannot leave fixture origins`, async () => {
    let forbiddenHits = 0;
    const forbidden = http.createServer((_req, res) => { forbiddenHits++; res.end('must never arrive'); });
    await new Promise(resolve => forbidden.listen(0, '127.0.0.1', resolve));
    const server = http.createServer((req, res) => {
      if (req.url === '/redirect') {res.writeHead(302, {Location:'https://redirect.example.invalid/'}).end(); return;}
      res.setHeader('Content-Type', 'text/html');
      res.end('<!doctype html><title>Synthetic isolation fixture</title><button>Fixture</button>');
    });
    await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
    const origin = `http://127.0.0.1:${server.address().port}`;
    const blockedOrigin = `http://127.0.0.1:${forbidden.address().port}`;
    const run = await launchIsolated(engine, {origins:[origin]});
    try {
      const page = await run.context.newPage();
      await page.goto(origin);
      assert.equal(await page.title(), 'Synthetic isolation fixture');
      await page.route('**/remapped', async route => {
        const response = await route.fetch({url:origin});
        await route.fulfill({response});
      });
      await page.goto(origin+'/remapped');
      assert.equal(await page.title(), 'Synthetic isolation fixture', 'Allowed APIRequestContext CONNECT works');
      run.synthetic('https://synthetic.example.invalid');
      await run.context.route('https://synthetic.example.invalid/', route => route.fulfill({contentType:'text/html',body:'<title>Explicit synthetic origin</title>'}));
      const synthetic = await run.context.newPage();
      await synthetic.goto('https://synthetic.example.invalid/');
      assert.equal(await synthetic.title(), 'Explicit synthetic origin');
      await synthetic.route('**/fetch-escape', async route => {
        await assert.rejects(route.fetch(), /denied non-loopback/);
        await route.fulfill({body:'caught by the fixture'});
      });
      await synthetic.goto('https://synthetic.example.invalid/fetch-escape');
      assert.ok(run.unexpected.some(item=>item.kind==='route-fetch'), 'Caught fetch escapes remain fatal in the ledger');
      await synthetic.route('**/synthetic-escape', route => route.continue());
      await synthetic.goto('https://synthetic.example.invalid/synthetic-escape').catch(() => {});
      assert.ok(run.unexpected.some(item=>item.kind==='route-continue'), 'Declared origins cannot hide a route escape');
      await synthetic.close();
      await page.evaluate(() => {
        window.open('https://popup.example.invalid/', '_blank');
        const frame = document.createElement('iframe'); frame.src = 'https://iframe.example.invalid/'; document.body.append(frame);
        navigator.sendBeacon('https://beacon.example.invalid/', 'synthetic-only');
      });
      // Deliberately bypass context routing: the network proxy must still deny both.
      await page.route('**/escape', route => route.continue());
      await page.evaluate(async blocked => {
        await Promise.all([
          fetch('https://escape.example.invalid/escape').catch(() => {}),
          fetch(blocked+'/escape').catch(() => {}),
        ]);
      }, blockedOrigin);
      await page.goto(origin+'/redirect').catch(() => {});
      for (let attempt=0; attempt<40 && run.unexpected.length<6; attempt++) await new Promise(resolve => setTimeout(resolve,25));
      const targets = run.unexpected.map(item => item.target).join(' ');
      for (const label of ['popup.example.invalid','iframe.example.invalid','beacon.example.invalid','redirect.example.invalid','escape.example.invalid']) assert.ok(targets.includes(label), `${name}: missing ${label}: ${targets}`);
      assert.equal(forbiddenHits, 0, 'Even non-allowlisted loopback traffic must be blocked');
      assert.ok(run.unexpected.some(item => item.kind === 'route-continue'), 'Explicit route escapes were audited');
    } finally {
      await run.close(); server.closeAllConnections(); forbidden.closeAllConnections();
      await Promise.all([new Promise(resolve => server.close(resolve)), new Promise(resolve => forbidden.close(resolve))]);
    }
  });
}

test('proxy denies raw HTTP/CONNECT escapes and retains deny-only synthetic transport ownership', async () => {
  let hits=0;
  const forbidden=http.createServer((_request,response)=>{hits++;response.end();});
  await new Promise(resolve=>forbidden.listen(0,'127.0.0.1',resolve));
  const proxy=await startIsolationProxy({origins:[]});
  const endpoint=new URL(proxy.server);
  async function request(method,path){
    return new Promise((resolve,reject)=>{
      const req=http.request({hostname:endpoint.hostname,port:endpoint.port,method,path});
      req.on('response',response=>{response.resume();response.on('end',()=>resolve(response.statusCode));});
      req.on('connect',(response,socket)=>{socket.destroy();resolve(response.statusCode);});
      req.on('error',reject);req.end();
    });
  }
  try {
    assert.equal(await request('GET',`http://127.0.0.1:${forbidden.address().port}/`),403);
    assert.equal(await request('CONNECT',`127.0.0.1:${forbidden.address().port}`),403);
    const release=proxy.declareSynthetic('https://synthetic.example.invalid');release();
    assert.equal(await request('CONNECT','synthetic.example.invalid:443'),403);
    assert.equal(proxy.unexpected.length,2);
    assert.equal(proxy.blockedTransports.length,1);
    assert.equal(hits,0);
  } finally {
    await proxy.close();forbidden.closeAllConnections();await new Promise(resolve=>forbidden.close(resolve));
  }
});
