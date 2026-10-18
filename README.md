# CHEMFORGE Enterprise Android and Control Plane (v2.5 synthetic security hardening)

**CHEMFORGE Student** has a default offline-only Android build and a separate opt-in connected QA variant for experimental A-Level Chemistry revision. **CHEMFORGE Control** is a separate connected institutional administration service, now with a same-origin browser dashboard. Automatic synchronisation remains unavailable. The connected variant adds a **manual**, explicit-consent, HTTPS upload to the existing student-scoped gateway; the default APK retains **no INTERNET permission**.

See [`docs/RELEASE_v2.1.md`](docs/RELEASE_v2.1.md) and [`docs/VERIFICATION_v2.1.md`](docs/VERIFICATION_v2.1.md) for the opt-in server-side browser PKCE flow, permission regressions and explicit production blockers. **No real IdP or staging deployment is configured.**

## Current entry points

- Android: `app/` — APK build and emulator CI are configured separately.
- Institution server: `control_plane/` — SQLite-backed pilot API, `GET /control/` dashboard.
- Administration: `python -m control_plane.cli bootstrap --db ... --tenant school-demo --admin-label 'Principal'` creates the one-time administrator credential (do not commit credentials).
- Local UI: `CHEMFORGE_CONTROL_DB=... uvicorn control_plane.app:create_app --factory --host 127.0.0.1 --port 8020` then open `http://127.0.0.1:8020/control/`. Use HTTPS for any non-loopback pilot.
- Server verification: `python -m pytest -q tests/control_plane`.

**Security and scientific limitations:** Control remains a private pilot, with only an optional pinned-JWKS OIDC access-token validation gate (not interactive SSO), without an independent teacher-permission security review, secure production deployment, or independent content validation. Android exports are editable by students; imported marks and cohort analytics are **unverified** and never certified assessment records. Content registry entries are metadata, not signatures. Learn more in `control_plane/README.md` and `docs/RELEASE_v1.7.md`.

## Qualifications achieved vs. pending

Android source and emulator build gates were completed in v1.4; they are not repeated by this dashboard change. On-device AI model behavior and Chemistry correctness require separately documented, reproducible evidence. The pilot question bank is not a complete reviewed ZIMSEC syllabus. The server is not ready for public institutional student-data collection.


## v1.7 (Control Plane)

See [`docs/RELEASE_v1.7.md`](docs/RELEASE_v1.7.md): teacher cohorts now deny access by default, and an admin-managed, per-student device upload gateway is available. **The Android client has not gained network permission or automatic synchronisation.**

## v1.8 (Connected Client Qualification)

See [`docs/RELEASE_v1.8.md`](docs/RELEASE_v1.8.md) for the distinct connected QA Android build. This build has INTERNET access and a host pinned at compile time, and requires an enrolled institution and manually entered student-scoped device credential. A **dummy disabled `.invalid` host is used in CI**. It is not an operational school sync release until a real endpoint is configured and independently end-to-end tested. The default `:app:assembleDebug` APK continues to have no INTERNET permission.

## v1.9 — Live synthetic HTTPS Android-to-teacher staging gate

The GitHub Actions workflow `.github/workflows/staging-e2e-https.yml` builds a **connected QA APK configured only for the Android emulator's `10.0.2.2` alias**. It provisions two **synthetic** schools, teacher/cohort permissions, student-scoped active/revoked/foreign device tokens and an ephemeral self-signed TLS certificate. FastAPI binds only to runner loopback port 443; emulator traffic reaches that isolated loopback server. The instrumentation uses a temporary test-only TLS trust anchor (not present in production APK) and executes the **real native `HttpsURLConnection` upload**. It tests created/duplicate/revoked/foreign receipts. A final HTTPS server query verifies that precisely one **unverified** attempt appears to the authorised teacher, and no data appear for the unrelated school.

This is a **CI-hosted, disposable staging run**, not a permanently deployed public server. No actual school data, real certificates, production SSO or live physical-device network qualification is involved. Production Android's TLS trust and offline APK policy remain unchanged.

Run host-only HTTPS proof locally: `python -m tests.integration.staging_https demo --dir /tmp/chemforge-v19-demo`.
See `docs/RELEASE_v1.9.md` and `docs/VERIFICATION_v1.9.md`.

The v1.9 gate additionally attempts a real HTTPS Chromium dashboard login using the synthetic teacher token and a private test certificate; the local ChatGPT browser sandbox denies localhost navigation, but the GitHub-hosted real HTTPS browser and Android E2E gate passed in run `38250549933`.


## v2.0-alpha — Opt-in staff OIDC bearer validation

The **server-only** `CHEMFORGE_STAFF_AUTH=oidc` mode rejects all pilot staff bearer tokens and accepts only short-lived, MFA-asserting, RSA-signed `at+jwt` access tokens from a *configured* HTTPS issuer and dedicated API audience, validated against operator-pinned local JWKS verification keys. Staff identities must be **manually linked** to existing school-scoped local actors; no account is created from external role or email claims. Revoked local actors remain blocked. See [`docs/RELEASE_v2.0.md`](docs/RELEASE_v2.0.md).

This is **not** a browser authorization-code/PKCE SSO flow. The existing dashboard accepts a manually supplied access token in tab memory; integrating a real identity provider, token acquisition/refresh, security assessment and production deployment are separate gates. The offline Android APK is unchanged.


## v2.5: device upload authorization is rechecked before writes

After initial Device credential authentication, the upload transaction now rechecks
revocation, expiration and student/tenant binding before inserting any unverified
evidence. See docs/DEVICE_REAUTH_ATOMICITY_v2.5.md.
This is synthetic qualification only: no public backend, no hosted Postgres,
no real student data and no paid deployment.

## v2.6: bounded synthetic staff sign-in state

The opt-in staff PKCE login start now prunes expired server flows and sessions
and caps outstanding flows at 256; exhaustion returns no-store HTTP 429.
See docs/OIDC_STATE_RESOURCE_LIMIT_v2.6.md. This is not a public or
provider-verified SSO rollout; production deployment remains blocked.

## v2.7: provisioned, locked Neon Free staging resource

A dedicated CHEMFORGE PostgreSQL 17 project was allocated on the existing
Neon free organization; its public connections are blocked and the database
was verified empty before blocking. No FastAPI process, migrations, credentials,
student records or public API were deployed. The offline/CI-only attestation
gate cannot authorize hosting or confirm ongoing provider settings. See
`docs/NEON_SYNTHETIC_STAGING_v2.7.md`.

## v2.8: Neon TLS profile checked offline (remote access remains BLOCKED)

The guarded staging preflight can validate a future Neon TLS DSN shape without
connecting or exposing a password. The dedicated Neon Free project remains
publicly blocked, no runtime can use its remote credentials, and the offline
student APK and unverified evidence boundaries are unchanged.
See [docs/NEON_TLS_PREFLIGHT_v2.8.md](docs/NEON_TLS_PREFLIGHT_v2.8.md).

## v2.9: disposable PostgreSQL runtime-role privilege experiment

A separate **NOLOGIN synthetic CI role** now models least-privilege runtime
permissions: normal data tables are usable, but security audit history is
append-only and the schema-version ledger is read-only. This is verified in the
existing *disposable* PostgreSQL 17 test container, not the locked Neon project.
The actual CI API still connects as a superuser and a live limited-login
backend is not yet qualified. See `docs/POSTGRES_ROLE_LEAST_PRIVILEGE_v2.9.md`.

The $0 budget, blocked public Neon access, explicit-consent connected QA,
fully offline default APK, and no-real-student-data gates remain unchanged.

## v3.0 synthetic database LOGIN qualification (not hosted)

A **real restricted PostgreSQL LOGIN**, using an ephemeral test-only password,
now exercises FastAPI and tenant-scoped reads/writes within a disposable local
PostgreSQL 17 GitHub Actions container. Its NOLOGIN parent group is limited to
application tables and append-only audit; the login cannot perform schema DDL,
change audit history, update migration versions or impersonate the owner.
`tools/postgres_login_gate.py` is guarded against live Neon connections and
never emits a credential into project files or Actions logs. See
`docs/DISPOSABLE_POSTGRES_LOGIN_v3.0.md`. The separate locked Neon Free project
is unchanged and still unreachable publicly. This does **not** enable a remote
API, production user identity, or real student information.
