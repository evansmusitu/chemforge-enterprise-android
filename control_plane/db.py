"""SQLite metadata store for CHEMFORGE Control (pilot; one writable DB instance).

All foreign keys carry both tenant ID and local identifier. Tokens are random
bearer capabilities, and only their SHA-256 hashes are stored on disk.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import re
import os
import secrets
import sqlite3
from uuid import uuid4


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_token() -> str:
    return 'cfcp_' + secrets.token_urlsafe(32)


def token_digest(token: str) -> str:
    return sha256(token.encode('ascii')).hexdigest()


SCHEMA = '''
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS tenants (
  id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS actors (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL REFERENCES tenants(id),
  label TEXT NOT NULL,
  role TEXT NOT NULL CHECK(role IN ('admin','teacher')),
  token_hash TEXT NOT NULL UNIQUE,
  revoked_at TEXT,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_actors_tenant ON actors(tenant_id,role);
CREATE TABLE IF NOT EXISTS oidc_actor_links (
  issuer TEXT NOT NULL,
  subject TEXT NOT NULL,
  actor_id TEXT NOT NULL UNIQUE REFERENCES actors(id) ON DELETE CASCADE,
  tenant_id TEXT NOT NULL REFERENCES tenants(id),
  linked_at TEXT NOT NULL,
  PRIMARY KEY (issuer, subject)
);
CREATE INDEX IF NOT EXISTS idx_oidc_actor_links ON oidc_actor_links(tenant_id,actor_id);

-- Pilot-only, process-local SQLite session state; not a PostgreSQL migration.
CREATE TABLE IF NOT EXISTS oidc_auth_flows (
  state_hash TEXT PRIMARY KEY,
  binding_hash TEXT NOT NULL,
  code_verifier TEXT NOT NULL,
  nonce TEXT NOT NULL,
  expires_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_oidc_auth_expires ON oidc_auth_flows(expires_at);
CREATE TABLE IF NOT EXISTS oidc_browser_sessions (
  session_hash TEXT PRIMARY KEY,
  actor_id TEXT NOT NULL REFERENCES actors(id) ON DELETE CASCADE,
  tenant_id TEXT NOT NULL REFERENCES tenants(id),
  issuer TEXT NOT NULL,
  subject TEXT NOT NULL,
  csrf_token TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_oidc_session_expires ON oidc_browser_sessions(expires_at);


CREATE TABLE IF NOT EXISTS teacher_cohorts (
  tenant_id TEXT NOT NULL,
  actor_id TEXT NOT NULL REFERENCES actors(id) ON DELETE CASCADE,
  cohort TEXT NOT NULL,
  granted_at TEXT NOT NULL,
  PRIMARY KEY(tenant_id,actor_id,cohort),
  FOREIGN KEY(tenant_id) REFERENCES tenants(id)
);
CREATE INDEX IF NOT EXISTS idx_teacher_cohorts ON teacher_cohorts(tenant_id,actor_id,cohort);

CREATE TABLE IF NOT EXISTS students (
  id TEXT NOT NULL,
  tenant_id TEXT NOT NULL REFERENCES tenants(id),
  pseudonym TEXT NOT NULL,
  cohort TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY(tenant_id,id)
);
CREATE INDEX IF NOT EXISTS idx_student_cohort ON students(tenant_id,cohort);
CREATE TABLE IF NOT EXISTS assignments (
  id TEXT NOT NULL,
  tenant_id TEXT NOT NULL REFERENCES tenants(id),
  title TEXT NOT NULL,
  cohort TEXT NOT NULL,
  objectives_json TEXT NOT NULL,
  due_at TEXT,
  actor_id TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY(tenant_id,id)
);
CREATE TABLE IF NOT EXISTS evidence (
  tenant_id TEXT NOT NULL,
  event_id TEXT NOT NULL,
  student_id TEXT NOT NULL,
  question_id TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  verification_status TEXT NOT NULL CHECK(verification_status='unverified_import'),
  received_at TEXT NOT NULL,
  PRIMARY KEY(tenant_id,event_id),
  FOREIGN KEY(tenant_id, student_id) REFERENCES students(tenant_id,id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_evidence_student ON evidence(tenant_id,student_id);
CREATE TABLE IF NOT EXISTS devices (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  student_id TEXT NOT NULL,
  label TEXT NOT NULL,
  token_hash TEXT NOT NULL UNIQUE,
  issued_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  revoked_at TEXT,
  FOREIGN KEY(tenant_id,student_id) REFERENCES students(tenant_id,id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_devices_student ON devices(tenant_id,student_id);

CREATE TABLE IF NOT EXISTS content_releases (
  tenant_id TEXT NOT NULL REFERENCES tenants(id),
  pack_version INTEGER NOT NULL CHECK(pack_version>=1),
  content_version TEXT NOT NULL,
  pack_sha256 TEXT NOT NULL,
  content_fingerprint TEXT NOT NULL,
  actor_id TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY(tenant_id,pack_version)
);
CREATE TABLE IF NOT EXISTS audit (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tenant_id TEXT NOT NULL REFERENCES tenants(id),
  actor_id TEXT NOT NULL,
  action TEXT NOT NULL,
  subject_id TEXT NOT NULL,
  occurred_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_audit_tenant ON audit(tenant_id,id);
'''


class Database:
    def __init__(self, path: str):
        self.path = str(Path(path).resolve())
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        # Newly created DB files are owner-only even under permissive process umask.
        # Existing files require an operator review before serving real data.
        if not Path(self.path).exists():
            try:
                fd=os.open(self.path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
                os.close(fd)
            except FileExistsError:
                pass
        with self.connect() as cx:
            cx.execute('PRAGMA journal_mode=WAL')
            cx.executescript(SCHEMA)

    @contextmanager
    def connect(self):
        cx = sqlite3.connect(self.path, timeout=15)
        cx.row_factory = sqlite3.Row
        cx.execute('PRAGMA foreign_keys=ON')
        cx.execute('PRAGMA busy_timeout=15000')
        try:
            yield cx
            cx.commit()
        except BaseException:
            cx.rollback()
            raise
        finally:
            cx.close()

    def bootstrap_tenant(self, tenant_id: str, admin_label: str) -> str:
        """Explicit CLI-only provisioning; no public bootstrap HTTP endpoint."""
        if not re.fullmatch(r'[a-z0-9][a-z0-9-]{2,39}', tenant_id):
            raise ValueError('tenant_id must be a 3–40 character lowercase identifier')
        if not 1 <= len(admin_label.strip()) <= 80:
            raise ValueError('admin label must be 1–80 characters')
        token = new_token()
        with self.connect() as cx:
            cx.execute('BEGIN IMMEDIATE')
            if cx.execute('SELECT 1 FROM tenants WHERE id=?',(tenant_id,)).fetchone():
                raise ValueError('tenant already exists; refusing to issue another bootstrap token')
            cx.execute('INSERT INTO tenants(id,created_at) VALUES(?,?)',(tenant_id,utcnow()))
            cx.execute('''INSERT INTO actors(id,tenant_id,label,role,token_hash,created_at)
                         VALUES(?,?,?,?,?,?)''', (str(uuid4()),tenant_id,admin_label.strip(),'admin',token_digest(token),utcnow()))
        return token

    @staticmethod
    def audit(cx: sqlite3.Connection, tenant_id: str, actor_id: str, action: str, subject_id: str):
        cx.execute('''INSERT INTO audit(tenant_id,actor_id,action,subject_id,occurred_at)
                      VALUES(?,?,?,?,?)''',(tenant_id,actor_id,action,subject_id,utcnow()))

    def link_oidc_subject(self, tenant_id: str, actor_id: str, issuer: str, subject: str) -> None:
        """Trusted operator-only link. No API endpoint may auto-provision accounts."""
        if (not isinstance(subject,str) or not 1<=len(subject)<=255 or not subject.strip()
                or not isinstance(issuer,str) or not issuer.startswith('https://')):
            raise ValueError('Invalid OIDC issuer or subject')
        with self.connect() as cx:
            cx.execute('BEGIN IMMEDIATE')
            actor = cx.execute('''SELECT id FROM actors
                   WHERE tenant_id=? AND id=? AND role IN ('admin','teacher') AND revoked_at IS NULL''',
                   (tenant_id,actor_id)).fetchone()
            if not actor:
                raise ValueError('Staff actor is missing or belongs to a different institution')
            if cx.execute('SELECT 1 FROM oidc_actor_links WHERE issuer=? AND subject=?',
                    (issuer,subject)).fetchone():
                raise ValueError('OIDC issuer/subject already linked')
            if cx.execute('SELECT 1 FROM oidc_actor_links WHERE actor_id=?',(actor_id,)).fetchone():
                raise ValueError('Staff actor already has an OIDC binding')
            cx.execute('''INSERT INTO oidc_actor_links(issuer,subject,actor_id,tenant_id,linked_at)
                          VALUES(?,?,?,?,?)''',(issuer,subject,actor_id,tenant_id,utcnow()))
            self.audit(cx,tenant_id,actor_id,'identity.oidc_linked',actor_id)
