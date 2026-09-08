import http from 'node:http';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {installationFixture} from '../../deploy/cloudflare/test/installation-fixture.mjs';

const root=path.join(fileURLToPath(new URL('.',import.meta.url)),'generated/installations');
const instances=new Map();
for(const owner of ['alpha','beta']) instances.set(owner,await installationFixture(path.join(root,owner,'staged')));
const server=http.createServer(async(req,res)=>{
  const owner=new URL(req.url,'http://127.0.0.1:4182').pathname.split('/')[1];
  const value=instances.get(owner);
  if(!value){res.writeHead(404);res.end('Unknown synthetic installation');return;}
  try{
    const response=await value.mf.dispatchFetch(new URL(req.url,value.config.vars.HISTORY_ORIGIN).href,{method:req.method});
    res.writeHead(response.status,Object.fromEntries(response.headers));res.end(Buffer.from(await response.arrayBuffer()));
  }catch{res.writeHead(500);res.end('Synthetic installation failed');}
});
server.listen(4182,'127.0.0.1');
for(const signal of ['SIGTERM','SIGINT'])process.on(signal,async()=>{server.close();await Promise.all([...instances.values()].map(v=>v.mf.dispose()));process.exit(0)});
