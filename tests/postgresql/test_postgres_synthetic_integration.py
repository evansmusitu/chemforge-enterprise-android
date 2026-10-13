"""Runs ONLY in a disposable PostgreSQL GitHub Actions service container.

No live Neon project, real students, or cloud provider credentials are used.
"""
from __future__ import annotations

import os
from uuid import uuid4

import pytest

if os.getenv('CHEMFORGE_PG_CI') != '1':
    pytest.skip('Dedicated synthetic PostgreSQL container is not configured',allow_module_level=True)

from fastapi.testclient import TestClient
from control_plane.app import create_app
from control_plane.postgres_synthetic import (
    PostgresSyntheticDatabase, apply_synthetic_migration, validate_configuration,
)


def headers(token):
    return {'Authorization': f'Bearer {token}'}


@pytest.fixture(scope='module')
def pg():
    assert os.getenv('CHEMFORGE_POSTGRES_SYNTHETIC_ONLY') == 'I_ACKNOWLEDGE_DISPOSABLE_SYNTHETIC_DATABASE_ONLY'
    assert '127.0.0.1:5432' in validate_configuration(os.environ)
    proof = apply_synthetic_migration(os.environ)
    assert proof['status'] == 'SYNTHETIC_SCHEMA_INITIALIZED_NOT_PRODUCTION'
    with pytest.raises(ValueError,match='empty database schema'):
        apply_synthetic_migration(os.environ)
    return PostgresSyntheticDatabase(os.environ)


def test_postgres_schema_rejects_cross_tenant_joins_at_db_boundary(pg):
    ta='pg-a-' + uuid4().hex[:10]
    tb='pg-b-' + uuid4().hex[:10]
    token_a = pg.bootstrap_tenant(ta, 'Synthetic A')
    token_b = pg.bootstrap_tenant(tb, 'Synthetic B')
    with TestClient(create_app()) as client:
        a=client.post('/v1/teachers',headers=headers(token_a),json={'label':'Teacher A'})
        assert a.status_code == 201,a.text
        teacher=a.json()['actor_id']
        with pg.connect() as cx:
            # Composite (tenant_id, actor_id) FK rejects a teacher from school A
            # being accidentally granted cohort access under school B.
            with pytest.raises(Exception) as error:
                cx.execute('''INSERT INTO teacher_cohorts(tenant_id,actor_id,cohort,granted_at)
                              VALUES(?,?,?,?)''', (tb,teacher,'U6','2026-01-01T00:00:00+00:00'))
            assert type(error.value).__name__ == 'ForeignKeyViolation'
        assert client.get('/v1/teachers',headers=headers(token_b)).json() == []


def test_postgres_api_tenant_roles_revocation_and_unverified_device_upload(pg):
    ta='pg-a-' + uuid4().hex[:10]
    tb='pg-b-' + uuid4().hex[:10]
    token_a = pg.bootstrap_tenant(ta, 'Synthetic Admin A')
    token_b = pg.bootstrap_tenant(tb, 'Synthetic Admin B')
    with TestClient(create_app()) as client:
        teacher_r = client.post('/v1/teachers',headers=headers(token_a),json={'label':'Synthetic Teacher'})
        assert teacher_r.status_code==201,teacher_r.text
        teacher = teacher_r.json()['token']; teacher_id = teacher_r.json()['actor_id']
        denied=client.get('/v1/students',headers=headers(teacher))
        assert denied.status_code==200 and denied.json()==[]
        assert client.post('/v1/students',headers=headers(teacher),json={'pseudonym':'T','cohort':'U6'}).status_code==403
        assert client.post(f'/v1/teachers/{teacher_id}/cohorts',headers=headers(token_a),json={'cohort':'U6'}).status_code==201
        s=client.post('/v1/students',headers=headers(teacher),json={'pseudonym':'Synthetic','cohort':'U6'})
        assert s.status_code==201,s.text
        student=s.json()['id']
        assert client.get('/v1/students',headers=headers(token_b)).json()==[]
        assert client.delete(f'/v1/students/{student}',headers=headers(token_b)).status_code==404
        dev=client.post('/v1/devices',headers=headers(token_a),json={'student_id':student,'label':'synthetic-device','valid_days':1})
        assert dev.status_code==201,dev.text
        credential=dev.json()['token']
        backup={'app':'CHEMFORGE_ANDROID','schema_version':1,'tenant_id':ta,
                'content_version':'pilot-0.1','content_fingerprint':'pilot-0.1',
                'attempts':[{'id':'pg-e-'+uuid4().hex[:9], 'question_id':'Q-CI',
                    'mark':1,'max_marks':2,'assessment_source':'learner_self_review','mode':'practice',
                    'hints_used':0,'recorded_at':'2026-10-11T12:00:00Z',
                    'tenant_id':ta,'content_version':'pilot-0.1', 'content_fingerprint':'pilot-0.1'}]}
        link={'Authorization': 'Device '+credential}
        uploaded=client.post('/v1/sync/backups',headers=link,json=backup)
        assert uploaded.status_code==201,uploaded.text
        assert uploaded.json()['verified']==0
        teacher_metrics=client.get('/v1/analytics/cohorts',headers=headers(teacher)).json()
        assert teacher_metrics[0]['unverified_attempts']==1
        assert teacher_metrics[0]['verified_attempts']==0
        assert client.get('/v1/analytics/cohorts',headers=headers(token_b)).json()==[]
        assert client.delete('/v1/devices/'+dev.json()['device_id'],headers=headers(token_a)).status_code==204
        assert client.post('/v1/sync/backups',headers=link,json=backup).status_code==401
        assert client.delete(f'/v1/teachers/{teacher_id}/cohorts/U6',headers=headers(token_a)).status_code==204
        assert client.get('/v1/students',headers=headers(teacher)).json()==[]
        assert client.delete('/v1/teachers/'+teacher_id,headers=headers(token_a)).status_code==204
        assert client.get('/v1/me',headers=headers(teacher)).status_code==401


@pytest.mark.parametrize('change', ['revoke', 'expire', 'switch_student'])
def test_postgres_device_upload_rechecks_authority_after_dependency(pg,change):
    """Real PostgreSQL write lock must enforce the post-auth credential state.

    The override wraps the actual auth dependency and then applies a committed
    synthetic admin DB change before the request handler starts writing.
    """
    from fastapi import Header
    from tests.control_plane.test_institution_sync_v17 import backup

    tenant='race-' + uuid4().hex[:11]
    token=pg.bootstrap_tenant(tenant,'Synthetic principal')
    app=create_app()
    with TestClient(app) as client:
        first=client.post('/v1/students',headers=headers(token),
            json={'pseudonym':'Student A','cohort':'U6'}).json()['id']
        second=client.post('/v1/students',headers=headers(token),
            json={'pseudonym':'Student B','cohort':'U6'}).json()['id']
        device=client.post('/v1/devices',headers=headers(token),
            json={'student_id':first,'label':'Synthetic tablet','valid_days':1}).json()
        route=next(r for r in app.routes if getattr(r,'path',None)=='/v1/sync/backups')
        verify=route.dependant.dependencies[0].call

        def after_auth(authorization: str | None = Header(default=None)):
            identity=verify(authorization)
            with pg.connect() as cx:
                if change=='revoke':
                    cx.execute('UPDATE devices SET revoked_at=? WHERE id=?',
                        ('2026-10-13T01:00:00+00:00',device['device_id']))
                elif change=='expire':
                    cx.execute('UPDATE devices SET expires_at=? WHERE id=?',
                        ('2020-01-01T00:00:00+00:00',device['device_id']))
                else:
                    cx.execute('UPDATE devices SET student_id=? WHERE id=?',
                        (second,device['device_id']))
            return identity

        app.dependency_overrides[verify]=after_auth
        attempt='pg-race-'+uuid4().hex[:12]
        resp=client.post('/v1/sync/backups', headers={'Authorization':'Device '+device['token']},
                         json=backup(tenant,attempt))
        assert resp.status_code==401,resp.text
        with pg.connect() as cx:
            assert cx.execute('SELECT COUNT(*) AS n FROM evidence WHERE tenant_id=? AND event_id=?',
                              (tenant,attempt)).fetchone()['n']==0
            assert cx.execute('SELECT COUNT(*) AS n FROM audit WHERE tenant_id=? AND action=?',
                              (tenant,'backup.imported')).fetchone()['n']==0
