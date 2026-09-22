/** Open generated fictional reports with both payment and Party traffic intercepted. */
import fs from 'node:fs/promises';
import path from 'node:path';
import http from 'node:http';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {chromium} from '@playwright/test';
import {launchIsolated} from './isolation.mjs';
import {enableSupportFixture} from './support-dialog.js';
import {enablePartyFixture} from './party-fixture.js';

const root=path.join(path.dirname(fileURLToPath(import.meta.url)), 'generated');
const manifest=JSON.parse(await fs.readFile(path.join(root,'preview-manifest.json'),'utf8'));
if(manifest.schema!=='maimai-synthetic-preview-1')throw new Error('Generate the synthetic fixtures first');
const files=new Map();
for(const [name,expected] of Object.entries(manifest.files)){
  if(name!==path.basename(name))throw new Error('Only fixture basenames are allowed');
  const bytes=await fs.readFile(path.join(root,name));
  if(crypto.createHash('sha256').update(bytes).digest('hex')!==expected)throw new Error('Synthetic fixture bytes changed: '+name);
  files.set('/'+name,bytes);
}
const server=http.createServer((request,response)=>{
  const name=new URL(request.url,'http://fixture.invalid').pathname;
  const bytes=files.get(name==='/'?'/complete.html':name);
  if(!bytes){response.writeHead(404).end();return;}
  response.writeHead(200,{'Content-Type':name.endsWith('.webp')?'image/webp':'text/html;charset=utf-8','Cache-Control':'no-store','Referrer-Policy':'no-referrer'}).end(bytes);
});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
const origin=`http://127.0.0.1:${server.address().port}`;
const run=await launchIsolated(chromium,{origins:[origin],launch:{headless:false}});
await enableSupportFixture(run.context);await enablePartyFixture(run.context,origin);
const page=await run.context.newPage();await page.goto(origin+'/complete.html');
console.log('Synthetic preview ready. Payment and player-import destinations are local fixtures. Close the browser to finish.');
await new Promise(resolve=>run.browser.on('disconnected',resolve));
await run.close();server.closeAllConnections();await new Promise(resolve=>server.close(resolve));
if(run.unexpected.length)throw new Error('Blocked unexpected preview requests: '+JSON.stringify(run.unexpected));
