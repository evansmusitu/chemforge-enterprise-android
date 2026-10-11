/* CHEMFORGE Android: portable, deliberately uncalibrated offline study heuristics.
 * Both Node tests and WebView load this same implementation. */
(function (root, make) {
  const api = make();
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.ChemEngine = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';
  const DOMAINS=['Physical','Inorganic','Organic','Applied','Practical'];
  const acceptedSources=new Set(['deterministic_key','numeric_tolerance','learner_self_review']);
  const iso=(value)=>{ const n=Date.parse(value||''); return Number.isFinite(n)?n:0; };
  const plain=(raw)=>String(raw??'').trim();
  // Never silently discard an entered unit: that previously awarded false Chemistry marks.
  function normalizeUnit(value) {
    return plain(value).toLowerCase().replace(/\u2212/g,'-')
      .replace(/⁻/g,'-').replace(/⁰/g,'0').replace(/¹/g,'1').replace(/²/g,'2').replace(/³/g,'3')
      .replace(/\u00b3/g,'3').replace(/\s+/g,'').replace(/\u00b7/g,'').replace(/\*/g,'');
  }
  function parseMeasurement(raw) {
    const text=plain(raw).replace(/−/g,'-').replace(/,/g,'').replace(/×\s*10\s*\^\s*([+-]?\d+)/g,'e$1');
    const match=text.match(/^([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)(?:\s+(.+))?$/);
    if(!match || !Number.isFinite(Number(match[1]))) return null;
    return {value:Number(match[1]),unit:plain(match[2]||'')};
  }
  function parseNumber(raw) { const measure=parseMeasurement(raw);return measure?measure.value:null; }
  function grade(q, answer) {
    if (q.type==='constructed') return {mark:null,outcome:'pending_review',assessment_source:'rubric_self_review_required',diagnosis:null,correct:null};
    if (q.type==='mcq') {
      const v=plain(answer).toUpperCase();
      const options=(q.choices||[]).map(c=>String(c.id).toUpperCase());
      if (!options.includes(v)) throw Error('Select a valid answer choice ('+options.join(', ')+').');
      const ok=v===String(q.answer).toUpperCase();
      return {mark:ok?q.max_marks:0,outcome:ok?'correct':'incorrect',assessment_source:'deterministic_key',diagnosis:ok?null:((q.distractor_diagnoses||{})[v]||'unclassified_error'),correct:ok};
    }
    if (q.type==='numeric') {
      const measurement=parseMeasurement(answer);
      if (measurement===null) throw Error('Enter a valid number, optionally followed by a unit separated by a space.');
      const expected=normalizeUnit(q.unit||'unitless');
      const entered=normalizeUnit(measurement.unit);
      let converted=measurement.value;
      if (entered && entered!==expected) {
        const mapping=(q.accepted_units||[]).find(x=>normalizeUnit(x.unit)===entered);
        if(!mapping || !Number.isFinite(Number(mapping.multiplier)) || Number(mapping.multiplier)<=0) {
          return {mark:0,outcome:'incorrect',assessment_source:'numeric_tolerance',diagnosis:'unit_mismatch',correct:false};
        }
        converted*=Number(mapping.multiplier);
      }
      if (entered && expected==='unitless') {
        return {mark:0,outcome:'incorrect',assessment_source:'numeric_tolerance',diagnosis:'unit_mismatch',correct:false};
      }
      const ok=Math.abs(converted-Number(q.answer))<=Number(q.tolerance)+1e-12;
      return {mark:ok?q.max_marks:0,outcome:ok?'correct':'incorrect',assessment_source:'numeric_tolerance',diagnosis:ok?null:'quantitative_method_or_units_unresolved',correct:ok};
    }
    throw Error('Unknown question type.');
  }
  function competenceStates(content,attempts,now=Date.now()) {
    const questions=Object.fromEntries(content.questions.map(q=>[q.id,q]));
    const states={};
    for (const o of content.objectives) {
      const events=attempts.filter(a=>!a.unverified_import && questions[a.question_id]?.objective_id===o.id && a.mark!==null);
      let a=1.5,b=1.5;
      for (const e of events) {
        let weight=e.assessment_source==='learner_self_review'?0.4:1;
        if (e.hints_used>0) weight*=e.hints_used>=2?0.3:0.55;
        if (e.mode==='exam') weight*=1.15;
        const ratio=Math.max(0,Math.min(1,e.mark/e.max_marks));
        a+=ratio*weight;b+=(1-ratio)*weight;
      }
      const estimate=a/(a+b);
      const independent=events.filter(e=>e.hints_used===0 && e.assessment_source!=='learner_self_review' && e.mark/e.max_marks>=.75);
      const dated=independent.map(e=>iso(e.recorded_at)).filter(Boolean).sort((x,y)=>x-y);
      const delayed=dated.length>=2 && dated[dated.length-1]-dated[0]>=86400000;
      const advanced=independent.some(e=>questions[e.question_id]?.difficulty>=4);
      let level='M0';
      if (events.length) level=estimate<.4?'M1':(estimate<.63||independent.length<2)?'M2':(estimate>=.75&&independent.length>=4&&delayed&&advanced)?'M4':'M3';
      const ordered=[...events].sort((x,y)=>iso(x.recorded_at)-iso(y.recorded_at));
      let nextDue=null;
      if (ordered.length) {
        const last=ordered[ordered.length-1];
        let streak=0;
        for (let i=ordered.length-1;i>=0;i--) {if (ordered[i].mark/ordered[i].max_marks>=.75) streak++; else break;}
        const days=last.mark/last.max_marks<.75?0:[1,3,7,14,30][Math.min(4,Math.max(0,streak-1))];
        nextDue=iso(last.recorded_at)+days*86400000;
      }
      states[o.id]={id:o.id,title:o.title,domain:o.domain,prerequisites:o.prerequisites,verification:o.verification,level,
        posterior_estimate:Number(estimate.toFixed(3)),evidence_count:events.length,independent_successes:independent.length,
        due:nextDue!==null&&nextDue<=now,next_due:nextDue?new Date(nextDue).toISOString():null,
        wrong:events.filter(e=>e.mark/e.max_marks<.75).length};
    }
    return states;
  }
  function chooseQuestion(content, attempts, opts={}) {
    const {mode='diagnostic',domain='All',paper='All',exclude=''}=opts;
    const objs=Object.fromEntries(content.objectives.map(o=>[o.id,o]));
    const states=competenceStates(content,attempts);
    let pool=content.questions.filter(q=>(domain==='All'||objs[q.objective_id]?.domain===domain)&&(paper==='All'||q.paper===paper));
    if (!pool.length) throw Error('No questions match these filters.');
    const without=pool.filter(q=>q.id!==exclude);
    if (without.length) pool=without;
    if (mode==='diagnostic') {const diag=pool.filter(q=>q.diagnostic);if(diag.length)pool=diag;}
    const counts={};const domainSeen={};const objSeen={};
    for(const a of attempts.filter(e=>!e.unverified_import)){counts[a.question_id]=(counts[a.question_id]||0)+1;const q=content.questions.find(x=>x.id===a.question_id);if(q){objSeen[q.objective_id]=(objSeen[q.objective_id]||0)+1;const d=objs[q.objective_id]?.domain;domainSeen[d]=(domainSeen[d]||0)+1;}}
    function score(q){const s=states[q.objective_id],seen=counts[q.id]||0;
      return (seen===0?4:0)+(objSeen[q.objective_id]?0:1.8)+(s.evidence_count?1.6*(1-s.posterior_estimate):0)+(s.due?2.1:0)+
        (mode==='diagnostic'?3/(1+(domainSeen[s.domain]||0)):0)-0.35*seen;
    }
    pool.sort((a,b)=>score(b)-score(a)||a.difficulty-b.difficulty||a.id.localeCompare(b.id));
    return pool[0];
  }
  function safeImport(raw,content,tenantId='',fingerprint=content.content_version,source='local') {
    if(!['local','external'].includes(source))throw Error('Invalid record source.');
    let data;try{data=JSON.parse(raw);}catch(_){throw Error('Invalid JSON file.');}
    if (!data||data.app!=='CHEMFORGE_ANDROID'||data.schema_version!==1||!Array.isArray(data.attempts)) throw Error('Not a CHEMFORGE Android v1 export.');
    if (data.attempts.length>10000) throw Error('Too many attempts in this backup.');
    if ((data.tenant_id !== tenantId && !(data.tenant_id === undefined && tenantId === '')) ) throw Error('Backup tenant does not match this organisation.');
    if (data.content_fingerprint !== fingerprint && !(data.content_fingerprint === undefined && fingerprint === 'pilot-0.1')) throw Error('Backup content fingerprint does not match this content revision.');
    if (data.content_version !== content.content_version && !(data.content_version === undefined && content.content_version === 'pilot-0.1')) throw Error('Backup content version does not match the installed question bank.');
    const qs=Object.fromEntries(content.questions.map(q=>[q.id,q]));
    const seenIds=new Set();
    return data.attempts.filter(v=>{
      if (!v || typeof v!=='object' || !qs[v.question_id])return false;
      if (v.tenant_id !== tenantId && !(v.tenant_id === undefined && tenantId === '')) return false;
      if (v.content_fingerprint !== fingerprint && !(v.content_fingerprint === undefined && fingerprint === 'pilot-0.1')) return false;
      if (v.content_version !== content.content_version && !(v.content_version === undefined && content.content_version === 'pilot-0.1')) return false;
      const q=qs[v.question_id];
      if (!acceptedSources.has(v.assessment_source)|| !['practice','exam','diagnostic'].includes(v.mode)) return false;
      if (typeof v.id!=='string'||v.id.length>100||!iso(v.recorded_at))return false;
      if (!Number.isInteger(v.hints_used)||v.hints_used<0||v.hints_used>5)return false;
      if (v.max_marks!==q.max_marks || !Number.isInteger(v.mark)||v.mark<0||v.mark>v.max_marks)return false;
      if (q.type==='constructed' && v.assessment_source!=='learner_self_review')return false;
      if (q.type!=='constructed' && v.assessment_source==='learner_self_review')return false;
      if (seenIds.has(v.id)) return false;
      seenIds.add(v.id);
      return true;
    }).map(v=>({id:v.id,question_id:v.question_id,mark:v.mark,max_marks:v.max_marks,assessment_source:v.assessment_source,
      mode:v.mode,recorded_at:v.recorded_at,hints_used:v.hints_used,diagnosis:typeof v.diagnosis==='string'?v.diagnosis.slice(0,120):null,
      content_version:content.content_version,content_fingerprint:fingerprint,tenant_id:tenantId,
      unverified_import:source==='external' || v.unverified_import===true,
      outcome:v.mark===v.max_marks?'correct':'incorrect'}));
  }
  function metrics(content,attempts){
    const states=competenceStates(content,attempts);
    const graded=attempts.filter(a=>!a.unverified_import && a.assessment_source!=='learner_self_review'&&a.mark!==null);
    const objectives=Object.values(states);
    return {attempts:attempts.length,assessed:objectives.filter(s=>s.evidence_count).length,competent:objectives.filter(s=>['M3','M4'].includes(s.level)).length,
      accuracy:graded.length?Math.round(100*graded.filter(a=>a.mark===a.max_marks).length/graded.length):null,
      due:objectives.filter(s=>s.due).length,domains:DOMAINS.map(domain=>({domain,total:objectives.filter(s=>s.domain===domain).length,
        assessed:objectives.filter(s=>s.domain===domain&&s.evidence_count).length}))};
  }
  return {grade,chooseQuestion,competenceStates,safeImport,metrics,parseNumber};
});
