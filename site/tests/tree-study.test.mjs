import assert from 'node:assert/strict';
import {test} from 'node:test';
import {readFileSync} from 'node:fs';
import {matches} from '../src/scripts/tree-study-state.mjs';
const facts=JSON.parse(readFileSync(new URL('../src/data/tree-study.v1.json',import.meta.url)));
test('matched selectors preserve a complete nine-pair slice and nulls',()=>{
  for(const window of facts.rules.windows.map(w=>w[0])) for(const horizon of [5,20])
  for(const fee_bps of [0,20,40]) for(const delay of [0,1]) for(const buffer of [0,20]) {
    const rows=facts.comparisons.filter(row=>matches(row,{window,horizon,fee_bps,delay,buffer}));
    assert.equal(rows.length,9);
    for(const row of rows) {
      assert.equal(row.window,window);
      if(row.reason) assert.equal(row.difference,null);
      assert.equal(row.reference_buffer,row.reference==='equal_weight'?0:buffer);
    }
  }
});
test('factor filters cannot mix horizon or window',()=>{
  const rows=facts.models.filter(row=>matches(row,{window:'2026-07-27',horizon:20}));
  assert.equal(rows.length,2);
  assert.deepEqual(rows.map(r=>r.model).sort(),['momentum20','shallow_tree']);
});
