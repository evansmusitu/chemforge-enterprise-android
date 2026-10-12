# CHEMFORGE Enterprise v1.7 — Restricted Cohorts & Device Sync Gateway

**Date:** 2026-10-12  
**Release type:** enterprise control-plane pilot, not an Android APK upgrade or production deployment.

## Implemented

1. **Deny-by-default teacher assignments:** new and existing teachers see no learner rosters, assignments or cohort metrics until an institution administrator explicitly grants the teacher access to a cohort. Student creation, assignment creation, individual evidence import and offline JSON backup import enforce the same cohort membership on the server. Grants can be revoked. Revoked teacher credentials are rejected immediately.
2. **Student-scoped device credentials:** an administrator may issue an expiring, revocable, random device token scoped to one pseudonymous student. Token hashes are stored; the plaintext is returned only once. Devices cannot use teacher/admin bearer routes.
3. **Idempotent upload gateway:** `POST /v1/sync/backups` accepts the existing `CHEMFORGE_ANDROID` backup envelope under `Authorization: Device cfsync_…`; it binds the import to the enrolled device's tenant and student, never to a client-supplied student selection. Duplicate attempts are safe; conflicting IDs fail; bulk imports are atomic. All outcomes remain `unverified_import`.
4. **Institution dashboard:** administrators can grant/revoke teacher cohorts, issue and revoke device tokens, view their expiry, and display credentials once. Controls never bypass server-side authorization.
5. **Safety regressions:** tests cover cross-tenant scope, automatic grant denial, per-student device privileges, expired/revoked device credentials, erasure and integrity conflicts.

## Breaking authorization change

Teacher access is now explicitly **default-deny**. Existing teachers must be assigned cohorts by an administrator before they can see or update records for those cohorts. Administrator access remains tenant-wide. Existing student data and manual backups remain intact; adding schema tables is non-destructive. Revoked teachers cannot regain cohort access without issuance of a new credential.

## Deliberate limitations

- The **Android APK retains no INTERNET permission**. The device upload endpoint is the server-side foundation for a future **optional connected client**. Automatic device-to-server sync is **not yet implemented or tested**. The existing manual offline JSON transfer is still supported.
- Not production ready: bearer capabilities and SQLite remain pilot-grade; no OIDC, MFA, transport termination, server rate limits, certificate pinning, institutional privacy governance, production backup/audit policy or independent penetration test.
- Possession of a device token is not proof of physical-device identity; uploaded study marks remain unverified. This gateway is not secure examination submission.
- Chemistry curriculum, marking rubrics and LLM accuracy still need independent scientific review.

## Next qualification gates

Run the optional connected-client opt-in design and end-to-end sync tests; introduce OIDC+MFA and lifecycle credential management; add production PostgreSQL and migration tooling; commission independent security/content reviews. Never deploy this pilot API openly to real student data.
