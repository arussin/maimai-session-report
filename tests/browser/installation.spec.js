import {enableSupportFixture, verifySupportDialog} from './support-dialog.js';
import {openExports} from './export-controls.js';
import {test,expect} from './fixtures.js';
import {readFile} from 'node:fs/promises';

const origin='http://127.0.0.1:4182';
test('installed Worker keeps the scorecard, complete pools, download and both support footers usable',async({page,context},testInfo)=>{
  const errors=[],external=[];
  page.on('pageerror',error=>errors.push(error.message));
  page.on('request',request=>{if(!request.url().startsWith(origin)&&!request.url().startsWith('data:'))external.push(request.url())});
  const requests=await enableSupportFixture(context);
  await page.goto(origin+'/alpha/');
  await expect(page.getByText('SYNTHETIC ALPHA',{exact:true})).toBeVisible();
  await expect(page.getByRole('tab',{name:'Scorecard',exact:true})).toBeVisible();
  expect(external).toEqual([]);
  await openExports(page);
  const filePromise=page.waitForEvent('download');
  await page.getByRole('link',{name:'Download B50',exact:true}).click();
  const file=await filePromise;
  expect(await file.failure()).toBeNull();
  expect(await readFile(await file.path())).toEqual(await readFile(new URL('generated/installations/alpha/staged/b50.webp',import.meta.url)));
  await page.getByRole('tab',{name:'Rating pools',exact:true}).click();
  await expect(page.locator('.pool-item:visible')).toHaveCount(50);
  await page.getByRole('tab',{name:'Scores',exact:true}).click();
  await page.locator('#session-search').fill('no synthetic match');
  await expect(page.locator('#session-rows tr[data-search]:visible')).toHaveCount(0);
  for(const url of ['/alpha/','/alpha/history']) {
    await page.goto(origin+url);
    await verifySupportDialog(page, requests);
  }
  await expect(page.getByRole('heading',{name:'No archived sessions yet'})).toBeVisible();
  await page.goto(origin+'/beta/');
  await expect(page.getByText('SYNTHETIC BETA',{exact:true})).toBeVisible();
  await expect(page.getByText('SYNTHETIC ALPHA',{exact:true})).toHaveCount(0);
  expect(errors).toEqual([]);
  await testInfo.attach('installed-scorecard.png',{body:await page.screenshot(),contentType:'image/png'});
});
