import {privateHeadersFor} from './security.js';
import {historyStream} from './history-reader.js';

export async function streamReport(request, env, ref, options={}) {
  if(!/^[a-f0-9]{64}$/.test(ref.sha256)||ref.key!==`objects/sha256/${ref.sha256}`)throw Error('Invalid report reference');
  const object=await env.HISTORY_OBJECTS.get(ref.key);
  if(!object||object.size<1||object.size>64*1024*1024||(ref.bytes!==undefined&&object.size!==ref.bytes))throw Error('Report unavailable');
  let body=object.body, flags=ref.flags;
  if(object.customMetadata?.sha256===ref.sha256&&object.customMetadata?.['report-flags']) {
    const verifiedFlags=JSON.parse(object.customMetadata['report-flags']);
    if(flags&&JSON.stringify(flags)!==JSON.stringify(verifiedFlags)) {
      // Property order is not significant in the independently retained descriptor.
      if(flags.support!==verifiedFlags.support||JSON.stringify(flags.party)!==JSON.stringify(verifiedFlags.party))throw Error('Report flags differ');
    }
    flags=verifiedFlags;
  } else {
    // Original archive objects have no verified streaming receipt. They remain
    // supported within their original bound, with an exact checksum read.
    if(object.size>20*1024*1024)throw Error('Report needs a verified streaming receipt');
    const bytes=await object.arrayBuffer();
    const hash=[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(b=>b.toString(16).padStart(2,'0')).join('');
    if(hash!==ref.sha256)throw Error('Report integrity mismatch');
    const html=new TextDecoder().decode(bytes);
    const response=new Response(request.method==='HEAD'?null:html,{headers:privateHeadersFor(html,{'Content-Type':'text/html; charset=utf-8'})});
    return request.method==='HEAD'?response:historyStream(response,options);
  }
  const response=new Response(request.method==='HEAD'?null:body,{headers:privateHeadersFor({flags},{'Content-Type':'text/html; charset=utf-8'})});
  return request.method==='HEAD'?response:historyStream(response,options);
}
