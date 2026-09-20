import {expect} from '@playwright/test';

// Exercise the shipped native dialog against synthetic Stripe and API responses.
export async function enableSupportFixture(context) {
  const requests = [];
  await context.route('https://maimai.party/api/support/*', async route => {
    const request = route.request();
    const headers = {'Access-Control-Allow-Origin': request.headers().origin || '*',
      'Access-Control-Allow-Methods': 'POST', 'Access-Control-Allow-Headers': 'content-type'};
    if (request.method() === 'OPTIONS') return route.fulfill({status: 204, headers});
    requests.push({url: request.url(), referer: request.headers().referer || '', body: request.postDataJSON()});
    await route.fulfill({headers, json: {status: 'open', session: 'cs_test_synthetic123456789', clientSecret: 'synthetic-secret'}});
  });
  await context.route('https://js.stripe.com/dahlia/stripe.js', route => route.fulfill({contentType: 'text/javascript', body: `
    window.Stripe = () => ({createEmbeddedCheckoutPage: async options => {
      await options.fetchClientSecret(); let frame;
      return {mount(node) { frame = document.createElement('iframe'); frame.title = 'Embedded checkout';
        frame.src = 'https://checkout.stripe.com/fixture'; frame.allow = 'payment'; node.append(frame); },
        destroy() { frame?.remove(); }};
    }});
  `}));
  await context.route('https://checkout.stripe.com/fixture', route => route.fulfill({contentType: 'text/html', body:
    '<!doctype html><html lang="en"><title>Synthetic Stripe</title><h1>Native checkout fixture</h1><label>Amount <input value="5.00"></label></html>'}));
  await context.route('https://maimai.party/support.html', () => {
    throw new Error('The report must not navigate to an external checkout window');
  });
  return requests;
}

export async function verifySupportDialog(page, requests) {
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
  const resuming = await page.evaluate(() => !!JSON.parse(sessionStorage.getItem('support.checkout.v2.session-report'))?.session);
  const pages = page.context().pages().length;
  await support.focus();
  await page.keyboard.press('Enter');
  const dialog = page.getByRole('dialog', {name: 'Support maimai.party'});
  await expect(dialog).toBeVisible();
  await expect(dialog.locator('iframe')).toHaveCount(1);
  await expect(page.frameLocator('iframe[title="Embedded checkout"]').getByRole('heading')).toHaveText('Native checkout fixture');
  expect(page.context().pages()).toHaveLength(pages);
  expect(requests.slice(before).map(request => request.url.split('/').at(-1)))
    .toEqual(resuming ? ['status', 'checkout'] : ['checkout']);
  const created = requests.at(-1);
  expect(created.url).toBe('https://maimai.party/api/support/checkout');
  expect(created.referer).toBe('');
  expect(Object.keys(created.body).sort()).toEqual(resuming ? ['attempt', 'project', 'session'] : ['attempt', 'project']);
  expect(created.body.project).toBe('session-report');
  await dialog.getByRole('button', {name: 'Close support checkout'}).click();
  await expect(dialog).not.toBeVisible();
  await expect(page.locator('iframe')).toHaveCount(0);
  await expect(support).toBeFocused();
  await support.click();
  await expect(dialog.locator('iframe')).toHaveCount(1);
  expect(requests.at(-1).body.attempt).toBe(created.body.attempt);
  expect(requests.at(-1).body.session).toBe('cs_test_synthetic123456789');
  await page.keyboard.press('Escape');
  await expect(dialog).not.toBeVisible();
  await expect(page).toHaveURL(originalUrl);
  expect(await page.locator('#report-data').textContent()).toBe(originalData);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
}
