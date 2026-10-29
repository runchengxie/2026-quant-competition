import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { selectSummary } from '../src/lib/us-cnn-summary.mjs';

const data=JSON.parse(readFileSync(new URL('../src/data/us-cnn-summary.v1.json', import.meta.url)));
test('summary preserves exact exposure, cost and independent window count', () => {
  const full=selectSummary(data,100,20);
  const partial=selectSummary(data,40,20);
  assert.equal(full.length,6);
  assert.equal(partial.length,6);
  assert.equal(full.find(r=>r.strategy==='equal_hold').return.toFixed(4),'0.0530');
  assert.equal(partial.find(r=>r.strategy==='equal_hold').return.toFixed(4),'0.0212');
  assert.ok(full.every(r=>r.windows===9 && r.exposure===100 && r.fee_bps===20));
  assert.throws(()=>selectSummary(data,55,20));
  assert.throws(()=>selectSummary(data,40,21));
});
test('public artifact contains portfolio aggregates only', () => {
  assert.equal(data.data_license_verified,false);
  assert.equal(data.records.length,36);
  assert.ok(data.records.every(r=>!('curve' in r) && r.strategy!=='spy_hold' && !('price' in r)));
});
