# CHEMFORGE v3.1 — PostgreSQL Authenticated Tenant Isolation Probe

**Security qualification, NOT production tenancy enforcement** (18 October 2026).

## Purpose

The previous CHEMFORGE Control app verifies tenant isolation primarily via
API-level predicates and composite foreign keys. Its dedicated synthetic PG CI
login is low privilege but still has broad visibility within the disposable
database. An accidental omitted tenant filter would be a problem in a real
multi-school backend.

This milestone adds an isolated PostgreSQL **row-level security (RLS) probe**
using two distinct PostgreSQL LOGIN connections and PostgreSQL-authenticated
`session_user` rather than a caller-controlled `app.tenant_id` setting.

The probe creates **only synthetic test-only tables**:

- `chemforge_ci_rls_principals` — locked owner-only login-to-tenant mapping.
- `chemforge_ci_rls_probe` — two disposable records under an `ENABLE` +
  `FORCE ROW LEVEL SECURITY` policy; SELECT/UPDATE/DELETE/INSERT are tested.

A `SECURITY DEFINER` mapping function resolves the current authenticated
PostgreSQL login in a fixed search path and provides the tenant id for the RLS
policy. Independent tenant login credentials are generated in memory. The
privileged database owner and these test roles cannot be reused on Neon.

The CI workflow executes the isolation proof **after** the main database
backup/restore comparison, so this test cannot change the restore baseline.
All tests run on the container's loopback PostgreSQL server; no external
network, real users, provider tokens or institutional data are used.

## What this is not

- Not an RLS migration on existing `students`, `evidence`, `audit`, or other
  CHEMFORGE application tables.
- Not a production authentication/tenant provisioning system.
- Not a guarantee that all existing FastAPI queries are safe under RLS.
- Not an authorization for hosted Neon SQL access, unrestricted connection
  URLs, credential reuse, budget exposure, or a public API.

## Production admission blockers

Before enforcing RLS on the actual app, design a reviewed **trusted binding**
between authenticated user, school tenant and database role, including shared
identity-provider flows, onboarding, job accounts, and per-tenant connection
pooling. Add policy coverage on every table that can hold cross-tenant data,
resolve global OIDC flow records separately, and run the full application
regressions through the actual restricted roles. Review owner bypass, backups,
migrations, SECURITY DEFINER functions, role defaults, credential rotation,
function EXECUTE permission, and privilege escalation. A blocked Neon Free
project does **not** itself supply a working private application route.

The protected hosted Neon PostgreSQL project remains remote-inaccessible,
empty of student records, and on the Free plan. The Android APK remains offline
by default; student marks imported by the separate consent-based QA variant
remain unverified.
