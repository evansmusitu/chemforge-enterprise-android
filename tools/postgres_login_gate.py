"""Synthetic, loopback-only LOGIN credential for disposable CI qualification.

No remote connections, Neon writes, production privilege grants or secrets
storage. The caller MUST own the disposable PostgreSQL transaction and commit it.
The credential exists only in ephemeral test-run memory, never in the repo.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import re
import secrets
from urllib.parse import urlsplit

from control_plane.postgres_synthetic import validate_configuration
from tools.postgres_role_gate import ROLE_NAME, DATABASE_NAME

LOGIN_NAME = 'chemforge_ci_app'
OWNER_NAME = 'chemforge_synthetic'


@dataclass(frozen=True)
class SyntheticLogin:
    username: str
    password: str = field(repr=False)

    def __repr__(self) -> str:
        return f'SyntheticLogin(username={self.username!r}, password=<redacted>)'

    __str__ = __repr__

    def public_evidence(self) -> dict:
        return {
            'status': 'SYNTHETIC_DISPOSABLE_LOGIN_QUALIFIED_NOT_DEPLOYED',
            'username': self.username,
            'password_exposed': False,
            'remote_access_allowed': False,
            'production_admission': False,
            'real_student_data_allowed': False,
        }


def provision_disposable_login(environment: dict, cursor) -> SyntheticLogin:
    """Provision one test-run LOGIN, inheriting the already-reviewed NOLOGIN group.

    Requires current_database/current_user identity checks and existing NOLOGIN
    runtime group. Uses only fixed known SQL identifiers; a 320-bit token_urlsafe
    secret is strictly checked before embedding as an SQL string literal.
    No DDL outside the disposable user's PostgreSQL transaction is attempted.
    """
    if environment.get('CHEMFORGE_PG_CI') != '1':
        raise ValueError('Disposable login requires acknowledged synthetic CI mode')
    dsn = validate_configuration(environment)
    parsed = urlsplit(dsn)
    if parsed.path != '/' + DATABASE_NAME or parsed.username != OWNER_NAME:
        raise ValueError('Disposable login requires the designated local synthetic owner')
    identity = cursor.execute('''SELECT current_database() AS database_name,
                                      current_user AS database_user''').fetchone()
    if (not identity or identity['database_name'] != DATABASE_NAME
            or identity['database_user'] != OWNER_NAME):
        raise ValueError('Live PostgreSQL connection must match synthetic owner and database')
    group = cursor.execute("SELECT rolcanlogin AS can_login FROM pg_roles "
                           "WHERE rolname = 'chemforge_ci_runtime'").fetchone()
    if not group or group['can_login'] is not False:
        raise ValueError('Reviewed NOLOGIN runtime group must already exist')

    password = secrets.token_urlsafe(40)
    if not re.fullmatch(r'[A-Za-z0-9_-]{40,}', password):
        raise ValueError('Unexpected CI-only credential encoding')
    # PostgreSQL CREATE ROLE does not accept bind placeholders for PASSWORD.
    # The secret contains no SQL metacharacters (fixed regexp above); identifiers
    # are compiled-in constants and never parsed from supplied configuration.
    cursor.execute(f"CREATE ROLE {LOGIN_NAME} WITH LOGIN INHERIT PASSWORD '{password}'")
    cursor.execute(f'GRANT {ROLE_NAME} TO {LOGIN_NAME} WITH INHERIT TRUE, SET FALSE')
    return SyntheticLogin(username=LOGIN_NAME, password=password)
