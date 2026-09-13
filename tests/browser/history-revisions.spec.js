import {openExports} from './export-controls.js';
import {test,expect} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import {readFile} from 'node:fs/promises';
import {withHistoryNavigation} from '../../deploy/cloudflare/src/history.js';

for (const presentation of ['corrected','original','unavailable']) {
  test(`historical ${presentation} context keeps original controls usable`,async({page})=>{
    const source=await readFile(new URL('generated/complete.html',import.meta.url),'utf8');
    const capture={id:'a'.repeat(64),sort_ms:1780000000000,timezone:'UTC',score_count:8,b50_key:'synthetic-b50'};
    const html=withHistoryNavigation(source,{prefix:'/maimai/',capture,presentation});
    const errors=[];page.on('pageerror',e=>errors.push(e.message));
    await page.setContent(html);
    const context=page.locator('.history-context');
    await expect(context).toContainText('Archived session');
    if(presentation==='corrected'){
      await expect(context).toContainText('Corrected rating contributions');
      const link=page.getByRole('link',{name:'Original report',exact:true});
      await expect(link).toHaveAttribute('href',`/maimai/history/c/${capture.id}/?view=original`);
      await link.focus();await expect(link).toBeFocused();
    } else if(presentation==='original'){
      await expect(context).toContainText('Original published report');
      await expect(page.getByRole('link',{name:'Corrected report',exact:true})).toHaveAttribute('href',`/maimai/history/c/${capture.id}/`);
    } else {
      await expect(context.getByRole('status')).toContainText('Corrected version unavailable');
    }
    await openExports(page);
    await expect(page.getByRole('link',{name:'Download B50',exact:true})).toHaveAttribute('href',`/maimai/history/c/${capture.id}/b50.webp`);
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
    const axe=await new AxeBuilder({page}).include('.history-context').analyze();
    expect(axe.violations).toEqual([]);
    expect(errors).toEqual([]);
  });
}
