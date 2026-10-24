import test from 'node:test';
import assert from 'node:assert/strict';
import {capitalCurve,feeWindowCells} from '../src/scripts/reader-charts.mjs';

const row=(start,fee,value)=>({status:'completed',market:'US',strategy:'buy_hold',start,end:'2026-03-01',cost_bps:fee,net_return:value,quote_currency:'USD',job_id:`${start}-${fee}`});
test('heatmap retains missing fee/window cells and actual job identities',()=>{
 const model=feeWindowCells({results:[row('2026-01-01',20,.1),row('2026-01-01',40,.08),row('2026-02-01',20,-.1)]},{market:'US',strategy:'buy_hold'});
 assert.deepEqual(model.fees,[20,40]);assert.equal(model.cells.length,4);
 assert.equal(model.cells.filter(c=>c.result===null).length,1);
 assert.equal(model.cells.find(c=>c.windowStart==='2026-01-01'&&c.feeBps===40).result.job_id,'2026-01-01-40');
 assert.throws(()=>feeWindowCells({results:[row('2026-01-01',20,.1),row('2026-01-01',20,.2)]},{market:'US',strategy:'buy_hold'}),/Duplicate/);
});
test('capital presentation preserves normalized points and separate currencies',()=>{
 const points=[{date:'2026-01-01',net_nav:1.02,gross_nav:1.03},{date:'2026-01-02',net_nav:.99,gross_nav:1.01}];
 for(const currency of ['USD','HKD','USDT']){
  const result=capitalCurve(points,currency);
  assert.equal(result.currency,currency);assert.equal(result.initialCapital,10000);
  assert.deepEqual(result.points.map(p=>p.net_capital),[10200,9900]);
 }
 assert.equal(points[0].net_nav,1.02);
 assert.throws(()=>capitalCurve([{date:'x',net_nav:Infinity,gross_nav:1}],'USD'),/Invalid/);
 assert.throws(()=>capitalCurve(points,'EUR'),/currency/);
});
test('heatmap reports requested, valid and blocked conditions without a fabricated return',()=>{
 const blocked={...row('2026-02-01',40,null),status:'blocked'};
 const model=feeWindowCells({results:[row('2026-01-01',20,.1),blocked]},{market:'US',strategy:'buy_hold'});
 assert.deepEqual(model.coverage,{requested:2,valid:1,blocked:1,missing:2});
 assert.equal(model.cells.find(c=>c.windowStart==='2026-02-01'&&c.feeBps===40).result,null);
});
