"""Least-privilege PostgreSQL *disposable-CI* role experiment.

This is not a Neon migration, production role installer, credential manager or
public application deployment. It only runs inside acknowledged local CI.
"""
from __future__ import annotations

from urllib.parse import urlsplit

from control_plane.postgres_synthetic import validate_configuration

ROLE_NAME = 'chemforge_ci_runtime'
DATABASE_NAME = 'chemforge_synthetic'
# Deliberately fixed trusted SQL identifiers. Never interpolate user input.
RW_TABLES = (
    'tenants', 'actors', 'oidc_actor_links', 'oidc_auth_flows',
    'oidc_browser_sessions', 'teacher_cohorts', 'students', 'assignments',
    'evidence', 'devices', 'content_releases',
)


def apply_synthetic_role_gate(environment: dict, cursor) -> dict:
    """Grant a NOLOGIN group only its needed synthetic runtime privileges.

    The caller controls a *disposable* loopback PostgreSQL transaction; that
    transaction must commit atomically or roll back. This function has no
    networking or connection-management side effects of its own.
    """
    if environment.get('CHEMFORGE_PG_CI') != '1':
        raise ValueError('Disposable PostgreSQL role gate is CI-only')
    dsn = validate_configuration(environment)
    if urlsplit(dsn).path != '/' + DATABASE_NAME:
        raise ValueError('Role gate requires the dedicated disposable synthetic database')
    # Validate effective connection target; the DSN text alone is not proof.
    actual = cursor.execute('SELECT current_database() AS database_name').fetchone()
    if not actual or actual['database_name'] != DATABASE_NAME:
        raise ValueError('Postgres database identity does not match synthetic target')
    cursor.execute(f'CREATE ROLE {ROLE_NAME} NOLOGIN NOINHERIT')
    cursor.execute(f'GRANT USAGE ON SCHEMA public TO {ROLE_NAME}')
    table_list = ', '.join('public.' + table for table in RW_TABLES)
    cursor.execute(f'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE {table_list} TO {ROLE_NAME}')
    # Keep security audit rows append-only for the runtime. Only the separate
    # operator/migrator can legitimately rectify/audit them.
    cursor.execute(f'GRANT SELECT, INSERT ON TABLE public.audit TO {ROLE_NAME}')
    cursor.execute(f'GRANT SELECT ON TABLE public.chemforge_schema_versions TO {ROLE_NAME}')
    cursor.execute(f'GRANT USAGE ON SEQUENCE public.audit_id_seq TO {ROLE_NAME}')
    return {
        'status': 'SYNTHETIC_ROLE_POLICY_CONFIGURED',
        'role': ROLE_NAME,
        'role_can_login': False,
        'role_can_modify_audit': False,
        'role_can_modify_schema_versions': False,
        'neon_connection_attempted': False,
        'production_admission': False,
        'real_student_data_allowed': False,
    }
