import test from "node:test";
import assert from "node:assert/strict";
import {selectAblations,summarizeAblations} from "../src/scripts/ablation-state.mjs";
const row={market:"US",quote_currency:"USD",strategy:"sma_cross",variant_id:"weekly",cost_bps:20,start:"2026-01-01",status:"completed",evidence_role:"retrospective_ablation",net_return:.04,excess_return:null,paired_net_change:.03,paired_drawdown_change:-.02,mean_daily_oneway_turnover_proxy:.01,mean_exposure:.8};
const snapshot={results:[row,{...row,cost_bps:40},{...row,market:"HK",quote_currency:"HKD"},{...row,status:"blocked",start:"2026-04-01",net_return:null}]};
test("selection_does_not_cross_market_or_fee",()=>{
 assert.equal(selectAblations(snapshot,{market:"US",feeBps:20}).length,2);
 assert.deepEqual(selectAblations(snapshot,{}),[]);
 assert.deepEqual(selectAblations(snapshot,{market:"US",variantId:"unknown"}),[]);
 assert.deepEqual(selectAblations(snapshot,{market:"US",feeBps:"20"}),[]);
 assert.equal(selectAblations(snapshot,{market:"US",feeBps:20,windowStart:"2026-04-01"})[0].status,"blocked");
});
test("summary_preserves_null_paired_values",()=>{
 const groups=summarizeAblations(snapshot,{market:"US",feeBps:20});
 assert.equal(groups.length,1);assert.equal(groups[0].count,1);
 assert.equal(groups[0].median_paired_net_change,.03);assert.equal(groups[0].median_excess_return,null);
 assert.equal(summarizeAblations({results:[{...row,paired_net_change:null}]},{market:"US"})[0].median_paired_net_change,null);
});
test("locale_never_changes_fact_objects",()=>{
 const before=JSON.stringify(snapshot);
 assert.deepEqual(summarizeAblations(snapshot,{market:"US",locale:"en"}),summarizeAblations(snapshot,{market:"US",locale:"zh-CN"}));
 assert.equal(JSON.stringify(snapshot),before);
});
test("a_market_cannot_silently_mix_currencies",()=>{
 assert.throws(()=>summarizeAblations({results:[row,{...row,quote_currency:"HKD"}]},{market:"US"}));
});

test("invalid_input_blockers_remain_inspectable_without_a_market",()=>{
 const blocked={market:"unknown",status:"blocked",reason_code:"INVALID_STUDY_INPUT",strategy:null,cost_bps:null};
 assert.deepEqual(selectAblations({results:[blocked]},{market:"unknown"}),[blocked]);
 assert.deepEqual(summarizeAblations({results:[blocked]},{market:"unknown"}),[]);
});
