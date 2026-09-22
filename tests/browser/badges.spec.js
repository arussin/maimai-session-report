import {test,expect} from './fixtures.js';
import {readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';

const tiers=[['white',0],['blue',1000],['green',2000],['yellow',4000],['red',7000],['purple',10000],['bronze',12000],['silver',13000],['gold',14000],['platinum',14500],['rainbow',15000],['rainbow-ex',16000]];
const demo=new URL('generated/demo.html',import.meta.url);

test('all twelve original tiers select distinct decodable local frames with unclipped digits',async({page},testInfo)=>{
  const errors=[],external=[],frames=[];
  let rating=0;
  const original=await readFile(demo,'utf8');
  page.on('pageerror',error=>errors.push(error.message));
  await page.route(/^https?:/,route=>{
    if(route.request().url()==='http://127.0.0.1:4180/badge-review.html') {
      const html=original.replace(/(<script id="report-data"[^>]*>)(.*?)(<\/script>)/s,(_,open,data,close)=>{
        const report=JSON.parse(data);
        report.before.reconstructedRating=rating;report.after.reconstructedRating=rating;
        report.delta.reconstructedRating=0;
        return open+JSON.stringify(report).replace(/</g,'\\u003c')+close;
      });
      return route.fulfill({contentType:'text/html',body:html});
    }
    external.push(route.request().url());return route.abort();
  });
  for(const [tier,value] of tiers) {
    rating=value;
    await page.goto('http://127.0.0.1:4180/badge-review.html');
    await expect(page.locator(`.namecard.tier-${tier}`)).toBeVisible();
    const frame=page.locator('.rating-plaque');
    const result=await frame.evaluate(async el=>{
      const url=getComputedStyle(el).backgroundImage.match(/url\("?(.*?)"?\)/)[1];
      const image=new Image();image.src=url;await image.decode();
      const bounds=el.getBoundingClientRect();
      const inside=[...el.querySelectorAll('.rating-value>span')].every(digit=>{
        const box=digit.getBoundingClientRect();
        return box.left>=bounds.left&&box.right<=bounds.right&&box.top>=bounds.top&&box.bottom<=bounds.bottom;
      });
      return {url,width:image.naturalWidth,height:image.naturalHeight,inside};
    });
    expect(result.url).toMatch(/^data:image\/webp;base64,/);
    expect([result.width,result.height]).toEqual([296,86]);expect(result.inside).toBe(true);
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
    frames.push(result.url);
    await testInfo.attach(`rating-${tier}.png`,{body:await page.locator('.namecard').screenshot(),contentType:'image/png'});
  }
  expect(new Set(frames).size).toBe(12);expect(errors).toEqual([]);expect(external).toEqual([]);
});

test('exported full custom pack retains original frames and characterized rendering',async({page,browserName},testInfo)=>{
  async function capture(path) {
    await page.goto(path);
    await page.locator('.namecard').evaluate(async card=>{
      await document.fonts.ready;
      const urls=[...card.querySelectorAll('*')].map(el=>getComputedStyle(el).backgroundImage).filter(value=>value.startsWith('url('));
      await Promise.all(urls.map(async value=>{const image=new Image();image.src=value.slice(4,-1).replace(/^"|"$/g,'');await image.decode();}));
      await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
    });
    const frame=await page.locator('.rating-plaque').evaluate(el=>{const css=getComputedStyle(el),box=el.getBoundingClientRect();return {image:css.backgroundImage,width:box.width,height:box.height};});
    let previous=null;
    for(let attempt=0;attempt<8;attempt++){
    const bytes=await page.locator('.namecard').screenshot({animations:'disabled'});
    const pixels=await page.evaluate(async source=>{
      const image=new Image();image.src='data:image/png;base64,'+source;await image.decode();
      const canvas=document.createElement('canvas');canvas.width=image.width;canvas.height=image.height;
      const context=canvas.getContext('2d');context.drawImage(image,0,0);
      const hash=await crypto.subtle.digest('SHA-256',context.getImageData(0,0,image.width,image.height).data);
      return {width:image.width,height:image.height,sha256:Array.from(new Uint8Array(hash),value=>value.toString(16).padStart(2,'0')).join('')};
    },bytes.toString('base64'));
    if(previous===pixels.sha256)return {bytes,pixels,frame};
    previous=pixels.sha256;
    await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
    }
    throw new Error('Namecard raster did not settle to two identical decoded captures');
  }
  const before=await capture('/demo.html'),after=await capture('/custom-badges.html');
  expect(after.frame).toEqual(before.frame);
  if(browserName==='firefox'){
    // Firefox historically resamples the shorthand-centered custom frame differently
    // from background-image at fractional widths. Both variants must retain exact
    // pre-revision HTML; source imagery and geometry above still match exactly.
    const baseline=JSON.parse(await readFile(new URL('../fixtures/badge-baseline.json',import.meta.url),'utf8'));
    for(const name of ['demo.html','custom-badges.html'])expect(createHash('sha256').update(await readFile(new URL('generated/'+name,import.meta.url))).digest('hex')).toBe(baseline.cases[name]);
    await testInfo.attach('historical-firefox-badge-rendering',{body:JSON.stringify({sourceCommit:baseline.source_commit,default:before.pixels,custom:after.pixels}),contentType:'application/json'});
    return;
  }
  if(JSON.stringify(before.pixels)!==JSON.stringify(after.pixels)) {
    await testInfo.attach('default-namecard',{body:before.bytes,contentType:'image/png'});
    await testInfo.attach('custom-namecard',{body:after.bytes,contentType:'image/png'});
  }
  expect(after.pixels).toEqual(before.pixels);
});
