"""Non-deploying native PostgreSQL backup/restore *verification* for synthetic CI.

Run `--phase preflight` before the CI-only pg_dump/pg_restore commands, then
`--phase verify` after pg_restore completes into a **separate empty** database.
This does not make backups, upload data, or create/replace any database.
Never use on real students or a remote PostgreSQL provider.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
import re
from urllib.parse import urlsplit

from control_plane.postgres_synthetic import (
    ACKNOWLEDGEMENT, SCHEMA_FILE, VERSION, validate_configuration,
)

# Explicitly admit only the tables of the reviewed disposable migration.
# Reject additional/unaccounted tables rather than accidentally exporting a
# separate institution's state.
TABLES = frozenset({
    'tenants', 'actors', 'oidc_actor_links', 'oidc_auth_flows',
    'oidc_browser_sessions', 'teacher_cohorts', 'students', 'assignments',
    'evidence', 'devices', 'content_releases', 'audit',
    'chemforge_schema_versions',
})


def table_inventory() -> frozenset[str]:
    """Check source-schema inventory without connecting to a database."""
    declared = frozenset(re.findall(r'^CREATE TABLE ([a-z][a-z0-9_]*)\s*\(',
                                  SCHEMA_FILE.read_text(encoding='utf-8'), re.M))
    if declared | {'chemforge_schema_versions'} != TABLES:
        raise ValueError('Synthetic schema inventory differs from reviewed tables')
    return TABLES


def validate_restore_config(environment: dict) -> tuple[str, str]:
    """Fail closed *before* any database/backup subprocess, never log secrets."""
    if environment.get('CHEMFORGE_PG_CI') != '1':
        raise ValueError('Restore drill requires isolated synthetic CI container')
    source = validate_configuration(environment)
    target = environment.get('CHEMFORGE_PG_RESTORE_DSN', '')
    validate_configuration({**environment, 'CHEMFORGE_PG_DSN': target})
    src, dst = urlsplit(source), urlsplit(target)
    if src.path != '/chemforge_synthetic' or dst.path != '/chemforge_synthetic_restore':
        raise ValueError('Restore drill requires exact dedicated disposable database names')
    if src.username != dst.username or src.password != dst.password:
        raise ValueError('Restore drill requires same synthetic CI role and password pair')
    table_inventory()
    return source, target


def _connect(dsn: str):
    from control_plane.postgres_synthetic import _driver
    psycopg, dict_row = _driver()
    try:
        return psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5)
    except psycopg.Error:
        raise ValueError('Disposable synthetic database not accessible') from None


def _tables(cx) -> set[str]:
    return {record['tablename'] for record in cx.execute(
        "SELECT tablename FROM pg_tables WHERE schemaname='public'"
    ).fetchall()}


def _schema_verified(cx) -> None:
    if _tables(cx) != TABLES:
        raise ValueError('Synthetic database has unexpected or missing public tables')
    row = cx.execute('SELECT sha256 FROM chemforge_schema_versions WHERE version=%s',
                     (VERSION,)).fetchone()
    if not row or row['sha256'] != sha256(SCHEMA_FILE.read_bytes()).hexdigest():
        raise ValueError('Synthetic migration checksum does not match source')


def _fingerprint(cx) -> tuple[dict, int]:
    """Read-only, bounded per-table data + constraint/index fingerprints.

    Returns digests only, never credentials or raw synthetic student records.
    """
    from psycopg import sql
    cx.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
    _schema_verified(cx)
    manifest: dict[str, str] = {}
    rows_total = 0
    for table in sorted(TABLES):
        statement = sql.SQL('SELECT to_jsonb(t)::text AS payload FROM {} AS t').format(
            sql.Identifier('public', table))
        # A digest of the sorted row digests handles rows without primary keys
        # and preserves duplicate multiplicities without imposing a SQL sort.
        digests = []
        for record in cx.execute(statement):
            data = record['payload'].encode('utf-8')
            if len(data) > 1_000_000 or len(digests) >= 10_000:
                raise ValueError('Synthetic snapshot safety limit exceeded')
            digests.append(sha256(data).hexdigest())
        rows_total += len(digests)
        manifest[table] = sha256(('\n'.join(sorted(digests))).encode()).hexdigest()
    # pg_dump must retain constraints and indexes, not just student row counts.
    constraints = cx.execute('''SELECT c.conname, pg_get_constraintdef(c.oid) AS definition,
                                      t.relname AS rel
                               FROM pg_constraint c JOIN pg_class t ON t.oid=c.conrelid
                               JOIN pg_namespace n ON t.relnamespace=n.oid
                               WHERE n.nspname='public' ORDER BY t.relname,c.conname''').fetchall()
    indexes = cx.execute('''SELECT tablename,indexname,indexdef FROM pg_indexes
                             WHERE schemaname='public' ORDER BY tablename,indexname''').fetchall()
    for name, rows in (('constraints',constraints),('indexes',indexes)):
        manifest[name] = sha256(json.dumps(rows,sort_keys=True,default=str).encode()).hexdigest()
    return manifest, rows_total


def check_preflight(environment: dict) -> dict:
    source, target = validate_restore_config(environment)
    with _connect(source) as cx:
        _schema_verified(cx)
    with _connect(target) as cx:
        if _tables(cx):
            raise ValueError('Restore destination must be an empty disposable database')
    return {'status':'SYNTHETIC_EMPTY_RESTORE_TARGET_CONFIRMED',
            'real_student_data':'FORBIDDEN','production_readiness':'NOT_ASSESSED'}


def check_restored(environment: dict) -> dict:
    source, target = validate_restore_config(environment)
    with _connect(source) as cx:
        original, src_rows = _fingerprint(cx)
    with _connect(target) as cx:
        restored, dest_rows = _fingerprint(cx)
    if original != restored or src_rows != dest_rows:
        raise ValueError('Restored synthetic data, constraints or indexes differ from source')
    return {'status':'SYNTHETIC_NATIVE_RESTORE_VERIFIED','tables':len(TABLES),
            'rows':src_rows, 'metadata_fingerprints_match':True,
            'real_student_data':'FORBIDDEN','production_readiness':'NOT_ASSESSED'}


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase',choices=['preflight','verify'],required=True)
    args=parser.parse_args()
    try:
        result = (check_preflight if args.phase=='preflight' else check_restored)(os.environ)
    except (ValueError, RuntimeError) as exc:
        # Sanitize unexpected backend errors: no DSN or credentials may leak.
        print('SYNTHETIC_RESTORE_DRILL_BLOCKED: '+str(exc),file=__import__('sys').stderr)
        raise SystemExit(2) from None
    print(json.dumps(result,sort_keys=True))


if __name__=='__main__':
    main()
