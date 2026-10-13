"""Disposable-loopback PostgreSQL adapter for synthetic CI ONLY.

Not production/staging admission. The actual database is externally managed,
no schema creation occurs at app startup, and the dedicated synthetic flag is
required for *every* connection. Never use this module on institutional data.
"""
from __future__ import annotations

from contextlib import contextmanager
from hashlib import sha256
import os
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from .db import Database

SCHEMA_FILE = Path(__file__).with_name('postgres') / '001_synthetic_schema.sql'
ACKNOWLEDGEMENT = 'I_ACKNOWLEDGE_DISPOSABLE_SYNTHETIC_DATABASE_ONLY'
VERSION = '001_synthetic_schema'
# Advisory lock scoped to transaction; serializes the pilot's BEGIN IMMEDIATE
# operations to keep synthetic concurrency behavior close to SQLite.
WRITE_LOCK_ID = 21753677


def validate_configuration(environment: dict) -> str:
    if environment.get('CHEMFORGE_POSTGRES_SYNTHETIC_ONLY') != ACKNOWLEDGEMENT:
        raise ValueError('Postgres requires explicit synthetic-only acknowledgement')
    dsn = environment.get('CHEMFORGE_PG_DSN', '')
    parsed = urlsplit(dsn)
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError('Postgres synthetic connection requires a valid port') from exc
    # For v1: even a private Neon instance is NOT admitted. No credentials are
    # printed, and an accidental hosted database URL is rejected pre-connect.
    if (parsed.scheme not in ('postgres', 'postgresql') or parsed.hostname not in ('127.0.0.1', 'localhost')
            or port != 5432 or not parsed.username or not parsed.password or not parsed.path.strip('/')
            or parse_qs(parsed.query) != {'sslmode': ['disable']}
            or parsed.fragment):
        raise ValueError('Postgres synthetic CI backend requires a dedicated 127.0.0.1:5432 disposable database')
    return dsn


def _driver():
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError as exc:
        raise RuntimeError('PostgreSQL synthetic driver missing: install psycopg[binary]') from exc
    return psycopg, dict_row


class PostgresCursorAdapter:
    def __init__(self, connection):
        self.connection = connection

    def execute(self, sql, params=()):
        cleaned = sql.strip()
        if cleaned == 'BEGIN IMMEDIATE':
            return self.connection.execute('SELECT pg_advisory_xact_lock(%s)', (WRITE_LOCK_ID,))
        if cleaned.startswith('INSERT OR IGNORE INTO '):
            sql = sql.replace('INSERT OR IGNORE INTO ', 'INSERT INTO ', 1) + ' ON CONFLICT DO NOTHING'
        # SQL in this application uses SQLite positional placeholders, not
        # literal question-mark operators. Values remain prepared parameters.
        return self.connection.execute(sql.replace('?', '%s'), params)


class PostgresSyntheticDatabase(Database):
    def __init__(self, environment):
        self.dsn = validate_configuration(environment)
        psycopg, dict_row = _driver()
        try:
            with psycopg.connect(self.dsn, row_factory=dict_row, connect_timeout=5) as cx:
                table = cx.execute("SELECT to_regclass('public.chemforge_schema_versions') AS name").fetchone()
                if not table['name']:
                    raise ValueError('Postgres schema missing: run the reviewed synthetic migrator first')
                record = cx.execute('SELECT sha256 FROM chemforge_schema_versions WHERE version=%s', (VERSION,)).fetchone()
                if not record or record['sha256'] != sha256(SCHEMA_FILE.read_bytes()).hexdigest():
                    raise ValueError('Postgres synthetic schema version/checksum mismatch')
        except ValueError:
            raise
        except psycopg.Error as exc:
            raise ValueError('Postgres synthetic backend unavailable or missing reviewed migration') from exc

    @contextmanager
    def connect(self):
        psycopg, dict_row = _driver()
        with psycopg.connect(self.dsn, row_factory=dict_row, connect_timeout=5) as cx:
            yield PostgresCursorAdapter(cx)


def apply_synthetic_migration(environment):
    """One-time migration on an isolated, empty CI database only; never drop."""
    dsn = validate_configuration(environment)
    psycopg, dict_row = _driver()
    schema = SCHEMA_FILE.read_text(encoding='utf-8')
    digest = sha256(SCHEMA_FILE.read_bytes()).hexdigest()
    # No injected or dynamic DDL identifiers. Force the whole installation to
    # roll back atomically on any failed statement or preexisting user table.
    with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as cx:
        cx.execute('SELECT pg_advisory_xact_lock(%s)', (WRITE_LOCK_ID,))
        names = cx.execute("""SELECT tablename FROM pg_tables
                             WHERE schemaname=current_schema()""").fetchall()
        if names:
            raise ValueError('Postgres synthetic migration requires a completely empty database schema')
        for statement in schema.split(';'):
            if statement.strip() and not statement.strip().startswith('--'):
                cx.execute(statement)
            elif statement.strip().startswith('--'):
                # Strip SQL comments before checking statement body.
                lines = [line for line in statement.splitlines() if not line.lstrip().startswith('--')]
                body = '\n'.join(lines).strip()
                if body:
                    cx.execute(body)
        cx.execute('''CREATE TABLE chemforge_schema_versions (
            version TEXT PRIMARY KEY, sha256 TEXT NOT NULL, applied_at TIMESTAMPTZ NOT NULL DEFAULT now())''')
        cx.execute('INSERT INTO chemforge_schema_versions(version,sha256) VALUES(%s,%s)', (VERSION,digest))
    return {'status':'SYNTHETIC_SCHEMA_INITIALIZED_NOT_PRODUCTION', 'version':VERSION, 'sha256':digest}
