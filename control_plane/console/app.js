/* CHEMFORGE Control: zero third-party scripts, zero persistent bearer-token storage.
 * All user-controlled text is appended using textContent, never HTML injection. */
(() => {
  'use strict';
  const doc = document;
  const $ = (id) => doc.getElementById(id);
  let token = null;
  let identity = null;
  let current = 'overview';
  let messageTimer = null;
  const views = [
    ['overview', '◈', 'Overview'], ['students', '♙', 'Students'],
    ['assignments', '▤', 'Assignments'], ['teachers', '♧', 'Teachers'],
    ['content', '⬡', 'Curriculum'], ['audit', '☷', 'Audit']
  ];
  const labels = {
    overview: 'Institution overview', students: 'Student roster',
    assignments: 'Assignments', teachers: 'Teacher administration',
    content: 'Curriculum registry', audit: 'Institution audit trail'
  };

  function node(tag, value = null, className = '') {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (value !== null) element.textContent = String(value);
    return element;
  }
  function put(parent, ...children) { children.forEach(child => parent.appendChild(child)); return parent; }
  function clear(parent) { parent.replaceChildren(); return parent; }
  function control(labelText, name, opts = {}) {
    const box = node('div');
    const label = node('label', labelText);
    const input = document.createElement(opts.type === 'select' ? 'select' : 'input');
    input.name = name;
    input.id = 'cf-' + name;
    label.htmlFor = input.id;
    if (opts.type && opts.type !== 'select') input.type = opts.type;
    if (opts.required !== false) input.required = true;
    if (opts.placeholder) input.placeholder = opts.placeholder;
    if (opts.maxLength) input.maxLength = opts.maxLength;
    if (opts.accept) input.accept = opts.accept;
    if (opts.type === 'select') {
      (opts.options || []).forEach(([value, label]) => {
        const option = node('option', label);
        option.value = value;
        input.appendChild(option);
      });
    }
    put(box, label, input);
    return {box, input};
  }
  function button(text, handler, cls = 'btn', kind = 'button') {
    const b = node('button', text, cls);
    b.type = kind;
    if (handler) b.addEventListener('click', handler);
    return b;
  }
  function notice(text, isError = false) {
    clear($('messages'));
    const element = node('div', null, 'notice' + (isError ? ' error' : ''));
    put(element, node('span', text), button('×', () => clear($('messages'))));
    $('messages').appendChild(element);
    if (messageTimer) clearTimeout(messageTimer);
    messageTimer = setTimeout(() => clear($('messages')), 9000);
  }
  async function request(path, options = {}) {
    if (!token) throw new Error('Sign in before using the administration API.');
    const response = await fetch(path, {
      method: options.method || 'GET', cache: 'no-store', credentials: 'omit',
      redirect: 'error', mode: 'same-origin',
      headers: {'Authorization': 'Bearer ' + token, ...(options.body ? {'Content-Type': 'application/json'} : {})},
      ...(options.body ? {body: JSON.stringify(options.body)} : {})
    });
    if (response.status === 401) {
      logout();
      throw new Error('Credential expired or was revoked; sign in again.');
    }
    const payload = response.status === 204 ? null : await response.json();
    if (!response.ok) {
      const raw = payload && payload.detail;
      const detail = typeof raw === 'string' ? raw : `Request rejected (${response.status})`;
      throw new Error(detail.slice(0, 240));
    }
    return payload;
  }
  function logout() {
    token = null; identity = null;
    clear($('content')); clear($('navigation')); clear($('messages'));
    $('workspace').hidden = true; $('navigation').hidden = true; $('identity').hidden = true;
    $('logout').hidden = true; $('login').hidden = false;
    $('page-title').textContent = 'Institutional console';
    $('credential').value = '';
  }
  function nav() {
    const pane = clear($('navigation'));
    views.filter(([key]) => identity.role === 'admin' || !['teachers','audit'].includes(key))
      .forEach(([key, icon, title]) => {
        const b = button('', () => { current = key; render(); });
        put(b, node('span', icon, 'nav-icon'), node('span', title));
        if (current === key) b.setAttribute('aria-current', 'page');
        pane.appendChild(b);
      });
    pane.hidden = false;
  }
  function wrap(title, description) {
    const root = node('div', null, 'content-wrap');
    const top = node('div', null, 'section-top');
    const section = node('div');
    put(section, node('h2', title), node('p', description));
    put(top, section); root.appendChild(top);
    return {root, top};
  }
  function card(title, ...content) {
    const block = node('section', null, 'card');
    block.appendChild(node('h3', title));
    content.forEach(child => block.appendChild(child));
    return block;
  }
  function metric(label, value, detail, alert = false) {
    const item = node('article', null, 'metric' + (alert ? ' alert' : ''));
    put(item, node('div', label, 'metric-label'), node('div', value, 'metric-value'), node('div', detail, 'metric-note'));
    return item;
  }
  function grid(headers, rows, transforms = []) {
    if (!rows.length) return node('p', 'No records available for this institution.', 'empty');
    const wrap = node('div', null, 'table-wrap');
    const table = node('table');
    const thead = node('thead');
    const tr = node('tr');
    headers.forEach(head => tr.appendChild(node('th', head)));
    thead.appendChild(tr);
    const tbody = node('tbody');
    rows.forEach(row => {
      const r = node('tr');
      row.forEach((item, i) => {
        const td = node('td');
        const render = transforms[i];
        if (render) render(td, item, row);
        else td.textContent = item == null ? '—' : String(item);
        r.appendChild(td);
      });
      tbody.appendChild(r);
    });
    put(table, thead, tbody); wrap.appendChild(table);
    return wrap;
  }
  function dateStr(s) { if (!s) return '—'; const d = new Date(s); return Number.isFinite(d.getTime()) ? d.toLocaleDateString() : String(s); }
  function dangerous(txt, action) {
    return button(txt, async () => {
      if (!window.confirm('Confirm this irreversible institution-level action?')) return;
      try { await action(); notice('Action completed.'); await render(); }
      catch (err) { notice(err.message, true); }
    }, 'btn btn-danger btn-small');
  }
  async function overview() {
    const [people, cohorts, assignments, releases] = await Promise.all([
      request('/v1/students'), request('/v1/analytics/cohorts'),
      request('/v1/assignments'), request('/v1/content/releases')
    ]);
    const {root} = wrap('Learning operations', 'At-a-glance records for your current institution. All imported learning evidence is unverified.');
    const metrics = node('div', null, 'metrics');
    const unverified = cohorts.reduce((sum, row) => sum + row.unverified_attempts, 0);
    put(metrics,
      metric('Registered learners', people.length, 'Pseudonymous profiles'),
      metric('Active assignments', assignments.length, 'Institutional activity'),
      metric('Offline imports', unverified, 'Unverified evidence', true),
      metric('Curriculum releases', releases.length, 'Metadata only'));
    root.appendChild(metrics);
    const cols = node('div', null, 'columns');
    put(cols,
      card('Cohort activity', grid(['Cohort','Learners','Unverified attempts','Verified'],
        cohorts.map(c => [c.cohort,c.students,c.unverified_attempts,c.verified_attempts]))),
      card('Evidence policy', node('p', 'CHEMFORGE Student remains offline. This control plane accepts manually imported study history but does not certify examination marks or on-device mastery.'), node('div', 'STATUS: ALL IMPORTED SCORES UNVERIFIED', 'badge warn')));
    root.appendChild(cols);
    return root;
  }
  async function students() {
    const people = await request('/v1/students');
    const {root} = wrap('Students', 'Pseudonymous learners are isolated within this institution.');
    const cols = node('div', null, 'columns');
    const form = node('form');
    const name = control('Student display name', 'pseudonym', {maxLength:80, placeholder:'Learner 001'});
    const cohort = control('Cohort / class', 'cohort', {maxLength:40, placeholder:'L6-A'});
    put(form, name.box, cohort.box);
    form.appendChild(button('Add student +', null, 'btn btn-primary', 'submit'));
    form.addEventListener('submit', async event => {
      event.preventDefault();
      try {await request('/v1/students',{method:'POST',body:{pseudonym:name.input.value.trim(),cohort:cohort.input.value.trim()}}); notice('Student added.'); await render();}
      catch(err) { notice(err.message,true); }
    });
    const importer = node('form');
    const studentSelect = control('Student to receive backup', 'backup_student', {type:'select', options:people.map(s => [s.id,`${s.pseudonym} · ${s.cohort}`])});
    const file = control('CHEMFORGE Android backup (.json)', 'backup', {type:'file',accept:'.json,application/json'});
    put(importer, studentSelect.box, file.box,
      node('p', 'Manual transfer only · Imported scores cannot become certified examination evidence.', 'hint'));
    importer.appendChild(button('Import backup', null, 'btn', 'submit'));
    importer.addEventListener('submit', async event => {
      event.preventDefault();
      const selected = file.input.files && file.input.files[0];
      if (!selected || !studentSelect.input.value) { notice('Choose a student and JSON file.',true); return; }
      if (selected.size > 1024 * 1024) { notice('Backup exceeds the 1 MB import limit.',true); return; }
      try {
        const body = JSON.parse(await selected.text());
        const result = await request(`/v1/students/${encodeURIComponent(studentSelect.input.value)}/backups`,{method:'POST',body});
        file.input.value = '';
        if (result.verified !== 0) throw new Error('Unexpected verified evidence in an offline import response.');
        notice(`Imported ${result.imported}; ${result.unchanged} already received. Status: ${'unverified_import'.replace('_', ' ')}.`);
        await render();
      } catch(err) { notice(err.message,true); }
    });
    put(cols,card('Add learner',form),card('Import offline learning history', importer));
    root.appendChild(cols);
    root.appendChild(card('Learner roster',grid(['Student','Cohort','Registered','Action'],
      people.map(x => [x.pseudonym,x.cohort,dateStr(x.created_at),x.id]),[
        null,null,null,(cell,id) => { if(identity.role === 'admin') cell.appendChild(dangerous('Erase', () => request(`/v1/students/${encodeURIComponent(id)}`,{method:'DELETE'}))); else cell.textContent = 'Admin only'; }
      ])));
    return root;
  }
  async function assignments() {
    const records = await request('/v1/assignments');
    const {root} = wrap('Assignments', 'Assign specific curriculum objectives to a cohort. Android distribution is not automatic in this pilot.');
    const form = node('form', null, 'form-grid');
    const title = control('Assignment title','assignment_title',{maxLength:120,placeholder:'Chemical Equilibrium Revision'});
    const cohort = control('Cohort','assignment_cohort',{maxLength:40,placeholder:'L6-A'});
    const objective = control('Objective IDs (comma separated)','objectives',{placeholder:'CHEM-001, CHEM-002'});
    objective.box.classList.add('span-all');
    const due = control('Due date (optional)','due',{type:'datetime-local',required:false});
    const action = node('div'); action.appendChild(button('Create assignment +',null,'btn btn-primary','submit'));
    put(form,title.box,cohort.box,objective.box,due.box,action);
    form.addEventListener('submit',async event => {
      event.preventDefault();
      const ids=objective.input.value.split(',').map(s=>s.trim()).filter(Boolean);
      const payload={title:title.input.value.trim(),cohort:cohort.input.value.trim(),objective_ids:ids};
      if(due.input.value) payload.due_at=new Date(due.input.value).toISOString();
      try{await request('/v1/assignments',{method:'POST',body:payload});notice('Assignment created.');await render();}
      catch(err){notice(err.message,true);}
    });
    root.appendChild(card('New assignment',form));
    root.appendChild(card('Assignments',grid(['Title','Cohort','Objectives','Due'],records.map(x=>[
      x.title,x.cohort,x.objective_ids.join(', '),dateStr(x.due_at)]))));
    return root;
  }
  async function teachers() {
    if(identity.role!=='admin') throw new Error('Administrator access required.');
    const records = await request('/v1/teachers');
    const {root}=wrap('Teachers','Issue and revoke institution-scoped teacher credentials.');
    const form=node('form'); const label=control('Teacher label','teacher_label',{maxLength:80,placeholder:'Instructor A'});
    put(form,label.box);
    form.appendChild(button('Issue teacher credential +',null,'btn btn-primary','submit'));
    const secretArea=node('div');
    form.addEventListener('submit',async event=>{
      event.preventDefault();
      try {
        const result=await request('/v1/teachers',{method:'POST',body:{label:label.input.value.trim()}});
        clear(secretArea);
        put(secretArea,node('div','Credential shown only once — transfer through an approved secure channel.','warnbox'),
          node('output',result.token,'secret'),button('Dismiss credential',()=>clear(secretArea),'btn btn-small'));
        label.input.value='';
        const table=$('teacher-table');
        if(table) table.replaceWith(await teachersTable());
        notice('Teacher credential issued.');
      } catch(err){notice(err.message,true);}
    });
    root.appendChild(card('New teacher',form,secretArea));
    root.appendChild(await teachersTable(records));
    return root;
  }
  async function teachersTable(records=null){
    records=records||await request('/v1/teachers');
    const table=card('Authorised teachers',grid(['Teacher','Registered','Action'],records.map(x=>[x.label,dateStr(x.created_at),x.id]),
      [null,null,(cell,id)=>cell.appendChild(dangerous('Revoke',()=>request(`/v1/teachers/${encodeURIComponent(id)}`,{method:'DELETE'})))]));
    table.id='teacher-table';return table;
  }
  async function content() {
    const releases=await request('/v1/content/releases');
    const {root}=wrap('Curriculum registry','Approved-package metadata. Registering a fingerprint does not sign or scientifically validate a content pack.');
    if(identity.role==='admin'){
      const form=node('form',null,'form-grid');
      const version=control('Pack revision','pack_version',{type:'number',placeholder:'1'});
      version.input.min='1';
      const name=control('Content version','content_version',{maxLength:120,placeholder:'2026-chemistry-pilot'});
      const hash=control('Pack SHA-256','pack_sha256',{placeholder:'64 lowercase hexadecimal characters'});
      const fingerprint=control('Content fingerprint','content_fingerprint',{placeholder:'64 lowercase hexadecimal characters'});
      put(form,version.box,name.box,hash.box,fingerprint.box);
      form.appendChild(button('Register metadata +',null,'btn btn-primary','submit'));
      form.addEventListener('submit',async event=>{
        event.preventDefault();
        try{await request('/v1/content/releases',{method:'POST',body:{pack_version:Number(version.input.value),content_version:name.input.value.trim(),pack_sha256:hash.input.value.trim(),content_fingerprint:fingerprint.input.value.trim()}});notice('Metadata registered (not cryptographically verified by Control).');await render();}catch(err){notice(err.message,true);}
      });
      root.appendChild(card('Register curriculum metadata',form));
    }
    root.appendChild(card('Institutional content history',grid(['Revision','Content version','Pack SHA-256','Registered'],releases.map(x=>[x.pack_version,x.content_version,x.pack_sha256,dateStr(x.created_at)]),
      [null,null,(cell,v)=>{cell.textContent=String(v);cell.className='mono mini';},null])));
    return root;
  }
  async function audit(){
    if(identity.role!=='admin') throw new Error('Administrator access required.');
    const entries=await request('/v1/audit');
    const {root}=wrap('Audit log','Recent institution-scoped administrative events. This pilot log is not cryptographically tamper-evident.');
    root.appendChild(card('Audit activity',grid(['Event','Actor ID','Subject ID','Occurred'],entries.map(x=>[x.action,x.actor_id,x.subject_id,dateStr(x.occurred_at)]))));
    return root;
  }
  const pages={overview,students,assignments,teachers,content,audit};
  async function render(){
    if(!identity) return;
    nav(); $('page-title').textContent=labels[current];
    const panel=$('content'); clear(panel); panel.appendChild(node('div','Loading institutional records…','loading'));
    const requested=current;
    try{const element=await pages[current](); if(token && current===requested) panel.replaceChildren(element);}
    catch(err){if(token && current===requested){clear(panel);notice(err.message,true);panel.appendChild(node('p','This view could not be loaded. Check your permission and try again.','loading'));}}
  }
  $('login-form').addEventListener('submit',async event=>{
    event.preventDefault();
    const value=$('credential').value.trim();
    const host=window.location.hostname;
    if(window.location.protocol!=='https:' && host!=='127.0.0.1' && host!=='localhost'){
      notice('HTTPS is required before entering institutional credentials on a remote host.',true);return;
    }
    if(!/^cfcp_[A-Za-z0-9_-]{40,60}$/.test(value)){notice('Invalid institutional credential format.',true);return;}
    token=value; $('credential').value='';
    try {
      identity=await request('/v1/me');
      current='overview';
      $('identity').textContent=`${identity.tenant_id} · ${identity.role}`;
      $('identity').hidden=false;$('logout').hidden=false;
      $('login').hidden=true;$('workspace').hidden=false;
      clear($('messages')); await render();
    } catch(err){ token=null;identity=null;notice(err.message,true); }
  });
  $('logout').addEventListener('click',logout);
})();
