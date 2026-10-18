"""Isolated PostgreSQL tenant RLS experiment for disposable local CI only.

The probe has no school/student application data and never modifies application
schema. In particular this is NOT a Neon migration or a production permission
installer. Its two LOGIN credentials live only in test memory.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import re
import secrets
from urllib.parse import urlsplit

from control_plane.postgres_synthetic import validate_configuration
from tools.postgres_login_gate import DATABASE_NAME, OWNER_NAME

# All identifiers and tenant names are fixed synthetic data; no caller input
# may be interpolated into DDL. Tenant bindings are owner-managed (not GUCs).
BINDINGS = {
    'chemforge_ci_rls_a': 'ci-rls-school-a',
    'chemforge_ci_rls_b': 'ci-rls-school-b',
}


@dataclass(frozen=True)
class RlsTestLogin:
    username: str
    tenant_id: str
    password: str = field(repr=False)


@dataclass(frozen=True)
class RlsProbe:
    logins: dict[str, RlsTestLogin] = field(repr=False)
    status: str = 'DISPOSABLE_RLS_PROBE_CREATED_NOT_DEPLOYED'

    def public_evidence(self):
        return {
            'status': self.status,
            'tenant_roles': sorted(self.logins),
            'binding': 'PostgreSQL session_user, not user-controlled app settings',
            'remote_access_allowed': False,
            'real_student_data_allowed': False,
            'public_api_enabled': False,
            'production_admission': False,
        }


def prepare_disposable_rls_probe(environment: dict, cursor) -> RlsProbe:
    """Create isolated probe tables + two real logins in caller's transaction.

    The only supported target is 127.0.0.1:5432/chemforge_synthetic under the
    designated owner and affirmative CI flag. The caller must commit before
    opening independent, restricted PostgreSQL LOGIN connections.
    """
    if environment.get('CHEMFORGE_PG_CI') != '1':
        raise ValueError('RLS probe is only permitted inside acknowledged disposable CI')
    dsn = validate_configuration(environment)
    parsed = urlsplit(dsn)
    if parsed.path != '/' + DATABASE_NAME or parsed.username != OWNER_NAME:
        raise ValueError('RLS probe must use the fixed disposable owner database')
    actual = cursor.execute('SELECT current_database() AS database_name, '
                            'current_user AS database_user').fetchone()
    if not actual or (actual['database_name'], actual['database_user']) != (DATABASE_NAME, OWNER_NAME):
        raise ValueError('RLS probe refused: wrong actual PostgreSQL connection identity')
    if cursor.execute("SELECT to_regclass('public.chemforge_ci_rls_probe') AS found").fetchone()['found'] is not None:
        raise ValueError('RLS probe requires unused disposable table name')
    if cursor.execute("SELECT rolname AS found FROM pg_roles WHERE rolname IN "
                      "('chemforge_ci_rls_a','chemforge_ci_rls_b') LIMIT 1").fetchone():
        raise ValueError('RLS probe requires unused disposable role names')

    cursor.execute('''CREATE TABLE public.chemforge_ci_rls_principals (
        login_name NAME PRIMARY KEY, tenant_id TEXT NOT NULL UNIQUE
    )''')
    cursor.execute('REVOKE ALL ON public.chemforge_ci_rls_principals FROM PUBLIC')
    cursor.execute('''CREATE TABLE public.chemforge_ci_rls_probe (
        tenant_id TEXT NOT NULL, record_id TEXT NOT NULL,
        payload TEXT NOT NULL, PRIMARY KEY (tenant_id, record_id)
    )''')
    cursor.execute('''CREATE FUNCTION public.chemforge_ci_rls_tenant() RETURNS TEXT
        LANGUAGE SQL STABLE SECURITY DEFINER SET search_path = pg_catalog
        AS $$ SELECT tenant_id FROM public.chemforge_ci_rls_principals
               WHERE login_name = session_user $$''')
    cursor.execute('ALTER TABLE public.chemforge_ci_rls_probe ENABLE ROW LEVEL SECURITY')
    cursor.execute('ALTER TABLE public.chemforge_ci_rls_probe FORCE ROW LEVEL SECURITY')
    cursor.execute('''CREATE POLICY chemforge_ci_rls_isolate
        ON public.chemforge_ci_rls_probe FOR ALL TO PUBLIC
        USING (tenant_id = public.chemforge_ci_rls_tenant())
        WITH CHECK (tenant_id = public.chemforge_ci_rls_tenant())''')

    logins = {}
    for username, tenant_id in BINDINGS.items():
        password = secrets.token_urlsafe(40)
        if not re.fullmatch(r'[A-Za-z0-9_-]{40,}', password):
            raise ValueError('Non-URL-safe generated disposable credential')
        # The secret cannot contain SQL quotes; both usernames are fixed code
        # constants, never populated from environment variables or files.
        cursor.execute(f"CREATE ROLE {username} LOGIN INHERIT PASSWORD '{password}'")
        cursor.execute(f'GRANT USAGE ON SCHEMA public TO {username}')
        cursor.execute('GRANT SELECT, INSERT, UPDATE, DELETE '
                       f'ON public.chemforge_ci_rls_probe TO {username}')
        cursor.execute('INSERT INTO public.chemforge_ci_rls_principals (login_name,tenant_id) '
                       'VALUES (%s,%s)', (username, tenant_id))
        logins[username] = RlsTestLogin(username, tenant_id, password)
    return RlsProbe(logins)
