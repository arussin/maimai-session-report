import {test,expect} from '@playwright/test';
import {readFile} from 'node:fs/promises';

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

test('exported full custom pack renders identically to the default original frames',async({page})=>{
  await page.goto('/demo.html');
  const before=await page.locator('.namecard').screenshot();
  await page.goto('/custom-badges.html');
  expect(await page.locator('.namecard').screenshot()).toEqual(before);
});
