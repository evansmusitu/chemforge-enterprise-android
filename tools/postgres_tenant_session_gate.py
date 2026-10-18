"""Bound, disposable CI-only connection routing for verified school identities.

Not a hosted Neon client and NOT installed in FastAPI. The caller must obtain
verified_tenant_id from validated server-side credentials, NEVER from a request
body/header/query field. Routes one immutable tenant to one LOGIN credential.
No connection reuse, SET ROLE, GUC selection, or role impersonation is allowed.
"""
from __future__ import annotations

from contextlib import contextmanager
import re
from types import MappingProxyType
from urllib.parse import quote, urlsplit

from control_plane.postgres_synthetic import validate_configuration
from tools.postgres_app_rls_gate import AppRlsLogin, BINDINGS
from tools.postgres_login_gate import DATABASE_NAME, OWNER_NAME

_PASSWORD_PATTERN = re.compile(r'[A-Za-z0-9_-]{40,}\Z', flags=re.ASCII)


class TenantSessionRouter:
    """One school -> one PostgreSQL LOGIN, with live DB identity attestation.

    Synthetic only. A real deployment must introduce identity-provider-backed
    authorization, production-approved connection handling and reviewed migrations.
    """

    def __init__(self, environment: dict, logins: dict[str, AppRlsLogin], *, connect=None):
        if environment.get('CHEMFORGE_PG_CI') != '1':
            raise ValueError('CI acknowledgement required')
        dsn = validate_configuration(environment)
        parsed = urlsplit(dsn)
        if parsed.path != '/' + DATABASE_NAME or parsed.username != OWNER_NAME:
            raise ValueError('Synthetic owner/database mismatch')
        if set(logins) != set(BINDINGS):
            raise ValueError('Unrecognized or missing synthetic login')
        for name, tenant in BINDINGS.items():
            login = logins[name]
            if (type(login) is not AppRlsLogin or login.username != name or
                    login.tenant_id != tenant or not isinstance(login.password, str) or
                    _PASSWORD_PATTERN.fullmatch(login.password) is None):
                raise ValueError('Unrecognized or invalid synthetic login')
        self._logins_by_tenant = MappingProxyType({login.tenant_id: login for login in logins.values()})
        if connect is None:
            from psycopg import connect as pg_connect
            from psycopg.rows import dict_row

            def connect(dsn, **kwargs):
                return pg_connect(dsn, row_factory=dict_row, **kwargs)
        self._connect = connect

    def __repr__(self):
        return '<TenantSessionRouter synthetic_only=True credentials=<redacted>>'

    def public_evidence(self):
        return {'status': 'CI_TENANT_BOUND_CONNECTIONS_NOT_DEPLOYED',
                'tenant_principals': sorted(self._logins_by_tenant),
                'production_admission': False, 'neon_access_allowed': False,
                'public_api_enabled': False, 'real_student_data_allowed': False}

    @contextmanager
    def open_for_authenticated_tenant(self, verified_tenant_id: str):
        """Open a fresh, unshared PostgreSQL transaction for an AUTHENTICATED tenant.

        Never call with an arbitrary request-supplied tenant_id. This gate has
        no HTTP identity verification and cannot attest who called it.
        """
        if not isinstance(verified_tenant_id, str):
            raise ValueError('unrecognized verified tenant')
        login = self._logins_by_tenant.get(verified_tenant_id)
        if login is None:
            raise ValueError('unrecognized verified tenant')
        # Role is compiled-in; password is URL encoded and never printed/logged.
        dsn = (f'postgresql://{login.username}:{quote(login.password, safe="")}'
               '@127.0.0.1:5432/chemforge_synthetic?sslmode=disable')
        with self._connect(dsn, connect_timeout=5) as cx:
            row = cx.execute('''SELECT current_database() AS database_name,
                        session_user AS session_user, current_user AS current_user,
                        public.chemforge_ci_app_tenant() AS tenant_id''').fetchone()
            if (not isinstance(row, dict) or row.get('database_name') != DATABASE_NAME or
                    row.get('session_user') != login.username or
                    row.get('current_user') != login.username or
                    row.get('tenant_id') != verified_tenant_id):
                raise ValueError('Database tenant identity mismatch')
            yield cx
