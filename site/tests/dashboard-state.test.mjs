import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { selectResults,selectSeries,selectWindowOptions,deriveChartModels } from "../src/scripts/dashboard-state.mjs";

const study=JSON.parse(readFileSync(new URL("../src/data/real-data-study.v1.json",import.meta.url),"utf8"));
const series=JSON.parse(readFileSync(new URL("../src/data/real-data-series.v1.json",import.meta.url),"utf8"));
const selection={market:"US",strategy:"equal_weight",feeBps:20};
test("selection preserves persisted facts, currencies and input bytes",()=>{
  const before=JSON.stringify(study);
  const rows=selectResults(study,selection);
  assert.equal(rows.length,11);
  assert.ok(rows.every(r=>r.market==="US"&&r.quote_currency==="USD"&&r.cost_bps===20&&r.strategy==="equal_weight"));
  for(const row of rows) assert.deepEqual(row,study.results.find(r=>r.job_id===row.job_id));
  assert.equal(JSON.stringify(study),before);
});
test("unknown selections never silently produce a different portfolio",()=>{
  for(const changes of [{market:"XX"},{strategy:"unknown"},{feeBps:30},{feeBps:"20"}])
    assert.deepEqual(selectResults(study,{...selection,...changes}),[]);
  assert.equal(selectSeries(series,"unknown"),null);
});
test("independent windows remain separate and curve summaries match the selected job",()=>{
  const rows=selectResults(study,selection);
  const windows=selectWindowOptions(rows);
  assert.equal(windows.length,11);
  const model=deriveChartModels(study,series,{...selection,windowStart:windows[0].start});
  assert.equal(model.foldReturns.length,11);
  assert.equal(model.selected.fold.start,windows[0].start);
  assert.equal(model.curve.points[0].net_nav,1);
  assert.equal(model.curve.job_id,model.selected.job_id);
  assert.equal(model.feeSensitivity.length,2);
  assert.ok(model.feeSensitivity.every(r=>r.fold.start===windows[0].start));
  assert.equal(model.histogram.reduce((sum,bin)=>sum+bin.count,0),11);
  assert.equal(deriveChartModels(study,series,{...selection,windowStart:"1900-01-01"}).selected,null);
});
test("zero excess return is retained and unpublished benchmark curves remain unavailable",()=>{
  const rows=selectResults(study,{...selection,strategy:"benchmark_buy_hold"});
  assert.ok(rows.every(r=>r.excess_return===0));
  assert.equal(selectSeries(series,rows[0].job_id),null);
  assert.equal(deriveChartModels(study,series,{...selection,strategy:"benchmark_buy_hold"}).curve,null);
});

test("window summaries separate fees and currencies, preserve nulls and never compound",async()=>{
 const {summarizeWindows}=await import('../src/scripts/dashboard-state.mjs');
 const rows=[-.2,.1,.3,0].map((value,i)=>({status:'completed',market:'US',strategy:'equal_weight',cost_bps:20,quote_currency:'USD',start:`2025-0${i+1}-01`,end:`2025-0${i+1}-28`,net_return:value,excess_return:i===3?null:value,cost_drag:.01}));
 const snapshot={results:[...rows,{...rows[0],market:'HK',quote_currency:'HKD',net_return:99},{...rows[0],cost_bps:40,net_return:99}]};
 const before=JSON.stringify(snapshot);
 assert.deepEqual(summarizeWindows(snapshot,selection),{count:4,excessCount:3,positiveExcessCount:2,positiveExcessRate:2/3,medianNetReturn:.05,medianExcessReturn:.1,worstNetReturn:-.2,medianCostDrag:.01,quoteCurrency:'USD'});
 assert.equal(JSON.stringify(snapshot),before);
 assert.equal(summarizeWindows(snapshot,{...selection,market:'XX'}),null);
 assert.equal(summarizeWindows({results:[{...rows[0],excess_return:null}]},selection).positiveExcessRate,null);
 assert.throws(()=>summarizeWindows({results:[rows[0],{...rows[1],quote_currency:'HKD'}]},selection),/currency/i);
});

test('comparison binds market, cost, exact window, currency and plan without fallback',async()=>{
 const {compareStrategies}=await import('../src/scripts/dashboard-state.mjs');
 const reference=selectResults(study,selection)[0];const options={...selection,windowStart:reference.start};
 const before=JSON.stringify(study);const model=compareStrategies(study,series,options,['equal_weight','momentum_20d','benchmark_buy_hold']);
 assert.equal(model.entries.length,3);assert.equal(model.entries[2].curve,null);
 for(const e of model.entries){assert.equal(e.result.start,reference.start);assert.equal(e.result.end,reference.end);assert.equal(e.result.cost_bps,20);assert.equal(e.result.quote_currency,'USD');}
 assert.equal(JSON.stringify(study),before);
 assert.equal(compareStrategies(study,series,options,['equal_weight','missing']).entries[1].result,null);
 assert.equal(compareStrategies(study,series,{...options,windowStart:'1900-01-01'},['equal_weight']).reference,null);
 assert.throws(()=>compareStrategies(study,series,options,['a','b','c','d']),/three/i);
 const corrupt=structuredClone(study);corrupt.results.find(r=>r.job_id===model.entries[1].result.job_id).quote_currency='HKD';
 assert.equal(compareStrategies(corrupt,series,options,['equal_weight','momentum_20d']).entries[1].result,null);
 const badCurve=structuredClone(series);badCurve.series.find(c=>c.job_id===model.entries[1].result.job_id).points.pop();
 assert.equal(compareStrategies(study,badCurve,options,['equal_weight','momentum_20d']).entries[1].curve,null);
 assert.throws(()=>compareStrategies({results:[...study.results,reference]},series,options,['equal_weight']),/duplicate/i);
});

test('fee robustness uses only common windows and keeps zero-cost controls and null excess',async()=>{
 const {summarizeFeeRobustness}=await import('../src/scripts/dashboard-state.mjs');
 const base=selectResults(study,selection)[0];
 const row=(cost,start,net,excess)=>({...base,job_id:`${cost}-${start}`,cost_bps:cost,start,end:start,net_return:net,excess_return:excess});
 const data={results:[row(0,'a',.2,.1),row(0,'b',.5,.3),row(20,'a',.1,null),row(40,'a',-.1,0),{...row(40,'z',99,99),market:'HK'}]};
 const before=JSON.stringify(data);const value=summarizeFeeRobustness(data,selection);
 assert.equal(value.matchedWindows,1);assert.equal(value.excludedWindows,1);
 assert.deepEqual(value.fees.map(f=>f.feeBps),[0,20,40]);assert.deepEqual(value.fees.map(f=>f.positiveNetCount),[1,1,0]);
 assert.deepEqual(value.fees.map(f=>f.summary.medianNetReturn),[.2,.1,-.1]);assert.equal(value.fees[1].summary.positiveExcessRate,null);assert.equal(value.fees[2].summary.positiveExcessRate,0);
 assert.equal(JSON.stringify(data),before);
 assert.equal(summarizeFeeRobustness({results:[row(0,'a',.2,.1),row(20,'b',.1,null)]},selection).matchedWindows,0);
 assert.deepEqual(summarizeFeeRobustness(data,{...selection,market:'XX'}).fees,[]);
});
