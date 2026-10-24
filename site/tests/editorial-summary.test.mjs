import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {editorialSummary} from '../src/scripts/editorial-summary.mjs';
const load=async name=>JSON.parse(await readFile(new URL(`../src/data/${name}.v1.json`,import.meta.url),'utf8'));
const snapshot=await load('strategy-robustness');
const readiness=await load('strategy-readiness');

test('derives exact published editorial facts',()=>{
 const value=editorialSummary(snapshot,readiness);
 assert.deepEqual(value.us.map(g=>g.poolId),['exclude_nvda','exclude_three','fixed_six']);
 for(const [index,want] of [-.004597942226943763,-.01973216763306440,-.02048237519275564].entries()){
  const group=value.us[index];assert.ok(Math.abs(group.medianReturnChange-want)<1e-12);
  assert.deepEqual([group.feeBps,group.returnWins,group.drawdownWins,group.windows,group.requestedWindows],[20,4,10,11,11]);
 }
 assert.deepEqual(value.crypto.map(g=>[g.feeBps,g.returnWins,g.requestedWindows]),[[35,6,12],[50,5,12]]);
 assert.ok(Math.abs(value.crypto[0].medianReturnChange-.0010757246587540514)<1e-12);
 assert.ok(Math.abs(value.crypto[1].medianReturnChange-(-.0031567072643501337))<1e-12);
 assert.equal(value.observation.observations,0);assert.equal(value.observation.firstEligibleObservationAt,null);
 assert.equal(value.coverage.requested_jobs,114);assert.equal(value.coverage.completed_capacity_checks,288);
 assert.equal(value.codeCommit,'e70040cc19f4d4f4e826afe295013a348e41b314');
 assert.equal(value.planSha256,'12c04fc53aa450dfb9bbbb66e4978a691e13fef1d36a7b7944ab5720aa7b4291');
 assert.deepEqual(value.evidenceRange.US,{start:snapshot.results.filter(r=>r.market==='US').map(r=>r.start).sort()[0],end:snapshot.results.filter(r=>r.market==='US').map(r=>r.end).sort().at(-1)});
});

test('blocked denominators and null medians survive the compact boundary',()=>{
 const value=structuredClone(snapshot);
 const blocked=new Set();
 for(const row of value.results.filter(r=>r.market==='US'&&r.pool_id==='exclude_nvda'&&r.fee_bps===20)){
  blocked.add(row.job_id);Object.assign(row,{status:'blocked',reason:'FAILED_OR_TIME_BUDGET',metrics:null,benchmark:null,baseline_net_return:null});
  value.coverage.completed_jobs--;value.coverage.blocked_jobs++;
 }
 value.us_pairs=value.us_pairs.filter(p=>!blocked.has(p.job_id));
 const group=editorialSummary(value,readiness).us[0];
 assert.deepEqual([group.requestedWindows,group.blockedWindows,group.windows],[11,11,0]);
 assert.equal(group.medianReturnChange,null);
});

test('readiness has no fabricated bars',()=>{
 const value=structuredClone(snapshot);value.status='readiness_only';
 for(const key of ['results','us_pairs','crypto_pairs','capacity'])value[key]=[];
 value.coverage.completed_jobs=0;value.coverage.blocked_jobs=114;value.coverage.completed_capacity_checks=0;
 const compact=editorialSummary(value,readiness);
 assert.deepEqual(compact.us,[]);assert.deepEqual(compact.crypto,[]);
 assert.deepEqual(compact.evidenceRange,{US:null,crypto:null});
});

test('invalid snapshots are rejected',()=>{
 const value=structuredClone(snapshot);value.results[0].metrics.net_return=NaN;
 assert.throws(()=>editorialSummary(value,readiness));
});

test('summary carries no full arrays or locale-dependent facts',()=>{
 const value=editorialSummary(snapshot,readiness);
 assert.deepEqual(Object.keys(value).sort(),['asOf','codeCommit','planSha256','coverage','observation','us','crypto','evidenceRange'].sort());
 assert.ok(JSON.stringify(value).length<10240);
 for(const key of ['results','capacity','us_pairs','crypto_pairs','private_path'])assert.ok(!Object.hasOwn(value,key));
 assert.deepEqual(editorialSummary(snapshot,readiness,'zh-CN'),value);
});
