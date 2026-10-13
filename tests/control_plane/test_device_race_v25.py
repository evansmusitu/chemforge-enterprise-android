"""A device disabled after FastAPI auth resolution must not write a backup.

This exercises the HTTP boundary and a real SQLite transaction. A dependency
wrapper establishes a deterministic auth/write interleaving without threads.
"""
from fastapi import Header
from fastapi.testclient import TestClient
import pytest
from control_plane.app import create_app
from control_plane.db import Database
from tests.control_plane.test_institution_sync_v17 import H, backup


@pytest.mark.parametrize('change', ['revoke', 'expire', 'switch_student'])
def test_device_upload_rechecks_live_authority_inside_write_transaction(tmp_path, change):
    path = str(tmp_path / 'pilot.sqlite')
    db = Database(path)
    admin = db.bootstrap_tenant('school-race', 'Synthetic Principal')
    app = create_app(path)
    with TestClient(app) as client:
        student = client.post('/v1/students', headers=H(admin),
                              json={'pseudonym':'Synthetic', 'cohort':'U6'}).json()['id']
        other = client.post('/v1/students', headers=H(admin),
                            json={'pseudonym':'Second', 'cohort':'U6'}).json()['id']
        issued = client.post('/v1/devices', headers=H(admin),
                             json={'student_id':student, 'label':'Synthetic', 'valid_days':1}).json()
        route = next(r for r in app.routes if getattr(r, 'path', None) == '/v1/sync/backups')
        authenticate = route.dependant.dependencies[0].call
        did = issued['device_id']

        def authenticate_then_mutate(authorization: str | None = Header(default=None)):
            # First perform REAL initial credential validation. The change
            # represents an admin action immediately after the dependency.
            resolved = authenticate(authorization)
            with db.connect() as cx:
                if change == 'revoke':
                    cx.execute('UPDATE devices SET revoked_at=? WHERE id=?',
                               ('2026-10-13T01:00:00+00:00', did))
                elif change == 'expire':
                    cx.execute('UPDATE devices SET expires_at=? WHERE id=?',
                               ('2020-01-01T00:00:00+00:00', did))
                else:
                    cx.execute('UPDATE devices SET student_id=? WHERE id=?', (other, did))
            return resolved

        app.dependency_overrides[authenticate] = authenticate_then_mutate
        event='race-'+change
        result = client.post('/v1/sync/backups',headers=H(issued['token'], 'Device'),
                             json=backup('school-race', event))
        assert result.status_code == 401, result.text
        with db.connect() as cx:
            assert cx.execute('SELECT COUNT(*) FROM evidence WHERE event_id=?', (event,)).fetchone()[0] == 0
            assert cx.execute('SELECT COUNT(*) FROM audit WHERE action=?', ('backup.imported',)).fetchone()[0] == 0
