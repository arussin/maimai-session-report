import {test,expect} from './fixtures.js';
import {enablePartyFixture} from './party-fixture.js';

test('synthetic preview recipient receives player bytes only after explicit acceptance',async({page,context,baseURL})=>{
  await enablePartyFixture(context,new URL(baseURL).origin);
  await page.goto('/complete.html');
  const popupPromise=context.waitForEvent('page');
  await page.getByRole('link',{name:'Open in maimai.party',exact:true}).click();
  const popup=await popupPromise;
  await expect(popup.locator('#status')).toHaveText('Synthetic offer ready; no score bytes received');
  await popup.getByRole('button',{name:'Import synthetic data'}).click();
  await expect(popup.locator('#status')).toHaveText('Synthetic player bytes received locally');
  await expect(page.locator('.party-transfer-status')).toHaveText('Your data is ready in maimai.party.');
});
