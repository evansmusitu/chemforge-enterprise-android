/* Offline study-only timed drills. NOT a secure or authentic ZIMSEC exam. */
(function(root,factory){const api=factory(typeof module==='object'&&module.exports?require('./engine.js'):root.ChemEngine);if(typeof module==='object'&&module.exports)module.exports=api;if(root)root.ChemMock=api;})(typeof window==='undefined'?null:window,function(E){
'use strict';
function randomOrder(rows,seed){let x=(seed||1)>>>0;const arr=[...rows];for(let i=arr.length-1;i>0;i--){x=(1664525*x+1013904223)>>>0;const j=x%(i+1);[arr[i],arr[j]]=[arr[j],arr[i]];}return arr;}
function start(content,options={},now=Date.now()){
 const {paper='P1',count=5,minutes=10,seed=1}=options;
 if(!['P1','P2','P3','P4'].includes(paper))throw Error('Invalid examination paper selection');
 if(!Number.isInteger(count)||count<1||count>30)throw Error('Invalid drill length');
 if(!Number.isInteger(minutes)||minutes<1||minutes>180)throw Error('Invalid drill duration');
 const pool=content.questions.filter(q=>q.paper===paper);
 if(!pool.length)throw Error('This pilot has no questions for the selected paper');
 const question_ids=randomOrder(pool,seed).slice(0,count).map(q=>q.id);
 return {paper,question_ids,started_at:now,deadline:now+minutes*60_000,answers:{},finished:false};
}
function expired(state,now=Date.now()){return now>=state.deadline;}
function answer(state,questionId,response,now=Date.now()){
 if(state.finished)throw Error('Drill already completed');
 if(expired(state,now))throw Error('Drill expired');
 if(!state.question_ids.includes(questionId))throw Error('Question is not part of this drill');
 return {...state,answers:{...state.answers,[questionId]:String(response??'').slice(0,2500)}};
}
function finish(content,state,now=Date.now()){
 if(state.finished)throw Error('Drill already completed');
 const index=Object.fromEntries(content.questions.map(q=>[q.id,q]));
 let auto_marks=0,auto_max_marks=0,total_possible_marks=0,pending=0;
 const items=state.question_ids.map(id=>{
   const q=index[id];if(!q)throw Error('Drill content changed; results cannot be safely compared');
   total_possible_marks+=q.max_marks;
   const raw=state.answers[id]||'';
   if(q.type==='constructed'){pending++;return {question_id:id,mark:null,max_marks:q.max_marks,response:raw,assessment_source:'requires_human_review',correct_answer:q.explanation};}
   let result;
   try{result=raw.trim()?E.grade(q,raw):{mark:0,assessment_source:q.type==='mcq'?'deterministic_key':'numeric_tolerance',diagnosis:'unanswered',correct:false};}
   catch(e){result={mark:0,assessment_source:q.type==='mcq'?'deterministic_key':'numeric_tolerance',diagnosis:'invalid_response',correct:false};}
   auto_marks+=result.mark;auto_max_marks+=q.max_marks;
   return {question_id:id,mark:result.mark,max_marks:q.max_marks,response:raw,assessment_source:result.assessment_source,diagnosis:result.diagnosis,correct_answer:q.answer,explanation:q.explanation};
 });
 return {finished:true,started_at:state.started_at,finished_at:now,timed_out:expired(state,now),items,auto_marks,auto_max_marks,total_possible_marks,pending};
}
return {start,answer,expired,finish};
});
