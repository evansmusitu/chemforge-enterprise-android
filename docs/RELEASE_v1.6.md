# CHEMFORGE Enterprise v1.6-alpha — Institutional Web Dashboard

## Included in this release

- Same-origin responsive admin dashboard at `/control/` served directly by the FastAPI server. No external assets, trackers, or client bundling step.
- Administrator/teacher credential entry, in-tab-only token lifetime and explicit sign-out (no localStorage or sessionStorage for credentials).
- Overview with pseudonymous student count, assignment count, active teachers (admin only) and clearly labelled **unverified** import counts by cohort.
- Pseudonymous student roster creation, search and admin-only erasure.
- Cohort assignment creation and listing.
- Manual institution-scoped Android JSON backup import; server remains authoritative for tenant, content and idempotency checks. No auto-sync or certificate of marks.
- Admin-only teacher provisioning, one-time display of teacher credentials, and revocation.
- Versioned curriculum package **metadata** registry, not content signing; institution audit list for admins.
- Responsive mobile layout, accessibility labels, no inline scripts or untrusted HTML insertion, restrictive CSP / cache / frame / referrer headers.

## Tests / boundaries

`python -m pytest -q tests` and `node --test tests/*.test.cjs` test the source. The Chromium functional harness `python tests/control_plane/dashboard_browser_smoke.py` exercises DOM/forms against real FastAPI TestClient API handlers using *synthetic institution data*; this container blocks browser localhost navigation, so the harness bridges network calls and bypasses the secure-origin guard **only in memory for testing**. No production file disables the guard. This is not full network/browser deployment proof or a penetration test.

## Not implemented / release blockers

- No Android-to-control-plane auto-sync, OIDC/SSO, MFA, credential lifecycle/rotation, rate limiting, signed assessment submissions, role-based class scopes, production migrations, monitoring, privacy consent, retention schedules, hosted deployment or teacher analytics beyond unverified counts.
- SQLite pilot datastore and bearer-token identity are unsuitable for unreviewed public deployment, especially for minors.
- Android AI inference quality and syllabus completeness remain separate unfinished validation projects. Physical app testing reported by user is not independent scientific/model verification.

This v1.6 release adds a **server dashboard**, not a new APK. The latest compiled Android client remains v1.4-alpha.
