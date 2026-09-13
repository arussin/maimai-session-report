import test from 'node:test';
import assert from 'node:assert/strict';
import {historyPage} from '../src/history.js';

test('historical session reads label current PB dates and unavailable comparisons honestly', () => {
  const row = {
    id:'a'.repeat(64), sort_ms:Date.UTC(2026,8,12), start_ms:Date.UTC(2026,5,1), end_ms:Date.UTC(2026,5,1,1),
    timezone:'UTC', score_count:150, pb_count:0, before_rating:null, after_rating:12000,
    before_old:null, after_old:8000, before_new:null, after_new:4000, versions:'["Current"]',
  };
  const html = historyPage({rows:[row], total:1});
  assert.match(html, /<h3>Sep 12, 2026<\/h3>/);
  assert.match(html, /Played Jun 1, 2026 · PBs at capture/);
  assert.match(html, /150 retained plays · PB changes unavailable/);
  assert.doesNotMatch(html, /0 PB changes/);
  assert.match(html, /Sep 12, 2026: 12,000/);
  const known = historyPage({rows:[{...row,before_rating:11900,pb_count:2}],total:1});
  assert.match(known, /2 PB changes/);
  assert.match(known, /\+100/);
});
