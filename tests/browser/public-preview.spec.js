import {test,expect} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test('public demo shows real targets, embedded demo tiles and original compact rating geometry', async ({page},testInfo)=> {
  const errors=[],external=[];
  page.on('pageerror',error=>errors.push(error.message));
  await page.route(/^https?:/,route=> {
    if(route.request().url().startsWith('http://127.0.0.1:4180/')) return route.continue();
    external.push(route.request().url()); return route.abort();
  });
  await page.goto('/demo.html');
  await expect(page.getByRole('heading',{name:'Sample Player',exact:true})).toBeVisible();
  await expect(page.locator('.overview-targets .target-row')).toHaveCount(2);
  await expect(page.locator('.overview-lead .jacket-missing')).toHaveCount(0);
  const geometry=await page.locator('.rating-plaque').evaluate(el=> {
    const frame=el.getBoundingClientRect(), digits=el.querySelector('.rating-value').getBoundingClientRect();
    return {ratio:frame.width/frame.height,left:(digits.left-frame.left)/frame.width,width:digits.width/frame.width};
  });
  expect(geometry.ratio).toBeCloseTo(296/86,1);
  expect(geometry.left).toBeGreaterThan(.40);
  expect(geometry.left).toBeLessThan(.44);
  expect(geometry.width).toBeGreaterThan(.50);
  expect(geometry.width).toBeLessThan(.55);
  for(const name of ['Scorecard','Scores','Rating pools','Targets']) {
    await page.getByRole('tab',{name,exact:true}).click();
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
    expect((await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze()).violations).toEqual([]);
    await testInfo.attach(`public-demo-${name}.png`,{body:await page.screenshot(),contentType:'image/png'});
  }
  // Hidden/offscreen images are deliberately lazy. Decode their embedded bytes
  // independently instead of incorrectly treating deferred loading as failure.
  expect(await page.locator('img').evaluateAll(async images=> {
    for(const image of images) {
      if(!image.src.startsWith('data:image/png;base64,')) return false;
      const decoded=new Image(); decoded.src=image.src; await decoded.decode();
      if(!decoded.naturalWidth) return false;
    }
    return true;
  })).toBe(true);
  expect(errors).toEqual([]);expect(external).toEqual([]);
});

test('public demo print exposes every report section and respects reduced motion', async ({page},testInfo)=> {
  await page.emulateMedia({media:'print',reducedMotion:'reduce'});
  await page.goto('/demo.html');
  for(const name of ['Scorecard','Scores','Rating pools','Targets']) {
    await expect(page.getByRole('tabpanel',{name,exact:true})).toBeVisible();
  }
  await expect(page.getByRole('navigation',{name:'Report views'})).toBeHidden();
  expect(await page.locator('.rating-plaque').evaluate(el=>getComputedStyle(el).animationName)).toBe('none');
  await testInfo.attach('public-demo-print.png',{body:await page.screenshot(),contentType:'image/png'});
});
