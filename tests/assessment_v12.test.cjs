const test = require('node:test');
const assert = require('node:assert/strict');
const E = require('../app/src/main/assets/engine.js');
const pilot = require('../app/src/main/assets/data.json');
const q = pilot.questions.find(q=>q.type==='numeric' && q.unit==='cm³');

test('answers support every valid MCQ choice including E and F',()=>{
 const mcq={type:'mcq',choices:['A','B','C','D','E','F'].map(id=>({id,text:id})),answer:'E',max_marks:1,distractor_diagnoses:{}};
 assert.equal(E.grade(mcq,'E').mark,1);
 assert.equal(E.grade(mcq,'F').mark,0);
 assert.throws(()=>E.grade(mcq,'G'),/choice/i);
});
test('numeric grading rejects incompatible units instead of silently dropping them',()=>{
 assert.equal(E.grade(q,String(q.answer)+' kg').mark,0);
 assert.equal(E.grade(q,String(q.answer)+' kg').diagnosis,'unit_mismatch');
 assert.equal(E.grade(q,String(q.answer)+' cm³').mark,q.max_marks);
 assert.equal(E.grade(q,String(q.answer)).mark,q.max_marks);
});
test('dimensionless measurements cannot be supplied with arbitrary units',()=>{
 const dimensionless=pilot.questions.find(q=>q.type==='numeric' && q.unit==='unitless');
 assert.equal(E.grade(dimensionless,String(dimensionless.answer)).mark,dimensionless.max_marks);
 assert.equal(E.grade(dimensionless,String(dimensionless.answer)+' kg').mark,0);
});
test('only explicitly configured unit conversions are allowed',()=>{
 const item={...q,answer:25,unit:'cm³',tolerance:0.1,accepted_units:[{unit:'dm³',multiplier:1000}]};
 assert.equal(E.grade(item,'0.025 dm³').mark,item.max_marks);
 assert.equal(E.grade(item,'0.025 m³').mark,0);
});
test('scientific notation and superscript typography survive parsing',()=>{
 assert.equal(E.grade({...q,answer:20,unit:'cm³'},'2×10^1 cm3').mark,q.max_marks);
 assert.equal(E.grade({...q,answer:20,unit:'cm³'},'2e1 cm³').mark,q.max_marks);
});
test('a unit cannot silently swallow arbitrary additional tokens',()=>{
 assert.equal(E.grade(q,String(q.answer)+' cm³ and garbage').mark,0);
});
