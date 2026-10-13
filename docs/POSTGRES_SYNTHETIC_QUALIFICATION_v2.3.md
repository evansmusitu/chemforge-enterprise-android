# CHEMFORGE Enterprise v2.3 — disposable PostgreSQL qualification

**Stage:** engineering-only / source qualification. **NOT** live hosting, production approval, Neon provisioning, or student-data admission. Date: 2026-10-13.

## Why this is a narrow milestone

The v2.2 CHEMFORGE Control pilot uses SQLite; the MUSITU Education Nexus reference uses Cloudflare, Modal and Neon. Reusing that pattern responsibly requires an isolated CHEMFORGE PostgreSQL adapter and real database tests **before** any deployment. This milestone adds a PostgreSQL adapter and versioned initial schema but deliberately authorises **only an ephemeral local GitHub Actions PostgreSQL service**. It does not migrate an institution database or reuse Nexus infrastructure.

## Implementation

- `control_plane/postgres/001_synthetic_schema.sql` — versioned, atomic first-use schema, all existing entities including OIDC sessions and device tokens; additional composite foreign keys constrain tenant membership at the database layer. Evidence remains constrained to `unverified_import`, never certified grades.
- `control_plane/postgres_synthetic.py` — optional `psycopg` adapter for the existing FastAPI service; parameterized query placeholders, a transaction-scoped advisory lock for SQLite-like serialized mutations, and an exact SHA-256 migration-version check before startup. **Not a reviewed production concurrency/connection-pooling design.**
- `tools/postgres_synthetic_migrate.py` — explicitly initializes an **empty** synthetic database; rejects reruns and never drops/replaces existing tables.
- `.github/workflows/postgres-synthetic-qualification.yml` — ephemeral PostgreSQL 17 service on the GitHub-hosted runner with fabricated, non-reusable testing credentials. No infrastructure deployment, real database, external access secrets, hosted Neon charge, or real schools.
- `tests/postgresql/` — negative admission checks and API-level PostgreSQL tenant/permission/device tests against the ephemeral database.

## Default failure behavior

The default remains `CHEMFORGE_STORAGE_BACKEND=sqlite_pilot` with the unchanged offline Android APK. The optional mode requires all of the following, simultaneously:

```
CHEMFORGE_STORAGE_BACKEND=postgres_synthetic
CHEMFORGE_POSTGRES_SYNTHETIC_ONLY=I_ACKNOWLEDGE_DISPOSABLE_SYNTHETIC_DATABASE_ONLY
CHEMFORGE_PG_DSN=postgresql://<SYNTHETIC_USER>:<DISPOSABLE_PASSWORD>@127.0.0.1:5432/<EMPTY_SYNTHETIC_DATABASE>?sslmode=disable
CHEMFORGE_PG_CI=1                    # integration test runner only
```

The DSN example is a **template**, not a working credential. This mode refuses non-loopback hosts, alternate ports, any other connection parameter, missing acknowledgment, existing unrelated tables, missing/bad migration versions, and accidentally supplied SQLite paths. Disabled TLS is permitted **only for the isolated runner's loopback database**. Never use this for a remote Neon database, school data, local production, or forwarded external access. The CLI writes neither DSNs nor passwords to logs.

## Reproduce

Local preflight without PostgreSQL or a container:

```
python -m pytest -q tests/control_plane tests/deployment tests/postgresql/test_postgres_contract.py
python tools/zero_budget_gate.py --contract deployment/zero_budget_contract.json
```

Real PostgreSQL qualification runs on GitHub-hosted Actions for source changes, using the disposable PostgreSQL 17 service. It tests two synthetic schools, cross-tenant actor FK denial, default-deny teacher cohorts, scoped grants and revocations, credentials revoked for student devices, and unverified marks. The initial schema migration is one-time and rejects reapplication.

## Remaining blockers for production

This is **not** a production PostgreSQL migration path. Still needed: review schema migration strategy for live upgrades/rollbacks (no production data conversion here), privilege separation, connection pooling, transactional idempotency under concurrency, audited backups and actual restoration, regional privacy compliance/child-data authorisation, rate limiting, retained audit integrity, legitimate real IdP integration/MFA validation, canonical HTTPS proxy security, zero-spend provider enforcement, and independent security review. No external cloud resources were created and no credentials were obtained. Public launch and student uploads remain disabled by the existing zero-budget contract.
