import {expect} from '@playwright/test';

// Exercise the release-gated UI with synthetic documents. Never contact Stripe.
export async function enableSupportFixture(context) {
  await context.route(/^http:\/\/127\.0\.0\.1:/, async route => {
    const response = await route.fetch();
    if (!(response.headers()['content-type'] || '').includes('text/html')) {
      await route.fulfill({response}); return;
    }
    await route.fulfill({response, body: (await response.text()).replace(
      'const supportAvailable = false;', 'const supportAvailable = true;')});
  });
  const requests = [];
  await context.route('https://maimai.party/support.html', async route => {
    requests.push({url: route.request().url(), referer: route.request().headers().referer || ""});
    await route.fulfill({contentType: 'text/html', body:
      '<!doctype html><html lang="en"><title>Synthetic support window</title><h1>Support fixture</h1></html>'});
  });
  return requests;
}

export async function verifySupportPopup(page, requests) {
  const originalUrl = page.url();
  const originalData = await page.locator('#report-data').textContent();
  const github = page.getByRole('link', {name: 'View on GitHub', exact: true});
  await expect(github).toHaveAttribute('href', 'https://github.com/arussin/maimai-session-report');
  await expect(github).toHaveAttribute('rel', 'noopener noreferrer');
  await expect(page.locator('.support-card + .footer')).toHaveCount(1);
  await expect(page.locator('iframe')).toHaveCount(0);
  const support = page.getByRole('link', {name: 'Support maimai.party', exact: true});
  await expect(support).toHaveAttribute('href', 'https://maimai.party/support.html');
  await expect(page.locator('.support-button-provider')).toContainText('Powered by');
  await expect(page.getByRole('img', {name: 'Stripe', exact: true})).toBeVisible();
  const before = requests.length;
  await support.focus();
  const pending = page.context().waitForEvent('page');
  await page.keyboard.press('Enter');
  const popup = await pending;
  await expect(popup.getByRole('heading')).toHaveText('Support fixture');
  expect(requests.slice(before)).toEqual([{url: 'https://maimai.party/support.html', referer: ""}]);
  expect(await popup.evaluate(() => ({opener: window.opener === null, referrer: document.referrer})))
    .toEqual({opener: true, referrer: ''});
  await popup.close();
  await expect(page).toHaveURL(originalUrl);
  expect(await page.locator('#report-data').textContent()).toBe(originalData);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
}
