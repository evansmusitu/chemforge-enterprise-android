# CHEMFORGE v3.2 — application-table RLS qualification

**2026-10-18 · disposable synthetic PostgreSQL 17 only · $0 · not deployed**

## What this adds

The v3.1 RLS experiment used a standalone `chemforge_ci_rls_probe` table. v3.2
applies independent Postgres-login-based tenant isolation to the **11 actual
synthetic CHEMFORGE Control schema tables** that have a direct tenant identity:
`tenants` (tenant key is `id`), `actors`, `oidc_actor_links`,
`oidc_browser_sessions`, `teacher_cohorts`, `students`, `assignments`,
`evidence`, `devices`, `content_releases`, and `audit`.

A disposable owner-managed mapping table ties each synthetic PostgreSQL
`session_user` to exactly one school. A `SECURITY DEFINER` lookup with a pinned
`pg_catalog` search path allows RLS to test that mapping without exposing the
mapping table. A custom session GUC such as `app.tenant_id` cannot override the
login's binding. All scoped tables have both ENABLE and FORCE row security;
11 corresponding ALL-command policies use USING and WITH CHECK.

Each of two fresh non-superuser LOGINs gets narrowly scoped table grants;
`audit` is SELECT/INSERT only. Global pre-authentication OIDC state,
`oidc_auth_flows`, and migration history remain unavailable. Neither login can
create tables, assume the other role, or directly inspect the owner mapping.

### Test coverage

The GitHub Actions PostgreSQL 17 service container finishes the existing schema,
FastAPI, backup/restore, restricted-login, and isolated RLS tests before this
experiment executes as a **last** data-modifying test step. Both authenticated
school logins then see only their own synthetic row in *each* of 11 actual app
tables. The tests exercise cross-school SELECT, UPDATE, DELETE, INSERT, forged
session settings, role impersonation, audit append-only privileges and direct
mapping/global-table denial. Owner queries independently verify no school B
rows were changed by school A.

The installer checks the explicit disposable CI flag, loopback-only
PostgreSQL DSN, fixed database and database owner, physical connected identity,
all 10 expected `tenant_id` columns and unused test-role names before issuing
DDL. It does not perform any network connection by itself and stores credentials
only in ephemeral CI test memory. It intentionally refuses the dedicated Neon
cloud project, even though that project exists and is currently locked.

### Critical production gaps

**This is NOT enabled as CHEMFORGE production RLS.** The current FastAPI
backend continues to use its historical synthetic database owner connection
and does not route requests through institution-bound database logins. A
PostgreSQL superuser bypasses RLS even with FORCE; deployment requires a
**non-superuser, non-BYPASSRLS role per authorized identity boundary** and
safe trusted routing. Some global pre-auth OIDC tables lack `tenant_id`, so
their ownership/isolation needs a distinct secure service-layer design.

Completing real production isolation also requires handling key uniqueness
side channels, foreign-key leakage and cascading deletes, staff-to-role
provisioning, tenant-safe connection pooling, migrations, rollback, least
privilege, TLS `verify-full`, secure secret distribution, backup retention,
real OIDC MFA and independent security/privacy review. These experiments have
**zero authority** to deploy, change Neon network settings, import real pupils,
or activate paid services.

The default Android variant remains offline without INTERNET permission;
connected QA requires explicit opt-in. Imported marks remain `unverified_import`.
