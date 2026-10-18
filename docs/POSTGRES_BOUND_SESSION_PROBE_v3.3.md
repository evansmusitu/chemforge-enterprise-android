# CHEMFORGE v3.3 — tenant-bound PostgreSQL sessions (disposable qualification)

**Scope:** Only the disposable, loopback PostgreSQL 17 database provisioned by GitHub Actions. **Never** deploy this test gateway on Neon or ingest real student/school data.

## Risk addressed

Sharing one database administrator connection or selecting a tenant by a user-supplied `app.tenant_id` setting would permit cross-school access despite application-layer checks. A connection carrying the previous tenant's identity could also contaminate a later request. This **synthetic** qualification instead binds each tenant to a separate PostgreSQL LOGIN, verified against a database-owned `session_user` lookup enforced through RLS on all 11 application tenant tables.

## Added safeguards

- The `TenantSessionRouter` constructor refuses hosted endpoints, non-CI contexts, incorrect owner/database names, unknown login keys, unexpected school mappings and invalid generated credentials **before opening any connection**.
- For each trusted, authenticated tenant identifier, it opens a **fresh connection**, using only the corresponding ephemeral role and password created by v3.2's disposable test. The connection is never pooled or switched using a tenant GUC or SQL `SET ROLE`.
- Before returning the connection, it attests `current_database`, `session_user`, `current_user` and the database-owned `chemforge_ci_app_tenant()` identity. Mismatch fails closed.
- Each context closes after the request. PostgreSQL rolls back unsuccessful transactions (also independently exercised with an interrupted synthetic insert).
- Wrong-school reads remain invisible under PostgreSQL's actual RLS on application tables. Unrecognized tenants are rejected before any network operation; secrets are redacted from gateway representations and evidence.

## Verification

Local mock-connector regressions exercise alternating schools, fresh connection teardown, invalid principals, forbidden remote contexts and database identity mismatches. The PostgreSQL 17 CI step runs these tests **and** reuses the independently issued in-memory test logins from the v3.2 app-table RLS test to test real alternating connections and rollback.

This is **not** a production authentication mechanism. The router receives an already-verified tenant identity as a parameter, but it does not verify that the HTTP caller is allowed to supply that identity. Connecting it to FastAPI without validated staff/device authentication would be unsafe. It is intentionally not wired into FastAPI or the Android application.

## Remaining blockers

- Genuine institution-specific OIDC and service-to-database authorization mapping, production RLS migration with recovery plan, backup/restore and security/privacy assessment.
- A private, authorized network path to the dedicated locked Neon project, verified `sslmode=verify-full`, controlled secret storage and non-admin provisioned accounts.
- An explicitly capped, verifiable **$0** hosting path. Free compute credits alone do not qualify as an enforceable no-charge guarantee.
- The default Android APK remains offline, no production API is exposed and imported assessment marks remain `unverified_import`.
