const test = require('node:test');
const assert = require('node:assert/strict');
const diagnostics = require('../app/src/main/assets/model_diagnostics.js');

const successful = () => JSON.stringify({
  kind: 'local_inference_benchmark', verified: true, backend: 'CPU',
  model_sha256_prefix: 'ab12cd34ef56', model_bytes: 374000000,
  load_ms: 1420, inference_ms: 2135, response_chars: 104,
  ram_available_before_mb: 1873, ram_available_after_mb: 1421,
  android_api: 35
});

test('offline model diagnostic displays measured load/inference and memory without generating scores',()=>{
  const result = diagnostics.formatBenchmark(successful());
  assert.match(result, /1,420 ms/);
  assert.match(result, /2,135 ms/);
  assert.match(result, /CPU/);
  assert.match(result, /1,873 MB/);
  assert.match(result, /ab12cd34ef56/);
  assert.doesNotMatch(result, /score|grade|mark/i);
});

test('offline diagnostic refuses unmeasured or invalid telemetry',()=>{
  assert.throws(()=>diagnostics.formatBenchmark('{}'), /invalid|unverified/i);
  assert.throws(()=>diagnostics.formatBenchmark(JSON.stringify({...JSON.parse(successful()),verified:false})),/unverified/i);
  assert.throws(()=>diagnostics.formatBenchmark(JSON.stringify({...JSON.parse(successful()),inference_ms:-5})),/invalid/i);
  assert.throws(()=>diagnostics.formatBenchmark('{broken'),/invalid/i);
});

test('diagnostic output is a narrow whitelist of numeric fields, not arbitrary model text',()=>{
  const attack={...JSON.parse(successful()), freeform:'<img src=x onerror=alert(1)>', model_sha256_prefix:'<script>'};
  assert.throws(()=>diagnostics.formatBenchmark(JSON.stringify(attack)),/invalid/i);
});
