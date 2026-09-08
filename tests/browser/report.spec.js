import {test, expect} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import {readFile} from 'node:fs/promises';

const data = async name => JSON.parse(await readFile(new URL(`generated/${name}.json`, import.meta.url), 'utf8'));
const grades = ['SSS+','SSS','SS+','SS','S+','S','AAA','AA','A','BBB','BB','B','C','D'];
const visibleRows = page => page.locator('#session-rows tr[data-search]:visible');
async function noOverflow(page) {
  const overflow=await page.evaluate(() => [...document.querySelectorAll('body *')].filter(el=>{const r=el.getBoundingClientRect();return r.width&&r.right>innerWidth+1&&getComputedStyle(el).position!=='fixed';}).map(el=>({tag:el.tagName,class:el.className,text:el.textContent.slice(0,70),right:el.getBoundingClientRect().right})));
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1),JSON.stringify(overflow)).toBe(true);
}
async function cleanAxe(page) {
  const result = await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();
  expect(result.violations.map(v=>({id:v.id, nodes:v.nodes.map(n=>({target:n.target,summary:n.failureSummary}))}))).toEqual([]);
}

test.beforeEach(async ({page})=> {
  // No actual provider checkout/payment request is made by this suite.
  await page.route('https://buymeacoffee.com/**', route=>route.fulfill({
    contentType:'text/html', body:'<!doctype html><html lang="en"><title>Synthetic checkout container</title><button>Test provider focus target</button></html>'
  }));
});

for (const scenario of ['complete','empty','incomplete']) {
  test(`${scenario}: all four views remain complete, accessible and within viewport`, async ({page},testInfo)=> {
    const model=await data(scenario), errors=[], unexpected=[];
    page.on('pageerror',error=>errors.push(error.message));
    page.on('request', request=> {if(!request.url().startsWith('http://127.0.0.1:4180/')) unexpected.push(request.url());});
    await page.goto(`/${scenario}.html`);
    await expect(page.getByRole('img',{name:`Reconstructed rating ${model.after.reconstructedRating.toLocaleString('en-US')}`})).toBeVisible();
    await expect(page.getByRole('progressbar')).toBeVisible();
    await expect(page.getByRole('button',{name:'Buy the developer a maimai credit'})).toHaveCount(1);
    for(const name of ['Scorecard','Scores','Rating pools','Targets']) {
      await page.getByRole('tab',{name,exact:true}).click();
      await expect(page.getByRole('tabpanel',{name,exact:true})).toBeVisible();
      await expect(page.getByRole('button',{name:'Buy the developer a maimai credit',exact:true})).toBeVisible();
      await expect(page.getByText('Enjoying maimai Session Report?',{exact:true})).toBeVisible();
      await expect(page.locator('.support-frame')).not.toHaveAttribute('src');
      await noOverflow(page);
      await cleanAxe(page);
      await testInfo.attach(`${scenario}-${name}.png`,{body:await page.screenshot(),contentType:'image/png'});
    }
    await page.getByRole('tab',{name:'Scores',exact:true}).click();
    await expect(visibleRows(page)).toHaveCount(model.session.scores.length);
    await page.getByRole('combobox',{name:'Show',exact:true}).selectOption('pbs');
    await expect(visibleRows(page)).toHaveCount(model.session.changedPBs.length);
    if(scenario==='empty') await expect(page.getByText('No score changes detected.',{exact:true})).toBeVisible();
    await page.getByRole('tab',{name:'Rating pools',exact:true}).click();
    await expect(page.locator('.pool-item:visible')).toHaveCount(model.after.old35.length+model.after.new15.length);
    if(scenario==='incomplete') await expect(page.getByText(/Open slot/)).toBeVisible();
    expect(errors).toEqual([]); expect(unexpected).toEqual([]);
  });
}

test('grades sort highest first; search, chart type, scope and sort compose', async ({page})=> {
  const model=await data('presentation');
  await page.goto('/presentation.html'); await page.getByRole('tab',{name:'Scores',exact:true}).click();
  const expected=[...new Set(model.session.scores.map(s=>s.grade||'—'))].sort((a,b)=>grades.indexOf(a)-grades.indexOf(b));
  expect(await page.locator('.grade-count .grade-pill').allTextContents()).toEqual(expected);
  await page.getByRole('searchbox',{name:'Filter session scores'}).fill('same-level 9');
  await expect(visibleRows(page)).toHaveCount(2);
  await page.getByRole('combobox',{name:'Chart type',exact:true}).selectOption('diff-advanced');
  await expect(visibleRows(page)).toHaveCount(1);
  await expect(visibleRows(page).first().locator('.difficulty-pill')).toHaveText('Advanced 9');
  const advancedColor=await visibleRows(page).first().locator('.difficulty-pill').evaluate(el=>getComputedStyle(el).backgroundColor);
  await page.getByRole('combobox',{name:'Chart type',exact:true}).selectOption('diff-expert');
  await expect(visibleRows(page)).toHaveCount(1);
  await expect(visibleRows(page).first().locator('.difficulty-pill')).toHaveText('Expert 9');
  expect(await visibleRows(page).first().locator('.difficulty-pill').evaluate(el=>getComputedStyle(el).backgroundColor)).not.toBe(advancedColor);
  await page.getByRole('searchbox',{name:'Filter session scores'}).fill('');
  await page.getByRole('combobox',{name:'Chart type',exact:true}).selectOption('');
  for(const [sort,key,column] of [['achievement','percent',2],['rating','rate',4]]) {
    await page.getByRole('combobox',{name:'Sort',exact:true}).selectOption(sort);
    const first=[...model.session.scores].sort((a,b)=>b[key]-a[key]||b.timeAchieved-a.timeAchieved)[0];
    await expect(visibleRows(page).first().locator('td').nth(column)).toContainText(key==='percent'?first.percent.toFixed(4):String(first.rate));
  }
  await page.getByRole('combobox',{name:'Show',exact:true}).selectOption('pbs');
  await expect(visibleRows(page)).toHaveCount(model.session.changedPBs.length);
  await expect(page.locator('#pb-gain-heading')).not.toHaveAttribute('hidden');
  await page.getByRole('searchbox',{name:'Filter session scores'}).fill('no-such-synthetic-song');
  await expect(visibleRows(page)).toHaveCount(0);
  await expect(page.locator('#score-count')).toHaveText(`0 of ${model.session.changedPBs.length} PB changes`);
});

test('full before/after pools retain every entry, occupancy and search', async ({page})=> {
  const model=await data('complete');
  await page.goto('/complete.html'); await page.getByRole('tab',{name:'Rating pools',exact:true}).click();
  const newRow=page.getByRole('region',{name:'Rating before and after'}).getByRole('row').filter({has:page.getByRole('rowheader',{name:'New 15',exact:true})});
  await expect(newRow).toContainText(`${model.before.newSlotsFilled}/15 counted`);
  for(const snapshot of ['before','after']) {
    await page.getByRole('combobox',{name:'Snapshot',exact:true}).selectOption(snapshot);
    for(const [key,id] of [['old35','old-pool'],['new15','new-pool']]) {
      const rows=page.locator(`#${id} .pool-item:visible`);
      await expect(rows).toHaveCount(model[snapshot][key].length);
      const rates=await rows.locator('.pool-rate').allTextContents();
      expect(rates.map(s=>Number(s.replace(/[^0-9]/g,'')))).toEqual(model[snapshot][key].map(x=>x.rate).sort((a,b)=>b-a));
    }
    await page.locator('#old-pool .pool-item').last().click();
    await expect(page.getByRole('dialog').filter({visible:true})).toContainText(snapshot==='before'?'Before session':'After session');
    await page.getByRole('button',{name:'Close score details'}).click();
  }
  await page.getByRole('searchbox',{name:'Filter rating pools'}).fill('unmatched-synthetic');
  await expect(page.locator('.pool-item:visible')).toHaveCount(0);
  await expect(page.locator('#pool-empty')).toBeVisible();
  await page.getByRole('searchbox',{name:'Filter rating pools'}).fill('');
  await expect(page.locator('.pool-item:visible')).toHaveCount(50);
});

test('score details expose PB comparisons and missing fields without inventing zeroes', async ({page})=> {
  const model=await data('presentation');
  await page.goto('/presentation.html'); await page.getByRole('tab',{name:'Scores',exact:true}).click();
  await page.getByRole('combobox',{name:'Chart type',exact:true}).selectOption('diff-advanced');
  await page.getByRole('searchbox',{name:'Filter session scores'}).fill('same-level');
  const opener=visibleRows(page).first().getByRole('button');
  await opener.click();
  const dialog=page.locator('.chart-dialog');
  await expect(dialog).toBeVisible(); await expect(dialog).toContainText('FULL COMBO');
  await expect(dialog.locator('.judgement-grid dd')).toHaveText(['—','—','—','—','—']);
  await cleanAxe(page); await noOverflow(page);
  await page.getByRole('button',{name:'Close score details'}).press('Tab');
  await expect(page.getByRole('button',{name:'Close score details'})).toBeFocused();
  await page.keyboard.press('Shift+Tab');
  await expect(page.getByRole('button',{name:'Close score details'})).toBeFocused();
  await page.keyboard.press('Escape'); await expect(dialog).not.toBeVisible(); await expect(opener).toBeFocused();
  await page.getByRole('searchbox',{name:'Filter session scores'}).fill('');
  await page.getByRole('combobox',{name:'Chart type',exact:true}).selectOption('');
  await page.getByRole('combobox',{name:'Show',exact:true}).selectOption('pbs');
  const pb=model.session.changedPBs.find(x=>x.changeType==='improved');
  await page.getByRole('searchbox',{name:'Filter session scores'}).fill(pb.title);
  await visibleRows(page).first().getByRole('button').click();
  await expect(dialog).toContainText('PB comparison');
  await expect(dialog.locator('.detail-comparison')).toContainText(pb.previousPercent.toFixed(4)+'%');
  await expect(dialog.locator('.detail-comparison')).toContainText(String(pb.previousRate));
  const bounds=await dialog.boundingBox();
  await page.mouse.click(Math.max(1,bounds.x-3),Math.max(1,bounds.y+3));
  await expect(dialog).not.toBeVisible();
});

test('uncounted targets open directly and keep the floor-aware estimate', async ({page})=> {
  const model=await data('presentation');
  const candidate=model.after.newPool.find(row=>row.chartID==='synthetic-target-chart');
  expect(model.after.new15Floor).toBeGreaterThan(candidate.rate);
  const expectedGain=Math.floor(candidate.levelNum*.97*20)-model.after.new15Floor;
  await page.goto('/presentation.html');
  await page.getByRole('button',{name:'Target details: Synthetic uncounted target',exact:true}).click();
  const dialog=page.locator('.chart-dialog');
  await expect(dialog).toContainText(`96.2000% → 97% · +${expectedGain} est.`);
  await expect(dialog).toContainText('New 15 floor');
  await page.keyboard.press('Escape');
  await page.getByRole('tab',{name:'Targets',exact:true}).click();
  await page.getByRole('button',{name:'Target details: Synthetic uncounted target',exact:true}).click();
  await expect(dialog).toContainText('Next rating opportunity');
  await page.keyboard.press('Escape');
  await expect(page.locator('.difficulty-sample .difficulty-pill').filter({hasText:'Advanced 9'})).toHaveCount(1);
  await expect(page.locator('.difficulty-sample .difficulty-pill').filter({hasText:'Expert 9'})).toHaveCount(1);
});

test('keyboard navigation, reduced motion and 200 percent text reflow', async ({page})=> {
  await page.emulateMedia({reducedMotion:'reduce'}); await page.goto('/presentation.html');
  await page.getByRole('tab',{name:'Scorecard',exact:true}).focus();
  await page.keyboard.press('ArrowRight'); await expect(page.getByRole('tab',{name:'Scores',exact:true})).toBeFocused();
  await page.keyboard.press('End'); await expect(page.getByRole('tab',{name:'Targets',exact:true})).toBeFocused();
  await page.keyboard.press('Home'); await expect(page.getByRole('tab',{name:'Scorecard',exact:true})).toBeFocused();
  await page.evaluate(()=>{document.documentElement.style.fontSize='200%';});
  for(const name of ['Scorecard','Scores','Rating pools','Targets']) {
    await page.getByRole('tab',{name,exact:true}).click(); await noOverflow(page);
  }
  expect(await page.evaluate(()=>document.getAnimations().filter(a=>a.playState==='running').length)).toBe(0);
});

test('B50 button downloads the exact supplied image', async ({page})=> {
  await page.goto('/complete.html');
  const pending=page.waitForEvent('download'); await page.getByRole('link',{name:'Download B50'}).click();
  const download=await pending;
  expect(download.suggestedFilename()).toBe('maimai-b50.webp');
  expect(await readFile(await download.path())).toEqual(await readFile(new URL('generated/synthetic-b50.webp',import.meta.url)));
});

test('footer checkout stays lazy and isolated; close, Escape and focus return work', async ({page})=> {
  const providerRequests=[];
  page.on('request',request=>{if(request.url().startsWith('https://buymeacoffee.com/')) providerRequests.push(request.url());});
  await page.goto('/complete.html');
  const frame=page.locator('.support-frame'), opener=page.getByRole('button',{name:'Buy the developer a maimai credit'});
  await expect(frame).not.toHaveAttribute('src'); expect(providerRequests).toHaveLength(0);
  await expect(page.locator('script[src]')).toHaveCount(0);
  await expect(frame).toHaveAttribute('allow','payment *');
  await expect(frame).toHaveAttribute('loading','lazy');
  await expect(frame).toHaveAttribute('referrerpolicy','no-referrer');
  await opener.click(); await expect(page.locator('#support-checkout-dialog')).toBeVisible();
  await expect(frame).toHaveAttribute('src',/^https:\/\/buymeacoffee\.com\/widget\/page\/russin\?/);
  const destination=new URL(await frame.getAttribute('src'));
  expect(destination.origin).toBe('https://buymeacoffee.com');
  expect(destination.pathname).toBe('/widget/page/russin');
  expect([...destination.searchParams.keys()].sort()).toEqual(['color','description']);
  expect(destination.search).not.toContain('Synthetic');
  const fallback=page.getByRole('link',{name:'Open separately ↗',exact:true});
  await expect(fallback).toHaveAttribute('href','https://buymeacoffee.com/russin');
  await expect(fallback).toHaveAttribute('target','_blank');
  await expect(fallback).toHaveAttribute('rel','noopener noreferrer');
  await expect(fallback).toHaveAttribute('referrerpolicy','no-referrer');
  await expect(page.getByRole('button',{name:'Close support checkout'})).toBeFocused();
  await page.frameLocator('.support-frame').getByRole('button',{name:'Test provider focus target'}).waitFor();
  await page.keyboard.press('Escape'); await expect(page.locator('#support-checkout-dialog')).not.toBeVisible();
  await expect(opener).toBeFocused(); await opener.click();
  await page.getByRole('button',{name:'Close support checkout'}).click();
  await expect(opener).toBeFocused(); expect(providerRequests).toHaveLength(1);
});
