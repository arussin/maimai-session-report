import {test,expect} from '@playwright/test';
import {readFile} from 'node:fs/promises';

const origin='http://127.0.0.1:4182';
test('installed Worker keeps the scorecard, complete pools, download and both support footers usable',async({page},testInfo)=>{
  const errors=[],external=[];
  page.on('pageerror',error=>errors.push(error.message));
  page.on('request',request=>{if(!request.url().startsWith(origin)&&!request.url().startsWith('data:'))external.push(request.url())});
  await page.route('https://buymeacoffee.com/**',route=>route.fulfill({contentType:'text/html',body:'<!doctype html><title>Synthetic provider container</title><button>Fixture</button>'}));
  await page.goto(origin+'/alpha/');
  await expect(page.getByText('SYNTHETIC ALPHA',{exact:true})).toBeVisible();
  await expect(page.getByRole('tab',{name:'Scorecard',exact:true})).toBeVisible();
  expect(external).toEqual([]);
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
    const trigger=page.getByRole('button',{name:'Buy the developer a maimai credit',exact:true});
    await expect(trigger).toHaveCount(1);
    await expect(page.locator('#support-checkout-dialog iframe')).not.toHaveAttribute('src');
    await trigger.focus();await page.keyboard.press('Enter');
    await expect(page.getByRole('dialog')).toBeVisible();
    await expect(page.getByRole('link',{name:'Open separately ↗',exact:true})).toHaveAttribute('href','https://buymeacoffee.com/russin');
    await page.keyboard.press('Escape');
    await expect(page.getByRole('dialog')).not.toBeVisible();
    await expect(trigger).toBeFocused();
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
  }
  await expect(page.getByRole('heading',{name:'No archived sessions yet'})).toBeVisible();
  await page.goto(origin+'/beta/');
  await expect(page.getByText('SYNTHETIC BETA',{exact:true})).toBeVisible();
  await expect(page.getByText('SYNTHETIC ALPHA',{exact:true})).toHaveCount(0);
  expect(errors).toEqual([]);
  await testInfo.attach('installed-scorecard.png',{body:await page.screenshot(),contentType:'image/png'});
});
