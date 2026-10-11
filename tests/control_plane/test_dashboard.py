"""Contract tests for locally-hosted CHEMFORGE Control operator console."""
from fastapi.testclient import TestClient
from control_plane.app import create_app
from control_plane.db import Database


def test_console_assets_are_served_locally_with_secure_headers(tmp_path):
    with TestClient(create_app(str(tmp_path / 'control.sqlite'))) as c:
        screen = c.get('/console')
        assert screen.status_code == 200
        assert 'CHEMFORGE Control' in screen.text
        assert 'src="/console/app.js"' in screen.text
        assert 'href="/console/style.css"' in screen.text
        assert screen.headers['cache-control'] == 'no-store'
        assert screen.headers['x-frame-options'] == 'DENY'
        assert screen.headers['x-content-type-options'] == 'nosniff'
        assert screen.headers['referrer-policy'] == 'no-referrer'
        csp = screen.headers['content-security-policy']
        assert "default-src 'none'" in csp
        assert "script-src 'self'" in csp
        assert "connect-src 'self'" in csp
        assert "frame-ancestors 'none'" in csp
        assert "'unsafe-inline'" not in csp
        for path, expected in [('/console/app.js','application/javascript'),('/console/style.css','text/css')]:
            response = c.get(path)
            assert response.status_code == 200
            assert expected in response.headers['content-type']
            assert response.headers['cache-control'] == 'no-store'
        assert c.get('/console/anything-private').status_code == 404
        assert c.get('/v1/students').status_code == 401


def test_console_ui_only_uses_in_memory_tokens_and_safe_dom(tmp_path):
    with TestClient(create_app(str(tmp_path / 'control.sqlite'))) as c:
        js = c.get('/console/app.js').text
        assert 'sessionStorage' not in js
        assert 'localStorage' not in js
        assert '.innerHTML' not in js
        assert 'eval(' not in js
        assert 'document.createElement' in js
        assert '.textContent' in js
        assert "credentials: 'omit'" in js
        assert 'Authorization' in js
        assert 'unverified_import' in js
        assert 'logout' in js
        assert 'confirm(' in js


def test_operator_endpoints_preserve_tenant_and_role_separation(tmp_path):
    db_path = str(tmp_path / 'control.sqlite')
    db = Database(db_path)
    admin_a = db.bootstrap_tenant('school-a', 'Admin A')
    admin_b = db.bootstrap_tenant('school-b', 'Admin B')
    with TestClient(create_app(db_path)) as c:
        head_a = {'Authorization': f'Bearer {admin_a}'}
        head_b = {'Authorization': f'Bearer {admin_b}'}
        added = c.post('/v1/students',headers=head_a,json={'pseudonym':'Learner D','cohort':'L6-A'})
        assert added.status_code == 201
        staff = c.post('/v1/teachers',headers=head_a,json={'label':'Ms Y'})
        assert staff.status_code == 201
        teacher = {'Authorization': f"Bearer {staff.json()['token']}"}
        assert c.get('/v1/teachers',headers=teacher).status_code == 403
        assert c.get('/v1/audit',headers=teacher).status_code == 403
        assert c.get('/v1/students',headers=head_b).json() == []
        assert c.get('/v1/students',headers=teacher).json()[0]['pseudonym'] == 'Learner D'
        assert c.post('/v1/assignments',headers=teacher,json={
           'title':'Acids', 'cohort':'L6-A', 'objective_ids':['ACID-01']}).status_code == 201
        assert c.get('/v1/assignments',headers=head_b).json() == []
        # Browser content cannot mark imported scores as verified.
        assert c.get('/v1/analytics/cohorts',headers=teacher).json()[0]['verified_attempts'] == 0


def test_console_csp_does_not_break_developer_api_documentation(tmp_path):
    with TestClient(create_app(str(tmp_path / 'control.sqlite'))) as c:
        docs = c.get('/docs')
        assert docs.status_code == 200
        # The console alone is locked to local assets; Swagger developer docs
        # retain their independent CSP configuration rather than silently break.
        assert "default-src 'none'" not in docs.headers.get('content-security-policy', '')
