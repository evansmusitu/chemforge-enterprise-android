# CHEMFORGE v2.7 — Dedicated Neon Free resource, locked and empty

**Recorded 2026-10-16 (UTC). Not a production deployment, real-user pilot, or operational API.**

## Provider-confirmed provisioning

Neon listed the account's organization on the **Free** plan before project
creation. After provisioning, the isolated project reported its subscription
as **free_v3**. The project is exclusively for CHEMFORGE, separate from MUSITU
Education Nexus credentials, projects, roles, student data, domains and runtime.

| Property | Verified state |
| --- | --- |
| Project | CHEMFORGE Synthetic Staging - No Student Data |
| Project ID | delicate-haze-29026531 |
| Branch | synthetic-staging (br-wandering-boat-b5o4f2ty) |
| Database and owner role | chemforge_synthetic |
| PostgreSQL | 17 (server reported 17.11) |
| Region | aws-us-east-2 |
| Maximum compute | 0.25 CU |
| Public database connections | **Blocked** |
| Public user-defined tables at initial read | **0** |

Immediately after creating the project, a **read-only** provider SQL query
confirmed the database name, role, PostgreSQL 17.11 and zero user-defined
tables. Then the provider's block_public_connections setting was changed
from false to true and independently read back as true. A subsequent table
listing was rejected by the provider with a **blocked network** error, as
expected. The verified empty-table observation therefore predates the public
network block; it cannot be rechecked through the blocked SQL connection.

No password, connection string, signing key, student backup, personal record,
secret, public API endpoint or FastAPI instance is stored or enabled.

## Safety and cost

This isolated resource is on an account that currently reported Neon Free.
Neon's published Free plan is $0/month within quotas; the observed plan is
not an invoice, a permanent plan lock or a guarantee about future billing.
No paid upgrade, shared MUSITU account secret or runtime deployment occurred.
The CHEMFORGE zero-budget contract still blocks a public API, live student
data, and provider *application/runtime* deployment.

The remote Postgres schema is **not migrated**. The existing experimental
Python backend's PostgreSQL adapter rejects remote hosts and continues
operating only against disposable loopback CI databases. The Android default
APK retains no INTERNET permission; connected QA remains separate with manual
consent. All imported marks remain unverified.

## Offline verification and limitations

The checked-in minimal evidence file records an **historical snapshot**
without secrets. Run from the repository root:

    python tools/neon_staging_gate.py
    python tools/zero_budget_gate.py
    python -m pytest -q tests/deployment

These tools do not contact Neon. A successful local check cannot establish
that the provider settings still match, that spending controls will continue,
or that the environment is approved for production.

## Remaining admission gates

1. Live recheck Free billing, provider isolation and publicly blocked access
   before making any future hosting decision. Do not unlock connections just
   to satisfy GitHub Actions.
2. Independently implement SSL verify-full TLS for a dedicated remote adapter,
   audited versioned migrations, least-privilege credentials and reversible
   synthetic-only DB admission. Do not silently remove the current loopback
   synthetic-only guard.
3. Qualify backup and restore, tenant isolation, revocation, expiration,
   audit retention and reliable rollback on an approved remote staging path.
4. Independently verify $0 *hard* spend controls before considering chargeable
   serverless hosting. Modal Starter credits are not a no-overage guarantee.
5. Validate HTTPS proxy trust, actual institutional IdP/MFA, privacy authority,
   child-data protection and independent security assessment before real use.

**Outcome: one dedicated empty, locked Neon Free project. Not an API deployment,
not a data migration, and not a production release.**
