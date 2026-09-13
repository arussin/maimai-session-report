/* Fixed-origin maimai.party navigation and an explicit browser-only handoff. */
(()=>{'use strict';
const origin='https://maimai.party',protocol='maimai-player-handoff/1';
const config=JSON.parse(document.getElementById('party-data').textContent);
const make=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
const wordmark=__PARTY_WORDMARK__;
const decode=()=>Uint8Array.from(atob(config.payload||''),c=>c.charCodeAt(0));
let status,download;
async function bounded(response,max){if(!response.ok)throw new Error('Data unavailable');const reader=response.body.getReader(),chunks=[];let total=0;try{for(;;){const {done,value}=await reader.read();if(done)break;total+=value.length;if(total>max)throw new Error('Data exceeds transfer limit');chunks.push(value);}}catch(e){await reader.cancel().catch(()=>{});throw e;}const result=new Uint8Array(total);let offset=0;for(const part of chunks){result.set(part,offset);offset+=part.length;}return result;}
async function latest(){
  if(!config.latestPath||location.protocol==='file:')return {offer:config.offer,bytes:decode,stale:false};
  try{if(!/^\/[A-Za-z0-9_-]+\/party\/latest\.json$/.test(config.latestPath))throw new Error('Invalid data endpoint');
    const raw=await bounded(await fetch(config.latestPath,{credentials:'same-origin',cache:'no-store',redirect:'error',signal:AbortSignal.timeout(10000)}),8*1024*1024),metadata=JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(raw));
    const prefix=config.latestPath.slice(0,-'latest.json'.length),ref=metadata.object;
    if(!ref||!/^[a-f0-9]{64}$/.test(ref.sha256)||ref.path!==prefix+'data/'+ref.sha256+'.gz'||!Number.isSafeInteger(ref.bytes)||ref.bytes<1||ref.bytes>32*1024*1024||metadata.player?.key!==config.offer?.player?.key)throw new Error('Invalid latest player data');
    return {offer:metadata,stale:false,bytes:async()=>{const bytes=await bounded(await fetch(ref.path,{credentials:'same-origin',cache:'no-store',redirect:'error',signal:AbortSignal.timeout(30000)}),ref.bytes);const hash=[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(b=>b.toString(16).padStart(2,'0')).join('');if(bytes.length!==ref.bytes||hash!==ref.sha256)throw new Error('Data integrity mismatch');return bytes;}};
  }catch{return {offer:config.offer,bytes:decode,stale:true};}
}
function save(){const raw=decode(),url=URL.createObjectURL(new Blob([raw],{type:'application/gzip'})),a=make('a');a.href=url;a.download='player.maimai.json.gz';document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),30000);}
function open(url){
  if(!config.enabled||!config.payload){window.open(url,'_blank','noopener');return;}
  const nonce=crypto.randomUUID();url.hash=new URLSearchParams({'party-import':nonce}).toString();
  const child=window.open(url.href,'_blank');
  if(!child){status.textContent='The new tab was blocked. Download your player file, open maimai.party, and import it from Settings.';download.hidden=false;status.classList.add('party-transfer-error');return;}
  status.textContent='Opening maimai.party…';let connected=false,port=null;const preparation=latest();
  const timeout=setTimeout(()=>{if(!connected){window.removeEventListener('message',receive);status.textContent='The transfer could not connect. Download the player file and import it from Settings on maimai.party.';download.hidden=false;status.classList.add('party-transfer-error');}},25000);
  async function receive(event){if(connected||event.origin!==origin||event.source!==child||event.data?.protocol!==protocol||event.data?.type!=='ready'||event.data?.nonce!==nonce)return;connected=true;clearTimeout(timeout);window.removeEventListener('message',receive);
    const source=await preparation;const channel=new MessageChannel();port=channel.port1;let accepted=false,finishTimer;
    function finish(label){clearTimeout(finishTimer);status.textContent=label;port.close();}
    port.onmessage=async event=>{if(event.data?.type==='accept'&&!accepted){accepted=true;status.textContent='Transferring the selected player data…';finishTimer=setTimeout(()=>{download.hidden=false;status.classList.add('party-transfer-error');finish('The transfer was interrupted. Use the player file to import your saved snapshot.');},45000);try{const bytes=await source.bytes();port.postMessage({type:'data',bytes:bytes.buffer},[bytes.buffer]);}catch{port.postMessage({type:'error'});download.hidden=false;status.classList.add('party-transfer-error');finish('Latest data could not be transferred. The download contains the snapshot saved in this report.');}}
      else if(event.data?.type==='imported')finish('Your data is ready in maimai.party.');else if(event.data?.type==='reused')finish('maimai.party already has your relevant data.');else if(event.data?.type==='declined')finish('Opened maimai.party without personal results.');else if(event.data?.type==='error'){download.hidden=false;status.classList.add('party-transfer-error');finish('Import did not complete. Your saved player file is available below.');}};
    child.postMessage({protocol,type:'offer',nonce,offer:source.offer,stale:source.stale},origin,[channel.port2]);status.textContent=source.stale?'Latest hosted data was unavailable. maimai.party will offer this report’s saved snapshot.':'Choose whether to import your data in maimai.party.';
  }
  window.addEventListener('message',receive);
}
function route(item,similar){const url=new URL(origin+'/'),ref=config.mapping?.[item.chartID];if(ref&&config.catalogVersion){url.searchParams.set('version',config.catalogVersion);url.searchParams.set('view',similar?'compare':'catalog');url.searchParams.set(similar?'left':'chart',ref.chart_id);if(similar)url.searchParams.set('similar','1');}else{url.searchParams.set('view','catalog');url.searchParams.set('search',item.title||'');}return url;}
function link(label,url){const a=make('a',label,'party-action');a.href=url.href;a.target='_blank';a.rel='noopener';a.onclick=e=>{e.preventDefault();open(new URL(url));};return a;}
function actions(item){const root=make('div',undefined,'party-chart-actions');const mapped=!!config.mapping?.[item.chartID];if(mapped){root.append(link('See song details on maimai.party',route(item,false)),link('Find similar on maimai.party',route(item,true)));}else{root.append(link('Search for this song on maimai.party',route(item,false)),make('small','An exact chart link is not available in the prepared catalog.'));}return root;}
function mount(){if(document.getElementById('open-maimai-party'))return;const toolbar=document.querySelector('.toolbar');if(!toolbar)return;status=make('p','','party-transfer-status');status.setAttribute('role','status');download=make('button','Download player file','action-button');download.id='download-player-data';download.type='button';download.hidden=!config.enabled||!config.payload;download.onclick=save;
  const holder=make('div');holder.innerHTML=wordmark;const brand=holder.firstElementChild;brand.id='open-maimai-party';brand.href=origin+'/';brand.target='_blank';brand.rel='noopener';brand.setAttribute('aria-label','Open in maimai.party');brand.prepend(make('span','Open in','party-open-label'));brand.onclick=e=>{e.preventDefault();status.classList.remove('party-transfer-error');open(new URL(origin+'/'));};toolbar.querySelector('.report-brand-block').append(brand);toolbar.querySelector('.report-downloads').append(download);toolbar.after(status);
}
window.maimaiParty=Object.freeze({actions,mount});queueMicrotask(mount);
})();
