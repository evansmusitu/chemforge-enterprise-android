"""Black-box tenant and evidence security regression tests for CHEMFORGE Control."""
import json
import pytest
from fastapi.testclient import TestClient
from control_plane.app import create_app
from control_plane.db import Database


@pytest.fixture
def setup(tmp_path):
    db = Database(str(tmp_path / 'control.sqlite'))
    token_a = db.bootstrap_tenant('school-a', 'Admin A')
    token_b = db.bootstrap_tenant('school-b', 'Admin B')
    with TestClient(create_app(str(tmp_path / 'control.sqlite'))) as client:
        yield client, {'A': token_a, 'B': token_b}, db


def h(token):
    return {'Authorization': f'Bearer {token}'}


def test_authentication_and_admin_teacher_scope(setup):
    client, token, _ = setup
    assert client.get('/health').json() == {'status': 'ok'}
    assert client.get('/v1/me').status_code == 401
    assert client.get('/v1/me', headers=h(token['A'])).json()['tenant_id'] == 'school-a'
    t = client.post('/v1/teachers', headers=h(token['A']), json={'label': 'Class Teacher'})
    assert t.status_code == 201, t.text
    teacher = t.json()['token']
    assert client.get('/v1/me', headers=h(teacher)).json()['role'] == 'teacher'
    assert client.post('/v1/teachers', headers=h(teacher), json={'label': 'unauthorized'}).status_code == 403
    assert client.get('/v1/teachers', headers=h(token['B'])).json() == []
    teacher_id = t.json()['actor_id']
    assert client.delete(f'/v1/teachers/{teacher_id}', headers=h(token['A'])).status_code == 204
    assert client.get('/v1/me', headers=h(teacher)).status_code == 401


def test_tenant_roster_assignments_and_cross_tenant_block(setup):
    client, token, _ = setup
    a = client.post('/v1/students', headers=h(token['A']), json={'pseudonym':'Learner 01','cohort':'L6-A'})
    b = client.post('/v1/students', headers=h(token['B']), json={'pseudonym':'Learner 02','cohort':'L6-A'})
    assert a.status_code == b.status_code == 201
    student_a, student_b = a.json()['id'], b.json()['id']
    assert len(client.get('/v1/students', headers=h(token['A'])).json()) == 1
    assert client.delete(f'/v1/students/{student_b}', headers=h(token['A'])).status_code == 404
    assert client.delete(f'/v1/students/{student_a}', headers=h(token['B'])).status_code == 404
    payload={'title':'Equilibrium Review','cohort':'L6-A','objective_ids':['CH-CHEM-001'], 'due_at': '2026-12-15T12:00:00Z'}
    r=client.post('/v1/assignments',headers=h(token['A']),json=payload)
    assert r.status_code == 201, r.text
    assert len(client.get('/v1/assignments',headers=h(token['A'])).json())==1
    assert client.get('/v1/assignments',headers=h(token['B'])).json()==[]


def test_unverified_evidence_idempotency_and_tenant_isolation(setup):
    client,token,_=setup
    student=client.post('/v1/students',headers=h(token['A']),json={'pseudonym':'Learner 03', 'cohort':'L6-A'}).json()['id']
    event={'event_id':'attempt_2026_001','student_id':student,'question_id':'Q1', 'assessment_source':'deterministic_key',
           'mark':2,'max_marks':3,'content_fingerprint':'f'*64,'recorded_at':'2026-10-11T12:00:00Z'}
    foreign=client.post('/v1/evidence',headers=h(token['B']),json=event)
    assert foreign.status_code == 404, foreign.text
    first=client.post('/v1/evidence',headers=h(token['A']),json=event)
    assert first.status_code==201, first.text
    assert first.json()['verification_status']=='unverified_import'
    assert client.post('/v1/evidence',headers=h(token['A']),json=event).status_code==200
    assert client.post('/v1/evidence',headers=h(token['A']),json={**event,'mark':3}).status_code==409
    bad=client.post('/v1/evidence',headers=h(token['A']),json={**event,'event_id':'x','mark':4})
    assert bad.status_code==422
    metrics=client.get('/v1/analytics/cohorts',headers=h(token['A'])).json()
    assert metrics==[{'cohort':'L6-A','students':1,'unverified_attempts':1,'verified_attempts':0}]
    assert client.get('/v1/analytics/cohorts',headers=h(token['B'])).json()==[]
    assert client.post('/v1/evidence',headers=h(token['A']),json={**event,'event_id':'e2','tenant_id':'school-b'}).status_code==422


def test_admin_audit_and_student_erasure(setup):
    client,token,_=setup
    t=client.post('/v1/teachers',headers=h(token['A']),json={'label':'T'}).json()
    teacher=t['token']
    assert client.post(f"/v1/teachers/{t['actor_id']}/cohorts",headers=h(token['A']),json={'cohort':'L6-B'}).status_code==201
    st=client.post('/v1/students',headers=h(teacher),json={'pseudonym':'Deleted learner', 'cohort':'L6-B'})
    assert st.status_code==201, st.text
    student=st.json()['id']
    assert client.get('/v1/audit',headers=h(teacher)).status_code==403
    assert client.delete(f'/v1/students/{student}',headers=h(teacher)).status_code==403
    assert client.delete(f'/v1/students/{student}',headers=h(token['A'])).status_code==204
    assert client.get('/v1/students',headers=h(token['A'])).json()==[]
    events=client.get('/v1/audit',headers=h(token['A'])).json()
    assert any(x['action']=='student.deleted' for x in events)
    assert client.get('/v1/audit',headers=h(token['B'])).json()==[]


def test_fail_closed_bootstrap_and_auth(setup):
    client,token,db=setup
    with pytest.raises(ValueError):db.bootstrap_tenant('school-a','Second admin')
    assert client.get('/v1/me',headers=h('fake')).status_code==401
    assert client.get('/v1/me',headers={'Authorization': 'Basic password'}).status_code==401
    assert client.post('/v1/students',headers=h(token['A']),json={'pseudonym':'x','cohort':'L6','role':'admin'}).status_code==422


def test_assignment_does_not_leak_internal_storage_fields(setup):
    client,tokens,_=setup
    r=client.post('/v1/assignments',headers=h(tokens['A']),json={'title':'Bonding','cohort':'U6-C','objective_ids':['OBJ-01']})
    assert r.status_code==201
    items=client.get('/v1/assignments',headers=h(tokens['A'])).json()
    assert 'objectives_json' not in items[0]
    assert items[0]['objective_ids']==['OBJ-01']


def test_offline_backup_import_is_tenant_scoped_atomic_unverified(setup):
    client,tokens,_=setup
    student_a=client.post('/v1/students',headers=h(tokens['A']),json={'pseudonym':'P1','cohort':'Sixth'}).json()['id']
    student_b=client.post('/v1/students',headers=h(tokens['B']),json={'pseudonym':'P2','cohort':'Sixth'}).json()['id']
    backup={
       'app':'CHEMFORGE_ANDROID','schema_version':1,
       'tenant_id':'school-a','content_version':'pilot-0.1','content_fingerprint':'pilot-0.1',
       'attempts':[{'id':'mob-unique001','question_id':'CF-Q-001','assessment_source':'deterministic_key',
                    'mark':1,'max_marks':1,'recorded_at':'2026-10-11T13:00:00Z','tenant_id':'school-a',
                    'content_version':'pilot-0.1','content_fingerprint':'pilot-0.1','mode':'practice','hints_used':0}]
    }
    route=f'/v1/students/{student_a}/backups'
    assert client.post(route,headers=h(tokens['B']),json=backup).status_code==404
    assert client.post(f'/v1/students/{student_b}/backups',headers=h(tokens['B']),json=backup).status_code==422
    created=client.post(route,headers=h(tokens['A']),json=backup)
    assert created.status_code==201,created.text
    assert created.json()['imported']==1 and created.json()['verified']==0
    assert client.post(route,headers=h(tokens['A']),json=backup).json()['unchanged']==1
    bad=json.loads(json.dumps(backup))
    bad['attempts'][0]['mark']=0
    assert client.post(route,headers=h(tokens['A']),json=bad).status_code==409
    mixed=json.loads(json.dumps(backup))
    mixed['attempts'].append({**mixed['attempts'][0],'id':'mob-other','tenant_id':'school-b'})
    assert client.post(route,headers=h(tokens['A']),json=mixed).status_code==422
    assert client.get('/v1/analytics/cohorts',headers=h(tokens['A'])).json()[0]['unverified_attempts']==1
    assert client.delete(f'/v1/students/{student_a}',headers=h(tokens['A'])).status_code==204
    assert client.get('/v1/analytics/cohorts',headers=h(tokens['A'])).json()==[]


def test_content_release_manifest_registration_must_monotonically_advance(setup):
    client,token,_=setup
    base={'pack_version':1,'content_version':'2026-oct-a','pack_sha256':'a'*64,'content_fingerprint':'b'*64}
    first=client.post('/v1/content/releases',headers=h(token['A']),json=base)
    assert first.status_code==201,first.text
    assert client.post('/v1/content/releases',headers=h(token['A']),json=base).status_code==409
    assert client.post('/v1/content/releases',headers=h(token['B']),json=base).status_code==201
    assert client.post('/v1/content/releases',headers=h(token['A']),json={**base,'pack_version':0}).status_code==422
    assert client.post('/v1/content/releases',headers=h(token['A']),json={**base,'pack_version':2,'pack_sha256':'a'*32}).status_code==422
    teacher=client.post('/v1/teachers',headers=h(token['A']),json={'label':'Instructor'}).json()['token']
    assert client.post('/v1/content/releases',headers=h(teacher),json={**base,'pack_version':2}).status_code==403
    assert client.get('/v1/content/releases',headers=h(token['A'])).json()[0]['pack_version']==1
    assert client.get('/v1/content/releases',headers=h(token['B'])).json()[0]['pack_version']==1


def test_backup_bulk_import_rolls_back_on_collision(setup):
    client,token,_=setup
    student=client.post('/v1/students',headers=h(token['A']),json={'pseudonym':'S1','cohort':'N6'}).json()['id']
    base={'app':'CHEMFORGE_ANDROID','schema_version':1,'tenant_id':'school-a','content_version':'pilot-0.1',
          'content_fingerprint':'pilot-0.1','attempts':[]}
    row={'id':'A-001','question_id':'Q1','mark':1,'max_marks':1,'assessment_source':'deterministic_key',
         'recorded_at':'2026-10-11T12:00:00Z','mode':'practice','hints_used':0,
         'tenant_id':'school-a','content_version':'pilot-0.1','content_fingerprint':'pilot-0.1'}
    url=f'/v1/students/{student}/backups'
    assert client.post(url,headers=h(token['A']),json={**base,'attempts':[row]}).status_code==201
    changed={**row,'mark':0}
    assert client.post(url,headers=h(token['A']),json={**base,'attempts':[{**row,'id':'B-002'},changed]}).status_code==409
    assert client.get('/v1/analytics/cohorts',headers=h(token['A'])).json()[0]['unverified_attempts']==1


def test_content_version_and_teacher_role_validation(setup):
    client,tokens,_=setup
    bad={'pack_version':1,'content_version':'x','pack_sha256':'d'*64,'content_fingerprint':'e'*64,'tenant_id':'school-b'}
    assert client.post('/v1/content/releases',headers=h(tokens['A']),json=bad).status_code==422
    assert client.post('/v1/students',headers=h(tokens['A']),json={'pseudonym':'','cohort':'6A'}).status_code==422
    assignment={'title':'Physics/chem','cohort':'6A','objective_ids':['OBJ1','OBJ1']}
    assert client.post('/v1/assignments',headers=h(tokens['A']),json=assignment).status_code==422
    assert client.post('/v1/assignments',headers=h(tokens['A']),json={**assignment,'objective_ids':['OBJ1'],'due_at':'2026-10-11T12:00:00'}).status_code==422
