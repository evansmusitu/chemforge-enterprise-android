"""v3.3 CI-only authenticated PostgreSQL session routing safety checks.

Only fake psycopg boundaries are used here; the real PostgreSQL test runs in
CI after v3.2 provisions independent disposable tenant logins.
"""
from contextlib import contextmanager
from dataclasses import dataclass

import pytest

from control_plane.postgres_synthetic import ACKNOWLEDGEMENT
from tools.postgres_app_rls_gate import AppRlsLogin, BINDINGS
from tools.postgres_tenant_session_gate import TenantSessionRouter

OWNER_DSN = ('postgresql://chemforge_synthetic:ci_password@127.0.0.1:5432/'
             'chemforge_synthetic?sslmode=disable')
ENV = {
    'CHEMFORGE_PG_CI': '1',
    'CHEMFORGE_POSTGRES_SYNTHETIC_ONLY': ACKNOWLEDGEMENT,
    'CHEMFORGE_PG_DSN': OWNER_DSN,
}
LOGINS = {name: AppRlsLogin(name, tenant, 'this_is_only_a_synthetic_CI_password_abcdefghijklmno')
          for name, tenant in BINDINGS.items()}


class FakeConnection:
    def __init__(self, username, tenant, *, current_user=None, database='chemforge_synthetic'):
        self.username, self.tenant = username, tenant
        self.current_user = current_user or username
        self.database = database
        self.closed = False
        self.sql = []
        self.rollback_calls = 0

    def execute(self, sql, params=()):
        self.sql.append((sql, params))
        return self

    def fetchone(self):
        return {'session_user': self.username, 'current_user': self.current_user,
                'database_name': self.database, 'tenant_id': self.tenant}

    def rollback(self):
        self.rollback_calls += 1

    def close(self):
        self.closed = True


class FakeDriver:
    def __init__(self, wrong=None):
        self.created = []
        self.wrong = wrong or {}

    @contextmanager
    def connect(self, dsn, **kwargs):
        from urllib.parse import urlsplit
        parsed = urlsplit(dsn)
        tenant = BINDINGS[parsed.username]
        cx = FakeConnection(parsed.username, tenant, **self.wrong)
        self.created.append(cx)
        try:
            yield cx
        finally:
            cx.closed = True


def test_sequential_tenants_receive_distinct_short_lived_connections():
    driver = FakeDriver()
    router = TenantSessionRouter(ENV, LOGINS, connect=driver.connect)
    a, b = list(BINDINGS.values())
    for tenant in [a, b, a, b, a]:
        with router.open_for_authenticated_tenant(tenant) as cx:
            assert cx.tenant == tenant
            assert not cx.closed
            assert 'session_user' in cx.sql[0][0]
        assert cx.closed
    assert len(driver.created) == 5
    assert len({id(c) for c in driver.created}) == 5
    assert not any('secret' in repr(router).lower() for _ in [1])
    assert router.public_evidence()['production_admission'] is False
    assert router.public_evidence()['tenant_principals'] == sorted(BINDINGS.values())


def test_unrecognized_tenant_rejected_without_network_connection():
    driver = FakeDriver()
    router = TenantSessionRouter(ENV, LOGINS, connect=driver.connect)
    with pytest.raises(ValueError, match='unrecognized'):
        with router.open_for_authenticated_tenant('school-from-http-payload'):
            pass
    assert not driver.created


@pytest.mark.parametrize('change', [
    {'CHEMFORGE_PG_CI': '0'},
    {'CHEMFORGE_POSTGRES_SYNTHETIC_ONLY': ''},
    {'CHEMFORGE_PG_DSN': 'postgresql://admin:pw@remote.neon.tech:5432/chemforge_synthetic?sslmode=require'},
    {'CHEMFORGE_PG_DSN': 'postgresql://admin:pw@127.0.0.1:5432/other?sslmode=disable'},
    {'CHEMFORGE_PG_DSN': 'postgresql://chemforge_ci_app:pw@127.0.0.1:5432/chemforge_synthetic?sslmode=disable'},
])
def test_configuration_fail_closed_before_connection(change):
    driver = FakeDriver()
    with pytest.raises(ValueError):
        TenantSessionRouter({**ENV, **change}, LOGINS, connect=driver.connect)
    assert not driver.created


@pytest.mark.parametrize('bad_logins', [
    {},
    {'chemforge_ci_data_a': LOGINS['chemforge_ci_data_a']},
    {**LOGINS, 'admin': AppRlsLogin('admin', 'school-admin', 'pw')},
    {**LOGINS, 'chemforge_ci_data_a': AppRlsLogin('chemforge_ci_data_a', 'ci-app-school-b', 'pw')},
    {**LOGINS, 'chemforge_ci_data_a': AppRlsLogin('admin', 'ci-app-school-a', 'pw')},
])
def test_untrusted_login_catalog_rejected(bad_logins):
    with pytest.raises(ValueError):
        TenantSessionRouter(ENV, bad_logins, connect=FakeDriver().connect)


@pytest.mark.parametrize('wrong', [
    {'current_user': 'chemforge_synthetic'},
    {'session_user': 'chemforge_ci_data_b'},
    {'database': 'another_database'},
    {'tenant': 'wrong'},
])
def test_database_identity_mismatch_raises_and_closes(wrong):
    class Wrong(FakeDriver):
        @contextmanager
        def connect(self, dsn, **kwargs):
            from urllib.parse import urlsplit
            parsed = urlsplit(dsn)
            row = dict(wrong)
            row.setdefault('tenant', BINDINGS[parsed.username])
            session_user = row.pop('session_user', None)
            cx = FakeConnection(parsed.username, **row)
            if session_user is not None:
                cx.username = session_user
            self.created.append(cx)
            try:
                yield cx
            finally:
                cx.closed = True

    driver = Wrong()
    router = TenantSessionRouter(ENV, LOGINS, connect=driver.connect)
    with pytest.raises(ValueError, match='identity mismatch'):
        with router.open_for_authenticated_tenant('ci-app-school-a'):
            pytest.fail('An untrusted database connection must never be yielded')
    assert driver.created[0].closed
