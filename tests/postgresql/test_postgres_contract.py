"""Early fail-closed PostgreSQL qualification contracts, no external provider used."""
from pathlib import Path
import os
import pytest
from control_plane.app import create_app


def test_pg_backend_not_enabled_without_synthetic_ack(monkeypatch, tmp_path):
    monkeypatch.setenv('CHEMFORGE_STORAGE_BACKEND', 'postgres_synthetic')
    monkeypatch.setenv('CHEMFORGE_PG_DSN', 'postgresql://synthetic:synthetic@127.0.0.1:5432/synthetic?sslmode=disable')
    monkeypatch.delenv('CHEMFORGE_POSTGRES_SYNTHETIC_ONLY', raising=False)
    with pytest.raises(ValueError, match='synthetic-only'):
        create_app(str(tmp_path / 'should-not-be-created.sqlite'))
    assert not (tmp_path / 'should-not-be-created.sqlite').exists()


def test_unknown_storage_backend_fails_closed(monkeypatch,tmp_path):
    monkeypatch.setenv('CHEMFORGE_STORAGE_BACKEND', 'production')
    with pytest.raises(ValueError, match='storage backend'):
        create_app(str(tmp_path / 'should-not-be-created.sqlite'))


def test_schema_has_tenant_qualified_foreign_keys_and_no_permissive_marks():
    sql=Path('control_plane/postgres/001_synthetic_schema.sql').read_text()
    assert 'FOREIGN KEY (tenant_id, actor_id) REFERENCES actors(tenant_id, id)' in sql
    assert 'FOREIGN KEY (tenant_id, student_id) REFERENCES students(tenant_id, id)' in sql
    assert "CHECK (verification_status = 'unverified_import')" in sql
    assert 'oidc_browser_sessions' in sql
    assert 'CREATE TABLE IF NOT EXISTS' not in sql  # migrations must be versioned, no silent drift


def test_postgres_schema_columns_match_all_existing_sqlite_pilot_entities():
    """Detect silent field omission while staging a PostgreSQL schema migration."""
    import re
    import sqlite3
    from control_plane.db import SCHEMA
    sql=Path('control_plane/postgres/001_synthetic_schema.sql').read_text()
    with sqlite3.connect(':memory:') as cx:
        cx.executescript(SCHEMA)
        tables={row[0] for row in cx.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
        assert tables
        for table in tables:
            columns={c[1] for c in cx.execute('PRAGMA table_info('+table+')')}
            statement=re.search(r'CREATE TABLE\s+'+re.escape(table)+r'\s*\((.*?)\);',sql,re.S)
            assert statement, f'Postgres schema omits {table}'
            pg_columns={m.group(1) for m in re.finditer(r'^\s{4}([a-z0-9_]+)\s+(?:TEXT|INTEGER|BIGINT)\b',statement.group(1),re.M)}
            assert columns==pg_columns, f'{table}: missing={columns-pg_columns} extra={pg_columns-columns}'


def test_postgres_hosted_neon_and_unknown_dsn_parameters_fail_without_connect(monkeypatch):
    from control_plane.postgres_synthetic import validate_configuration, ACKNOWLEDGEMENT
    env={'CHEMFORGE_POSTGRES_SYNTHETIC_ONLY':ACKNOWLEDGEMENT}
    for url in (
        'postgresql://u:p@neon.example.invalid:5432/chemforge?sslmode=disable',
        'postgresql://u:p@127.0.0.1:5432/chemforge?sslmode=require',
        'postgresql://u:p@127.0.0.1:5432/chemforge?sslmode=disable&connect_timeout=1',
        'postgresql://u:p@127.0.0.1:6432/chemforge?sslmode=disable',
    ):
        with pytest.raises(ValueError,match='disposable database'):
            validate_configuration({**env,'CHEMFORGE_PG_DSN':url})
