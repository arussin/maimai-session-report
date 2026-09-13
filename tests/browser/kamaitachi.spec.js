import {test, expect} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

for (const scenario of ['missing', 'partial', 'snapshot', 'lamp']) {
  test(`Kamaitachi ${scenario}: coverage and comparison context stay honest`, async ({page}, testInfo) => {
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(`/kama-${scenario}.html`);
    await expect(page.locator('.capture-context')).toContainText('current PBs at report capture');
    await expect(page.locator('.capture-context')).toContainText(scenario === 'lamp' ? 'may include other sessions' : 'gain unavailable');
    await testInfo.attach(`kamaitachi-${scenario}-scorecard.png`, {body:await page.screenshot(), contentType:'image/png'});
    for (const name of ['Scorecard', 'Scores', 'Rating pools', 'Targets']) {
      await page.getByRole('tab', {name, exact:true}).click();
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
    }
    await page.getByRole('tab', {name:'Rating pools', exact:true}).click();
    await expect(page.locator('#pool-count')).toContainText('Current PBs at capture');
    await page.locator('.pool-item:visible').first().click();
    await expect(page.locator('.chart-dialog')).toContainText('Current PBs at capture');
    await page.getByRole('button', {name:'Close score details'}).click();
    await expect(page.locator('#pool-snapshot option[value="before"]')).toHaveJSProperty('disabled', scenario !== 'lamp');
    await page.getByRole('tab', {name:'Scores', exact:true}).click();
    const rows = page.locator('#session-rows tr[data-search]:visible');
    await expect(rows).toHaveCount(scenario === 'missing' ? 150 : scenario === 'partial' ? 3 : 0);
    await expect(page.locator('.timing-balance')).toHaveText(scenario === 'partial' ? 'Partial timing data' : 'Timing unavailable');
    if (scenario === 'partial') {
      await expect(page.locator('.timing-summary')).toContainText('Timing recorded for 1 of 3 plays.');
      await expect(page.locator('.timing-line strong')).toHaveText(['0', '4']);
    }
    if (scenario !== 'lamp') {
      await expect(page.locator('#score-scope option[value="pbs"]')).toHaveJSProperty('disabled', true);
    } else {
      await page.getByRole('combobox', {name:'Show', exact:true}).selectOption('pbs');
      await expect(rows).toHaveCount(1);
      await rows.first().getByRole('button').click();
      await expect(page.locator('.detail-comparison tr').filter({has:page.getByRole('rowheader', {name:'Lamp', exact:true})})).toContainText('FULL COMBO');
      await expect(page.locator('.chart-dialog')).toContainText('since the saved baseline');
      await page.getByRole('button', {name:'Close score details'}).click();
    }
    if (scenario === 'snapshot' || scenario === 'lamp') {
      await expect(page.locator('.session-record-counts')).toContainText('Individual plays unavailable');
      await expect(page.locator('.grade-count')).toHaveCount(0);
      await page.getByRole('tab', {name:'Targets', exact:true}).click();
      await expect(page.locator('.level-group')).toHaveCount(0);
    }
    const results = await new AxeBuilder({page}).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze();
    expect(results.violations.map(value => value.id)).toEqual([]);
    expect(errors).toEqual([]);
    await testInfo.attach(`kamaitachi-${scenario}.png`, {body:await page.screenshot(), contentType:'image/png'});
  });
}
