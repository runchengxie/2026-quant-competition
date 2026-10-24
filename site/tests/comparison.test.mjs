import test from 'node:test';
import assert from 'node:assert/strict';
import {selectComparison,costSeries,pairedSummary} from '../src/scripts/comparison-state.mjs';

function fixture(){
 const arms={equity:['equal_weight','reversal','ridge','elastic_net'],crypto:['buy_hold_equal_weight','fixed60_weekly','trend_weekly','matched_weekly']};
 const facts={};
 for(const market of ['equity','crypto'])facts[market]={currency:market==='equity'?'USD':'USDT',accounts:['a','b'].flatMap(window=>arms[market].flatMap((arm,index)=>(market==='equity'?[0,20,40]:[0,35,50]).flatMap(fee_bps=>[0,1].map(delay=>({window,end:window,arm,fee_bps,delay,status:window==='b'&&index===2?'blocked':'completed',metrics:window==='b'&&index===2?null:{net_return:index/100-fee_bps/10000-delay/100}})))))};
 return facts;
}

test('selection binds market, fee, delay and exact window without changing facts',()=>{
 const facts=fixture(),before=structuredClone(facts);
 const rows=selectComparison(facts,{market:'crypto',window:'a',fee:50,delay:1});
 assert.equal(rows.length,4);
 assert.ok(rows.every(row=>row.window==='a'&&row.fee_bps===50&&row.delay===1));
 assert.deepEqual(facts,before);
});

test('cost curves preserve blocked cells and only published scenario points',()=>{
 const values=costSeries(fixture(),{market:'equity',window:'b',delay:0});
 assert.deepEqual(values.fees,[0,20,40]);
 assert.deepEqual(values.series.find(row=>row.arm==='ridge').values,[null,null,null]);
 assert.equal(values.series.find(row=>row.arm==='equal_weight').values[0],0);
});

test('paired counts retain missing windows instead of treating them as zero returns',()=>{
 assert.deepEqual(pairedSummary(fixture(),{market:'equity',fee:40,delay:0}),{requested:2,comparable:1,blocked:1,wins:1});
});

test('unknown choices and mixed currency fail without a fallback',()=>{
 for(const bad of [{market:'unknown'},{window:'unknown'},{fee:true},{delay:true},{fee:25},{delay:2}]){
  assert.throws(()=>selectComparison(fixture(),{market:'equity',window:'a',fee:40,delay:0,...bad}));
 }
 const facts=fixture();facts.crypto.currency='USD';
 assert.throws(()=>selectComparison(facts,{market:'crypto',window:'a',fee:50,delay:0}));
});
