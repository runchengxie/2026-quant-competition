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
