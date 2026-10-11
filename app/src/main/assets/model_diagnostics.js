(function(root,factory){
 const api=factory();
 if(typeof module==='object'&&module.exports)module.exports=api;
 if(root)root.ChemModelDiagnostics=api;
})(typeof window==='undefined'?null:window,function(){
 'use strict';
 function formatBenchmark(raw){
  let result;
  try {
    if (typeof raw!=='string'||raw.length>2048)throw Error('Too large');
    result=JSON.parse(raw);
  } catch(_) {throw Error('Invalid offline model diagnostic data.');}
  if(!result||result.kind!=='local_inference_benchmark'||result.verified!==true)
    throw Error('Unverified offline model diagnostic.');
  const counters=['load_ms','inference_ms','model_bytes','response_chars','ram_available_before_mb','ram_available_after_mb','android_api'];
  if(counters.some(k=>!Number.isSafeInteger(result[k])||result[k]<0))
    throw Error('Invalid offline model diagnostic measurements.');
  if(result.response_chars===0||result.model_bytes===0||result.inference_ms===0||result.android_api<26||result.backend!=='CPU'||
      typeof result.model_sha256_prefix!=='string'||!(/^[0-9a-f]{12}$/.test(result.model_sha256_prefix)))
    throw Error('Invalid offline model diagnostic metadata.');
  const number=n=>n.toLocaleString('en-US');
  return [
    'Offline inference completed on this device (CPU).',
    `Model SHA-256 prefix: ${result.model_sha256_prefix}`,
    `Model file: ${number(result.model_bytes)} bytes`,
    `Model initialization: ${number(result.load_ms)} ms`,
    `Response generation: ${number(result.inference_ms)} ms`,
    `Available RAM: ${number(result.ram_available_before_mb)} MB before / ${number(result.ram_available_after_mb)} MB after`,
    `Android API: ${number(result.android_api)}`,
    'Diagnostic only; no learning evidence has been changed.'
  ].join('\n');
}
 return {formatBenchmark};
});
