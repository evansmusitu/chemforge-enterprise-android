const test=require('node:test');const assert=require('node:assert/strict');const fs=require('node:fs');const path=require('node:path');
const file=path.resolve(__dirname,'../app/src/main/assets/mock.js');const M=fs.existsSync(file)?require(file):null;
const corpus=require('../app/src/main/assets/data.json');
test('mock selects unique paper-specific questions and records a fixed deadline',()=>{
 assert(M); const now=Date.parse('2026-10-11T12:00:00Z');
 const state=M.start(corpus,{paper:'P1',count:5,minutes:10,seed:11},now);
 assert.equal(state.question_ids.length,5);assert.equal(new Set(state.question_ids).size,5);
 assert(state.question_ids.every(id=>corpus.questions.find(q=>q.id===id).paper==='P1'));
 assert.equal(state.deadline,now+600000);
});
test('mock defers feedback until completion and checks all attempted questions',()=>{
 const at=Date.parse('2026-10-11T12:00:00Z');const state=M.start(corpus,{paper:'P1',count:2,minutes:5,seed:3},at);
 const q=corpus.questions.find(q=>q.id===state.question_ids[0]);
 const updated=M.answer(state,q.id,q.answer,at+1000);
 assert.equal(updated.answers[q.id],q.answer);
 assert.equal(updated.feedback,undefined);
 const result=M.finish(corpus,updated,at+5000);
 assert.equal(result.finished,true);
 const scored=result.items.find(x=>x.question_id===q.id);
 assert.equal(scored.mark,q.max_marks);
 assert.equal(result.items.length,2);
});
test('late submissions are rejected and time expiry completes automatically',()=>{
 const at=Date.parse('2026-10-11T12:00:00Z');const state=M.start(corpus,{paper:'P1',count:2,minutes:1},at);
 assert.equal(M.expired(state,at+60001),true);
 assert.throws(()=>M.answer(state,state.question_ids[0],'A',at+60001),/expired/i);
 const result=M.finish(corpus,state,at+60001);assert.equal(result.timed_out,true);
});
test('constructed questions must never enter automatically scored marks',()=>{
 const at=Date.parse('2026-10-11T12:00:00Z');const state=M.start(corpus,{paper:'P3',count:2,minutes:5,seed:99},at);
 const q=corpus.questions.find(q=>q.id===state.question_ids[0]);
 const result=M.finish(corpus,M.answer(state,q.id,'This is a sample explanation',at+10),at+200);
 assert(result.items.some(item=>item.mark===null));
 assert(result.auto_max_marks<result.total_possible_marks);
});
test('does not allow duplicate answer references or invalid paper selectors',()=>{
 assert.throws(()=>M.start(corpus,{paper:'P9',count:3,minutes:5}),/paper/i);
 const state=M.start(corpus,{paper:'P1',count:2,minutes:5},Date.now());
 assert.throws(()=>M.answer(state,'NOT-A-QUESTION','A'),/not part/i);
});
