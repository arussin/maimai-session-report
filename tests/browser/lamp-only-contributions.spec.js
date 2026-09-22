import {test, expect} from './fixtures.js';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';

const source = readFileSync(new URL('../../src/maimai_report/assets/app.js', import.meta.url), 'utf8');
const start = source.indexOf('  function calculateRatingContributions(report) {');
const end = source.indexOf('  const ratingContributions = calculateRatingContributions(data);', start);
assert(start >= 0 && end > start);
const context = {};
vm.runInNewContext(source.slice(start, end) + ';globalThis.calculate = calculateRatingContributions;', context);
const calc = model => JSON.parse(JSON.stringify(context.calculate(model)));
const chart = (id, rate=200, percent=99, lamp='CLEAR', timeAchieved=1000) => ({
  chartID:id, songID:id, title:`Fictional ${id}`, difficulty:'DX Expert', level:'10', levelNum:10,
  displayVersion:'OLD', rate, percent, lamp, grade:'SS', timeAchieved,
});
const snapshot = items => {
  const old35=[...items].sort((a,b)=>b.rate-a.rate).slice(0,35);
  const old35Rating=old35.reduce((sum,item)=>sum+item.rate,0);
  return {old35,new15:[],old35Rating,new15Rating:0,reconstructedRating:old35Rating};
};
function fixture(withGain=true) {
  const initial=Array.from({length:35},(_,i)=>chart(`old${i}`));
  const lamp={...initial[0],lamp:'FULL COMBO',changeType:'improved',previousLamp:'CLEAR',previousPercent:99,previousRate:200};
  const scoring=chart('scoring',225,100,'CLEAR',3000);
  const before=snapshot(initial);
  const after=snapshot([lamp,...initial.slice(1),...(withGain?[scoring]:[])]);
  return {before,after,currentNewDisplayVersions:['NEW'],
    delta:{old35Rating:withGain?25:0,new15Rating:0,reconstructedRating:withGain?25:0},
    session:{scores:[chart('old0',200,99,'FULL COMBO',2000),...(withGain?[scoring]:[])],
      changedPBs:[lamp,...(withGain?[{...scoring,changeType:'new',previousRate:null,previousPercent:null,previousLamp:null}]:[])]}};
}
test('lamp-only PB leaves other verified contributions intact',()=>{
  assert.deepEqual(calc(fixture()),{complete:true,contributions:[{chartID:'scoring',amount:25}],total:25});
});
test('lamp-only session has a verified zero rating gain',()=>{
  assert.deepEqual(calc(fixture(false)),{complete:true,contributions:[],total:0});
});
test('composite PB can obtain a better lamp on a lower-scoring play',()=>{
  const model=fixture(); model.session.scores[0].percent=98; model.session.scores[0].rate=195;
  assert.equal(calc(model).total,25);
});
test('equal achievement without a lamp change remains invalid',()=>{
  const model=fixture(); model.session.changedPBs[0].lamp='CLEAR';
  assert.equal(calc(model).complete,false);
});
test('missing empty whitespace and non-string lamp evidence is rejected',()=>{
  for(const key of ['lamp','previousLamp']) for(const value of [undefined,null,'',' ',0,{},[]]) {
    const model=fixture(); model.session.changedPBs[0][key]=value;
    assert.equal(calc(model).complete,false,`${key}: ${JSON.stringify(value)}`);
  }
});
test('lamp change cannot conceal rate correction at equal achievement',()=>{
  const model=fixture(); model.session.changedPBs[0].rate=201;
  assert.equal(calc(model).complete,false);
});
test('lamp change cannot conceal a lower PB achievement',()=>{
  const model=fixture(); model.session.changedPBs[0].percent=98;
  assert.equal(calc(model).complete,false);
});
test('lamp change cannot conceal a missing scoring play',()=>{
  const model=fixture(); model.session.scores=model.session.scores.slice(0,1);
  assert.equal(calc(model).complete,false);
});
test('lamp-only calculation does not mutate retained inputs',()=>{
  const model=fixture(),saved=JSON.stringify(model); calc(model);
  assert.equal(JSON.stringify(model),saved);
});
test('mixed lamp and scoring session renders without the reconciliation warning',async({page})=>{
  const errors=[]; page.on('pageerror',error=>errors.push(error.message));
  await page.setContent('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Fictional lamp changes</title></head><body><main id="app"></main><script id="report-data" type="application/json"></script><script id="jacket-data" type="application/json">{}</script><script id="download-data" type="application/json">{}</script></body></html>');
  await page.locator('#report-data').evaluate((element,value)=>{element.textContent=JSON.stringify(value);},fixture());
  await page.addScriptTag({content:source});
  await expect(page.locator('.overview-scores .score-info > strong')).toHaveText(['Fictional scoring']);
  await expect(page.locator('.overview-scores .score-gain')).toHaveText(['+25rating gain']);
  await expect(page.locator('.contribution-summary')).toContainText('+25 of +25');
  await expect(page.locator('.overview-scores')).not.toContainText('Rating contributions unavailable');
  await page.getByRole('button',{name:'All scores',exact:true}).click();
  await page.locator('#score-scope').selectOption('pbs');
  await expect(page.locator('#session-rows tr[data-search]')).toHaveCount(2);
  expect(errors).toEqual([]);
});
