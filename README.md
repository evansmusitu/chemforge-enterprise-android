# CHEMFORGE Enterprise Android and Control Plane (v1.9 alpha)

**CHEMFORGE Student** has a default offline-only Android build and a separate opt-in connected QA variant for experimental A-Level Chemistry revision. **CHEMFORGE Control** is a separate connected institutional administration service, now with a same-origin browser dashboard. Automatic synchronisation remains unavailable. The connected variant adds a **manual**, explicit-consent, HTTPS upload to the existing student-scoped gateway; the default APK retains **no INTERNET permission**.

## Current entry points

- Android: `app/` — APK build and emulator CI are configured separately.
- Institution server: `control_plane/` — SQLite-backed pilot API, `GET /control/` dashboard.
- Administration: `python -m control_plane.cli bootstrap --db ... --tenant school-demo --admin-label 'Principal'` creates the one-time administrator credential (do not commit credentials).
- Local UI: `CHEMFORGE_CONTROL_DB=... uvicorn control_plane.app:create_app --factory --host 127.0.0.1 --port 8020` then open `http://127.0.0.1:8020/control/`. Use HTTPS for any non-loopback pilot.
- Server verification: `python -m pytest -q tests/control_plane`.

**Security and scientific limitations:** Control remains a private pilot, without OIDC/SSO, MFA, independent teacher-permission security review, secure production deployment, or independent content validation. Android exports are editable by students; imported marks and cohort analytics are **unverified** and never certified assessment records. Content registry entries are metadata, not signatures. Learn more in `control_plane/README.md` and `docs/RELEASE_v1.7.md`.

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

The v1.9 gate additionally attempts a real HTTPS Chromium dashboard login using the synthetic teacher token and a private test certificate; the local ChatGPT browser sandbox denies localhost navigation, so its result must be read from GitHub Actions.
