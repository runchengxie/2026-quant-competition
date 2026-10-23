import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {controlsFixture} from './strategy-controls-fixture.mjs';
import {validateControlsSnapshot,selectControls,selectControlPairs,summarizeControls,compareControlCosts} from '../src/scripts/strategy-controls-state.mjs';

test('small percentage-point changes keep distinct readable tick values',async()=>{
 const {formatControlChange}=await import('../src/scripts/strategy-controls-state.mjs');
 for(const locale of ['en','zh-CN','unknown']){
  assert.equal(formatControlChange(.00005,locale),'0.005');
  assert.equal(formatControlChange(.0001,locale),'0.01');
  assert.equal(formatControlChange(.00015,locale),'0.015');
  assert.equal(formatControlChange(.00020489,locale),'0.0205');
  assert.equal(formatControlChange(0,locale),'0');
 }
});

test('headline comparisons preserve paired fee window and risk denominators',async()=>{
 const {controlsHighlights}=await import('../src/scripts/strategy-controls-state.mjs');
 const actual=JSON.parse(readFileSync(new URL('../src/data/strategy-controls.v1.json',import.meta.url),'utf8'));
 const rows=controlsHighlights(actual);
 assert.equal(rows.length,2);
 assert.deepEqual(rows.map(r=>[r.market,r.feeBps,r.windows,r.returnWins]),[['US',20,11,6],['crypto',25,12,7]]);
 assert.equal(rows[1].drawdownWins,4);
 assert.ok(Math.abs(rows[1].medianReturnChange-.004125644533451767)<1e-12);
 assert.deepEqual(controlsHighlights({...actual,status:'readiness_only',results:[],pairs:[]}),[]);
});

test('selection cannot mix fees markets or quote currencies',()=>{
 const fixture=controlsFixture();validateControlsSnapshot(fixture);
 assert.equal(selectControls(fixture,{market:'US',feeBps:20}).length,2);
 for(const selection of [{market:'HK',feeBps:20},{market:'US',feeBps:'20'},{market:'US'}])assert.deepEqual(selectControls(fixture,selection),[]);
 assert.equal(selectControlPairs(fixture,{market:'US',feeBps:40})[0].fee_bps,40);
});
test('paired facts require the same window fee and known identities',()=>{
 for(const mutate of [s=>s.results[0].start='2024-02-01',s=>s.pairs[0].fee_bps=40,s=>s.pairs[0].control_job_id='f'.repeat(64),s=>s.results[0].private_path='private']){
  const fixture=controlsFixture();mutate(fixture);assert.throws(()=>validateControlsSnapshot(fixture));
 }
});
test('locale cannot change summaries comparisons or source objects',()=>{
 const fixture=controlsFixture(),before=JSON.stringify(fixture);
 const base=summarizeControls(fixture,{market:'US',feeBps:20});
 for(const locale of ['en','zh-CN','unknown'])assert.deepEqual(summarizeControls(fixture,{market:'US',feeBps:20,locale}),base);
 assert.equal(compareControlCosts(fixture,{market:'US',armId:'ew_monthly'}).length,2);
 assert.equal(JSON.stringify(fixture),before);
});
test('readiness retains every failed denominator without exposing metrics',()=>{
 const fixture=controlsFixture();fixture.status='readiness_only';fixture.coverage={requested_jobs:6,completed_jobs:5,blocked_jobs:1};fixture.blockers=['PUBLICATION_PERMISSION_UNVERIFIED','INCOMPLETE_CONTROLS_RUN'];fixture.results=[];fixture.pairs=[];
 validateControlsSnapshot(fixture);assert.deepEqual(selectControls(fixture,{market:'US',feeBps:20}),[]);assert.equal(fixture.coverage.blocked_jobs,1);
 fixture.results=controlsFixture().results;assert.throws(()=>validateControlsSnapshot(fixture));
 const actual=JSON.parse(readFileSync(new URL('../src/data/strategy-controls.v1.json',import.meta.url),'utf8'));validateControlsSnapshot(actual);
});
