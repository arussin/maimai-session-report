import {test, expect} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import {readFile} from 'node:fs/promises';

test('Scorecard and Targets share concise rows and unchanged floor-aware opportunities', async ({page}, testInfo) => {
  const errors = [], external = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.route('**/*', route => {
    if (new URL(route.request().url()).hostname === '127.0.0.1') return route.continue();
    external.push(route.request().url()); return route.abort();
  });
  await page.goto('/presentation.html');
  const before = await page.locator('#report-data').textContent();
  const overview = page.locator('#overview-view .target-list');
  // Authored fixture: floor 278; S ratings 294 and 291, respectively.
  await expect(overview.locator('.target-estimate')).toHaveText(['+16 est.', '+13 est.']);
  await expect(overview.locator('.target-progress')).toHaveText(['PB 96.2000% → 97% S', 'PB 96.4200% → 97% S']);
  const rows = await overview.innerHTML();
  await page.getByRole('tab', {name:'Targets', exact:true}).click();
  expect(await page.locator('#targets-view .target-list').innerHTML()).toBe(rows);
  await expect(page.locator('#targets-view details, #targets-view select')).toHaveCount(0);
  await expect(page.locator('#targets-view').getByRole('button', {name:'View', exact:true})).toHaveCount(0);
  await expect(page.locator('#targets-view .practice-note')).toContainText('Practice idea');
  await expect(page.locator('#targets-view .practice-note')).toContainText('Aim for 97–99%');
  await expect(page.locator('#targets-view')).not.toContainText('Coach’s read');
  await expect(page.locator('#targets-view .pool-threshold-note')).toContainText('New 15 floor · 278');
  const opener = page.locator('#targets-view .target-row').first();
  await opener.click();
  await expect(page.locator('.chart-dialog')).toContainText('Synthetic uncounted target');
  await expect(page.locator('.chart-dialog')).toContainText('+16 est.');
  await page.keyboard.press('Escape');
  await expect(opener).toBeFocused();
  expect(await page.locator('#report-data').textContent()).toBe(before);
  const axe = await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();
  expect(axe.violations).toEqual([]);
  await page.screenshot({path:testInfo.outputPath('compact-targets.png'), fullPage:true});
  await page.evaluate(() => {document.documentElement.style.fontSize='200%';});
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
  expect(errors).toEqual([]); expect(external).toEqual([]);
});

test('no new session retains prior targets; no eligible candidates is explicit; B50 still downloads', async ({page}) => {
  await page.goto('/empty.html');
  await page.getByRole('tab', {name:'Targets', exact:true}).click();
  // The bundled empty scenario has no new plays, but still retains earlier PBs.
  await expect(page.locator('#targets-view .target-estimate')).toHaveText(['+13 est.', '+9 est.']);
  await expect(page.locator('#targets-view .practice-note')).toHaveCount(0);
  const html = (await readFile(new URL('generated/empty.html', import.meta.url), 'utf8'))
    .replace(/(<script id="report-data"[^>]*>)(.*?)(<\/script>)/s, (_, open, json, close) => {
      const model = JSON.parse(json);
      // Exclude the two uncounted near-S records from this authored catalog;
      // preserve counted pools, ratings and the empty session unchanged.
      model.after.newPool = model.after.newPool.filter(item => item.percent >= 97);
      return open + JSON.stringify(model).replace(/</g, '\\u003c') + close;
    });
  await page.route('**/no-targets.html', route => route.fulfill({contentType:'text/html', body:html}));
  await page.goto('/no-targets.html');
  await page.getByRole('tab', {name:'Targets', exact:true}).click();
  await expect(page.locator('#targets-view .target-row')).toHaveCount(0);
  await expect(page.locator('#targets-view')).toContainText('No positive-gain S-threshold targets');
  await expect(page.locator('#targets-view .practice-note')).toHaveCount(0);
  await page.goto('/complete.html');
  await page.getByRole('tab', {name:'Targets', exact:true}).click();
  const pending = page.waitForEvent('download');
  await page.getByRole('link', {name:'Download B50'}).click();
  const downloaded = await pending;
  expect(await readFile(await downloaded.path())).toEqual(await readFile(new URL('generated/synthetic-b50.webp', import.meta.url)));
});
