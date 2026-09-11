import {test, expect} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

const rows = page => page.locator('#session-rows tr[data-search]:visible');
const heading = (page, key) => page.locator(`th:has(button[data-score-sort="${key}"])`);
const button = (page, key) => page.locator(`button[data-score-sort="${key}"]`);
const order = page => rows(page).locator('button[data-detail-index]').evaluateAll(
  elements => elements.map(element => Number(element.dataset.detailIndex))
);
const recent = [0,8,12,9,10,11,2,3,1,4,5,6,7];

// Independent authored expectations, not a second implementation of the sort.
// The last three numeric entries exercise null, empty and invalid values; equal
// values retain source order even when switching direction or another column.
const sorts = [
  {key:'song', label:'Song', first:'ascending', asc:'song-asc', desc:'song-desc',
    ascending:[0,2,3,4,5,6,7,8,9,1,11,12,10], descending:[12,11,1,9,8,7,6,5,4,3,0,2,10]},
  {key:'chart', label:'Chart', first:'ascending', asc:'chart-asc', desc:'chart-desc',
    ascending:[3,4,12,0,2,8,1,11,7,9,5,6,10], descending:[6,5,7,1,11,8,0,2,12,9,4,3,10]},
  {key:'achievement', label:'Achievement', first:'descending', asc:'achievement-asc', desc:'achievement',
    ascending:[4,0,12,10,11,9,8,2,3,1,5,6,7], descending:[1,2,3,8,9,11,10,12,0,4,5,6,7]},
  {key:'grade', label:'Grade', first:'descending', asc:'grade-asc', desc:'grade-desc',
    ascending:[0,4,12,11,10,9,8,7,3,2,1,5,6], descending:[1,2,3,7,8,9,10,11,12,4,0,5,6]},
  {key:'rating', label:'Rating', first:'descending', asc:'rating-asc', desc:'rating',
    ascending:[4,0,3,12,10,11,9,8,1,2,5,6,7], descending:[1,2,8,9,11,10,12,3,0,4,5,6,7]},
  {key:'timing', label:'Fast / Slow', first:'ascending', asc:'timing-asc', desc:'timing-desc',
    ascending:[4,0,3,11,12,2,8,10,1,9,5,6,7], descending:[1,2,0,3,11,12,8,10,4,9,5,6,7]},
];

async function expectSort(page, sort, direction) {
  expect(await order(page)).toEqual(sort[direction]);
  await expect(heading(page, sort.key)).toHaveAttribute('scope', 'col');
  await expect(heading(page, sort.key)).toHaveAttribute('aria-sort', direction);
  await expect(page.locator('.session-table th[aria-sort]')).toHaveCount(1);
  const next = direction === 'ascending' ? 'descending' : 'ascending';
  await expect(button(page, sort.key)).toHaveAccessibleName(`Sort by ${sort.label}, ${next}`);
  await expect(page.locator('#score-sort')).toHaveValue(direction === 'ascending' ? sort.asc : sort.desc);
}

test.beforeEach(async ({page}) => {
  await page.route('**/*', route => {
    const url = new URL(route.request().url());
    return url.hostname === '127.0.0.1' ? route.continue() : route.abort();
  });
  await page.goto('/score-sort.html');
  await page.getByRole('tab', {name:'Scores', exact:true}).click();
  await expect(rows(page)).toHaveCount(13);
});

test.describe('original table headers', () => {
test.use({viewport:{width:1280,height:900}});

for (const sort of sorts) {
  test(`${sort.label} header sorts both directions with stable ties and missing values last`, async ({page}) => {
    expect(await order(page)).toEqual(recent);
    await expect(page.locator('.session-table th[aria-sort]')).toHaveCount(0);
    await expect(button(page, sort.key)).toHaveAccessibleName(`Sort by ${sort.label}, ${sort.first}`);
    await button(page, sort.key).click();
    await expectSort(page, sort, sort.first);
    const second = sort.first === 'ascending' ? 'descending' : 'ascending';
    await button(page, sort.key).click();
    await expectSort(page, sort, second);
    // A different prior ordering must not become the tie-break order.
    await page.locator('#score-sort').selectOption('oldest');
    await page.locator('#score-sort').selectOption(sort.desc);
    await expectSort(page, sort, 'descending');
    await page.locator('#score-sort').selectOption(sort.asc);
    await expectSort(page, sort, 'ascending');
  });
}

test('latest and oldest sort numeric timestamps, keeping ties stable and missing timestamps last', async ({page}) => {
  expect(await order(page)).toEqual(recent);
  await page.locator('#score-sort').selectOption('oldest');
  expect(await order(page)).toEqual([4,1,2,3,11,10,9,12,8,0,5,6,7]);
  await expect(page.locator('.session-table th[aria-sort]')).toHaveCount(0);
  await button(page, 'achievement').click();
  await expect(heading(page, 'achievement')).toHaveAttribute('aria-sort', 'descending');
  await page.locator('#score-sort').selectOption('recent');
  expect(await order(page)).toEqual(recent);
  await expect(page.locator('.session-table th[aria-sort]')).toHaveCount(0);
});

test('displayed level and plus bands precede retained constants without inventing missing values', async ({page}) => {
  await page.goto('/score-sort-levels.html');
  await page.getByRole('tab', {name:'Scores', exact:true}).click();
  await expect(rows(page)).toHaveCount(10);
  await button(page, 'chart').click();
  expect(await order(page)).toEqual([0,2,9,7,3,1,6,8,4,5]);
  await expect(heading(page, 'chart')).toHaveAttribute('aria-sort', 'ascending');
  await button(page, 'chart').click();
  expect(await order(page)).toEqual([4,8,3,7,1,2,0,9,6,5]);
  await expect(heading(page, 'chart')).toHaveAttribute('aria-sort', 'descending');
});

test('header keyboard activation and dropdown keep a single accessible sort state', async ({page}) => {
  const song = sorts.find(sort => sort.key === 'song');
  await button(page, 'song').focus();
  await page.keyboard.press('Enter');
  await expectSort(page, song, 'ascending');
  await expect(button(page, 'song')).toBeFocused();
  await page.keyboard.press('Space');
  await expectSort(page, song, 'descending');
  await expect(button(page, 'song')).toBeFocused();
  await page.locator('#score-sort').selectOption('rating');
  await expectSort(page, sorts.find(sort => sort.key === 'rating'), 'descending');
  await expect(heading(page, 'song')).not.toHaveAttribute('aria-sort');
  await button(page, 'rating').focus();
  await page.keyboard.press('Enter');
  await expectSort(page, sorts.find(sort => sort.key === 'rating'), 'ascending');
});

test('PB gain handles new, positive, zero, negative and missing comparisons in both directions', async ({page}) => {
  await expect(button(page, 'gain')).toBeHidden();
  await page.locator('#score-scope').selectOption('pbs');
  await expect(rows(page)).toHaveCount(10);
  const gain = {key:'gain', label:'PB gain', asc:'gain-asc', desc:'gain-desc',
    ascending:[4,3,9,2,1,0,5,6,7,8], descending:[0,1,2,3,9,4,5,6,7,8]};
  await expect(button(page, 'gain')).toBeVisible();
  await button(page, 'gain').click();
  await expectSort(page, gain, 'descending');
  for (const [index, expected] of [[1,'+20'], [3,'0'], [4,'-20'], [5,'—'], [6,'—'], [7,'—'], [8,'—'], [9,'0']]) {
    await expect(page.locator(`#session-rows tr:has(button[data-detail-index="${index}"]) [data-label="PB gain"]`)).toHaveText(expected);
  }
  await button(page, 'gain').focus();
  await page.keyboard.press('Space');
  await expectSort(page, gain, 'ascending');
  await page.locator('#score-sort').selectOption('gain-desc');
  await expectSort(page, gain, 'descending');
  await page.locator('#score-scope').selectOption('plays');
  await expect(page.locator('#score-sort')).toHaveValue('recent');
  await expect(button(page, 'gain')).toBeHidden();
  await expect(page.locator('.session-table th[aria-sort]')).toHaveCount(0);
  expect(await order(page)).toEqual(recent);
});

test('search, chart filter and scopes preserve exact repeated-play detail identity', async ({page}) => {
  const search = page.getByRole('searchbox', {name:'Filter session scores'});
  await search.fill('Twin 9');
  await page.locator('#score-difficulty').selectOption('diff-expert');
  await button(page, 'achievement').click();
  expect(await order(page)).toEqual([2,0]);
  await expect(page.locator('#score-count')).toHaveText('2 of 13 plays');
  let opener = rows(page).first().getByRole('button');
  await expect(opener).toHaveAttribute('data-detail-source', 'plays');
  await opener.click();
  const dialog = page.locator('.chart-dialog');
  await expect(dialog).toContainText('99.9000%');
  await expect(dialog.locator('.detail-facts')).toContainText('FULL COMBO');
  await expect(dialog.locator('.judgement-grid dd').first()).toHaveText('102');
  await page.keyboard.press('Escape');
  await expect(opener).toBeFocused();
  await page.locator('#score-sort').selectOption('rating-asc');
  expect(await order(page)).toEqual([0,2]);
  opener = rows(page).first().getByRole('button');
  await opener.click();
  await expect(dialog).toContainText('9.5000%');
  await expect(dialog.locator('.judgement-grid dd').first()).toHaveText('100');
  await page.keyboard.press('Escape');
  await expect(opener).toBeFocused();
  await page.locator('#score-scope').selectOption('pbs');
  await expect(search).toHaveValue('Twin 9');
  await expect(page.locator('#score-difficulty')).toHaveValue('diff-expert');
  expect(await order(page)).toEqual([0]);
  await button(page, 'gain').click();
  await rows(page).first().getByRole('button').click();
  await expect(dialog).toContainText('PB comparison');
  await expect(dialog.locator('.detail-comparison')).toContainText('99.9000%');
  await expect(dialog.locator('.judgement-grid dd').first()).toHaveText('102');
  await page.keyboard.press('Escape');
  await page.locator('#score-scope').selectOption('plays');
  expect(await order(page)).toEqual([0,2]);
  await expect(page.locator('#score-sort')).toHaveValue('recent');
  await expect(search).toHaveValue('Twin 9');
  await expect(page.locator('#score-difficulty')).toHaveValue('diff-expert');
  await search.fill('no-matching-synthetic-score');
  await button(page, 'chart').click();
  await expect(rows(page)).toHaveCount(0);
  await expect(page.locator('#score-count')).toHaveText('0 of 13 plays');
  await expect(heading(page, 'chart')).toHaveAttribute('aria-sort', 'ascending');
  await search.fill('Twin 9');
  expect(await order(page)).toEqual([0,2]);
});

});

test('original table and mobile cards retain accessible sorting without a separate header grid', async ({page}, testInfo) => {
  await page.emulateMedia({reducedMotion:'reduce'});
  for (const scope of ['plays', 'pbs']) {
    await page.locator('#score-scope').selectOption(scope);
    for (const enlarged of [false, true]) {
      await page.evaluate(value => { document.documentElement.style.fontSize = value ? '200%' : ''; }, enlarged);
      const cardLayout = await page.locator('.session-table thead').evaluate(element => getComputedStyle(element).display === 'none');
      const headers = page.locator('button[data-score-sort]:visible');
      await expect(headers).toHaveCount(cardLayout ? 0 : scope === 'pbs' ? 7 : 6);
      if (!cardLayout) {
        const cells = await page.locator('.session-table th:visible').evaluateAll(elements => elements.map(element => ({display:getComputedStyle(element).display,top:element.getBoundingClientRect().top})));
        expect(cells.every(cell => cell.display === 'table-cell')).toBe(true);
        expect(new Set(cells.map(cell => Math.round(cell.top))).size).toBe(1);
      }
      const layout = await page.evaluate(() => {
        const viewport = innerWidth;
        const overflow = [...document.querySelectorAll('.score-controls label, .score-controls input, .score-controls select')]
          .filter(element => element.getClientRects().length)
          .map(element => ({text:element.textContent.trim(), ...element.getBoundingClientRect().toJSON()}))
          .filter(rect => rect.left < -1 || rect.right > viewport + 1);
        return {viewport, documentWidth:document.documentElement.scrollWidth, overflow};
      });
      expect(layout.documentWidth, JSON.stringify(layout)).toBeLessThanOrEqual(layout.viewport + 1);
      expect(layout.overflow).toEqual([]);
      if (cardLayout) {
        await page.locator('#score-sort').focus();
        await expect(page.locator('#score-sort')).toBeFocused();
        await page.locator('#score-sort').selectOption('song-asc');
      } else {
        await button(page, 'song').click();
      }
      await expect(heading(page, 'song')).toHaveAttribute('aria-sort', /ascending|descending/);
    }
  }
  await page.evaluate(() => {document.documentElement.style.fontSize='';});
  await page.locator('#score-scope').selectOption('plays');
  await page.locator('.score-detail-section').scrollIntoViewIfNeeded();
  await page.screenshot({path:testInfo.outputPath('score-original-layout.png')});
  const results = await new AxeBuilder({page}).include('#session-view').withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();
  expect(results.violations.map(violation => ({id:violation.id, nodes:violation.nodes.map(node => node.target)}))).toEqual([]);
});
