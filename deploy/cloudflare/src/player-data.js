const ID = /^[a-f0-9]{64}$/;
const MAX_BYTES = 32 * 1024 * 1024;

export async function handlePlayerData(request, env, makeHeaders) {
  const url = new URL(request.url), prefix = env.HISTORY_PREFIX;
  if (!url.pathname.startsWith(prefix + 'party/')) return null;
  const respond = (body,status=200,extra={}) => new Response(request.method==='HEAD'?null:body,
    {status,headers:makeHeaders({'Content-Type':'application/json; charset=utf-8',...extra})});
  if(url.origin!==env.HISTORY_ORIGIN || !/^\/[A-Za-z0-9_-]+\/$/.test(prefix)) return respond(null,404);
  if(!['GET','HEAD'].includes(request.method))return respond(null,405,{Allow:'GET, HEAD'});
  try {
    const latest = url.pathname===prefix+'party/latest.json';
    const file = new RegExp('^'+prefix+'party/data/([a-f0-9]{64})\\.gz$').exec(url.pathname);
    if(!latest&&!file)return respond(null,404);
    const row=await (latest ? env.HISTORY_DB.prepare(
      'SELECT r.metadata FROM player_state s JOIN player_revisions r ON r.scope=s.scope AND r.revision=s.revision WHERE s.scope=?').bind(env.HISTORY_SCOPE)
      : env.HISTORY_DB.prepare("SELECT metadata FROM player_revisions WHERE scope=? AND json_extract(metadata,'$.sha256')=? LIMIT 1").bind(env.HISTORY_SCOPE,file[1])).first();
    if(!row)return respond(JSON.stringify({error:'No verified player dataset is available yet.'}),404);
    const meta=JSON.parse(row.metadata);
    if(meta.scope!==env.HISTORY_SCOPE||!ID.test(meta.sha256)||meta.key!==`objects/sha256/${meta.sha256}`||
       !Number.isSafeInteger(meta.bytes)||meta.bytes<1||meta.bytes>MAX_BYTES||meta.revision!==meta.offer?.revision)throw Error('Invalid player reference');
    if(latest)return respond(JSON.stringify({...meta.offer,object:{sha256:meta.sha256,bytes:meta.bytes,path:prefix+'party/data/'+meta.sha256+'.gz'}}));
    const object=await env.HISTORY_OBJECTS.get(meta.key);
    if(!object||object.size!==meta.bytes||object.customMetadata?.sha256!==meta.sha256)throw Error('Unavailable player object');
    return respond(object.body,200,{'Content-Type':'application/gzip','Content-Length':String(meta.bytes),
      'Content-Disposition':'attachment; filename="player.maimai.json.gz"'});
  }catch{return respond(JSON.stringify({error:'Player data is temporarily unavailable. Your report’s saved snapshot can still be imported.'}),503);}
}
