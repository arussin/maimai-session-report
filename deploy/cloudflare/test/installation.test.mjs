import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import {mkdtemp,readFile,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import test from 'node:test';
import {installationFixture} from './installation-fixture.mjs';

const root=fileURLToPath(new URL('../../../',import.meta.url));
test('packaged Worker serves two isolated installations, exact retained bytes and honest empty history',async()=>{
  const directory=await mkdtemp(path.join(tmpdir(),'maimai-installation-'));
  try {
    const run=spawnSync(process.env.PYTHON || (process.platform === 'win32' ? 'python' : 'python3'),['-m','tests.prepare_installation',directory],{cwd:root,encoding:'utf8',env:{...process.env,PYTHONPATH:path.join(root,'src')}});
    assert.equal(run.status,0,run.stderr);
    for(const owner of ['alpha','beta']) {
      const stage=path.join(directory,owner,'staged');
      const {mf,config}=await installationFixture(stage);
      try {
        const origin=config.vars.HISTORY_ORIGIN, prefix=config.vars.HISTORY_PREFIX;
        const response=await mf.dispatchFetch(origin+prefix);
        assert.equal(response.status,200);
        assert.match(await response.text(),new RegExp('SYNTHETIC '+owner.toUpperCase()));
        const b50=await mf.dispatchFetch(origin+prefix+'b50.webp');
        assert.deepEqual(Buffer.from(await b50.arrayBuffer()),await readFile(path.join(stage,'b50.webp')));
        assert.equal((await mf.dispatchFetch(origin+'/other/')).status,404);
        assert.equal((await mf.dispatchFetch('https://foreign.example.invalid'+prefix)).status,404);
        const head=await mf.dispatchFetch(origin+prefix,{method:'HEAD'});
        assert.equal(head.status,200);assert.equal(await head.text(),'');
        assert.equal((await mf.dispatchFetch(origin+prefix,{method:'POST'})).status,405);
        const history=await mf.dispatchFetch(origin+prefix+'history');
        assert.equal(history.status,200);
        assert.match(await history.text(),/No archived sessions/i);
        assert.match(response.headers.get('Content-Security-Policy'),/connect-src 'none'/);
        assert.match(response.headers.get('Content-Security-Policy'),/frame-src https:\/\/buymeacoffee.com/);
        assert.equal(response.headers.get('Referrer-Policy'),'no-referrer');
      } finally {await mf.dispose();}
    }
  } finally {await rm(directory,{recursive:true,force:true});}
});
