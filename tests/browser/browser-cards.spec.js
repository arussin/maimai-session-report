import {test,expect} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
test('prepared report cards remain offline and link only public chart identities',async({page})=>{
  const remote=[];page.on('request',request=>{if(!request.url().startsWith('http://127.0.0.1:4180'))remote.push(request.url());});
  await page.goto('/browser-cards-links.html');await page.locator('#tab-targets').click();
  await expect(page.locator('.prepared-card')).toHaveCount(1);
  const link=page.getByRole('link',{name:'Explore chart'});
  await expect(link).toHaveAttribute('href','https://charts.example.test/browser/?catalog=synthetic&version=one&chart=chart%3Aone');
  await expect(link).toHaveAttribute('rel','noopener noreferrer');
  await page.locator('.prepared-session-details summary').click();await expect(page.locator('.practice-layout')).toBeVisible();
  expect(remote).toEqual([]);
  const audit=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();
  expect(audit.violations).toEqual([]);
});
test('prepared report cards work without a hosted browser address',async({page})=>{
  await page.goto('/browser-cards-offline.html');await page.locator('#tab-targets').click();
  await expect(page.locator('.prepared-card')).toHaveCount(1);await expect(page.getByRole('link',{name:'Explore chart'})).toHaveCount(0);
  await page.evaluate(()=>document.documentElement.style.fontSize='200%');
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
});
