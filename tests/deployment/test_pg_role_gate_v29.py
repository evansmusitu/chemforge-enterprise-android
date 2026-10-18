"""Role hardening contract on a synthetic/loopback database, with no sockets."""
from __future__ import annotations


import pytest

from tools.postgres_role_gate import apply_synthetic_role_gate


class FakeCursor:
    def __init__(self):
        self.statements = []

    def execute(self, statement, params=()):
        self.statements.append((statement, params))
        if 'current_database()' in statement:
            return type('OneRow', (), {'fetchone': lambda self: {'database_name': 'chemforge_synthetic'}})()
        return self


@pytest.fixture
def environment():
    return {
        'CHEMFORGE_POSTGRES_SYNTHETIC_ONLY': 'I_ACKNOWLEDGE_DISPOSABLE_SYNTHETIC_DATABASE_ONLY',
        'CHEMFORGE_PG_CI': '1',
        'CHEMFORGE_PG_DSN': 'postgresql://chemforge_synthetic:PLACEHOLDER_NOT_REAL@127.0.0.1:5432/chemforge_synthetic?sslmode=disable',
    }


def test_grants_runtime_permissions_but_never_audit_mutation_or_schema_ddl(environment):
    cursor = FakeCursor()
    outcome = apply_synthetic_role_gate(environment, cursor)
    assert outcome['status'] == 'SYNTHETIC_ROLE_POLICY_CONFIGURED'
    assert outcome['neon_connection_attempted'] is False
    commands = '\n'.join(sql for sql, _ in cursor.statements)
    assert 'CREATE ROLE chemforge_ci_runtime NOLOGIN' in commands
    assert 'GRANT USAGE ON SCHEMA public TO chemforge_ci_runtime' in commands
    assert 'GRANT SELECT, INSERT ON TABLE public.audit TO chemforge_ci_runtime' in commands
    assert 'GRANT SELECT ON TABLE public.chemforge_schema_versions TO chemforge_ci_runtime' in commands
    assert 'GRANT USAGE ON SEQUENCE public.audit_id_seq TO chemforge_ci_runtime' in commands
    assert 'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE' in commands
    assert 'public.devices' in commands and 'public.students' in commands
    assert 'public.audit TO chemforge_ci_runtime' not in '\n'.join(
        cmd for cmd, _ in cursor.statements if 'UPDATE, DELETE' in cmd
    )
    assert 'public.chemforge_schema_versions TO chemforge_ci_runtime' not in '\n'.join(
        cmd for cmd, _ in cursor.statements if 'UPDATE, DELETE' in cmd
    )
    assert 'GRANT CREATE' not in commands
    assert 'ALTER ROLE' not in commands
    assert 'PASSWORD' not in commands


@pytest.mark.parametrize('key,changed', [
    ('CHEMFORGE_PG_CI', '0'),
    ('CHEMFORGE_POSTGRES_SYNTHETIC_ONLY', ''),
    ('CHEMFORGE_PG_DSN', 'postgresql://u:p@ep-not-ours.neon.tech:5432/chemforge_synthetic?sslmode=disable'),
    ('CHEMFORGE_PG_DSN', 'postgresql://u:p@127.0.0.1:5432/another_database?sslmode=disable'),
    ('CHEMFORGE_PG_DSN', 'postgresql://u:p@127.0.0.1:5432/chemforge_synthetic?sslmode=require'),
])
def test_rejects_non_disposable_config_before_any_statements(environment, key, changed):
    environment[key] = changed
    cursor = FakeCursor()
    with pytest.raises(ValueError):
        apply_synthetic_role_gate(environment, cursor)
    assert cursor.statements == []


def test_requires_actual_database_identity_not_merely_url(environment):
    class WrongCursor(FakeCursor):
        def execute(self, statement, params=()):
            self.statements.append((statement, params))
            return type('OneRow', (), {'fetchone': lambda self: {'database_name': 'unrelated'}})()
    wrong = WrongCursor()
    with pytest.raises(ValueError, match='database identity'):
        apply_synthetic_role_gate(environment, wrong)
    assert all('CREATE ROLE' not in command for command, _ in wrong.statements)


def test_role_policy_returns_no_password_uri_or_connection(environment):
    cursor=FakeCursor()
    status=apply_synthetic_role_gate(environment,cursor)
    assert environment['CHEMFORGE_PG_DSN'] not in repr(status)
    assert 'PLACEHOLDER_NOT_REAL' not in repr(status)
