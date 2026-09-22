import {readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {Miniflare,convertV4MiniflareOptions} from 'miniflare';

export async function publicImportFixture(enabled) {
  const payload='fictional player payload',hash=createHash('sha256').update(payload).digest('hex'),revision='a'.repeat(64);
  const meta={scope:'fictional:maimaidx',revision,sha256:hash,key:'objects/sha256/'+hash,bytes:payload.length,offer:{revision}};
  const source=await readFile(new URL('../src/player-data.js',import.meta.url),'utf8');
  const script=source+`
    const meta=${JSON.stringify(meta)},payload=${JSON.stringify(payload)};
    export default {fetch(request){
      const env={HISTORY_ORIGIN:new URL(request.url).origin,HISTORY_PREFIX:'/maimai/',HISTORY_SCOPE:meta.scope,
        HISTORY_DB:{prepare(){return {bind(){return {async first(){return {metadata:JSON.stringify(meta)}}}}}}},
        HISTORY_OBJECTS:{async get(){return {size:meta.bytes,customMetadata:{sha256:meta.sha256},body:payload}}}};
      return handlePlayerData(request,env,x=>({'Cache-Control':'private, no-store','Cross-Origin-Resource-Policy':'same-origin',...x}),${enabled});
    }};
  `;
  const mf=new Miniflare(convertV4MiniflareOptions({cf:false,modules:true,script,https:true,host:'127.0.0.1',port:0,compatibilityDate:'2026-08-31'}));
  return {mf,origin:(await mf.ready).origin};
}
