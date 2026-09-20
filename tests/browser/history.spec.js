import {enableSupportFixture, verifySupportDialog} from './support-dialog.js';
import {openExports} from './export-controls.js';
import {test,expect} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
const origin='http://127.0.0.1:4181';
test('history dates open the full retained report and return to latest',async({page})=>{
  const errors=[];page.on('pageerror',error=>errors.push(error.message));
  await page.goto(origin+'/maimai/history');
  await expect(page.getByRole('heading',{name:'Session history',exact:true})).toBeVisible();
  await expect(page.locator('.capture')).toHaveCount(20);
  await expect(page.locator('body')).toHaveJSProperty('scrollWidth',await page.evaluate(()=>window.innerWidth));
  const first=page.locator('.capture').first();
  const href=await first.getAttribute('href');
  await first.click();
  await expect(page.locator('.history-context')).toContainText('Archived session');
  await expect(page.getByRole('tab')).toHaveCount(4);
  for(const tab of await page.getByRole('tab').all()){
    await tab.click();await expect(tab).toHaveAttribute('aria-selected','true');
    await expect(page).toHaveURL(origin+href);
  }
  await openExports(page);
  const download=page.getByRole('link',{name:'Download B50',exact:true});
  await expect(download).toHaveAttribute('href',href+'b50.webp');
  const [file]=await Promise.all([page.waitForEvent('download'),download.click()]);
  expect(await file.failure()).toBeNull();
  await page.getByRole('link',{name:'Latest session',exact:true}).click();
  await expect(page).toHaveURL(origin+'/maimai/');
  expect(errors).toEqual([]);
});

test('history pagination, unavailable B50, keyboard access and reduced motion',async({page})=>{
  await page.emulateMedia({reducedMotion:'reduce'});
  await page.goto(origin+'/maimai/history');
  const firstPageIds=await page.locator('.capture').evaluateAll(nodes=>nodes.map(n=>n.getAttribute('href')));
  await page.getByRole('link',{name:'Older sessions'}).click();
  await expect(page.locator('.capture')).toHaveCount(2);
  const olderIds=await page.locator('.capture').evaluateAll(nodes=>nodes.map(n=>n.getAttribute('href')));
  expect(olderIds.every(id=>!firstPageIds.includes(id))).toBeTruthy();
  await page.locator('.capture').last().focus();
  await page.keyboard.press('Enter');
  await openExports(page);
  await expect(page.getByText('B50 not retained',{exact:true})).toBeVisible();
  await expect(page.getByRole('link',{name:'Download B50',exact:true})).toHaveCount(0);
  await page.getByRole('link',{name:'History',exact:true}).click();
  const results=await new AxeBuilder({page}).analyze();
  expect(results.violations).toEqual([]);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
});

test('archived support opens in the report dialog without changing the selected session', async ({page, context}) => {
  const requests = await enableSupportFixture(context);
  await page.goto(origin+'/maimai/history');
  const links = await page.locator('.capture').evaluateAll(nodes => nodes.map(node => node.getAttribute('href')));
  await page.locator('.capture').first().click();
  expect(requests).toEqual([]);
  await verifySupportDialog(page, requests);
  await page.getByRole('link', {name:'History', exact:true}).click();
  expect(await page.locator('.capture').evaluateAll(nodes => nodes.map(node => node.getAttribute('href')))).toEqual(links);
});

for (const empty of [false,true]) test(`history footer links work for ${empty?'empty':'populated'} archives`, async ({page, context}) => {
  const requests = await enableSupportFixture(context);
  await page.goto(origin+'/maimai/history'+(empty?'?fixture=empty':''));
  if (empty) await expect(page.getByRole('heading', {name:'No archived sessions yet'})).toBeVisible();
  expect(requests).toEqual([]);
  await verifySupportDialog(page, requests);
  expect((await new AxeBuilder({page}).analyze()).violations).toEqual([]);
});
