# CHEMFORGE v2.9 — disposable PostgreSQL least-privilege role qualification

**2026-10-18 — synthetic engineering experiment, not a live Neon connection, production migration or institutional data admission.** Budget ceiling: **US$0**.

## Change

The v2.3-v2.8 PostgreSQL CI database runs the application with the disposable superuser that also installed its schema. That role has privileges far exceeding those required for normal API operation. v2.9 adds an explicit, fixed-identifier **`chemforge_ci_runtime` NOLOGIN group role** and proves selected privileges in the **same disposable GitHub Actions PostgreSQL 17 service container**. This is a privilege-model qualification only, *not* a runtime-auth change.

`tools/postgres_role_gate.py` requires **both** the CI acknowledgment (`CHEMFORGE_PG_CI=1`) and the existing loopback-only Postgres synthetic acknowledgment/DSN. It separately confirms that the *connected* database is exactly `chemforge_synthetic` before issuing any CREATE or GRANT statements. No user-controlled identifier reaches the SQL; no password, DSN, Neon credential or API token is printed. The role has `NOLOGIN`, cannot modify table definitions, and receives `USAGE` but not `CREATE` on `public`.

| Object(s) | Allowed to CI runtime group | Deliberately denied |
|---|---|---|
| Learner, actor, device, cohort, assignment, OIDC and content tables | SELECT, INSERT, UPDATE, DELETE | TRUNCATE, DDL and ownership |
| `public.audit` | SELECT, INSERT (append) | UPDATE, DELETE |
| `public.chemforge_schema_versions` | SELECT | INSERT, UPDATE, DELETE |
| `public.audit_id_seq` | USAGE | Ownership / ALTER |
| `public` schema | USAGE | CREATE |

## Evidence and limitations

Local unit tests: a **red-green** regression cycle was recorded. The initial stub returned `NOT_IMPLEMENTED`; 7 of 8 tests failed on intended missing privileges and missing fail-closed validation; then all 8 passed after implementation. The full locally available control, deployment and Postgres tests passed **113** with **2 Postgres integration tests skipped** due to the absent local PostgreSQL server. A real PostgreSQL 17 privilege test has been added to the already existing disposable service-container CI suite, which checks catalog privileges, a successful runtime SELECT after `SET LOCAL ROLE`, and denial of CREATE TABLE, UPDATE audit, and UPDATE schema-version rows.

**Do not claim this qualifies a live API least-privilege login.** The CI `chemforge_synthetic` superuser still runs the FastAPI integration tests. The new `NOLOGIN` role is a *model* for eventual separate non-superuser application credentials. The role installer is intentionally unusable against the currently blocked remote Neon project.

## Provider/network boundary

The dedicated Neon project is `delicate-haze-29026531` (synthetic only). Its organization is on the Free plan. **Public connections remain blocked**; they were not opened for this work, and no actual TLS `verify-full` database connection to Neon was established. The v2.8 offline `sslmode=verify-full&sslrootcert=system` profile check is a configuration linter, not a certificate handshake or project-identity proof.

## Blocked next gates

1. Establish a zero-charge, secure private access path without weakening the current Neon network block. Verify real TLS certificate + hostname and project/branch binding; no real credentials in source, CI logs or handoff.
2. Isolate production/staging schema owner and real LOGIN runtime roles; audit exact grants, role escalation and privilege revocation. Verify actual API endpoints run under the limited identity, not the synthetic superuser.
3. Implement reviewed PostgreSQL migration progression and reversibility, backup/restore retention, tenant context / row-level protection analysis, true HTTPS proxy trust and monitoring.
4. Qualify institutional OIDC+MFA, child/student-data privacy authority and independent security testing before real student records. Preserve offline Android without INTERNET permission and mark all uploaded evidence as `unverified_import`.

No public service, real IdP, student PII, app signing material or paid infrastructure was activated in this milestone.
