/** Explicit synthetic recipient for report handoffs; no hosted page is requested. */
export async function enablePartyFixture(context, sourceOrigin) {
  await context.route('https://maimai.party/', route => route.fulfill({contentType:'text/html',body:`
    <!doctype html><html lang="en"><title>Synthetic maimai.party recipient</title>
    <h1>Synthetic player import</h1><p id="status">Waiting for an offer</p>
    <button id="accept" disabled>Import synthetic data</button><button id="decline" disabled>Decline</button>
    <script>
    const sourceOrigin=${JSON.stringify(sourceOrigin)}, protocol='maimai-player-handoff/1';
    const nonce=new URLSearchParams(location.hash.slice(1)).get('party-import');
    addEventListener('message',event=>{
      if(event.origin!==sourceOrigin || event.source!==opener || event.data?.protocol!==protocol || event.data?.nonce!==nonce || event.data?.type!=='offer')return;
      const port=event.ports[0]; if(!port)return;
      document.querySelector('#status').textContent='Synthetic offer ready; no score bytes received';
      const accept=document.querySelector('#accept'),decline=document.querySelector('#decline');accept.disabled=decline.disabled=false;
      accept.onclick=()=>{accept.disabled=decline.disabled=true;port.postMessage({type:'accept'});};
      decline.onclick=()=>{accept.disabled=decline.disabled=true;port.postMessage({type:'declined'});document.querySelector('#status').textContent='Declined';};
      port.onmessage=event=>{if(event.data?.type==='data'){document.querySelector('#status').textContent='Synthetic player bytes received locally';port.postMessage({type:'imported'});}};
    });
    if(opener&&nonce)opener.postMessage({protocol,type:'ready',nonce},sourceOrigin);
    </script></html>`}));
}
