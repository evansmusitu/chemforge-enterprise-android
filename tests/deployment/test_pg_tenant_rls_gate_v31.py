"""Fail-closed tests for the disposable PostgreSQL row-policy experiment."""
import re
import pytest
from tools.postgres_tenant_rls_gate import prepare_disposable_rls_probe

ACK = 'I_ACKNOWLEDGE_DISPOSABLE_SYNTHETIC_DATABASE_ONLY'
ENV = {
    'CHEMFORGE_PG_CI': '1',
    'CHEMFORGE_POSTGRES_SYNTHETIC_ONLY': ACK,
    'CHEMFORGE_PG_DSN': ('postgresql://chemforge_synthetic:not_a_secret@127.0.0.1:5432/'
                         'chemforge_synthetic?sslmode=disable'),
}

class FakeCursor:
    def __init__(self, database='chemforge_synthetic', owner='chemforge_synthetic', existing=False):
        self.database, self.owner, self.existing = database, owner, existing
        self.commands = []
    def execute(self, sql, params=()):
        self.commands.append((str(sql), params))
        return self
    def fetchone(self):
        statement = self.commands[-1][0]
        if 'current_database()' in statement:
            return {'database_name': self.database, 'database_user': self.owner}
        if 'to_regclass(' in statement or 'FROM pg_roles' in statement:
            return {'found': 'existing'} if self.existing else {'found': None} if 'to_regclass(' in statement else None
        raise AssertionError(statement)

@pytest.mark.parametrize('edit', [
    {'CHEMFORGE_PG_CI': '0'},
    {'CHEMFORGE_POSTGRES_SYNTHETIC_ONLY': ''},
    {'CHEMFORGE_PG_DSN': 'postgresql://u:p@neon.example.invalid:5432/chemforge_synthetic?sslmode=disable'},
    {'CHEMFORGE_PG_DSN': 'postgresql://chemforge_synthetic:p@127.0.0.1:5432/other?sslmode=disable'},
    {'CHEMFORGE_PG_DSN': 'postgresql://chemforge_ci_app:p@127.0.0.1:5432/chemforge_synthetic?sslmode=disable'},
])
def test_rejects_unsafe_connectivity_without_any_sql(edit):
    cur=FakeCursor()
    with pytest.raises(ValueError):
        prepare_disposable_rls_probe({**ENV, **edit},cur)
    assert cur.commands==[]

@pytest.mark.parametrize('db,owner,existing', [
    ('some_other_db','chemforge_synthetic',False),
    ('chemforge_synthetic','non_owner',False),
    ('chemforge_synthetic','chemforge_synthetic',True),
])
def test_refuses_non_empty_or_wrong_database_before_any_ddl(db,owner,existing):
    cur=FakeCursor(db,owner,existing)
    with pytest.raises(ValueError):
        prepare_disposable_rls_probe(ENV,cur)
    assert not any(s.lstrip().startswith(('CREATE ', 'ALTER ', 'GRANT ', 'INSERT ', 'REVOKE ')) for s,_ in cur.commands)

def test_policy_is_bound_to_pg_authenticated_principal_not_spoofable_settings():
    cur=FakeCursor()
    result=prepare_disposable_rls_probe(ENV,cur)
    assert result.status=='DISPOSABLE_RLS_PROBE_CREATED_NOT_DEPLOYED'
    assert result.public_evidence()['real_student_data_allowed'] is False
    assert result.public_evidence()['remote_access_allowed'] is False
    assert len(result.logins)==2
    assert set(result.logins)=={'chemforge_ci_rls_a','chemforge_ci_rls_b'}
    assert all(re.fullmatch('[A-Za-z0-9_-]{40,}',login.password) for login in result.logins.values())
    assert all(login.password not in repr(result) for login in result.logins.values())
    sql='\n'.join(s for s,_ in cur.commands)
    assert 'session_user' in sql
    assert 'current_setting(' not in sql
    assert 'ENABLE ROW LEVEL SECURITY' in sql
    assert 'FORCE ROW LEVEL SECURITY' in sql
    assert 'USING (tenant_id = public.chemforge_ci_rls_tenant())' in sql
    assert 'WITH CHECK (tenant_id = public.chemforge_ci_rls_tenant())' in sql
    assert 'REVOKE ALL ON public.chemforge_ci_rls_principals FROM PUBLIC' in sql
    assert 'GRANT SELECT, INSERT, UPDATE, DELETE ON public.chemforge_ci_rls_probe' in sql
    assert 'CREATEDB' not in sql and 'SUPERUSER' not in sql
