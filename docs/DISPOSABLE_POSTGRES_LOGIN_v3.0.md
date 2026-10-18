# CHEMFORGE v3.0 — disposable PostgreSQL LOGIN and API qualification

Date: 2026-10-18. **SYNTHETIC LOCAL CI ONLY.** Zero-dollar, no production admission.

## Change

Earlier CI verified privileges by issuing `SET LOCAL ROLE` from a privileged
PostgreSQL owner session. That was not sufficient evidence that a separate
non-administrator LOGIN account could connect to the database and run FastAPI.

The v3.0 qualification adds `tools/postgres_login_gate.py`, which installs a
single named LOGIN (`chemforge_ci_app`) inside the disposable PostgreSQL 17
GitHub Actions service container, inheriting the previously verified NOLOGIN
group `chemforge_ci_runtime`. All identifiers are fixed compile-time constants;
a 320-bit random password exists only in the ephemeral Python test process.
Secrets are redacted from object representations and not written to repo,
Actions outputs, migration files, Drive, or application logs.

The installer requires all conditions **before SQL role creation**:

- Explicit `CHEMFORGE_PG_CI=1` and exact disposable-synthetic acknowledgment.
- Loopback PostgreSQL at 127.0.0.1:5432 with `sslmode=disable` (permitted **only**
  in the isolated CI container). Remote hosts and Neon are rejected.
- Owner username and both the DSN database and actual PostgreSQL database must
  match the fixed `chemforge_synthetic` identity.
- A preexisting `chemforge_ci_runtime` group must be NOLOGIN.
- Only the synthetic group may be inherited (`SET FALSE`), no superuser/CREATEROLE/CREATEDB,
  no public-schema CREATE, no audit UPDATE/DELETE, no migration-table UPDATE.

## Verification

- Unit tests exercise wrong configuration, wrong live identity, missing group,
  random password generation and credential-output redaction without network.
- Real PostgreSQL CI test logs in with the new username/password (not `SET
  ROLE`), verifies `current_user=session_user=chemforge_ci_app`, and checks
  forbidden SQL fails with `InsufficientPrivilege`.
- The FastAPI app boots against the dedicated role; it can bootstrap a
  **synthetic** tenant via the test fixture, read actor information, insert a
  synthetic student and record audit events.
- Existing PostgreSQL backup/restore and tenant-boundary tests still run.

These checks do **not** validate production row-level security: a shared
app database login can technically read other tenants' rows if the application
fails to filter by tenant. Stronger DB-enforced isolation remains required.

## What is still blocked

The CHEMFORGE Neon Free project `delicate-haze-29026531` retains
`block_public_connections=true` and is not touched by this experiment.
There is no approved private route, live TLS verification, production role,
secrets manager, cloud provider spending cap, institutional OIDC, external
security review or lawful real-student-data admission. The current synthetic
adapter refuses every non-loopback DSN. No public backend is deployed.

Android defaults to an offline APK with no INTERNET permission. The connected
QA variant is separate and requires student-scoped opt-in; imported marks
remain unverified.
