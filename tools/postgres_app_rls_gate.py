"""CI-only RLS probe on CHEMFORGE's *actual* synthetic application tables.

NEVER connect to Neon or run this on institutional records. PostgreSQL role
credentials exist only in the disposable test runner's memory. Owner-controlled
login mappings use session_user, not a spoofable custom session setting.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import re
import secrets
from urllib.parse import urlsplit

from control_plane.postgres_synthetic import validate_configuration
from tools.postgres_login_gate import DATABASE_NAME, OWNER_NAME

APP_TENANT_TABLES = (
    'actors', 'oidc_actor_links', 'oidc_browser_sessions', 'teacher_cohorts',
    'students', 'assignments', 'evidence', 'devices', 'content_releases', 'audit',
)
APP_TABLES = ('tenants',) + APP_TENANT_TABLES
BINDINGS = {
    'chemforge_ci_data_a': 'ci-app-school-a',
    'chemforge_ci_data_b': 'ci-app-school-b',
}
PRINCIPAL_TABLE = 'chemforge_ci_app_bindings'
LOOKUP_FUNCTION = 'chemforge_ci_app_tenant'


@dataclass(frozen=True)
class AppRlsLogin:
    username: str
    tenant_id: str
    password: str = field(repr=False)


@dataclass(frozen=True)
class AppRlsProbe:
    logins: dict[str, AppRlsLogin] = field(repr=False)

    def public_evidence(self):
        return {
            'status': 'CI_APP_TABLE_RLS_PROBE_NOT_DEPLOYED',
            'protected_tables': sorted(APP_TABLES),
            'tenant_principals': sorted(self.logins),
            'login_binding': 'database-owned mapping indexed by session_user',
            'neon_access_allowed': False,
            'production_admission': False,
            'public_api_enabled': False,
            'real_student_data_allowed': False,
        }


def prepare_disposable_app_rls(environment: dict, cursor) -> AppRlsProbe:
    """Install the test-only policies in an owner-managed atomic PG transaction.

    Prerequisite: the real synthetic schema has been migrated, backup/restore
    qualification completed, and this experiment is the LAST SQL test step.
    Never insert/alter credentials in GitHub, on Neon, or in an environment file.
    """
    if environment.get('CHEMFORGE_PG_CI') != '1':
        raise ValueError('Application RLS qualification requires explicitly acknowledged CI')
    dsn = validate_configuration(environment)
    parsed = urlsplit(dsn)
    if parsed.path != '/' + DATABASE_NAME or parsed.username != OWNER_NAME:
        raise ValueError('Application RLS installer requires disposable database owner')
    identity = cursor.execute('''SELECT current_database() AS database_name,
                                      current_user AS database_user''').fetchone()
    if not identity or (identity['database_name'], identity['database_user']) != (DATABASE_NAME, OWNER_NAME):
        raise ValueError('Live PostgreSQL identity does not match disposable synthetic owner')

    # Before any DDL, check all expected real app tenant columns exist, so a
    # schema drift cannot leave a tenant-scoped table outside this experiment.
    count = cursor.execute('''SELECT COUNT(*) AS total
        FROM information_schema.columns WHERE table_schema='public'
          AND column_name='tenant_id' AND table_name = ANY(%s)''',
        (list(APP_TENANT_TABLES),)).fetchone()
    if not count or count['total'] != len(APP_TENANT_TABLES):
        raise ValueError('Application schema mismatch: tenant_id columns not exactly available')
    if cursor.execute(f"SELECT to_regclass('public.{PRINCIPAL_TABLE}') AS found").fetchone()['found'] is not None:
        raise ValueError('CI-only principal mapping table already exists')
    for role in BINDINGS:
        if cursor.execute('SELECT rolname AS found FROM pg_roles WHERE rolname=%s', (role,)).fetchone():
            raise ValueError('Disposable CI-only login already exists')

    cursor.execute(f'''CREATE TABLE public.{PRINCIPAL_TABLE} (
        login_name NAME PRIMARY KEY, tenant_id TEXT NOT NULL UNIQUE
    )''')
    cursor.execute(f'REVOKE ALL ON public.{PRINCIPAL_TABLE} FROM PUBLIC')
    cursor.execute(f'''CREATE FUNCTION public.{LOOKUP_FUNCTION}() RETURNS TEXT
        LANGUAGE SQL STABLE SECURITY DEFINER SET search_path = pg_catalog
        AS $$ SELECT tenant_id FROM public.{PRINCIPAL_TABLE}
               WHERE login_name = session_user $$''')
    cursor.execute(f'REVOKE ALL ON FUNCTION public.{LOOKUP_FUNCTION}() FROM PUBLIC')

    for table in APP_TABLES:
        column = 'id' if table == 'tenants' else 'tenant_id'
        cursor.execute(f'ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY')
        cursor.execute(f'ALTER TABLE public.{table} FORCE ROW LEVEL SECURITY')
        cursor.execute(f'''CREATE POLICY chemforge_ci_app_isolate
            ON public.{table} FOR ALL TO PUBLIC
            USING ({column} = public.{LOOKUP_FUNCTION}())
            WITH CHECK ({column} = public.{LOOKUP_FUNCTION}())''')

    logins = {}
    rw_tables = ', '.join('public.' + table for table in APP_TABLES if table != 'audit')
    for username, tenant in BINDINGS.items():
        password = secrets.token_urlsafe(40)
        if not re.fullmatch(r'[A-Za-z0-9_-]{40,}', password):
            raise ValueError('Non-url-safe generated disposable password')
        # Identifiers are fixed compiled-in strings; secret is regex-checked to
        # exclude SQL punctuation (Postgres CREATE ROLE cannot bind PASSWORD).
        cursor.execute(f"CREATE ROLE {username} LOGIN INHERIT PASSWORD '{password}'")
        cursor.execute(f'GRANT USAGE ON SCHEMA public TO {username}')
        cursor.execute(f'GRANT EXECUTE ON FUNCTION public.{LOOKUP_FUNCTION}() TO {username}')
        cursor.execute(f'GRANT SELECT, INSERT, UPDATE, DELETE ON {rw_tables} TO {username}')
        cursor.execute(f'GRANT SELECT, INSERT ON public.audit TO {username}')
        cursor.execute(f'GRANT USAGE ON SEQUENCE public.audit_id_seq TO {username}')
        cursor.execute(f'INSERT INTO public.{PRINCIPAL_TABLE}(login_name,tenant_id) VALUES (%s,%s)',
                       (username,tenant))
        logins[username] = AppRlsLogin(username,tenant,password)
    return AppRlsProbe(logins)
