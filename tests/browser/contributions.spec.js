import {test, expect} from './fixtures.js';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';

// Test the production implementation; all score records below are fictional.
const source = readFileSync(new URL('../../src/maimai_report/assets/app.js', import.meta.url), 'utf8');
const start = source.indexOf('  function calculateRatingContributions(report) {');
const end = source.indexOf('  const ratingContributions = calculateRatingContributions(data);', start);
assert(start >= 0 && end > start, 'Production contribution calculation was not found');
const context = {};
vm.runInNewContext(source.slice(start, end) + ';globalThis.calculate = calculateRatingContributions;', context);
const calc = report => JSON.parse(JSON.stringify(context.calculate(report)));
const chart=(id,rate,percent=99,version='OLD',timeAchieved=1000)=>({chartID:id,songID:id,title:`Fictional ${id}`,difficulty:'DX Expert',level:'10',levelNum:10,rate,percent,displayVersion:version,timeAchieved,grade:'SS'});
const snapshot=items=>{
 const sorted=[...items].sort((a,b)=>b.rate-a.rate);
 const old35=sorted.filter(x=>x.displayVersion==='OLD').slice(0,35),new15=sorted.filter(x=>x.displayVersion==='NEW').slice(0,15);
 const sum=a=>a.reduce((s,x)=>s+x.rate,0);const old35Rating=sum(old35),new15Rating=sum(new15);
 return {old35,new15,old35Rating,new15Rating,reconstructedRating:old35Rating+new15Rating};
};
const report=(initial,plays)=>{
 const state=new Map(initial.map(x=>[x.chartID,x]));
 for(const p of [...plays].sort((a,b)=>a.timeAchieved-b.timeAchieved)) {const prev=state.get(p.chartID);if(!prev||p.percent>prev.percent)state.set(p.chartID,p);}
 const before=snapshot(initial),after=snapshot([...state.values()]);
 const changedPBs=[...state.values()].flatMap(x=>{const prev=initial.find(y=>y.chartID===x.chartID);return !prev||prev.rate!==x.rate||prev.percent!==x.percent?[{...x,changeType:prev?'improved':'new',previousRate:prev?.rate??null,previousPercent:prev?.percent??null}]:[];});
 return {before,after,delta:Object.fromEntries(['old35Rating','new15Rating','reconstructedRating'].map(k=>[k,after[k]-before[k]])),session:{changedPBs,scores:plays},currentNewDisplayVersions:['NEW']};
};
const full=()=>[...Array.from({length:35},(_,i)=>chart(`o${i}`,200)),...Array.from({length:15},(_,i)=>chart(`n${i}`,100,99,'NEW'))];
test('first PB subtracts the displaced floor',()=>{const r=calc(report(full(),[chart('entry',230,100)]));assert.deepEqual(r.contributions,[{chartID:'entry',amount:30}]);});
test('uncounted PB is excluded',()=>{assert.deepEqual(calc(report(full(),[chart('low',180,100)])).contributions,[]);});
test('existing counted PB gains count incrementally',()=>{assert.equal(calc(report(full(),[chart('o0',211,100)])).total,11);});
test('previous uncounted PB is not subtracted instead of floor',()=>{assert.equal(calc(report([...full(),chart('below',160,95)],[chart('below',235,100)])).total,35);});
test('new15 and old35 pools are independent',()=>{const r=calc(report(full(),[chart('new',105,100,'NEW',1100),chart('old',209,100,'OLD',1200)]));assert.equal(r.total,14);assert.deepEqual(r.contributions,[{chartID:'old',amount:9},{chartID:'new',amount:5}]);});
test('empty slot credits whole new score',()=>{assert.equal(calc(report([],[chart('first',150)])).total,150);});
test('repeat plays aggregate; failed repeats do not inflate',()=>{const r=calc(report(full(),[chart('repeat',210,98,'OLD',1000),chart('repeat',220,99,'OLD',1100),chart('repeat',205,97,'OLD',1200)]));assert.deepEqual(r.contributions,[{chartID:'repeat',amount:20}]);});
test('reversed API order is replayed chronologically',()=>{const r=report(full(),[chart('one',225,99,'OLD',1000),chart('two',215,99,'OLD',2000)]);const expected=calc(r);r.session.scores.reverse();assert.deepEqual(calc(r),expected);});
test('earlier contributor may later leave final pool',()=>{const initial=[...Array.from({length:34},(_,i)=>chart(`high${i}`,300)),chart('floor',200)];const r=calc(report(initial,[chart('early',210,99,'OLD',1000),chart('later',230,99,'OLD',2000)]));assert.deepEqual(r.contributions,[{chartID:'later',amount:20},{chartID:'early',amount:10}]);});
test('same-rate PB percent improvement contributes zero',()=>{assert.equal(calc(report(full(),[chart('o0',200,100)])).total,0);});
test('first-time raw PB does not outrank a larger genuine gain',()=>{const initial=[...Array.from({length:34},(_,i)=>chart(`high${i}`,300)),chart('floor',200)];const r=calc(report(initial,[chart('new',210,99,'OLD',1000),chart('high0',321,100,'OLD',2000)]));assert.deepEqual(r.contributions,[{chartID:'high0',amount:21},{chartID:'new',amount:10}]);});
test('missing retained play refuses rankings',()=>{const r=report(full(),[chart('entry',230,100)]);r.session.scores=[];assert.equal(calc(r).complete,false);});
test('missing below-pool endpoint also refuses false full coverage',()=>{const r=report(full(),[chart('low',180,100)]);r.session.scores=[];assert.equal(calc(r).complete,false);});
test('metadata correction refuses chronological attribution',()=>{const r=report(full(),[chart('o0',210,100)]);r.session.changedPBs[0].previousRate=205;assert.equal(calc(r).complete,false);});
test('version reclassification refuses attribution',()=>{const r=report(full(),[chart('o0',210,100)]);r.before.old35[0].displayVersion='NEW';assert.equal(calc(r).complete,false);});
test('different charts at same timestamp refuse arbitrary ordering',()=>{assert.equal(calc(report(full(),[chart('a',220),chart('b',230)])).complete,false);});
test('missing timestamps refuse attribution',()=>{const r=report(full(),[chart('entry',230)]);r.session.scores[0].timeAchieved=null;assert.equal(calc(r).complete,false);});
test('explicit unavailable comparison refuses attribution',()=>{const r=report(full(),[chart('entry',230,100)]);r.comparison={available:false};assert.equal(calc(r).complete,false);});
test('missing snapshots refuse attribution',()=>{assert.equal(calc({}).complete,false);});
test('malformed rating refuses attribution',()=>{const r=report(full(),[chart('entry',230)]);r.session.changedPBs[0].rate='230';assert.equal(calc(r).complete,false);});
test('no change remains verified zero',()=>{assert.deepEqual(calc(report(full(),[])),{complete:true,contributions:[],total:0});});
test('input data is immutable',()=>{const r=report(full(),[chart('entry',230)]);const before=JSON.stringify(r);calc(r);assert.equal(JSON.stringify(r),before);});
test('negative rating correction refuses attribution',()=>{const r=report(full(),[chart('o0',180,100)]);assert.equal(calc(r).complete,false);});

async function showReport(page, model) {
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.setContent('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Synthetic contributions</title></head><body><main id="app"></main><script id="report-data" type="application/json"></script><script id="jacket-data" type="application/json">{}</script><script id="download-data" type="application/json">{}</script></body></html>');
  await page.locator('#report-data').evaluate((element, value) => {element.textContent = JSON.stringify(value);}, model);
  await page.addStyleTag({content: readFileSync(new URL('../../src/maimai_report/assets/styles.css', import.meta.url), 'utf8')});
  await page.addScriptTag({content: source});
  return errors;
}

test('highlight cards rank net gain, keep PB details, and fit narrow displays', async ({page}) => {
  const initial = [...Array.from({length:34},(_,i)=>chart(`high${i}`,300)),chart('floor',200)];
  const model = report(initial,[chart('new',210,99,'OLD',1000),chart('high0',321,100,'OLD',2000)]);
  const errors = await showReport(page, model);
  const rows = page.locator('.overview-scores .score-row');
  await expect(rows.locator('.score-info > strong')).toHaveText(['Fictional high0','Fictional new']);
  await expect(rows.locator('.score-gain')).toHaveText(['+21rating gain','+10rating gain']);
  await expect(page.locator('.contribution-summary')).toContainText('Top 2: +31 of +31 verified session rating gain.');
  await expect(rows.first()).toContainText('PB rating: 300 → 321');
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
  await rows.first().click();
  await expect(page.locator('.chart-dialog')).toContainText('Session rating contribution: +21.');
  await expect(page.locator('.detail-comparison')).toContainText('300');
  await expect(page.locator('.detail-comparison')).toContainText('321');
  expect(errors).toEqual([]);
});

test('unreconciled data shows unavailable rather than raw gains', async ({page}) => {
  const model = report(full(),[chart('entry',230,100)]);
  model.session.scores=[];
  const errors=await showReport(page,model);
  await expect(page.locator('.overview-scores .score-row')).toHaveCount(0);
  await expect(page.locator('.overview-scores')).toContainText('Rating contributions unavailable');
  await page.getByRole('button',{name:'All scores',exact:true}).click();
  await page.locator('#score-scope').selectOption('pbs');
  await expect(page.locator('#session-rows tr[data-search]')).toHaveCount(1);
  expect(errors).toEqual([]);
});

test('zero-gain session does not promote first-time uncounted PBs', async ({page}) => {
  const model=report(full(),[chart('low',180,100)]);
  const errors=await showReport(page,model);
  await expect(page.locator('.overview-scores .score-row')).toHaveCount(0);
  await expect(page.locator('.overview-scores')).toContainText('No rating gains this session.');
  expect(errors).toEqual([]);
});

test('hostile titles in contribution cards remain text', async ({page}) => {
  const play=chart('hostile',230,100);
  play.title='<img src=x onerror="globalThis.injected=true"> & fictional';
  const errors=await showReport(page,report(full(),[play]));
  await expect(page.locator('.overview-scores .score-info > strong')).toHaveText(play.title);
  await expect(page.locator('.overview-scores img')).toHaveCount(0);
  expect(await page.evaluate(()=>globalThis.injected)).toBeUndefined();
  expect(errors).toEqual([]);
});
