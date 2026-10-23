import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {validateRobustnessSnapshot,selectRobustness,summarizeRobustness,robustnessHeadlines,capacitySummary} from '../src/scripts/robustness-state.mjs';
const snapshot=JSON.parse(await readFile(new URL('../src/data/strategy-robustness.v1.json',import.meta.url),'utf8'));

test('all new results and volume assumptions remain separate from the original protocol',()=>{
 assert.equal(validateRobustnessSnapshot(snapshot),snapshot);
 assert.equal(selectRobustness(snapshot,{market:'US',feeBps:20}).length,33);
 assert.equal(selectRobustness(snapshot,{market:'crypto',feeBps:50}).length,24);
 const us=summarizeRobustness(snapshot,{market:'US',feeBps:20}).find(g=>g.poolId==='exclude_three');
 assert.equal(us.windows,11);assert.equal(us.returnWins,4);assert.equal(us.drawdownWins,10);
 assert.ok(Math.abs(us.medianReturnChange-(-.019732167633064401))<1e-12);
 const crypto=summarizeRobustness(snapshot,{market:'crypto',feeBps:50})[0];
 assert.equal(crypto.returnWins,5);assert.equal(crypto.windows,12);
 assert.ok(Math.abs(crypto.medianReturnChange-(-.0031567072643501337))<1e-12);
 assert.equal(robustnessHeadlines(snapshot)[0].returnWins,4);
});

test('capacity is an ex-post account diagnostic with the full denominator',()=>{
 const value=capacitySummary(snapshot,{notionalUsdt:1000000,threshold:.01});
 assert.equal(value.accounts,48);assert.equal(value.breachingAccounts,6);
 assert.ok(Math.abs(value.maxParticipation-.05967559865628072)<1e-12);
 assert.equal(capacitySummary(snapshot,{notionalUsdt:1000000,threshold:.05}).breachingAccounts,2);
});

test('invalid facts are rejected and locale cannot alter selection',()=>{
 for(const mutate of [v=>v.results.pop(),v=>v.results[0].fee_bps=true,v=>v.results[0].metrics.net_return=NaN,v=>v.capacity[0].execution_eligible=true,v=>v.results[0].private_path='sentinel']){
  const value=structuredClone(snapshot);mutate(value);assert.throws(()=>validateRobustnessSnapshot(value));
 }
 assert.deepEqual(selectRobustness(snapshot,{market:'US',feeBps:40,locale:'zh-CN'}),selectRobustness(snapshot,{market:'US',feeBps:40,locale:'unknown'}));
});

test('blocked windows retain the requested denominator instead of disappearing',()=>{
 const value=structuredClone(snapshot),row=value.results.find(r=>r.market==='US'&&r.pool_id==='exclude_nvda'&&r.fee_bps===20);
 row.status='blocked';row.reason='FAILED_OR_TIME_BUDGET';row.metrics=null;row.benchmark=null;row.baseline_net_return=null;
 value.coverage.completed_jobs--;value.coverage.blocked_jobs++;
 value.us_pairs=value.us_pairs.filter(p=>p.job_id!==row.job_id);
 const group=summarizeRobustness(value,{market:'US',feeBps:20}).find(g=>g.poolId==='exclude_nvda');
 assert.equal(group.requestedWindows,11);assert.equal(group.windows,10);assert.equal(group.blockedWindows,1);
});
