"""CI-only: authenticated RLS on the 11 ACTUAL synthetic CHEMFORGE tables.

Run LAST after Postgres backup/restore; never uses live Neon. No real students.
"""
from __future__ import annotations

import os
from urllib.parse import quote
from uuid import uuid4

import pytest

if os.getenv('CHEMFORGE_PG_CI') != '1':
    pytest.skip('Actual application-table RLS only runs in disposable PostgreSQL CI',
                allow_module_level=True)

import psycopg
from psycopg.rows import dict_row

from control_plane.postgres_synthetic import validate_configuration
from tools.postgres_app_rls_gate import APP_TABLES, BINDINGS, prepare_disposable_app_rls

TS='2026-10-18T00:00:00+00:00'


def _dsn(login):
    return (f'postgresql://{login.username}:{quote(login.password,safe="")}'
            '@127.0.0.1:5432/chemforge_synthetic?sslmode=disable')


def _seed(cx, tenant, suffix):
    """Populate each production-shaped tenant table with wholly synthetic data."""
    actor='staff-'+suffix
    student='student-'+suffix
    cx.execute('INSERT INTO tenants(id,created_at) VALUES(%s,%s)',(tenant,TS))
    cx.execute('''INSERT INTO actors(id,tenant_id,label,role,token_hash,created_at)
        VALUES(%s,%s,%s,%s,%s,%s)''',(actor,tenant,'Synthetic staff','admin','tok-'+suffix,TS))
    cx.execute('''INSERT INTO oidc_actor_links(issuer,subject,actor_id,tenant_id,linked_at)
        VALUES(%s,%s,%s,%s,%s)''',('https://login.invalid',suffix,actor,tenant,TS))
    cx.execute('''INSERT INTO oidc_browser_sessions(session_hash,actor_id,tenant_id,
        issuer,subject,csrf_token,expires_at,created_at)
        VALUES(%s,%s,%s,%s,%s,%s,%s,%s)''',
        ('session-'+suffix,actor,tenant,'https://login.invalid',suffix,'csrf-'+suffix,TS,TS))
    cx.execute('INSERT INTO teacher_cohorts(tenant_id,actor_id,cohort,granted_at) VALUES(%s,%s,%s,%s)',
               (tenant,actor,'U6',TS))
    cx.execute('INSERT INTO students(id,tenant_id,pseudonym,cohort,created_at) VALUES(%s,%s,%s,%s,%s)',
               (student,tenant,'Synthetic '+suffix,'U6',TS))
    cx.execute('''INSERT INTO assignments(id,tenant_id,title,cohort,objectives_json,actor_id,created_at)
        VALUES(%s,%s,%s,%s,%s,%s,%s)''',('hw-'+suffix,tenant,'Synthetic Chemistry','U6','[]',actor,TS))
    cx.execute('''INSERT INTO evidence(tenant_id,event_id,student_id,question_id,payload_sha256,
        payload_json,verification_status,received_at) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)''',
        (tenant,'event-'+suffix,student,'Q-SYNTH','sha-'+suffix,'{}','unverified_import',TS))
    cx.execute('''INSERT INTO devices(id,tenant_id,student_id,label,token_hash,issued_at,expires_at)
        VALUES(%s,%s,%s,%s,%s,%s,%s)''',
        ('device-'+suffix,tenant,student,'Synthetic','device-token-'+suffix,TS,TS))
    cx.execute('''INSERT INTO content_releases(tenant_id,pack_version,content_version,
        pack_sha256,content_fingerprint,actor_id,created_at)
        VALUES(%s,%s,%s,%s,%s,%s,%s)''',(tenant,1,'synthetic','sha-'+suffix,'fp-'+suffix,actor,TS))
    cx.execute('INSERT INTO audit(tenant_id,actor_id,action,subject_id,occurred_at) VALUES(%s,%s,%s,%s,%s)',
               (tenant,actor,'ci.synthetic_seed',student,TS))
    return {'actor':actor,'student':student}


def test_application_schema_all_tenant_tables_enforce_database_principal():
    owner_dsn=validate_configuration(os.environ)
    with psycopg.connect(owner_dsn,row_factory=dict_row) as owner:
        profile=prepare_disposable_app_rls(os.environ,owner)
        seeded={}
        for username,login in profile.logins.items():
            seeded[username]=_seed(owner, login.tenant_id,username)
    assert profile.public_evidence()['production_admission'] is False
    assert len(APP_TABLES)==11
    a=profile.logins['chemforge_ci_data_a']
    b=profile.logins['chemforge_ci_data_b']

    # All 11 of the actual schema tables have one visible tenant row, not only
    # the special v3.1 RLS-probe table. No app controlled tenant GUC is trusted.
    for caller,foreign in ((a,b),(b,a)):
        with psycopg.connect(_dsn(caller),row_factory=dict_row) as cx:
            assert cx.execute('SELECT session_user AS name, current_user AS role').fetchone() == {
                'name':caller.username,'role':caller.username}
            for table in APP_TABLES:
                shown=cx.execute(f'SELECT * FROM public.{table}').fetchall()
                assert len(shown)==1,(caller.username,table,shown)
                key='id' if table=='tenants' else 'tenant_id'
                assert shown[0][key]==caller.tenant_id,(table,shown)
                assert cx.execute(f'SELECT COUNT(*) AS n FROM public.{table} WHERE {key}=%s',
                    (foreign.tenant_id,)).fetchone()['n']==0
            cx.execute('SELECT set_config(%s,%s,true)',('app.tenant_id',foreign.tenant_id))
            assert cx.execute('SELECT COUNT(*) AS n FROM public.students WHERE tenant_id=%s',
                (foreign.tenant_id,)).fetchone()['n']==0
            assert cx.execute('UPDATE public.students SET pseudonym=%s WHERE id=%s',
                ('intruded',seeded[foreign.username]['student'])).rowcount==0
            assert cx.execute('DELETE FROM public.students WHERE tenant_id=%s',
                (foreign.tenant_id,)).rowcount==0
            # Positive own-tenant inserts are possible with real LOGIN authority.
            sid='own-'+uuid4().hex
            cx.execute('INSERT INTO public.students(id,tenant_id,pseudonym,cohort,created_at) VALUES(%s,%s,%s,%s,%s)',
                (sid,caller.tenant_id,'Synthetic additional','U6',TS))
            assert cx.execute('DELETE FROM public.students WHERE id=%s',(sid,)).rowcount==1
            cx.execute('INSERT INTO public.audit(tenant_id,actor_id,action,subject_id,occurred_at) VALUES(%s,%s,%s,%s,%s)',
                (caller.tenant_id,seeded[caller.username]['actor'],'ci.synthetic_append','x',TS))
        # An attempted cross-tenant INSERT must abort its own transaction.
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with psycopg.connect(_dsn(caller),row_factory=dict_row) as cx:
                cx.execute('INSERT INTO public.students(id,tenant_id,pseudonym,cohort,created_at) VALUES(%s,%s,%s,%s,%s)',
                    ('forged-'+uuid4().hex,foreign.tenant_id,'Forged','U6',TS))
        for command in (
            'SELECT * FROM public.chemforge_ci_app_bindings',
            'SELECT * FROM public.oidc_auth_flows',
            'UPDATE public.audit SET action=\'forbidden\' WHERE FALSE',
            'DELETE FROM public.audit WHERE FALSE',
            'UPDATE public.chemforge_schema_versions SET sha256=\'forbidden\' WHERE FALSE',
            'CREATE TABLE public.chemforge_ci_illicit(id TEXT)',
            f'SET ROLE {foreign.username}',
            f"SET SESSION AUTHORIZATION '{foreign.username}'",
        ):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                with psycopg.connect(_dsn(caller),row_factory=dict_row) as cx:
                    cx.execute(command)

    # Independently confirm no forbidden mutation, using the CI-only superuser
    # (which BY DESIGN bypasses RLS) solely for this synthetic verification.
    with psycopg.connect(owner_dsn,row_factory=dict_row) as owner:
        for login in (a,b):
            for table in APP_TABLES:
                key='id' if table=='tenants' else 'tenant_id'
                rows=owner.execute(f'SELECT COUNT(*) AS n FROM public.{table} WHERE {key}=%s',
                    (login.tenant_id,)).fetchone()
                assert rows['n']==(2 if table=='audit' else 1),(login.username,table,rows)
            assert owner.execute('SELECT pseudonym FROM public.students WHERE tenant_id=%s',
                (login.tenant_id,)).fetchone()['pseudonym'].startswith('Synthetic')
