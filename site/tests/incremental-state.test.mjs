import test from 'node:test';
import assert from 'node:assert/strict';
import {formatResearchNumber, equitySeries, cryptoPoints} from '../src/scripts/incremental-state.mjs';

test('small negative IC and MSE remain readable in both locales',()=>{
 for(const locale of ['en','zh-CN']){
  assert.match(formatResearchNumber(-0.00003707265,locale),/370727/);
  assert.notEqual(formatResearchNumber(0.00043610179,locale),formatResearchNumber(0.00043722274,locale));
  assert.equal(formatResearchNumber(null,locale,'missing'),'missing');
 }
});
test('paired chart uses actual selected model and daily reversal on common dates',()=>{
 const facts={equity:{folds:[{models:[
  {model:'reversal',metrics:{daily:[{date:'2026-08-03',rank_ic:.25,count:50},{date:'2026-08-04',rank_ic:null,count:20}]}},
  {model:'ridge_full',metrics:{daily:[{date:'2026-08-03',rank_ic:.5,count:50},{date:'2026-08-04',rank_ic:null,count:20}]}}
 ]}]}};
 assert.deepEqual(equitySeries(facts,'ridge_full',0),{dates:['2026-08-03','2026-08-04'],differences:[.25,null],counts:[50,20]});
});
test('crypto selection preserves cost window and account identity',()=>{
 const facts={crypto:{jobs:[{fee_bps:35,arm:'weekly_trend',window_id:'a',metrics:{turnover:2,net_return:.1}},
                          {fee_bps:50,arm:'weekly_trend',window_id:'a',metrics:{turnover:3,net_return:.05}}]}};
 assert.deepEqual(cryptoPoints(facts,50),[{arm:'weekly_trend',window:'a',value:[3,5]}]);
});
