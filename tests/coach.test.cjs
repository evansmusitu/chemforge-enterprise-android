const test = require('node:test');
const assert = require('node:assert/strict');
const coach = require('../app/src/main/assets/coach.js');

test('AI coach never supplies a prompt before an independent submission', ()=> {
  assert.throws(()=>coach.makePrompt({submitted:false, question:{stem:'Why?'}, feedback:'F'}, 'Help'), /Submit/);
});
test('grounded prompt includes verified-on-screen data and labels unreviewed content', ()=> {
  const p=coach.makePrompt({submitted:true, question:{id:'Q1', stem:'Why does pressure affect equilibrium?',explanation:'Le Chatelier',rubric:[{text:'Gas moles',marks:1}]}},'Explain simply');
  assert.match(p,/Q1/); assert.match(p,/Le Chatelier/); assert.match(p,/Gas moles/);
  assert.match(p,/unreviewed/); assert.match(p,/Explain simply/);
  assert.match(p,/Do not award marks/);
});
test('student input has bounded length', ()=> {
  assert.throws(()=>coach.makePrompt({submitted:true,question:{stem:'A'}}, 'x'.repeat(1801)), /length/);
});
test('empty question rejected', ()=> {
  assert.throws(()=>coach.makePrompt({submitted:true,question:{stem:'A'}}, '   '), /empty/);
});
test('untrusted response rendering uses textContent instead of innerHTML', ()=> {
  const box={textContent:''}; coach.renderResponse(box, '<img src=x onerror=alert(1)>');
  assert.equal(box.textContent,'<img src=x onerror=alert(1)>');
  assert.equal(box.innerHTML,undefined);
});

test('4 GB mode uses a short prompt even with long editorial text', ()=> {
 const question={id:'LONG', stem:'S'.repeat(3000),explanation:'E'.repeat(3000),rubric:[{text:'R'.repeat(1500)}]};
 const p=coach.makePrompt({submitted:true, question},'Why does this happen?');
 assert.ok(p.length<=2400, `prompt too long: ${p.length}`);
 assert.match(p,/Why does this happen\?/);
});
test('student request must stay within the 4 GB coaching limit', ()=> {
 assert.throws(()=>coach.makePrompt({submitted:true,question:{stem:'A'}},'q'.repeat(601)),/limit/);
});
