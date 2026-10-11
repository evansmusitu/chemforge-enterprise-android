const test = require('node:test');
const assert = require('node:assert/strict');
const E = require('../app/src/main/assets/engine.js');
const seed = require('../app/src/main/assets/data.json');
const mcq = seed.questions.find(q => q.type === 'mcq');
const numeric = seed.questions.find(q => q.type === 'numeric');
const written = seed.questions.find(q => q.type === 'constructed');

function wrongLetter(answer) {return ['A','B','C','D'].find(x => x !== answer);}

test('original content remains limited and identified as unreviewed', () => {
  assert.equal(seed.scope, 'limited_editorial_pilot_not_full_syllabus');
  assert.equal(seed.questions.length, 44);
  assert(seed.questions.every(q => q.review_status === 'unreviewed'));
});
test('MCQ marks correct and incorrect answers without granting phantom credit', () => {
  assert.deepEqual(E.grade(mcq,mcq.answer).mark, 1);
  assert.equal(E.grade(mcq,wrongLetter(mcq.answer)).mark, 0);
  assert.throws(() => E.grade(mcq, 'E'), /choice/i);
});
test('numeric grading respects absolute tolerance and rejects invalid input', () => {
  assert.equal(E.grade(numeric, String(numeric.answer)).mark,1);
  assert.equal(E.grade(numeric, String(numeric.answer)+' '+numeric.unit).mark,1);
  assert.equal(E.grade(numeric, String(numeric.answer)+' kg').mark,0);
  assert.equal(E.grade(numeric, String(numeric.answer+numeric.tolerance*2+1)).mark,0);
  assert.throws(() => E.grade(numeric,'one mole'), /number/i);
  assert.throws(() => E.grade(numeric, 'Infinity'), /number/i);
});
test('constructed answers are never automatically marked', () => {
  assert.equal(E.grade(written,'some explanation').mark,null);
  assert.equal(E.grade(written,'some explanation').outcome,'pending_review');
});
test('unassessed topics never count as mastered', () => {
 const states=E.competenceStates(seed,[]);
 assert.equal(Object.keys(states).length,28);
 assert.equal(states[mcq.objective_id].level,'M0');
});
test('self review is weaker evidence than deterministically graded work', () => {
 const now = new Date().toISOString();
 const a = {id:'1',question_id:mcq.id,mark:1,max_marks:1,assessment_source:'deterministic_key',hints_used:0,mode:'practice',recorded_at:now};
 const b = {...a,id:'2',assessment_source:'learner_self_review'};
 const x=E.competenceStates(seed,[a])[mcq.objective_id];
 const y=E.competenceStates(seed,[b])[mcq.objective_id];
 assert(x.posterior_estimate>y.posterior_estimate);
});
test('question selection honors filters and avoids immediate repeats', () => {
 const q1=E.chooseQuestion(seed,[],{domain:'Physical',paper:'P1',mode:'diagnostic'});
 assert.equal(q1.paper,'P1');
 const q2=E.chooseQuestion(seed,[],{domain:'Physical',paper:'P1',mode:'diagnostic',exclude:q1.id});
 assert.notEqual(q1.id,q2.id);
});
test('validation excludes adversarial stored attempts and preserves only expected record fields', () => {
 const result=E.safeImport(JSON.stringify({app:'CHEMFORGE_ANDROID',schema_version:1,attempts:[{id:'one',question_id:mcq.id,mark:1,max_marks:1,recorded_at:'2026-10-11T01:00:00Z',hints_used:0,assessment_source:'deterministic_key',mode:'practice',outcome:'correct',diagnosis:null},{id:'x',question_id:'fake',mark:100,max_marks:1}]}),seed);
 assert.equal(result.length,1);
 assert.equal(result[0].question_id,mcq.id);
 assert.throws(()=>E.safeImport('{oops',seed),/JSON/i);
});

test('duplicate imported attempt IDs are discarded to prevent accidental double counting', () => {
 const attempt={id:'same',question_id:mcq.id,mark:1,max_marks:1,recorded_at:'2026-10-11T01:00:00Z',hints_used:0,assessment_source:'deterministic_key',mode:'practice'};
 const imported=E.safeImport(JSON.stringify({app:'CHEMFORGE_ANDROID',schema_version:1,attempts:[attempt,{...attempt}]}),seed);
 assert.equal(imported.length,1);
});

test('institutional backups cannot count results from a different content version', () => {
 const attempt={id:'signed-1',question_id:mcq.id,mark:1,max_marks:1,recorded_at:'2026-10-11T01:00:00Z',hints_used:0,assessment_source:'deterministic_key',mode:'practice',content_version:'campus-2027-r1',content_fingerprint:'c'.repeat(64)};
 const doc={app:'CHEMFORGE_ANDROID',schema_version:1,content_version:'campus-2027-r1',content_fingerprint:'c'.repeat(64),attempts:[attempt]};
 assert.throws(()=>E.safeImport(JSON.stringify(doc),seed,'','c'.repeat(64)),/content version/i);
 const institutional={...seed,content_version:'campus-2027-r1'};
 assert.equal(E.safeImport(JSON.stringify(doc),institutional,'','c'.repeat(64)).length,1);
 assert.equal(E.safeImport(JSON.stringify({...doc,attempts:[{...attempt,content_version:'campus-old'}]}),institutional,'','c'.repeat(64)).length,0);
});

test('legacy pilot attempt backup remains importable only with pilot content', () => {
 const doc={app:'CHEMFORGE_ANDROID',schema_version:1,content_version:'pilot-0.1',attempts:[{id:'legacy',question_id:mcq.id,mark:1,max_marks:1,recorded_at:'2026-10-11T01:00:00Z',hints_used:0,assessment_source:'deterministic_key',mode:'practice'}]};
 assert.equal(E.safeImport(JSON.stringify(doc),seed).length,1);
 assert.throws(()=>E.safeImport(JSON.stringify(doc),{...seed,content_version:'campus-2027-r1'}),/content (version|fingerprint)/i);
});

test('institution student records cannot migrate into another tenant even if content ids match', () => {
 const a={id:'1',question_id:mcq.id,mark:1,max_marks:1,recorded_at:'2026-10-11T01:00:00Z',hints_used:0,assessment_source:'deterministic_key',mode:'practice',content_version:'pilot-0.1',tenant_id:'school-A'};
 const p={app:'CHEMFORGE_ANDROID',schema_version:1,content_version:'pilot-0.1',tenant_id:'school-A',attempts:[a]};
 assert.throws(()=>E.safeImport(JSON.stringify(p),seed,'school-B'),/tenant/i);
 assert.equal(E.safeImport(JSON.stringify(p),seed,'school-A').length,1);
});

test('changing a signed question pack digest invalidates previous evidence even with the same version label', () => {
 const a={id:'i1',question_id:mcq.id,mark:1,max_marks:1,recorded_at:'2026-10-11T01:00:00Z',hints_used:0,assessment_source:'deterministic_key',mode:'practice',content_version:'school-r2',tenant_id:'school-A',content_fingerprint:'a'.repeat(64)};
 const doc={app:'CHEMFORGE_ANDROID',schema_version:1,content_version:'school-r2',tenant_id:'school-A',content_fingerprint:'a'.repeat(64),attempts:[a]};
 const institutional={...seed,content_version:'school-r2'};
 assert.equal(E.safeImport(JSON.stringify(doc),institutional,'school-A','a'.repeat(64)).length,1);
 assert.throws(()=>E.safeImport(JSON.stringify(doc),institutional,'school-A','b'.repeat(64)),/fingerprint/i);
});

test('external JSON backup is retained as history but cannot mint verified mastery evidence', () => {
 const when='2026-10-11T01:00:00Z';
 const attempt={id:'imported',question_id:mcq.id,mark:1,max_marks:1,recorded_at:when,
   hints_used:0,assessment_source:'deterministic_key',mode:'exam'};
 const incoming={app:'CHEMFORGE_ANDROID',schema_version:1,content_version:seed.content_version,
   content_fingerprint:seed.content_version,tenant_id:'',attempts:[attempt]};
 const imported=E.safeImport(JSON.stringify(incoming),seed,'',seed.content_version,'external');
 assert.equal(imported.length,1);
 assert.equal(imported[0].unverified_import,true);
 assert.equal(E.competenceStates(seed,imported)[mcq.objective_id].level,'M0');
 const local=E.safeImport(JSON.stringify({...incoming,attempts:imported}),seed);
 assert.equal(local[0].unverified_import,true,'untrusted origin must survive encrypted local reload');
 assert.equal(E.metrics(seed,local).accuracy,null);
 const original=E.safeImport(JSON.stringify(incoming),seed);
 assert.notEqual(original[0].unverified_import,true);
});

test('unverified external scores cannot manipulate adaptive question prioritisation', () => {
 const baseline=E.chooseQuestion(seed,[],{mode:'diagnostic'}).id;
 const fabricated={id:'fake-1',question_id:baseline,mark:1,max_marks:1,
   recorded_at:'2026-10-11T10:00:00Z',hints_used:0,mode:'practice',
   assessment_source:'deterministic_key',unverified_import:true};
 assert.equal(E.chooseQuestion(seed,[fabricated],{mode:'diagnostic'}).id,baseline);
});

test('auto-marked items award their declared mark allocation rather than a hard-coded one', () => {
 assert.equal(E.grade({...mcq,max_marks:2},mcq.answer).mark,2);
 assert.equal(E.grade({...numeric,max_marks:3},String(numeric.answer)).mark,3);
 assert.equal(E.grade({...numeric,max_marks:3},String(numeric.answer+numeric.tolerance+100)).mark,0);
});
