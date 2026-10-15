"""Synthetic OIDC protection for the strictly free, unhosted control pilot."""
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlsplit

from fastapi.testclient import TestClient

from control_plane import browser_oidc
from control_plane.db import token_digest
from tests.control_plane.test_oidc_browser_v21 import BASE, oidc_env


def test_start_limits_outstanding_state_and_recovers_expired_slot(oidc_env, monkeypatch):
    """An unauthenticated caller cannot grow the state table past its cap."""
    monkeypatch.setattr(browser_oidc, 'MAX_ACTIVE_FLOWS', 2, raising=False)
    with TestClient(oidc_env['app'], base_url=BASE) as client:
        first = client.get('/auth/start', follow_redirects=False)
        second = client.get('/auth/start', follow_redirects=False)
        assert first.status_code == 302
        assert second.status_code == 302
        denied = client.get('/auth/start', follow_redirects=False)
        assert denied.status_code == 429, denied.text
        assert denied.headers.get('cache-control') == 'no-store'
        assert 'retry-after' in denied.headers
        with oidc_env['db'].connect() as cx:
            assert cx.execute('SELECT COUNT(*) FROM oidc_auth_flows').fetchone()[0] == 2
            state = parse_qs(urlsplit(first.headers['location']).query)['state'][0]
            cx.execute('UPDATE oidc_auth_flows SET expires_at=? WHERE state_hash=?',
                       ('2020-01-01T00:00:00+00:00', token_digest(state)))
        recovered = client.get('/auth/start', follow_redirects=False)
        assert recovered.status_code == 302
        with oidc_env['db'].connect() as cx:
            assert cx.execute('SELECT COUNT(*) FROM oidc_auth_flows').fetchone()[0] == 2


def test_start_prunes_expired_staff_sessions_without_removing_active_ones(oidc_env):
    """Expired opaque session hashes are purged, active sessions retained."""
    ids = oidc_env['ids']
    now = datetime.now(timezone.utc)
    with oidc_env['db'].connect() as cx:
        for tag, age in [('expired', -5), ('active', 5)]:
            cx.execute('''INSERT INTO oidc_browser_sessions
                (session_hash,actor_id,tenant_id,issuer,subject,csrf_token,expires_at,created_at)
                VALUES(?,?,?,?,?,?,?,?)''',
                (tag, ids['school-a'], 'school-a', 'https://login.example.invalid/realm',
                 'staff-a', 'synthetic-csrf', (now + timedelta(minutes=age)).isoformat(), now.isoformat()))
    with TestClient(oidc_env['app'], base_url=BASE) as client:
        assert client.get('/auth/start', follow_redirects=False).status_code == 302
    with oidc_env['db'].connect() as cx:
        rows = {r[0] for r in cx.execute('SELECT session_hash FROM oidc_browser_sessions')}
    assert rows == {'active'}


def test_429_still_commits_expired_session_cleanup(oidc_env, monkeypatch):
    """Capacity denial must not roll back maintenance of expired records."""
    monkeypatch.setattr(browser_oidc, 'MAX_ACTIVE_FLOWS', 0)
    with oidc_env['db'].connect() as cx:
        cx.execute('''INSERT INTO oidc_browser_sessions
            (session_hash,actor_id,tenant_id,issuer,subject,csrf_token,expires_at,created_at)
            VALUES(?,?,?,?,?,?,?,?)''',
            ('expired', oidc_env['ids']['school-a'], 'school-a',
             'https://login.example.invalid/realm', 'staff-a', 'synthetic-csrf',
             '2020-01-01T00:00:00+00:00', '2020-01-01T00:00:00+00:00'))
    with TestClient(oidc_env['app'], base_url=BASE) as client:
        assert client.get('/auth/start', follow_redirects=False).status_code == 429
    with oidc_env['db'].connect() as cx:
        assert cx.execute('SELECT COUNT(*) FROM oidc_browser_sessions').fetchone()[0] == 0
