"""Security and safety gate for app-schema RLS qualification, with NO database needed."""
import pytest

from tools.postgres_app_rls_gate import (APP_TABLES, APP_TENANT_TABLES,
    prepare_disposable_app_rls,)

ACK='I_ACKNOWLEDGE_DISPOSABLE_SYNTHETIC_DATABASE_ONLY'
ENV={'CHEMFORGE_PG_CI':'1','CHEMFORGE_POSTGRES_SYNTHETIC_ONLY':ACK,
     'CHEMFORGE_PG_DSN':'postgresql://chemforge_synthetic:ci@127.0.0.1:5432/chemforge_synthetic?sslmode=disable'}

class Cursor:
    def __init__(self, db='chemforge_synthetic', user='chemforge_synthetic',
                 missing=False, preexisting=False):
        self.db,self.user,self.missing,self.preexisting=db,user,missing,preexisting
        self.commands=[]
    def execute(self,sql,params=()):
        self.commands.append((str(sql),params))
        return self
    def fetchone(self):
        sql=self.commands[-1][0]
        if 'current_database()' in sql:
            return {'database_name':self.db,'database_user':self.user}
        if 'to_regclass(' in sql or 'FROM pg_roles' in sql:
            return ({'found':'already'} if self.preexisting else None) if 'FROM pg_roles' in sql else {'found':'already' if self.preexisting else None}
        if 'COUNT(*)' in sql and 'information_schema.columns' in sql:
            return {'total':len(APP_TENANT_TABLES)-int(self.missing)}
        raise AssertionError(sql)

@pytest.mark.parametrize('changes',[{'CHEMFORGE_PG_CI':'0'},
    {'CHEMFORGE_POSTGRES_SYNTHETIC_ONLY':''},
    {'CHEMFORGE_PG_DSN':'postgresql://u:p@unsafe.example.com:5432/chemforge_synthetic?sslmode=disable'},
    {'CHEMFORGE_PG_DSN':'postgresql://chemforge_ci_app:p@127.0.0.1:5432/chemforge_synthetic?sslmode=disable'},
    {'CHEMFORGE_PG_DSN':'postgresql://chemforge_synthetic:p@127.0.0.1:5432/other?sslmode=disable'}])
def test_fails_closed_before_any_sql(changes):
    cur=Cursor()
    with pytest.raises(ValueError): prepare_disposable_app_rls({**ENV,**changes},cur)
    assert cur.commands==[]

@pytest.mark.parametrize('db,user,missing,preexisting',[
    ('elsewhere','chemforge_synthetic',False,False),
    ('chemforge_synthetic','non_owner',False,False),
    ('chemforge_synthetic','chemforge_synthetic',True,False),
    ('chemforge_synthetic','chemforge_synthetic',False,True)])
def test_checks_live_identity_schema_and_unused_resources_before_mutation(db,user,missing,preexisting):
    cur=Cursor(db,user,missing,preexisting)
    with pytest.raises(ValueError):prepare_disposable_app_rls(ENV,cur)
    assert not any(statement.startswith(('CREATE ','GRANT ','ALTER ','REVOKE ','INSERT '))
                   for statement,_ in cur.commands)

def test_installs_rls_on_every_app_tenant_table_but_no_global_oidc_or_migrations():
    cur=Cursor()
    profile=prepare_disposable_app_rls(ENV,cur)
    assert profile.public_evidence()['production_admission'] is False
    assert profile.public_evidence()['neon_access_allowed'] is False
    assert profile.public_evidence()['protected_tables']==sorted(APP_TABLES)
    assert len(profile.logins)==2
    for login in profile.logins.values():
        assert login.password not in repr(profile)
    sql='\n'.join(s for s,_ in cur.commands)
    assert 'session_user' in sql and 'current_setting(' not in sql
    assert 'SECURITY DEFINER SET search_path = pg_catalog' in sql
    for table in APP_TABLES:
        assert f'ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY' in sql
        assert f'ALTER TABLE public.{table} FORCE ROW LEVEL SECURITY' in sql
        assert f'ON public.{table} FOR ALL' in sql
    for table in ('oidc_auth_flows','chemforge_schema_versions'):
        assert f'ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY' not in sql
        assert f'GRANT SELECT, INSERT, UPDATE, DELETE ON public.{table}' not in sql
    assert 'REVOKE ALL ON public.chemforge_ci_app_bindings FROM PUBLIC' in sql
    assert 'GRANT SELECT, INSERT ON public.audit' in sql
    assert 'GRANT SELECT, INSERT, UPDATE, DELETE ON public.audit' not in sql
    assert 'rolbypassrls' not in sql.lower()
