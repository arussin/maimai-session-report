import {test, expect} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import {readFile} from 'node:fs/promises';

const tiers = [['white','White',0],['blue','Blue',1000],['green','Green',2000],
  ['yellow','Yellow',4000],['red','Red',7000],['purple','Purple',10000],
  ['bronze','Bronze',12000],['silver','Silver',13000],['gold','Gold',14000],
  ['platinum','Platinum',14500],['rainbow','Rainbow',15000],['rainbow-ex','Rainbow EX',16000]];
const number = value => Number(value).toLocaleString('en-US');
const signed = value => `${value > 0 ? '+' : ''}${number(value)}`;

// Start with the real renderer's allowlisted fictional output. Only explicitly
// synthetic display cases change totals; no real account or historical report is read.
async function showCard(page, scenario = 'complete', change = () => {}) {
  let model;
  const html = (await readFile(new URL(`generated/${scenario}.html`, import.meta.url), 'utf8'))
    .replace(/(<script id="report-data"[^>]*>)(.*?)(<\/script>)/s, (_,open,json,close) => {
      model = JSON.parse(json);
      change(model);
      return open + JSON.stringify(model).replace(/</g, '\\u003c') + close;
    });
  await page.route('**/synthetic-playercard.html', route => route.fulfill({contentType:'text/html',body:html}));
  await page.goto('/synthetic-playercard.html');
  await expect(page.locator('.namecard')).toBeVisible();
  return model;
}

async function withinCard(page) {
  const result = await page.locator('.namecard').evaluate(card => {
    const box = card.getBoundingClientRect();
    return [...card.querySelectorAll('h1, .namecard-tier, .rating-plaque, .rating-value, .rating-value>span, .namecard-label, .tier-progress, .tier-next')]
      .filter(el => {
        const r = el.getBoundingClientRect();
        return r.left < box.left - 1 || r.right > box.right + 1 || r.top < box.top - 1 || r.bottom > box.bottom + 1;
      }).map(el => el.className || el.tagName);
  });
  expect(result).toEqual([]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
}

test('all twelve approved frames decode locally with gold digits in the original number window', async ({page},testInfo) => {
  const errors = [], unexpected = [], frames = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('request', request => {if (!request.url().endsWith('/synthetic-playercard.html')) unexpected.push(request.url());});
  for (const [key,name,rating] of tiers) {
    await showCard(page, 'complete', model => {
      model.before.reconstructedRating = rating;
      model.after.reconstructedRating = rating;
      model.delta.reconstructedRating = 0;
    });
    await expect(page.locator('.namecard')).toHaveClass(`namecard tier-${key}`);
    await expect(page.locator('.namecard-tier')).toHaveText(name);
    await expect(page.getByRole('img',{name:`Reconstructed rating ${number(rating)}`,exact:true})).toBeVisible();
    await expect(page.locator('.rating-value')).toHaveText(String(rating));
    await expect(page.locator('.rating-value>span')).toHaveCount(5);
    const frame = await page.locator('.rating-plaque').evaluate(async el => {
      const style = getComputedStyle(el);
      const url = style.backgroundImage.match(/url\("?(.*?)"?\)/)?.[1];
      if (!url) return {url:null};
      const image = new Image(); image.src = url; await image.decode();
      const box = el.getBoundingClientRect(), digits = el.querySelector('.rating-value');
      const r = digits.getBoundingClientRect(), text = getComputedStyle(digits);
      return {url,width:image.naturalWidth,height:image.naturalHeight,aspect:box.width/box.height,
        left:(r.left-box.left)/box.width,right:(box.right-r.right)/box.width,
        top:(r.top-box.top)/box.height,bottom:(box.bottom-r.bottom)/box.height,
        color:text.color,font:text.fontFamily,pseudo:getComputedStyle(el,'::before').content};
    });
    expect(frame.url).toMatch(/^data:image\/webp;base64,/);
    expect([frame.width,frame.height]).toEqual([296,86]);
    expect(frame.aspect).toBeCloseTo(296/86,2);
    expect(frame.left).toBeCloseTo(.4155,2); expect(frame.right).toBeCloseTo(.05,2);
    expect(frame.top).toBeCloseTo(.186,2); expect(frame.bottom).toBeCloseTo(.2325,2);
    expect(frame.color).toBe('rgb(255, 227, 82)'); expect(frame.font).toContain('Arial Black');
    expect(frame.pseudo).toBe('none');
    await withinCard(page);
    frames.push(frame.url);
    await testInfo.attach(`playercard-${key}.png`,{body:await page.locator('.namecard').screenshot(),contentType:'image/png'});
  }
  expect(new Set(frames).size).toBe(12);
  expect(errors).toEqual([]); expect(unexpected).toEqual([]);
});

test('restored card keeps synthetic receipt values, empty sessions and pool navigation', async ({page},testInfo) => {
  for (const scenario of ['complete','empty','incomplete']) {
    const model = await showCard(page, scenario);
    await expect(page.locator('.namecard-identity h1')).toHaveText(model.player.displayName);
    await expect(page.locator('.session-change')).toHaveText(`${signed(model.delta.reconstructedRating)}this session`);
    await expect(page.locator('.session-facts')).toContainText(`${number(model.session.scoreCount)} plays`);
    await expect(page.locator('.session-facts')).toContainText(`${number(model.session.newPBCount)} new PBs`);
    await expect(page.locator('.contribution.old strong')).toHaveText(signed(model.delta.old35Rating));
    await expect(page.locator('.contribution.new strong')).toHaveText(signed(model.delta.new15Rating));
    const retained = JSON.parse(await page.locator('#report-data').textContent());
    expect(retained).toEqual(model);
    await withinCard(page);
    const axe = await new AxeBuilder({page}).include('.session-header').withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();
    expect(axe.violations).toEqual([]);
    await testInfo.attach(`playercard-${scenario}-receipt.png`,{body:await page.locator('.session-header').screenshot(),contentType:'image/png'});
    await page.getByRole('button',{name:'Breakdown',exact:true}).click();
    await expect(page.getByRole('tabpanel',{name:'Rating pools',exact:true})).toBeVisible();
  }
});

test('tier transition, negative change and long names reflow at 200 percent text', async ({page},testInfo) => {
  await page.emulateMedia({reducedMotion:'reduce'});
  for (const [before,after,delta] of [[13999,14000,1],[14000,13999,-1],[16005,16005,0]]) {
    await showCard(page, 'complete', model => {
      model.player.displayName = 'Synthetic Player With A Very Long Name 合成プレイヤー';
      model.before.reconstructedRating = before;
      model.after.reconstructedRating = after;
      model.delta.reconstructedRating = delta;
    });
    await page.evaluate(() => {document.documentElement.style.fontSize='200%';document.body.style.fontFamily='Georgia, serif';});
    await withinCard(page);
    await expect(page.locator('.session-change')).toHaveText(`${signed(delta)}this session`);
    if (delta === 1) await expect(page.locator('.tier-next strong')).toHaveText('Silver → Gold');
    if (delta === -1) await expect(page.locator('.session-change')).toHaveClass(/negative/);
    if (delta === 0) await expect(page.getByRole('progressbar')).toHaveAttribute('aria-valuenow','100');
    expect(await page.evaluate(() => document.getAnimations().filter(a => a.playState==='running').length)).toBe(0);
    await testInfo.attach(`playercard-reflow-${delta}.png`,{body:await page.locator('.session-header').screenshot(),contentType:'image/png'});
  }
});

test('print retains the frame and forced colors retains readable rating text', async ({page,browserName}) => {
  await showCard(page);
  await page.emulateMedia({media:'print'});
  await expect(page.locator('.rating-plaque')).toHaveCSS('print-color-adjust','exact');
  await expect(page.locator('.rating-plaque')).toHaveCSS('background-image',/^url\("data:image\/webp;base64,/);
  if (browserName === 'webkit') return; // WebKit does not emulate forced-colors.
  await page.emulateMedia({media:'screen',forcedColors:'active'});
  await expect(page.locator('.rating-plaque')).toHaveCSS('background-image','none');
  await expect(page.locator('.rating-value')).toHaveCSS('text-shadow','none');
  expect(await page.locator('.rating-plaque').evaluate(el => getComputedStyle(el,'::before').content)).toBe('"DX RATING"');
  await withinCard(page);
});
