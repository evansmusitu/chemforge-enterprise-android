"""Synthetic-only, actual LOGIN role provisioning contract (no local DB needed)."""
from __future__ import annotations

import re
import pytest

from tools.postgres_login_gate import provision_disposable_login


class FakeCursor:
    def __init__(self, actual_database='chemforge_synthetic', user='chemforge_synthetic', group=True):
        self.actual_database = actual_database
        self.user = user
        self.group = group
        self.statements = []

    def execute(self, sql, params=()):
        self.statements.append((str(sql), params))
        return self

    def fetchone(self):
        q = self.statements[-1][0]
        if 'current_database()' in q:
            return {'database_name': self.actual_database, 'database_user': self.user}
        if 'pg_roles' in q:
            return {'can_login': False} if self.group else None
        raise AssertionError('Unexpected query: '+q)


@pytest.fixture
def safe_env():
    return {
        'CHEMFORGE_PG_CI':'1',
        'CHEMFORGE_POSTGRES_SYNTHETIC_ONLY':'I_ACKNOWLEDGE_DISPOSABLE_SYNTHETIC_DATABASE_ONLY',
        'CHEMFORGE_PG_DSN':'postgresql://chemforge_synthetic:CI_NOT_REAL@127.0.0.1:5432/chemforge_synthetic?sslmode=disable',
    }


def test_disposable_login_is_unique_nonadmin_and_never_prints_password(safe_env):
    cursor=FakeCursor()
    login=provision_disposable_login(safe_env,cursor)
    assert login.username=='chemforge_ci_app'
    assert len(login.password)>=40
    assert re.fullmatch(r'[A-Za-z0-9_-]+',login.password)
    assert login.password not in repr(login)
    assert login.password not in str(login)
    assert 'CI_NOT_REAL' not in repr(login)
    commands='\n'.join(command for command,_ in cursor.statements)
    assert "CREATE ROLE chemforge_ci_app WITH LOGIN INHERIT" in commands
    assert 'GRANT chemforge_ci_runtime TO chemforge_ci_app WITH INHERIT TRUE, SET FALSE' in commands
    assert 'CREATEDB' not in commands and 'CREATEROLE' not in commands and 'SUPERUSER' not in commands
    assert 'chemforge_ci_runtime' in commands
    assert login.password in commands
    assert login.password not in login.public_evidence()['status']
    assert login.public_evidence()['production_admission'] is False


@pytest.mark.parametrize('change',[
    {'CHEMFORGE_PG_CI':'0'},
    {'CHEMFORGE_POSTGRES_SYNTHETIC_ONLY':''},
    {'CHEMFORGE_PG_DSN':'postgresql://x:y@neon.example.invalid:5432/chemforge_synthetic?sslmode=disable'},
    {'CHEMFORGE_PG_DSN':'postgresql://chemforge_synthetic:p@127.0.0.1:5432/other?sslmode=disable'},
    {'CHEMFORGE_PG_DSN':'postgresql://chemforge_ci_app:p@127.0.0.1:5432/chemforge_synthetic?sslmode=disable'},
    {'CHEMFORGE_PG_DSN':'postgresql://chemforge_synthetic:p@127.0.0.1:5432/chemforge_synthetic?sslmode=verify-full'},
])
def test_refuses_unsafe_config_before_sql(safe_env,change):
    cursor=FakeCursor()
    with pytest.raises(ValueError):
        provision_disposable_login({**safe_env,**change},cursor)
    assert cursor.statements==[]


@pytest.mark.parametrize('actual,user,group',[
    ('another_database','chemforge_synthetic',True),
    ('chemforge_synthetic','unexpected_owner',True),
    ('chemforge_synthetic','chemforge_synthetic',False),
])
def test_refuses_missing_group_or_wrong_live_identity(safe_env,actual,user,group):
    cursor=FakeCursor(actual,user,group)
    with pytest.raises(ValueError):
        provision_disposable_login(safe_env,cursor)
    assert all(not s.startswith(('CREATE ROLE','GRANT ')) for s,_ in cursor.statements)
