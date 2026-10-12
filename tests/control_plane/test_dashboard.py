"""Behavioral tests for the same-origin, token-in-memory CHEMFORGE Control dashboard."""
from pathlib import Path
import re
from fastapi.testclient import TestClient
from control_plane.app import create_app
from control_plane.db import Database


def test_dashboard_is_locally_served_with_browser_isolation_headers(tmp_path):
    with TestClient(create_app(str(tmp_path / 'control.sqlite'))) as client:
        for path, mimetype in [('/control/', 'text/html'), ('/control/app.js', 'javascript'),
                               ('/control/styles.css', 'text/css')]:
            r = client.get(path)
            assert r.status_code == 200, (path, r.text[:200])
            assert mimetype in r.headers['content-type']
            assert r.headers['cache-control'] == 'no-store'
            assert r.headers['x-content-type-options'] == 'nosniff'
            assert r.headers['referrer-policy'] == 'no-referrer'
            assert r.headers['x-frame-options'] == 'DENY'
            assert "default-src 'none'" in r.headers['content-security-policy']
            assert "connect-src 'self'" in r.headers['content-security-policy']
            assert "frame-ancestors 'none'" in r.headers['content-security-policy']
            assert 'unsafe-inline' not in r.headers['content-security-policy']


def test_dashboard_exposes_workflows_but_no_secret_persistence(tmp_path):
    with TestClient(create_app(str(tmp_path / 'control.sqlite'))) as client:
        html = client.get('/control/').text
        js = client.get('/control/app.js').text
        assert 'CHEMFORGE Control' in html
        assert '<script src="/control/app.js" defer></script>' in html
        assert 'type="password"' in html
        assert 'Unverified' in html
        for endpoint in ['/v1/me', '/v1/students', '/v1/teachers', '/v1/assignments',
                         '/v1/analytics/cohorts', '/v1/content/releases', '/v1/audit']:
            assert endpoint in js
        assert '/backups' in js
        assert 'localStorage' not in js and 'sessionStorage' not in js
        assert 'innerHTML' not in js and 'document.write' not in js
        assert 'eval(' not in js
        assert re.search(r'\btextContent\b', js)
        assert not re.search(r'\bon[a-z]+\s*=', html, flags=re.I)
        assert '<script>' not in html


def test_dashboard_does_not_bypass_api_permissions(tmp_path):
    db = Database(str(tmp_path / 'control.sqlite'))
    admin = db.bootstrap_tenant('school-x', 'Principal')
    with TestClient(create_app(str(tmp_path / 'control.sqlite'))) as client:
        assert client.get('/control/').status_code == 200
        assert client.get('/v1/students').status_code == 401
        assert client.get('/v1/audit').status_code == 401
        teacher = client.post('/v1/teachers', json={'label':'Teacher'},
                              headers={'Authorization':f'Bearer {admin}'}).json()['token']
        assert client.get('/v1/students',headers={'Authorization':f'Bearer {teacher}'}).status_code == 200
        assert client.get('/v1/audit', headers={'Authorization':f'Bearer {teacher}'}).status_code == 403
        assert client.delete('/v1/teachers/anything',headers={'Authorization':f'Bearer {teacher}'}).status_code == 403
