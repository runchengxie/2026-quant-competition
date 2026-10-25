import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {selectHoldings,holdingCosts,selectModels,selectAttribution,bufferSummary} from '../src/scripts/low-turnover-state.mjs';
import {marketForHash} from '../src/scripts/market-panels.mjs';
import {valueAxisLayout} from '../src/scripts/chart-axis.mjs';
const facts=JSON.parse(readFileSync(new URL('../src/data/low-turnover.v1.json',import.meta.url),'utf8'));
const windows=[...new Set(facts.equity.accounts.map(row=>row.window))].sort();

test('holdings filters preserve exact facts and the unbuffered equal-weight baseline',()=>{
 const selected=selectHoldings(facts,{window:windows[0],horizon:20,fee:20,delay:0,buffer:20});
 assert.equal(selected.length,4);assert.equal(selected[0].buffer,0);
 assert.equal(selected[2].status,'blocked');assert.equal(selected[2].metrics,null);
 assert.deepEqual(selectModels(facts,{window:windows[0],horizon:20}).map(r=>r.status),['unavailable','unavailable']);
 const curves=holdingCosts(facts,{window:windows[0],horizon:20,buffer:20,delay:0});
 assert.deepEqual(curves.fees,[0,20,40]);assert.deepEqual(curves.series.find(r=>r.arm==='ridge').values,[null,null,null]);
});

test('fees and horizons never silently fall back or mix currencies',()=>{
 for(const horizon of [1,21,true])assert.throws(()=>selectHoldings(facts,{window:windows[0],horizon,fee:20,delay:0,buffer:0}),RangeError);
 assert.throws(()=>selectHoldings(facts,{window:windows[0],horizon:5,fee:10,delay:0,buffer:0}),RangeError);
 assert.throws(()=>selectHoldings({...facts,equity:{...facts.equity,currency:'USDT'}},{window:windows[0],horizon:5,fee:20,delay:0,buffer:0}),RangeError);
});

test('buffer summaries compare matching windows and preserve unavailable pairs',()=>{
 const summary=bufferSummary(facts,{horizon:20,fee:20,delay:0});
 assert.equal(summary.requested,6);assert.equal(summary.comparable,3);assert.equal(summary.blocked,3);
 assert.ok(summary.lowerTurnover<=summary.comparable);assert.ok(summary.higherReturn<=summary.comparable);
});

test('attribution is additive PnL and retains the same exact selected accounts',()=>{
 const window=facts.crypto.accounts[0].window;
 for(const delay of [0,1])for(const fee of [0,35,50]){
  const rows=selectAttribution(facts,{window,fee,delay});assert.equal(rows.length,4);
  for(const row of rows)assert.ok(Math.abs(Object.values(row.components).reduce((a,b)=>a+b,0)-row.net_return)<1e-10);
 }
});

test('market hash selection recognizes only declared markets',()=>{
 assert.equal(marketForHash('#market-hk'),'HK');assert.equal(marketForHash('#market-us'),'US');assert.equal(marketForHash('#market-crypto'),'crypto');
 assert.equal(marketForHash('#account-private'),null);assert.equal(marketForHash('#%broken'),null);
 assert.equal(marketForHash('#market-constructor'),null);
});

test('daily-return omission labels do not claim a holdings and fee replay',()=>{
 const en=JSON.parse(readFileSync(new URL('../src/i18n/comparison-en.json',import.meta.url),'utf8'));
 const zh=JSON.parse(readFileSync(new URL('../src/i18n/comparison-zh-CN.json',import.meta.url),'utf8'));
 assert.doesNotMatch(en.removed,/cash/i);assert.doesNotMatch(zh.removed,/现金/);
 assert.match(en.stressNote,/not recalculated/);assert.match(zh.stressNote,/不重新计算持仓和费用/);
});

test('narrow charts use fewer value ticks and hide overlapping labels',()=>{
 assert.equal(valueAxisLayout(344).splitNumber,3);
 assert.equal(valueAxisLayout(900).splitNumber,5);
 assert.equal(valueAxisLayout(344).axisLabel.hideOverlap,true);
 assert.throws(()=>valueAxisLayout(NaN),RangeError);
});
