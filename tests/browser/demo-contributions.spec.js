import {test, expect} from './fixtures.js';
import {readFile} from 'node:fs/promises';

for (const scenario of ['complete', 'empty', 'incomplete']) {
  test(`${scenario}: demo rating contributions reconcile`, async ({page}) => {
    const model = JSON.parse(await readFile(new URL(`generated/${scenario}.json`, import.meta.url), 'utf8'));
    await page.goto(`/${scenario}.html`);
    const highlights = page.locator('.overview-scores');
    await expect(highlights).not.toContainText('Rating contributions unavailable');
    if (scenario === 'empty') {
      await expect(highlights).toContainText('No rating gains this session.');
      await expect(highlights.locator('.score-row')).toHaveCount(0);
    } else {
      await expect(highlights.locator('.contribution-summary')).toContainText(`of +${model.delta.reconstructedRating.toLocaleString('en-US')} verified session rating gain.`);
      const gains = await highlights.locator('.score-gain').allTextContents();
      expect(gains.length).toBeGreaterThan(0);
      expect(gains.every(text => text.includes('rating gain'))).toBe(true);
    }
  });
}
