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
  await expect(page.getByText('B50 not retained',{exact:true})).toBeVisible();
  await expect(page.getByRole('link',{name:'Download B50',exact:true})).toHaveCount(0);
  await page.getByRole('link',{name:'History',exact:true}).click();
  const results=await new AxeBuilder({page}).analyze();
  expect(results.violations).toEqual([]);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
});

test('archived checkout stays lazy and closes with Escape',async({page})=>{
  const unexpected=[];
  page.on('request',request=>{if(!request.url().startsWith(origin)&&!request.url().startsWith('data:'))unexpected.push(request.url())});
  await page.goto(origin+'/maimai/history');
  await page.locator('.capture').first().click();
  await expect(page.locator('#support-checkout-dialog iframe')).not.toHaveAttribute('src');
  expect(unexpected).toEqual([]);
  // Container behavior only: no provider request or payment flow is exercised.
  await page.route('https://buymeacoffee.com/**',route=>route.fulfill({status:200,contentType:'text/html',body:'<p>Synthetic checkout provider container</p>'}));
  const trigger=page.getByRole('button',{name:'Buy the developer a maimai credit',exact:true});
  await trigger.click();
  await expect(page.locator('#support-checkout-dialog')).toBeVisible();
  await expect(page.locator('#support-checkout-dialog iframe')).toHaveAttribute('referrerpolicy','no-referrer');
  await page.keyboard.press('Escape');
  await expect(page.locator('#support-checkout-dialog')).not.toBeVisible();
  await expect(trigger).toBeFocused();
});

for (const empty of [false,true]) test(`history footer checkout is lazy and keyboard accessible (${empty?'empty':'populated'} archive)`,async({page})=>{
  await page.emulateMedia({reducedMotion:'reduce'});
  const external=[],errors=[];
  page.on('pageerror',error=>errors.push(error.message));
  page.on('request',request=>{if(!request.url().startsWith(origin)&&!request.url().startsWith('data:'))external.push(request.url())});
  // Container behavior only. The provider is mocked; no payment is submitted.
  await page.route('https://buymeacoffee.com/**',route=>route.fulfill({status:200,contentType:'text/html',body:'<p>Synthetic checkout container</p>'}));
  await page.goto(origin+'/maimai/history'+(empty?'?fixture=empty':''));
  if(empty)await expect(page.getByRole('heading',{name:'No archived sessions yet'})).toBeVisible();
  const trigger=page.getByRole('button',{name:'Buy the developer a maimai credit',exact:true});
  const dialog=page.getByRole('dialog',{name:'Buy the developer a maimai credit',exact:true});
  const frame=page.locator('#support-checkout-dialog iframe');
  await expect(trigger).toHaveCount(1);
  await expect(page.locator('.support-card + .footer')).toHaveCount(1);
  await expect(frame).not.toHaveAttribute('src');
  expect(external).toEqual([]);
  await trigger.focus();
  await page.keyboard.press('Enter');
  await expect(dialog).toBeVisible();
  const close=page.getByRole('button',{name:'Close support checkout'});
  await expect(close).toBeFocused();
  await expect(frame).toHaveAttribute('referrerpolicy','no-referrer');
  await expect(frame).toHaveAttribute('loading','lazy');
  await expect(frame).toHaveAttribute('allow','payment *');
  await expect(frame).toHaveAttribute('src',/^https:\/\/buymeacoffee\.com\/widget\/page\/russin\?/);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
  expect(await dialog.evaluate(el=>{const r=el.getBoundingClientRect();return r.left>=0&&r.right<=innerWidth&&r.top>=0&&r.bottom<=innerHeight})).toBeTruthy();
  await close.click();
  await expect(dialog).not.toBeVisible();
  await expect(trigger).toBeFocused();
  await trigger.click();
  await page.keyboard.press('Escape');
  await expect(dialog).not.toBeVisible();
  await expect(trigger).toBeFocused();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
  const results=await new AxeBuilder({page}).analyze();
  expect(results.violations).toEqual([]);
  expect(errors).toEqual([]);
  await trigger.scrollIntoViewIfNeeded();
  await page.screenshot({path:test.info().outputPath(`history-footer-${empty?'empty':'populated'}.png`)});
});
