const test=require('node:test');const assert=require('node:assert/strict');
const Coach=require('../app/src/main/assets/coach.js');
const fs=require('node:fs'); const filename=require('node:path').resolve(__dirname,'../app/src/main/assets/lessons.js'); const library=fs.existsSync(filename)?require(filename):[];
const data=require('../app/src/main/assets/data.json');
test('offline micro lessons cover multiple Chemistry domains without pretending expert approval',()=>{
 assert.equal(library.length,data.objectives.length);
 assert.equal(new Set(library.map(l=>l.objective_id)).size,library.length);
 assert(new Set(library.map(l=>l.domain)).size>=4);
 const ids=new Set(data.objectives.map(o=>o.id));
 for(const l of library){assert(ids.has(l.objective_id));assert(l.title && l.principle && l.example && l.common_error);assert.equal(l.review_status,'unreviewed');}
});
test('AI prompt adds available curriculum-context but treats it as unreviewed data',()=>{
 const question=data.questions[0];const lesson={title:'Pilot lesson',principle:'PILOT PRINCIPLE',example:'x',common_error:'y'};
 const prompt=Coach.makePrompt({submitted:true,question,lesson},'Explain the key idea');
 assert(prompt.includes('PILOT PRINCIPLE'));
 assert(prompt.includes('unreviewed'));
 assert(prompt.length<=2800);
});
test('unknown lesson data never breaks AI prompt creation',()=>{
 const prompt=Coach.makePrompt({submitted:true,question:data.questions[0],lesson:null},'Explain please');
 assert(prompt.includes('QUESTION ID:'));
});
