import {test, expect} from './fixtures.js';
import AxeBuilder from '@axe-core/playwright';
import {readFile} from 'node:fs/promises';
import {openExports} from './export-controls.js';

test('exports stay compact, accessible and preserve both download files', async ({page}, testInfo) => {
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('/complete.html');
  const toggle = page.getByRole('button', {name:'Export', exact:true});
  const compact = page.viewportSize().width <= 1000;
  const toolbar = await page.locator('.toolbar').boundingBox();
  expect(toolbar.height).toBeLessThan(90);
  if (compact) {
    await expect(toggle).toBeVisible();
    await expect(page.getByRole('group', {name:'Report exports'})).toBeHidden();
    await toggle.focus();
    await page.keyboard.press('ArrowDown');
    await expect(page.getByRole('link', {name:'Download B50', exact:true})).toBeFocused();
  } else await expect(toggle).toBeHidden();
  await openExports(page);
  const panel = await page.locator('#report-downloads').boundingBox();
  expect(panel.x).toBeGreaterThanOrEqual(0);
  expect(panel.x + panel.width).toBeLessThanOrEqual(page.viewportSize().width);
  const axe = await new AxeBuilder({page}).include('.toolbar').withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();
  expect(axe.violations).toEqual([]);
  await page.screenshot({path:testInfo.outputPath('exports-open.png')});
  if (compact) {
    await page.keyboard.press('Escape');
    await expect(toggle).toBeFocused();
    await expect(toggle).toHaveAttribute('aria-expanded', 'false');
    await openExports(page);
    await page.locator('.session-header').click();
    await expect(toggle).toHaveAttribute('aria-expanded', 'false');
    await openExports(page);
  }
  const b50Promise = page.waitForEvent('download');
  await page.getByRole('link', {name:'Download B50', exact:true}).click();
  const b50 = await b50Promise;
  expect(await readFile(await b50.path())).toEqual(await readFile(new URL('generated/synthetic-b50.webp', import.meta.url)));
  if (compact) await expect(toggle).toHaveAttribute('aria-expanded', 'false');
  const payload = await page.locator('#party-data').textContent();
  await openExports(page);
  const playerPromise = page.waitForEvent('download');
  await page.getByRole('button', {name:'Download player file', exact:true}).click();
  const player = await playerPromise;
  expect(player.suggestedFilename()).toBe('player.maimai.json.gz');
  expect(await readFile(await player.path())).toEqual(Buffer.from(JSON.parse(payload).payload, 'base64'));
  expect(errors).toEqual([]);
});

test('export panel adapts to resizing and enlarged text; standalone print remains available', async ({page}) => {
  await page.goto('/demo.html');
  const toggle = page.getByRole('button', {name:'Export', exact:true});
  await page.setViewportSize({width:768, height:1024});
  await openExports(page);
  const print = page.getByRole('button', {name:'Print / Save PDF', exact:true});
  await print.focus();
  await page.setViewportSize({width:1280, height:900});
  await expect(print).toBeVisible();
  await page.setViewportSize({width:320, height:800});
  await expect(toggle).toBeFocused();
  await expect(print).toBeHidden();
  await page.evaluate(() => {document.documentElement.style.fontSize = '200%';});
  await openExports(page);
  await expect(print).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
  const panel = await page.locator('#report-downloads').boundingBox();
  expect(panel.x).toBeGreaterThanOrEqual(0);
  expect(panel.x + panel.width).toBeLessThanOrEqual(320);
  await print.focus();
  await page.keyboard.press('Escape');
  await expect(toggle).toBeFocused();
});
