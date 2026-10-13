# CHEMFORGE v2.5 — transaction-time device authentication

2026-10-13. $0 synthetic security qualification only; no production or hosted staging.

## Fixed race

Before v2.5, an API request could authenticate a Device cfsync token in the
FastAPI dependency and then import evidence in a later write transaction after
the device was revoked, expired, or moved to another student. The write did not
revalidate the authorization record.

The import transaction now rechecks device ID, exact tenant/student binding,
revocation, and expiration after it has obtained the backend's serialized write
lock. A changed or expired device is rejected with HTTP 401 before evidence or
audit rows are written. No token secret is stored in plaintext.

## Evidence

The new SQLite HTTP regression simulates each interleaving by wrapping the
real initial authentication dependency, committing a change, and invoking the
real upload endpoint. All three tests failed on the pre-fix source (HTTP 201
instead of 401) and pass after the fix, including zero evidence/audit writes.

The three matching PostgreSQL 17 regression cases are added to the existing
synthetic-only GitHub Actions service-container suite. This does not establish
live PostgreSQL or Neon behavior until the matching CI run is confirmed.

The offline Android APK retains no INTERNET permission; the separate connected
QA client retains explicit manual consent and revocable student credentials.
Imported marks remain unverified, never certified exam grades.

## Remaining admission blockers

The current synthetic PostgreSQL adapter explicitly prohibits remote hosts.
The zero-budget contract prohibits real student records, public API enabling,
provider deployment, and reuse of MUSITU Education Nexus credentials/data.
A dedicated CHEMFORGE hosted database, provider spending controls, true
institutional OIDC, production DB migrations and least-privilege roles, HTTPS
proxy trust, audit retention, backups, independent security/privacy review,
and student-data authority are not established.

Staff mutation authorization races are separate review work; this change
closes the device backup-import TOCTOU window only.
