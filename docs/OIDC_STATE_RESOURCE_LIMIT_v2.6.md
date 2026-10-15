# CHEMFORGE v2.6 — bounded OIDC login state (synthetic security qualification)

Date: 2026-10-15. This is a local/CI security hardening candidate, not a hosted production deployment.

## Resource-bound login state

The optional staff OIDC Authorization Code + PKCE start endpoint can be requested
by an unauthenticated browser. A large number of unused attempts otherwise
persist until cleanup, putting unnecessary pressure on the $0 SQLite pilot.

The server now deletes expired OIDC login flows and expired staff sessions inside
a serialized transaction. It refuses to allocate more than 256 outstanding
unexpired OIDC flows across the pilot, returning HTTP 429 with Retry-After and
Cache-Control: no-store. Cleanup is committed even when capacity is exhausted.
An expired slot becomes available on a subsequent start request.

The cap is a last-resort resource boundary. It is *not* per-user/per-IP rate
limiting, does not stop a malicious caller from filling the cap, and does not
replace Cloudflare edge abuse controls. Real identity provider registration,
HTTPS hosting, actual provider-side MFA, proxy trust, server monitoring, audit
retention and staff session lifecycle security review remain mandatory gates.

## Engineering evidence

The three new behavioral regressions establish bounded allocations,
expired-slot recovery, selective session cleanup, and persistence of cleanup
during a denied start. The missing behaviors were observed failing (2/2 and
1/3 cases respectively) before implementation. After implementation, the
focused tests were green (3/3) and the local combined suite passed
88 Python tests plus 7 subtests with 2 local PostgreSQL skips, along with
40 Node tests and Android packaging/source-policy checks.

The synthetic GitHub PostgreSQL tests must be checked separately after pushing.
No remote database, credentials, secrets, production fees, or real student
fixtures are required for this milestone.

The default Android APK continues to have no INTERNET permission; the
connected QA variant is separate and explicitly consent-based. Imported
marks remain unverified, never certified assessment records.

## Safety boundary

This change does not enable deployment. The dedicated PostgreSQL synthetic-only
adapter still rejects remote database hosts; the zero-dollar deployment
contract remains unchanged and forbids public API/data admission and
reuse of MUSITU Education Nexus credentials, data or hosting.


## PostgreSQL dictionary-row compatibility repair

Follow-up verification identified that psycopg's dictionary row representation
cannot be indexed by integer zero. The count query now returns a named
`active_flows` column, read by column name in both SQLite and PostgreSQL.
A deterministic mapping-row regression was observed failing with `KeyError: 0`
before the fix, and green afterward. An additional true PostgreSQL 17 test
checks login-flow capacity and expired-slot recovery inside the existing
synthetic service-container pipeline; do not count it as verified until that
CI workflow succeeds on the repair commit.
