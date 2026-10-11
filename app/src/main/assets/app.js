/* CHEMFORGE Android Enterprise v1.3 — offline-only learning + optional in-process local inference. */
(()=>{
'use strict';
const data=window.CF_DATA;
const E=window.ChemEngine;
const Coach=window.ChemCoach;
const policy=window.CF_ENTERPRISE_POLICY||{tenant_id:'',enable_local_ai:true,allow_data_export:true,allow_data_import:true,allow_content_import:false};
const tenant=policy.tenant_id||window.CF_PACK_INFO?.tenant_id||'';
const fingerprint=window.CF_PACK_INFO?.content_sha256||data.content_version;
const STORAGE='CHEMFORGE_ANDROID_V1:'+tenant+':'+fingerprint;
const lookup=Object.fromEntries(data.objectives.map(o=>[o.id,o]));
// Never attach the bundled pilot study notes to an installed institutional curriculum.
const lessons=(window.CF_PACK_INFO?data.lessons||[]:window.CF_PILOT_LESSONS||[]);
const lessonByObjective=Object.fromEntries(lessons.map(l=>[l.objective_id,l]));
const $=id=>document.getElementById(id);
const esc=s=>String(s??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
const fmt=stamp=>new Date(stamp).toLocaleDateString(undefined,{month:'short',day:'numeric',year:'numeric'});
let attempts=[];
let storageProblem=false;
let storageLocked=false;
const nativeRecordStore=!!(window.ChemforgeNative && typeof window.ChemforgeNative.loadRecords==='function' && typeof window.ChemforgeNative.saveRecords==='function');
let didMigrate=false;
const initialBackup=()=>({app:'CHEMFORGE_ANDROID',schema_version:1,content_version:data.content_version,content_fingerprint:fingerprint,tenant_id:tenant,attempts});
try {
 if(nativeRecordStore){
   const loaded=JSON.parse(window.ChemforgeNative.loadRecords(tenant,fingerprint));
   if(!loaded.ok)throw Error(loaded.error||'Encrypted history inaccessible');
   if(loaded.found) attempts=E.safeImport(loaded.payload,data,tenant,fingerprint);
   else {
     // One-time upgrade from v1.0 plaintext localStorage. Delete only after sealed write succeeds.
     const legacyKeys=[STORAGE];
     if(data.content_version==='pilot-0.1'&&!tenant)legacyKeys.push('CHEMFORGE_ANDROID_V1');
     for(const oldKey of legacyKeys){
       const raw=localStorage.getItem(oldKey);
       if(!raw)continue;
       attempts=E.safeImport(raw,data,tenant,fingerprint);
       if(!window.ChemforgeNative.saveRecords(tenant,fingerprint,JSON.stringify(initialBackup())))
         throw Error('Could not encrypt migrated history');
       didMigrate=true;
       break;
     }
   }
   // Remove leftover plaintext only after encrypted records are safely stored.
   if(loaded.found || didMigrate){
     localStorage.removeItem(STORAGE);
     if(data.content_version==='pilot-0.1'&&!tenant)localStorage.removeItem('CHEMFORGE_ANDROID_V1');
   }
 } else {
   const raw=localStorage.getItem(STORAGE) || (data.content_version==='pilot-0.1'&&!tenant ? localStorage.getItem('CHEMFORGE_ANDROID_V1'):null);
   if(raw){attempts=E.safeImport(raw,data,tenant,fingerprint);localStorage.setItem(STORAGE,JSON.stringify(initialBackup()));}
 }
} catch(err){storageProblem=true;storageLocked=nativeRecordStore;console.warn('Local study record unavailable:',err.message);}
let mode='diagnostic',screen='home',q=null,selection='',hintsUsed=0,hasSubmitted=false,lastQuestion='';
let coachSequence=0, activeCoachRequest='';
const institutionStatus=$('institution-status');
if (window.CF_PACK_INFO) {
 institutionStatus.textContent='Signed pack: '+window.CF_PACK_INFO.content_version+' · Institution: '+window.CF_PACK_INFO.tenant_id+' · Revision '+window.CF_PACK_INFO.pack_version+' (publisher signature verified; academic accuracy not independently validated).';
} else institutionStatus.textContent='Bundled unreviewed pilot content. '+(tenant?'Managed institution: '+tenant+'. ':'')+'No signed curriculum pack active.';
if(storageProblem) institutionStatus.textContent += ' WARNING: Secure history unavailable; this session may not be saved.';
$('pack-import').disabled=!policy.allow_content_import;
if (!policy.allow_content_import)$('pack-import').title='Disabled by institution policy';
if (!policy.enable_local_ai) {
 $('model-card').classList.add('hidden');
 $('coach-panel').classList.add('hidden');
}
if (!policy.allow_data_export) {
 $('export').disabled=true;
 $('export').title='Institution policy blocks export';
}
if (!policy.allow_data_import) {
 $('import').disabled=true;
 $('import').title='Institution policy blocks study record imports';
}
$('pack-import').addEventListener('click',()=>{
 if (!policy.allow_content_import) return;
 if (window.ChemforgeNative?.importContentPack) window.ChemforgeNative.importContentPack();
 else institutionStatus.textContent='Institution pack import requires the native Android app and an institution-built trust key.';
});
function persist(){
 if(storageLocked){storageProblem=true;return false;}
 try {
   const payload=JSON.stringify(backup());
   if(nativeRecordStore) {
     if(!window.ChemforgeNative.saveRecords(tenant,fingerprint,payload))throw Error('Encrypted storage write failed');
   } else localStorage.setItem(STORAGE,payload);
   storageProblem=false;
   return true;
 }catch(err){storageProblem=true;console.warn('Unable to save local study record:',err.message);return false;}
};
function backup(){return {app:'CHEMFORGE_ANDROID',schema_version:1,exported_at:new Date().toISOString(),content_version:data.content_version,content_fingerprint:fingerprint,tenant_id:tenant,attempts};}
function navigate(name){
 screen=name;
 document.querySelectorAll('.screen').forEach(el=>el.classList.toggle('active',el.id==='screen-'+name));
 document.querySelectorAll('.bottom-nav button').forEach(el=>el.classList.toggle('active',el.dataset.screen===name));
 if(name==='home')renderHome();
 if(name==='learn')renderLessons();
 if(name==='map')renderMap();
 if(name==='journal')renderJournal();
 if(name==='practice'&&!q)nextQuestion();
 window.scrollTo({top:0,behavior:'instant'});
}
function renderHome(){
 const m=E.metrics(data,attempts);
 $('stat-attempts').textContent=m.attempts;
 $('stat-assessed').innerHTML=m.assessed+'<small>/'+data.objectives.length+'</small>';
 $('stat-accuracy').textContent=m.accuracy===null?'—':m.accuracy+'%';
 $('stat-due').textContent=m.due;
 $('domain-bars').innerHTML=m.domains.map(d=>`<div class="domain-row"><div class="domain-label"><b>${esc(d.domain)}</b><span>${d.assessed}/${d.total} assessed</span></div><div class="bar"><div style="width:${d.total?(d.assessed/d.total)*100:0}%"></div></div></div>`).join('');
}
function renderLessons(){
 const domain=$('learn-domain').value;
 const filtered=lessons.filter(l=>domain==='All'||l.domain===domain);
 $('lesson-count').textContent=filtered.length+' editorial lessons';
 $('lesson-list').innerHTML=filtered.length?filtered.map(l=>`<article class="card micro-lesson"><span class="badge">${esc(l.domain)} · ${esc(l.objective_id)}</span><h2>${esc(l.title)}</h2><h3>Key principle</h3><p>${esc(l.principle)}</p><h3>Worked illustration</h3><p>${esc(l.example)}</p><h3>Watch for this error</h3><p>${esc(l.common_error)}</p><small>Editorial review status: ${esc(l.review_status||'unspecified')}</small></article>`).join(''):'<div class="card">No offline lessons for this selection. Curriculum questions remain available.</div>';
}
// Distinct timed study drill: answers and marking points remain hidden until finish.
let mockState=null,mockIndex=0,mockTimer=null;
const mockQuestions=()=>mockState?mockState.question_ids.map(id=>data.questions.find(item=>item.id===id)):[];
function renderMockQuestion(){
 if(!mockState)return;
 const question=mockQuestions()[mockIndex];
 $('mock-count').textContent=`Question ${mockIndex+1} of ${mockState.question_ids.length} · ${mockState.paper}`;
 const previous=mockState.answers[question.id]||'';
 const answers=question.type==='mcq'?`<div>${question.choices.map(c=>`<label class="mock-choice"><input type="radio" name="mock-answer" value="${esc(c.id)}" ${previous===c.id?'checked':''}><span><b>${esc(c.id)}.</b> ${esc(c.text)}</span></label>`).join('')}</div>`:question.type==='numeric'?`<input type="text" id="mock-answer" aria-label="Numeric answer" class="input-answer" inputmode="decimal" value="${esc(previous)}" placeholder="Answer ${esc(question.unit||'')}" />`:`<textarea id="mock-answer" aria-label="Written answer" class="input-answer">${esc(previous)}</textarea>`;
 $('mock-question').innerHTML=`<span class="badge">${esc(question.id)} · ${question.max_marks} MARKS · ${esc(question.paper)}</span><h2>${esc(question.stem)}</h2>${answers}`;
 $('mock-next').textContent=mockIndex===mockState.question_ids.length-1?'Save & finish →':'Save & next →';
 updateMockClock();
}
function storeCurrentMockAnswer(){
 if(!mockState)return;
 const question=mockQuestions()[mockIndex];
 const selected=question.type==='mcq'?(document.querySelector('input[name="mock-answer"]:checked')?.value||''):($('mock-answer')?.value||'');
 if(selected.trim()&&!window.ChemMock.expired(mockState)){
   try{mockState=window.ChemMock.answer(mockState,question.id,selected);}catch(error){console.warn('Mock answer not saved:',error.message);}
 }
}
function updateMockClock(){
 if(!mockState)return;
 const remaining=Math.max(0,Math.ceil((mockState.deadline-Date.now())/1000));
 $('mock-timer').textContent=`${String(Math.floor(remaining/60)).padStart(2,'0')}:${String(remaining%60).padStart(2,'0')}`;
 if(remaining===0)completeMock(true);
}
function completeMock(expired=false){
 if(!mockState)return;
 if(!expired)storeCurrentMockAnswer();
 const result=window.ChemMock.finish(data,mockState);
 if(mockTimer){clearInterval(mockTimer);mockTimer=null;}
 mockState=null;
 $('mock-running').classList.add('hidden');
 $('mock-setup').classList.remove('hidden');
 $('mock-results').classList.remove('hidden');
 let recording='Auto-marked results were not saved.';
 if(!storageLocked){
   const previous=attempts.slice();
   for(const item of result.items.filter(item=>item.mark!==null)){
     attempts.push({id:'mock-'+Date.now()+'-'+Math.random().toString(36).slice(2,9),question_id:item.question_id,
       mark:item.mark,max_marks:item.max_marks,assessment_source:item.assessment_source,mode:'exam',hints_used:0,
       recorded_at:new Date().toISOString(),tenant_id:tenant,content_version:data.content_version,
       content_fingerprint:fingerprint,diagnosis:item.diagnosis||null,outcome:item.mark===item.max_marks?'correct':'incorrect'});
   }
   if(persist())recording='Auto-marked attempts were stored in this device’s study history.';
   else attempts=previous;
 }
 $('mock-results').innerHTML=`<div class="card mock-feedback"><span class="badge">${result.timed_out?'TIME LIMIT REACHED':'DRILL FINISHED'}</span><h2>Automatically scored: ${result.auto_marks}/${result.auto_max_marks} marks</h2><p>${result.pending} written question(s) require separate marking. Total available in this drill: ${result.total_possible_marks}. This is not an official examination score.</p><p>${esc(recording)}</p></div>`+
 result.items.map(item=>{
   const question=data.questions.find(q=>q.id===item.question_id);
   const actual=item.mark===null?'Written response: not automatically marked':`${item.mark}/${item.max_marks} marks`;
   const answer=question.type==='constructed'?question.explanation:question.type==='numeric'?`${question.answer} ${question.unit||''}`:question.answer;
   return `<div class="card mock-feedback"><span class="badge">${esc(item.question_id)}</span><h3>${esc(actual)}</h3><p>Your answer: ${esc(item.response||'(no response)')}</p><p>Editorial answer or explanation: ${esc(String(answer))}</p><p>${esc(question.explanation||'')}</p></div>`;
 }).join('');
}
$('mock-start').addEventListener('click',()=>{
 try{
   const paper=$('mock-paper').value,minutes=Number($('mock-minutes').value);
   mockState=window.ChemMock.start(data,{paper,minutes,count:5,seed:Date.now()>>>0});
   mockIndex=0;
   $('mock-setup').classList.add('hidden');$('mock-results').classList.add('hidden');$('mock-running').classList.remove('hidden');
   renderMockQuestion();
   if(mockTimer)clearInterval(mockTimer);
   mockTimer=setInterval(updateMockClock,1000);
 }catch(err){window.alert(err.message);}
});
$('mock-next').addEventListener('click',()=>{
 if(!mockState)return;
 storeCurrentMockAnswer();
 if(mockIndex<mockState.question_ids.length-1){mockIndex++;renderMockQuestion();}
 else completeMock(false);
});
$('mock-finish').addEventListener('click',()=>completeMock(false));
function renderMap(){
 const s=E.competenceStates(data,attempts);
 const groups=['Physical','Inorganic','Organic','Applied','Practical'];
 $('skill-list').innerHTML=groups.map(domain=>`<h3 class="domain-heading">${domain.toUpperCase()}</h3><section class="card">${data.objectives.filter(o=>o.domain===domain).map(o=>`<div class="objective"><div><strong>${esc(o.title)}</strong><small>${esc(o.competency)}</small>${o.prerequisites.length?`<small>Prerequisites: ${esc(o.prerequisites.map(id=>lookup[id]?.title||id).join(' · '))}</small>`:''}</div><b class="level lv-${s[o.id].level}">${s[o.id].level}</b></div>`).join('')}</section>`).join('');
}
function renderJournal(){
 $('journal-count').textContent=attempts.length+' records';
 $('history-list').innerHTML=attempts.length? [...attempts].reverse().slice(0,100).map(a=>{
  const item=data.questions.find(q=>q.id===a.question_id);
  return `<div class="history-row"><div><strong>${esc(item?.id||a.question_id)} · ${esc(lookup[item?.objective_id]?.title||'Chemistry')}</strong><small>${esc(fmt(a.recorded_at))} · ${esc(a.unverified_import?'Imported (unverified)':(a.assessment_source==='learner_self_review'?'Self-reviewed':'Auto-marked'))}</small></div><b>${a.mark}/${a.max_marks}</b></div>`;
 }).join(''):'<p class="minor">No answers recorded. Start a diagnostic session.</p>';
 $('storage-message').textContent=storageProblem?'Warning: Secure local storage is unavailable. Your newest attempts may not persist.':'';
}
function nextQuestion(){
 const options={mode,domain:$('filter-domain').value,paper:$('filter-paper').value,exclude:lastQuestion};
 try{q=E.chooseQuestion(data,attempts,options);}catch(err){$('question-area').textContent=err.message;return;}
 lastQuestion=q.id; selection='';hintsUsed=0;hasSubmitted=false;
 $('feedback').className='card feedback hidden';$('feedback').innerHTML='';delete $('feedback').dataset.marked;
 $('coach-panel').classList.add('hidden');$('coach-output').textContent='';$('coach-request').value='';activeCoachRequest='';
 const o=lookup[q.objective_id];
 let answers='';
 if(q.type==='mcq') answers='<div id="options">'+q.choices.map(c=>`<button type="button" class="choice" data-choice="${c.id}"><strong>${c.id}</strong><span>${esc(c.text)}</span></button>`).join('')+'</div>';
 else if(q.type==='numeric')answers=`<input aria-label="Numeric response" id="answer-input" class="input-answer" placeholder="Enter number ${esc(q.unit?'(unit: '+q.unit+')':'')}" inputmode="decimal" autocomplete="off" />`;
 else answers='<textarea aria-label="Written chemistry answer" id="answer-input" class="input-answer" placeholder="Write your independent answer. You will self-review against the rubric after submitting."></textarea>';
 $('question-area').innerHTML=`<div class="question-top"><span class="badge">${esc(q.id)} · ${esc(q.paper)} · ${esc(q.max_marks)} MARK${q.max_marks>1?'S':''}</span><span class="meta">${esc(o.domain)} / DIFFICULTY ${q.difficulty}</span></div><h2>${esc(q.stem)}</h2>${answers}<div class="q-tools"><button id="submit-answer" type="button" class="button primary">${q.type==='constructed'?'Reveal assessment rubric':'Submit answer'} <span>→</span></button>${mode!=='exam'?'<button type="button" class="hint-button" id="show-hint">Need a nudge?</button>':''}</div><div id="hint-text" class="hint-text hidden"></div>`;
 document.querySelectorAll('[data-choice]').forEach(b=>b.addEventListener('click',()=>{selection=b.dataset.choice;document.querySelectorAll('[data-choice]').forEach(c=>c.classList.toggle('selected',c.dataset.choice===selection));}));
 $('submit-answer').addEventListener('click',submit);
 if($('show-hint')) $('show-hint').addEventListener('click',()=>{
   hintsUsed++;$('hint-text').classList.remove('hidden');$('hint-text').textContent='Start with the core competency: '+o.competency;
 });
}
function record(mark,source,diagnosis){
 const now=new Date().toISOString();
 attempts.push({id:'mob-'+Date.now()+'-'+Math.random().toString(36).slice(2,9),question_id:q.id,mark,max_marks:q.max_marks,assessment_source:source,
   hints_used:hintsUsed,content_version:data.content_version,content_fingerprint:fingerprint,tenant_id:tenant,recorded_at:now,mode,diagnosis:diagnosis||null,outcome:mark===q.max_marks?'correct':'incorrect'});
 if(!persist()){attempts.pop();window.alert('Answer was evaluated but could not be saved securely. This result will not count towards mastery.');return false;}
 return true;
}
function submit(){
 if(!q||hasSubmitted)return;
 let value=q.type==='mcq'?selection:$('answer-input').value;
 if(!value||!value.trim()){window.alert('Please enter an answer before submitting.');return;}
 let result;try{result=E.grade(q,value);}catch(err){window.alert(err.message);return;}
 hasSubmitted=true;
 document.querySelectorAll('.choice').forEach(b=>b.disabled=true);
 if($('answer-input'))$('answer-input').disabled=true;
 $('submit-answer').disabled=true;
 const panel=$('feedback');panel.className='card feedback';
 if(q.type==='constructed') {
  panel.innerHTML=`<h3>Self-review required · ${q.max_marks} marks</h3><p><b>Model explanation:</b> ${esc(q.explanation)}</p><ol class="rubric">${q.rubric.map(point=>`<li>${esc(point.text||point.description||point.criterion||point.id)} (${point.marks} mark${point.marks>1?'s':''})</li>`).join('')}</ol><p>Compare your answer with these points. This is weaker evidence than independent examiner marking.</p><div class="review-buttons" id="review-buttons">${Array.from({length:q.max_marks+1},(_,n)=>`<button type="button" data-mark="${n}">${n} / ${q.max_marks}</button>`).join('')}</div>`;
  document.querySelectorAll('[data-mark]').forEach(btn=>btn.addEventListener('click',()=>{
    if(panel.dataset.marked==='yes')return;
    const mark=Number(btn.dataset.mark);const saved=record(mark,'learner_self_review',mark<q.max_marks?'self_reported_gap':null);
    panel.dataset.marked='yes';panel.innerHTML+=`<p class="badge">${saved?'Recorded':'NOT SAVED'} ${mark}/${q.max_marks} · learner self-review</p>`;
    document.querySelectorAll('[data-mark]').forEach(b=>b.disabled=true);
  }));
 } else {
  const saved=record(result.mark,result.assessment_source,result.diagnosis);
  panel.classList.add(result.correct?'correct':'incorrect');
  panel.innerHTML=`<h3>${saved?(result.correct?'✓ Correct — evidence recorded':'↗ Not yet — review this principle'):'⚠ Answer evaluated — could not save evidence'}</h3>${!result.correct?`<p>Correct answer: <strong>${esc(q.type==='mcq'?q.answer:q.answer+' '+q.unit)}</strong></p>`:''}<p>${esc(q.explanation)}</p>${result.diagnosis?`<p class="minor">Diagnostic hypothesis: ${esc(result.diagnosis.replaceAll('_',' '))}</p>`:''}<p class="minor">${hintsUsed?'Hint-assisted evidence is discounted.':'Independent answer recorded.'} Academic accuracy requires institution validation.</p>`;
 }
 if (policy.enable_local_ai) $('coach-panel').classList.remove('hidden');
 panel.scrollIntoView({behavior:'smooth',block:'nearest'});
}
function exportStudy(){
 if (!policy.allow_data_export)return;
 const json=JSON.stringify(backup(),null,2);
 if(window.ChemforgeNative&&typeof window.ChemforgeNative.exportJson==='function')window.ChemforgeNative.exportJson(json);
 else {const file=new Blob([json],{type:'application/json'});const a=document.createElement('a');a.href=URL.createObjectURL(file);a.download='chemforge-study-backup.json';document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(a.href),1000);}
}
window.receiveChemforgeImport=function(raw){
 if(!policy.allow_data_import){window.alert('Institution policy blocks study backup imports.');return;}
 try{
 const incoming=E.safeImport(raw,data,tenant,fingerprint,'external');
 if(!window.confirm(`Replace ${attempts.length} local records with ${incoming.length} imported records?`))return;
 if(storageLocked)throw Error('Secure device history is locked; use managed device recovery before importing.');
 const previous=attempts;attempts=incoming;
 if(!persist()){attempts=previous;throw Error('Could not save imported history securely.');}
 renderJournal();renderHome();window.alert('Imported '+incoming.length+' history records (unverified). Imported scores cannot establish mastery.');
 }catch(err){window.alert('Import rejected: '+err.message);}
};
window.receiveChemforgeModelEvent=function(kind, requestId, text){
 if(kind==='status' || (kind==='error' && !requestId)) { $('model-status').textContent=text; return; }
 if(!activeCoachRequest || requestId!==activeCoachRequest)return;
 if(kind==='answer'||kind==='error'||kind==='progress') {
   Coach.renderResponse($('coach-output'),text);
   if(kind!=='progress') $('coach-ask').disabled=false;
 }
};
$('learn-domain').addEventListener('change',renderLessons);
$('model-unload').addEventListener('click',()=>{
 if(window.ChemforgeNative?.unloadModel)window.ChemforgeNative.unloadModel();
 else $('model-status').textContent='Model controls require the Android app.';
});
$('model-import').addEventListener('click',()=>{
 if(window.ChemforgeNative?.importModel)window.ChemforgeNative.importModel();
 else $('model-status').textContent='Model importing only works inside the Android app.';
});
$('coach-ask').addEventListener('click',()=>{
 if(!q || !hasSubmitted)return;
 let prompt;
 try { prompt=Coach.makePrompt({submitted:hasSubmitted,question:q,lesson:lessonByObjective[q.objective_id]||null},$('coach-request').value); }
 catch(err){Coach.renderResponse($('coach-output'),err.message);return;}
 if(!window.ChemforgeNative?.askModel) {
  Coach.renderResponse($('coach-output'),'Local model inference requires the Android version with LiteRT-LM and an imported model.');return;
 }
 activeCoachRequest='coach-'+(++coachSequence);
 $('coach-ask').disabled=true;
 Coach.renderResponse($('coach-output'),'Queued locally. No internet connection is used…');
 window.ChemforgeNative.askModel(activeCoachRequest,prompt);
});
if(!policy.enable_local_ai) $('model-status').textContent='Disabled by enterprise policy.';
else if(window.ChemforgeNative?.modelStatus)window.ChemforgeNative.modelStatus();
else $('model-status').textContent='Desktop preview: native offline model runtime not available.';
for(const b of document.querySelectorAll('[data-screen]'))b.addEventListener('click',()=>navigate(b.dataset.screen));
$('start-study').addEventListener('click',()=>navigate('practice'));
$('review-next').addEventListener('click',()=>{mode='practice';syncModes();navigate('practice');nextQuestion();});
function syncModes(){document.querySelectorAll('[data-mode]').forEach(b=>b.classList.toggle('active',b.dataset.mode===mode));}
document.querySelectorAll('[data-mode]').forEach(b=>b.addEventListener('click',()=>{mode=b.dataset.mode;syncModes();nextQuestion();}));
for(const id of ['filter-domain','filter-paper'])$(id).addEventListener('change',nextQuestion);
$('next-question').addEventListener('click',nextQuestion);
$('export').addEventListener('click',exportStudy);
$('import').addEventListener('click',()=>{
 if(!policy.allow_data_import)return;
 if(window.ChemforgeNative&&typeof window.ChemforgeNative.importJson==='function') window.ChemforgeNative.importJson();
 else {let el=$('import-file');if(!el){el=document.createElement('input');el.type='file';el.accept='application/json';el.id='import-file';el.hidden=true;document.body.appendChild(el);el.addEventListener('change',async()=>{if(el.files?.[0]){if(el.files[0].size>2_000_000){window.alert('File too large');return;}window.receiveChemforgeImport(await el.files[0].text());}el.value='';});}el.click();}
});
$('clear-history').addEventListener('click',()=>{
 if(window.confirm('Permanently delete all locally saved CHEMFORGE attempts?')){
   if(storageLocked){window.alert('Encrypted history is inaccessible and cannot be overwritten from study mode.');return;}
   const previous=attempts;attempts=[];if(!persist()){attempts=previous;window.alert('Could not delete encrypted history.');return;}
   renderJournal();renderHome();q=null;
 }
});
renderHome();
})();
