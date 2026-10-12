"""v1.7 acceptance: deny-by-default teacher cohorts and student-scoped sync."""
from fastapi.testclient import TestClient
from control_plane.db import Database
from control_plane.app import create_app


def H(token, scheme='Bearer'):
    return {'Authorization': f'{scheme} {token}'}


def backup(tenant, identity='sync-v17-001', mark=1):
    return {
        'app':'CHEMFORGE_ANDROID','schema_version':1,'tenant_id':tenant,
        'content_version':'pilot-0.1','content_fingerprint':'pilot-0.1',
        'attempts':[{'id':identity,'question_id':'CF-Q-001','assessment_source':'deterministic_key',
                     'mark':mark,'max_marks':1,'recorded_at':'2026-10-12T08:00:00Z','tenant_id':tenant,
                     'content_version':'pilot-0.1','content_fingerprint':'pilot-0.1',
                     'mode':'practice','hints_used':0}]
    }


def test_teacher_cohorts_are_deny_by_default_and_restricted(tmp_path):
    db=Database(str(tmp_path/'control.sqlite'))
    admin=db.bootstrap_tenant('school-one','Principal')
    other=db.bootstrap_tenant('school-two','Principal')
    client=TestClient(create_app(str(tmp_path/'control.sqlite')))
    t=client.post('/v1/teachers',headers=H(admin),json={'label':'Chemistry'}).json()
    teacher=t['token']; tid=t['actor_id']
    a=client.post('/v1/students',headers=H(admin),json={'pseudonym':'A','cohort':'S6A'}).json()['id']
    b=client.post('/v1/students',headers=H(admin),json={'pseudonym':'B','cohort':'S6B'}).json()['id']
    assert client.get('/v1/students',headers=H(teacher)).json()==[]
    assert client.post('/v1/students',headers=H(teacher),json={'pseudonym':'Unassigned','cohort':'S6B'}).status_code==403
    assert client.post('/v1/assignments',headers=H(teacher),json={'title':'B','cohort':'S6B','objective_ids':['CF1']}).status_code==403
    assert client.post(f'/v1/students/{b}/backups',headers=H(teacher),json=backup('school-one')).status_code==403
    assert client.post(f'/v1/teachers/{tid}/cohorts',headers=H(other),json={'cohort':'S6B'}).status_code==404
    assert client.post(f'/v1/teachers/{tid}/cohorts',headers=H(teacher),json={'cohort':'S6B'}).status_code==403
    granted=client.post(f'/v1/teachers/{tid}/cohorts',headers=H(admin),json={'cohort':'S6A'})
    assert granted.status_code==201,granted.text
    assert client.get('/v1/students',headers=H(teacher)).json()[0]['id']==a
    assert len(client.get('/v1/students',headers=H(teacher)).json())==1
    assert client.get('/v1/students',headers=H(teacher),params={'cohort':'S6B'}).json()==[]
    assert client.post('/v1/assignments',headers=H(teacher),json={'title':'A','cohort':'S6A','objective_ids':['CF1']}).status_code==201
    assert client.post('/v1/assignments',headers=H(admin),json={'title':'B','cohort':'S6B','objective_ids':['CF1']}).status_code==201
    assert len(client.get('/v1/assignments',headers=H(teacher)).json())==1
    assert client.post(f'/v1/students/{a}/backups',headers=H(teacher),json=backup('school-one')).status_code==201
    assert client.get('/v1/analytics/cohorts',headers=H(teacher)).json()[0]['cohort']=='S6A'
    assert len(client.get('/v1/analytics/cohorts',headers=H(teacher)).json())==1
    assert client.delete(f'/v1/teachers/{tid}/cohorts/S6A',headers=H(admin)).status_code==204
    assert client.get('/v1/students',headers=H(teacher)).json()==[]
    assert client.post(f'/v1/students/{a}/backups',headers=H(teacher),json=backup('school-one','another')).status_code==403


def test_scoped_device_sync_tenant_student_idempotency_revoke_and_expiry(tmp_path):
    db=Database(str(tmp_path/'control.sqlite'))
    admin=db.bootstrap_tenant('school-one','Principal')
    foreign=db.bootstrap_tenant('school-two','Principal')
    client=TestClient(create_app(str(tmp_path/'control.sqlite')))
    student=client.post('/v1/students',headers=H(admin),json={'pseudonym':'A','cohort':'S6A'}).json()['id']
    second=client.post('/v1/students',headers=H(admin),json={'pseudonym':'B','cohort':'S6B'}).json()['id']
    denied=client.post('/v1/devices',headers=H(foreign),json={'student_id':student,'label':'Tablet'})
    assert denied.status_code==404
    new=client.post('/v1/devices',headers=H(admin),json={'student_id':student,'label':'Tablet','valid_days':7})
    assert new.status_code==201,new.text
    device=new.json();assert device['token'].startswith('cfsync_')
    listed=client.get('/v1/devices',headers=H(admin)).json()
    assert len(listed)==1 and 'token' not in listed[0]
    assert client.post('/v1/sync/backups',headers=H(admin),json=backup('school-one')).status_code==401
    assert client.get('/v1/me',headers=H(device['token'])).status_code==401
    assert client.post('/v1/sync/backups',headers=H(device['token'],'Device'),json=backup('school-two')).status_code==422
    first=client.post('/v1/sync/backups',headers=H(device['token'],'Device'),json=backup('school-one'))
    assert first.status_code==201,first.text
    assert first.json()['student_id']==student and first.json()['verified']==0 and first.json()['imported']==1
    repeat=client.post('/v1/sync/backups',headers=H(device['token'],'Device'),json=backup('school-one'))
    assert repeat.status_code==200 and repeat.json()['unchanged']==1
    assert client.post('/v1/sync/backups',headers=H(device['token'],'Device'),json=backup('school-one',mark=0)).status_code==409
    # Pairing is student-scoped, not an administrator credential capable of selecting a student.
    assert client.post(f'/v1/students/{second}/backups',headers=H(device['token'],'Device'),json=backup('school-one')).status_code==401
    assert client.delete(f"/v1/devices/{device['device_id']}",headers=H(foreign)).status_code==404
    assert client.delete(f"/v1/devices/{device['device_id']}",headers=H(admin)).status_code==204
    assert client.post('/v1/sync/backups',headers=H(device['token'],'Device'),json=backup('school-one','new-attempt')).status_code==401
    # No leaked secret in access list or database.
    with db.connect() as cx:
        assert cx.execute('SELECT count(*) FROM devices WHERE token_hash=?', (device['token'],)).fetchone()[0]==0


def test_sync_delete_student_invalidates_device_and_out_of_scope_calls(tmp_path):
    db=Database(str(tmp_path/'control.sqlite'))
    admin=db.bootstrap_tenant('school-one','Principal')
    client=TestClient(create_app(str(tmp_path/'control.sqlite')))
    student=client.post('/v1/students',headers=H(admin),json={'pseudonym':'A','cohort':'S6A'}).json()['id']
    device=client.post('/v1/devices',headers=H(admin),json={'student_id':student,'label':'Learner device','valid_days':1}).json()
    assert client.post('/v1/devices',headers=H(admin),json={'student_id':student,'label':'bad','valid_days':366}).status_code==422
    assert client.post('/v1/sync/backups',headers=H(device['token'],'Device'),json={'app':'OTHER'}).status_code==422
    # Valid issuance followed by server-side expiry is always rejected without writes.
    with db.connect() as cx:
        cx.execute("UPDATE devices SET expires_at=? WHERE id=?",('2020-01-01T00:00:00+00:00',device['device_id']))
    assert client.post('/v1/sync/backups',headers=H(device['token'],'Device'),json=backup('school-one','exp-attempt')).status_code==401
    assert client.delete(f'/v1/students/{student}',headers=H(admin)).status_code==204
    assert client.post('/v1/sync/backups',headers=H(device['token'],'Device'),json=backup('school-one','newattempt')).status_code==401
