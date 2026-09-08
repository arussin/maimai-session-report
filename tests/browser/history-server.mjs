import http from 'node:http';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {fixture} from '../../deploy/cloudflare/test/history-fixture.mjs';
const origin='http://127.0.0.1:4181';
const directory=path.join(fileURLToPath(new URL('.',import.meta.url)),'generated/history');
const {mf}=await fixture(directory,origin);
const server=http.createServer(async(req,res)=>{
  try {
    const response=await mf.dispatchFetch(new URL(req.url,origin).href,{method:req.method,headers:req.headers});
    res.writeHead(response.status,Object.fromEntries(response.headers));
    res.end(Buffer.from(await response.arrayBuffer()));
  } catch {res.writeHead(500);res.end('Synthetic fixture server failed');}
});
server.listen(4181,'127.0.0.1',()=>process.stdout.write('Synthetic D1/R2 history fixture ready\n'));
for(const signal of ['SIGTERM','SIGINT'])process.on(signal,async()=>{server.close();await mf.dispose();process.exit(0)});
