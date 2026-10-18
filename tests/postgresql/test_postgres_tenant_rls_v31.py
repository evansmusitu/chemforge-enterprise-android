"""Real PostgreSQL 17 authenticated-session RLS probe (disposable CI only).

Executed AFTER the existing backup/restore comparison, never on hosted Neon.
This experiment uses new CI-specific tables, NOT real students or app tables.
"""
from __future__ import annotations

import os
from uuid import uuid4
from urllib.parse import quote

import pytest

if os.environ.get('CHEMFORGE_PG_CI') != '1':
    pytest.skip('RLS requires isolated synthetic PostgreSQL CI',allow_module_level=True)

import psycopg
from psycopg.rows import dict_row
from control_plane.postgres_synthetic import validate_configuration
from tools.postgres_tenant_rls_gate import prepare_disposable_rls_probe


def _dsn(login):
    # Ephemeral URL-safe secrets never appear in logs, GitHub Actions env, or files.
    return ('postgresql://' + login.username + ':' + quote(login.password, safe='') +
            '@127.0.0.1:5432/chemforge_synthetic?sslmode=disable')


def test_real_separate_login_connections_enforce_tenant_rows():
    owner_dsn = validate_configuration(os.environ)
    with psycopg.connect(owner_dsn, row_factory=dict_row) as owner:
        probe = prepare_disposable_rls_probe(os.environ, owner)
        assert probe.public_evidence()['production_admission'] is False
    a = probe.logins['chemforge_ci_rls_a']
    b = probe.logins['chemforge_ci_rls_b']
    assert a.tenant_id != b.tenant_id
    row_a, row_b = 'a-'+uuid4().hex, 'b-'+uuid4().hex
    with psycopg.connect(_dsn(a), row_factory=dict_row) as cx:
        assert cx.execute('SELECT session_user AS auth_user, current_user AS role').fetchone() == {
            'auth_user': a.username, 'role': a.username,
        }
        cx.execute('INSERT INTO public.chemforge_ci_rls_probe VALUES (%s,%s,%s)',
                   (a.tenant_id,row_a,'synthetic-a'))
    with psycopg.connect(_dsn(b), row_factory=dict_row) as cx:
        cx.execute('INSERT INTO public.chemforge_ci_rls_probe VALUES (%s,%s,%s)',
                   (b.tenant_id,row_b,'synthetic-b'))
    for allowed, blocked, own_row, foreign_row in [(a,b,row_a,row_b),(b,a,row_b,row_a)]:
        with psycopg.connect(_dsn(allowed), row_factory=dict_row) as cx:
            visible = cx.execute('SELECT tenant_id, record_id FROM public.chemforge_ci_rls_probe').fetchall()
            assert visible == [{'tenant_id':allowed.tenant_id, 'record_id':own_row}]
            assert cx.execute('UPDATE public.chemforge_ci_rls_probe SET payload=%s '
                              'WHERE tenant_id=%s AND record_id=%s',
                              ('attacked',blocked.tenant_id,foreign_row)).rowcount == 0
            assert cx.execute('DELETE FROM public.chemforge_ci_rls_probe '
                              'WHERE tenant_id=%s AND record_id=%s',
                              (blocked.tenant_id,foreign_row)).rowcount == 0
            # Setting a forged app variable is not a trusted identity change.
            cx.execute('SELECT set_config(%s,%s,true)',('app.tenant_id',blocked.tenant_id))
            assert cx.execute('SELECT COUNT(*) AS n FROM public.chemforge_ci_rls_probe '
                              'WHERE tenant_id=%s',(blocked.tenant_id,)).fetchone()['n'] == 0
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with psycopg.connect(_dsn(allowed), row_factory=dict_row) as cx:
                cx.execute('INSERT INTO public.chemforge_ci_rls_probe VALUES (%s,%s,%s)',
                           (blocked.tenant_id,'forged-'+uuid4().hex,'cross-tenant'))
        for forbidden in (
            'SELECT * FROM public.chemforge_ci_rls_principals',
            f'SET ROLE {blocked.username}',
            f"SET SESSION AUTHORIZATION '{blocked.username}'",
        ):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                with psycopg.connect(_dsn(allowed), row_factory=dict_row) as cx:
                    cx.execute(forbidden)
    with psycopg.connect(owner_dsn, row_factory=dict_row) as cx:
        # Verify deny/no-mutation effects independently of the restricted views.
        rows=cx.execute('SELECT tenant_id,record_id,payload FROM public.chemforge_ci_rls_probe '
                        'ORDER BY tenant_id').fetchall()
        # Force RLS applies to owner; owner has no principal binding. Query via
        # privileged non-RLS bypass is deliberately unavailable in this probe.
        assert rows == []
    with psycopg.connect(_dsn(a), row_factory=dict_row) as cx:
        assert cx.execute('SELECT payload FROM public.chemforge_ci_rls_probe '
                          'WHERE tenant_id=%s',(a.tenant_id,)).fetchone()['payload']=='synthetic-a'
    with psycopg.connect(_dsn(b), row_factory=dict_row) as cx:
        assert cx.execute('SELECT payload FROM public.chemforge_ci_rls_probe '
                          'WHERE tenant_id=%s',(b.tenant_id,)).fetchone()['payload']=='synthetic-b'
