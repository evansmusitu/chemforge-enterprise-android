/* CHEMFORGE Control: same-origin, bearer in ephemeral tab memory only.
   Client-side restrictions are presentation only; server enforces tenant and role. */
(() => {
  'use strict';
  let credential = null;
  let identity = null;
  let currentView = 'overview';
  let dataset = { students: [], assignments: [], analytics: [], teachers: [], devices: [], releases: [], audit: [] };
  const $ = id => document.getElementById(id);
  const viewMetadata = {
    overview: ['Overview', 'An at-a-glance view of your school\'s learning activity.'],
    students: ['Students', 'Manage pseudonymous learner records and cohort enrolment.'],
    assignments: ['Assignments', 'Plan curriculum-focused tasks for your classes.'],
    imports: ['Import records', 'Bring offline Android learning histories into this workspace.'],
    teachers: ['Teachers', 'Control teaching staff access to your institution.'],
    devices: ['Device sync', 'Provision scoped, expiring device credentials for later optional synchronisation.'],
    content: ['Content releases', 'Version and organise curriculum package metadata.'],
    audit: ['Audit log', 'Review recent institutional administrative operations.']
  };
  const canAdmin = () => identity && identity.role === 'admin';
  function node(tag, value, className) {
    const element = document.createElement(tag);
    if (value !== undefined && value !== null) element.textContent = String(value);
    if (className) element.className = className;
    return element;
  }
  function cell(value, className) {
    return node('td', value ?? '—', className);
  }
  function clearChildren(element) { element.replaceChildren(); }
  function formatDate(value) {
    if (!value) return 'Not specified';
    const d = new Date(value);
    return Number.isNaN(d.valueOf()) ? 'Unknown' : d.toLocaleDateString(undefined, {day: 'numeric', month: 'short', year:'numeric'});
  }
  function feedback(message, error = false, target = 'workspace-feedback') {
    const element = $(target);
    element.textContent = String(message);
    element.classList.remove('hidden');
    element.classList.toggle('error', Boolean(error));
  }
  function hideFeedback(target = 'workspace-feedback') { $(target).classList.add('hidden'); }
  function humanError(error) { return error instanceof Error ? error.message : 'Request failed'; }
  async function api(path, opts = {}) {
    if (!credential) throw new Error('Sign in to continue');
    const response = await fetch(path, {
      ...opts, credentials: 'omit', cache: 'no-store', redirect: 'error',
      headers: { Authorization: 'Bearer ' + credential, ...(opts.body ? {'Content-Type': 'application/json'} : {}), ...opts.headers }
    });
    if (response.status === 401) {
      logout();
      throw new Error('Credential invalid or revoked. Please sign in again.');
    }
    if (!response.ok) {
      let explanation = `Request rejected (${response.status})`;
      try {
        const body = await response.json();
        if (typeof body.detail === 'string') explanation = body.detail;
        else if (Array.isArray(body.detail)) explanation = body.detail.slice(0, 2).map(x => x.msg).join('; ');
      } catch { /* API may return an empty error body. */ }
      throw new Error(explanation);
    }
    return response.status === 204 ? null : response.json();
  }
  function isSecureEndpoint() {
    return window.location.protocol === 'https:' || ['localhost', '127.0.0.1', '[::1]'].includes(window.location.hostname);
  }
  function clearVolatileSecrets() {
    credential = null;
    identity = null;
    $('credential').value = '';
    $('new-token-value').textContent = '';
    $('new-token').classList.add('hidden');
    $('device-token-value').textContent = '';
    $('device-new-token').classList.add('hidden');
    dataset = { students: [], assignments: [], analytics: [], teachers: [], devices: [], releases: [], audit: [] };
  }
  function logout() {
    clearVolatileSecrets();
    $('app-screen').classList.add('hidden');
    $('sign-in-screen').classList.remove('hidden');
    hideFeedback();
  }
  async function signin(event) {
    event.preventDefault();
    hideFeedback('signin-feedback');
    if (!isSecureEndpoint()) {
      feedback('Use HTTPS or localhost. Credentials must not be sent over an insecure connection.', true, 'signin-feedback');
      return;
    }
    credential = $('credential').value.trim();
    $('credential').value = '';
    try {
      identity = await api('/v1/me');
      $('tenant-sidebar').textContent = identity.tenant_id;
      $('actor-label').textContent = identity.label;
      $('role-badge').textContent = identity.role.toUpperCase();
      for (const item of document.querySelectorAll('[data-admin-only], .admin-only, .admin-col')) {
        item.classList.toggle('hidden', !canAdmin());
      }
      $('sign-in-screen').classList.add('hidden');
      $('app-screen').classList.remove('hidden');
      $('welcome-title').textContent = `${identity.tenant_id} · learning overview`;
      switchView('overview');
    } catch (error) {
      clearVolatileSecrets();
      feedback(humanError(error), true, 'signin-feedback');
    }
  }
  async function refresh() {
    if (!identity) return;
    hideFeedback();
    const routes = {
      students:'/v1/students',assignments:'/v1/assignments',analytics:'/v1/analytics/cohorts',
      teachers:'/v1/teachers',devices:'/v1/devices',releases:'/v1/content/releases',audit:'/v1/audit'
    };
    const keys = currentView === 'overview' ? ['students','assignments','analytics',...(canAdmin()?['teachers']:[])]
      : currentView === 'imports' ? ['students']
      : currentView === 'devices' ? ['devices','students']
      : currentView === 'content' ? ['releases']
      : currentView === 'audit' ? ['audit']
      : [currentView];
    try {
      const collected = await Promise.all(keys.map(async key => [key, await api(routes[key])]));
      if (!identity) return;
      for (const [key, value] of collected) dataset[key] = value;
      render();
    } catch (error) {
      feedback(humanError(error), true);
    }
  }
  function switchView(view) {
    if (!Object.hasOwn(viewMetadata, view) || (!canAdmin() && (view === 'teachers' || view === 'audit' || view === 'devices'))) return;
    currentView = view;
    for (const panel of document.querySelectorAll('[data-view-panel]')) {
      panel.classList.toggle('hidden', panel.id !== `view-${view}`);
    }
    for (const b of document.querySelectorAll('[data-view]')) {
      b.classList.toggle('active', b.dataset.view === view);
      if (b.dataset.view === view) b.setAttribute('aria-current', 'page');
      else b.removeAttribute('aria-current');
    }
    $('breadcrumb').textContent = view.toUpperCase();
    $('view-heading').textContent = viewMetadata[view][0];
    $('view-subheading').textContent = viewMetadata[view][1];
    refresh();
  }
  function render() {
    switch (currentView) {
      case 'overview': return renderOverview();
      case 'students': return renderStudents();
      case 'assignments': return renderAssignments();
      case 'imports': return renderBackupSelect();
      case 'teachers': return renderTeachers();
      case 'devices': return renderDevices();
      case 'content': return renderReleases();
      case 'audit': return renderAudit();
      default: break;
    }
  }
  function renderOverview() {
    const count = dataset.analytics.reduce((sum, row) => sum + Number(row.unverified_attempts || 0), 0);
    const metrics = [
      ['Registered students', dataset.students.length, 'Pseudonymous learners', '♙'],
      ['Class assignments', dataset.assignments.length, 'Planned learning activities', '☷'],
      ['Active teachers', canAdmin() ? dataset.teachers.length : '—', canAdmin() ? 'Authorized teachers' : 'Admin access required', '◇'],
      ['Unverified attempts', count, 'Not certified assessments', '◈']
    ];
    const root = $('overview-cards');
    clearChildren(root);
    for (const [label, value, hint, icon] of metrics) {
      const card = node('article',null,'stat-card');
      const top = node('div',null,'stat-top');
      top.append(node('span',label), node('span',icon,'stat-icon'));
      card.append(top,node('strong',value),node('div',hint,'stat-foot'));
      root.append(card);
    }
    const container = $('cohort-overview');
    clearChildren(container);
    if (!dataset.analytics.length) { container.append(node('div','No cohort activity yet. Add students to begin.','empty'));return; }
    for (const c of dataset.analytics) {
      const line = node('div',null,'cohort-row');
      const l = node('div'); l.append(node('strong',c.cohort),node('small', `${c.students} students`));
      const r = node('div',null,'cohort-values'); r.append(node('strong',c.unverified_attempts),node('small','unverified attempts'));
      line.append(l,r);container.append(line);
    }
  }
  function addEmptyRow(body, message, columns) {
    const tr = node('tr');const td = cell(message,'muted-row');td.colSpan = columns;tr.append(td);body.append(tr);
  }
  function actionButton(text, callback, klass = 'table-action') {
    const button = node('button',text,klass);button.type='button';button.addEventListener('click', callback);return button;
  }
  function renderStudents() {
    const body = $('students-body');clearChildren(body);
    const search = $('student-search').value.trim().toLowerCase();
    const list = dataset.students.filter(s => `${s.pseudonym} ${s.cohort}`.toLowerCase().includes(search));
    $('student-total').textContent = `${dataset.students.length} enrolled`;
    if (!list.length) {addEmptyRow(body,'No matching students.', canAdmin() ? 4:3);return;}
    for (const student of list) {
      const tr = node('tr');
      const name = cell();name.append(node('span',student.pseudonym.substring(0,1).toUpperCase(),'mini-avatar'),node('span',student.pseudonym,'table-name'));
      tr.append(name,cell(student.cohort),cell(formatDate(student.created_at)));
      if (canAdmin()) {
        const actions=cell();actions.append(actionButton('Delete', async () => {
          if (!window.confirm(`Permanently erase ${student.pseudonym} and their imported history?`)) return;
          try {await api(`/v1/students/${encodeURIComponent(student.id)}`,{method:'DELETE'});
            feedback('Student and associated imported history erased.');await refresh();}
          catch (e) {feedback(humanError(e),true);}
        }));tr.append(actions);
      }
      body.append(tr);
    }
  }
  function renderAssignments() {
    const body = $('assignments-body');clearChildren(body);
    if (!dataset.assignments.length) {addEmptyRow(body,'No assignments created yet.',4);return;}
    for(const a of dataset.assignments){const tr=node('tr');tr.append(cell(a.title,'table-name'),cell(a.cohort),cell(a.objective_ids.join(', ')),cell(formatDate(a.due_at)));body.append(tr);}
  }
  function renderBackupSelect() {
    const select = $('backup-student');const selected=select.value;clearChildren(select);
    const option=node('option','Select a student');option.value='';select.append(option);
    for(const s of dataset.students){const o=node('option',`${s.pseudonym} — ${s.cohort}`);o.value=s.id;select.append(o);}
    if(dataset.students.some(s=>s.id===selected))select.value=selected;
  }
  function renderTeachers() {
    const body=$('teachers-body');clearChildren(body);
    const select=$('teacher-cohort-select'), selected=select.value;clearChildren(select);
    const empty=node('option','Select teacher');empty.value='';select.append(empty);
    for(const teacher of dataset.teachers){const option=node('option',teacher.label);option.value=teacher.id;select.append(option);}
    if(dataset.teachers.some(t=>t.id===selected))select.value=selected;
    if(!dataset.teachers.length){addEmptyRow(body,'No teachers registered yet.',3);refreshTeacherGrants();return;}
    refreshTeacherGrants();
    for(const teacher of dataset.teachers){const tr=node('tr');const c=cell();c.append(node('span',teacher.label,'table-name'));const action=cell();action.append(actionButton('Revoke access',async()=>{
      if(!window.confirm(`Revoke ${teacher.label}'s credential immediately?`))return;
      try{await api(`/v1/teachers/${encodeURIComponent(teacher.id)}`,{method:'DELETE'});feedback('Teacher credential revoked.');await refresh();}
      catch(e){feedback(humanError(e),true);}
    }));tr.append(c,cell(formatDate(teacher.created_at)),action);body.append(tr);}
  }
  function renderDeviceStudents() {
    const select = $('device-student');
    const previous = select.value;
    clearChildren(select);
    const empty = node('option','Choose student'); empty.value='';select.append(empty);
    for(const s of dataset.students){const option=node('option',`${s.pseudonym} — ${s.cohort}`);option.value=s.id;select.append(option);}
    if(dataset.students.some(s=>s.id===previous))select.value=previous;
  }
  function renderDevices() {
    renderDeviceStudents();
    const body=$('devices-body');clearChildren(body);
    if(!dataset.devices.length){addEmptyRow(body,'No active device credentials.',4);return;}
    for(const device of dataset.devices){
      const tr=node('tr');const person=dataset.students.find(s=>s.id===device.student_id);
      const action=cell();action.append(actionButton('Revoke',async()=>{
        if(!window.confirm(`Revoke device ${device.label}?`))return;
        try{await api(`/v1/devices/${encodeURIComponent(device.id)}`,{method:'DELETE'});feedback('Device credential revoked.');await refresh();}
        catch(e){feedback(humanError(e),true);}
      }));
      tr.append(cell(device.label,'table-name'),cell(person?person.pseudonym:'Student no longer listed'),cell(formatDate(device.expires_at)),action);
      body.append(tr);
    }
  }
  async function refreshTeacherGrants() {
    const select=$('teacher-cohort-select'), holder=$('teacher-cohort-list');
    clearChildren(holder);
    if(!select.value)return;
    const id=select.value;
    try{
      const grants=await api(`/v1/teachers/${encodeURIComponent(id)}/cohorts`);
      if(id!==select.value || currentView!=='teachers')return;
      if(!grants.length){holder.append(node('span','No cohorts assigned — student access denied.'));return;}
      for(const cohort of grants){
        const row=node('div',null,'cohort-row');row.append(node('span',cohort));
        row.append(actionButton('Remove',async()=>{
          try{await api(`/v1/teachers/${encodeURIComponent(id)}/cohorts/${encodeURIComponent(cohort)}`,{method:'DELETE'});
            feedback(`Cohort ${cohort} removed.`);await refreshTeacherGrants();}
          catch(e){feedback(humanError(e),true);}
        }));holder.append(row);
      }
    }catch(e){feedback(humanError(e),true);}
  }
  function renderReleases() {
    const body=$('releases-body');clearChildren(body);
    if(!dataset.releases.length){addEmptyRow(body,'No content metadata registered.',4);return;}
    for(const rel of dataset.releases){const tr=node('tr');tr.append(cell(`v${rel.pack_version}`,'table-name'),cell(rel.content_version),cell(`${rel.pack_sha256.slice(0,12)}…`),cell(formatDate(rel.created_at)));body.append(tr);}
  }
  function renderAudit() {
    const body=$('audit-body');clearChildren(body);
    if(!dataset.audit.length){addEmptyRow(body,'No administrative events yet.',3);return;}
    for(const record of dataset.audit){const tr=node('tr');tr.append(cell(record.action,'table-name'),cell(record.subject_id),cell(formatDate(record.occurred_at)));body.append(tr);}
  }
  async function postForm(event,path,data,successMessage){
    event.preventDefault();
    try {await api(path,{method:'POST',body:JSON.stringify(data)});
      event.target.reset(); feedback(successMessage); await refresh();}
    catch(e){feedback(humanError(e),true);}
  }
  $('signin-form').addEventListener('submit',signin);
  $('signout').addEventListener('click',logout);
  $('refresh').addEventListener('click',refresh);
  $('student-search').addEventListener('input',()=>{if(currentView==='students')renderStudents();});
  for(const nav of document.querySelectorAll('[data-view]'))nav.addEventListener('click',()=>switchView(nav.dataset.view));
  $('student-form').addEventListener('submit',e=>{
    const f=new FormData(e.currentTarget);
    postForm(e,'/v1/students',{pseudonym:String(f.get('pseudonym')).trim(),cohort:String(f.get('cohort')).trim()},'Student registered.');
  });
  $('assignment-form').addEventListener('submit',e=>{
    const f=new FormData(e.currentTarget);const ids=String(f.get('objective_ids')).split(',').map(s=>s.trim()).filter(Boolean);
    const due=String(f.get('due_at'));const timestamp=due?new Date(due).toISOString():null;
    postForm(e,'/v1/assignments',{title:String(f.get('title')).trim(),cohort:String(f.get('cohort')).trim(),objective_ids:ids,due_at:timestamp},'Assignment created.');
  });
  $('teacher-form').addEventListener('submit',async e=>{
    e.preventDefault(); const form=e.currentTarget;
    try{const data=await api('/v1/teachers',{method:'POST',body:JSON.stringify({label:String(new FormData(form).get('label')).trim()})});
      if (typeof data.token === 'string') {
        $('new-token-value').textContent=data.token; $('new-token').classList.remove('hidden');
        feedback('Pilot teacher credential issued; transfer it securely.');
      } else {
        $('new-token-value').textContent=''; $('new-token').classList.add('hidden');
        feedback('Teacher created without a pilot credential. An operator must link their OIDC subject using the protected CLI.');
      }
      form.reset();await refresh();}
    catch(err){feedback(humanError(err),true);}
  });
  $('dismiss-token').addEventListener('click',()=>{$('new-token-value').textContent='';$('new-token').classList.add('hidden');});
  $('teacher-cohort-select').addEventListener('change',refreshTeacherGrants);
  $('teacher-cohort-form').addEventListener('submit',async e=>{
    e.preventDefault();const form=e.currentTarget;const f=new FormData(form);
    try{const id=String(f.get('teacher_id')), cohort=String(f.get('cohort')).trim();
      await api(`/v1/teachers/${encodeURIComponent(id)}/cohorts`,{method:'POST',body:JSON.stringify({cohort})});
      form.querySelector('[name=cohort]').value='';feedback(`Granted ${cohort}.`);await refreshTeacherGrants();}
    catch(err){feedback(humanError(err),true);}
  });
  $('device-form').addEventListener('submit',async e=>{
    e.preventDefault();const form=e.currentTarget;const f=new FormData(form);
    try{const response=await api('/v1/devices',{method:'POST',body:JSON.stringify({
      student_id:String(f.get('student_id')),label:String(f.get('label')).trim(),valid_days:Number(f.get('valid_days'))})});
      $('device-token-value').textContent=response.token;
      $('device-new-token').classList.remove('hidden');
      form.querySelector('[name=label]').value='';feedback('Student-scoped device credential issued; store securely.');await refresh();}
    catch(err){feedback(humanError(err),true);}
  });
  $('dismiss-device-token').addEventListener('click',()=>{$('device-token-value').textContent='';$('device-new-token').classList.add('hidden');});

  $('backup-form').addEventListener('submit',async e=>{
    e.preventDefault();const file=$('backup-file').files[0];const studentId=$('backup-student').value;
    if(!file||!studentId){feedback('Choose a student and a JSON file.',true);return;}
    if(file.size>2_000_000){feedback('File exceeds the 2 MB browser import limit.',true);return;}
    try{const backup=JSON.parse(await file.text());
      if(backup.app!=='CHEMFORGE_ANDROID'||backup.tenant_id!==identity.tenant_id||!Array.isArray(backup.attempts))
        throw new Error('Backup format or institution does not match.');
      const result=await api(`/v1/students/${encodeURIComponent(studentId)}/backups`,{method:'POST',body:JSON.stringify(backup)});
      feedback(`Import processed: ${result.imported} new and ${result.unchanged} already received. Verified marks: 0.`);
      $('backup-file').value='';
    }catch(err){feedback(humanError(err),true);}
  });
  $('release-form').addEventListener('submit',e=>{
    const f=new FormData(e.currentTarget);
    postForm(e,'/v1/content/releases',{pack_version:Number(f.get('pack_version')),
      content_version:String(f.get('content_version')).trim(),pack_sha256:String(f.get('pack_sha256')).trim(),
      content_fingerprint:String(f.get('content_fingerprint')).trim()},'Curriculum metadata registered (not cryptographically signed by this service).');
  });
  window.addEventListener('pagehide',clearVolatileSecrets);
})();
