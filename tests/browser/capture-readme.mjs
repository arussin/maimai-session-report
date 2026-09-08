// Explicit local documentation build. Uses only the bundled fictional demo.
import {chromium} from '@playwright/test';
import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import {mkdir,readFile} from 'node:fs/promises';
import {fileURLToPath, pathToFileURL} from 'node:url';
import path from 'node:path';

const root=fileURLToPath(new URL('../../',import.meta.url));
const python=process.env.PYTHON || (process.platform==='win32'?'python':'python3');
const run=spawnSync(python,['-m','maimai_report','demo','--output','docs/sample-report.html'],{
  cwd:root,encoding:'utf8',env:{...process.env,PYTHONPATH:path.join(root,'src')}
});
assert.equal(run.status,0,run.stderr);
const sample=path.join(root,'docs/sample-report.html');
assert.doesNotMatch(await readFile(sample,'utf8'),/https?:\/\//i);
await mkdir(path.join(root,'docs/images'),{recursive:true});
const browser=await chromium.launch();
try {
  for(const [name,width,height] of [['desktop',1280,1044],['mobile',390,844]]) {
    const page=await browser.newPage({viewport:{width,height},reducedMotion:'reduce'});
    const errors=[],external=[];
    page.on('pageerror',error=>errors.push(error.message));
    await page.route(/^https?:/,route=>{external.push(route.request().url());return route.abort()});
    await page.goto(pathToFileURL(sample).href);
    await page.getByRole('heading',{name:'Sample Player',exact:true}).waitFor();
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
    await page.screenshot({path:path.join(root,`docs/images/demo-${name}.png`)});
    assert.deepEqual(errors,[]);assert.deepEqual(external,[]);
    await page.close();
  }
} finally {await browser.close()}
console.log('README previews generated from fictional offline fixtures only.');
