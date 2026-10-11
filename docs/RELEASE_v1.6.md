# CHEMFORGE Enterprise v1.6 — Institutional Console (Pilot)

## Delivered

The Android student application remains unchanged and offline-first. v1.6 extends the separate **CHEMFORGE Control** FastAPI administration service with a first-party, responsive, dependency-free browser console served locally at `/console`.

Functional flows: credential sign-in/sign-out, institution overview, cohort counts, pseudonymous student creation/deletion (admin), teacher account issuance/revocation (admin), assignment creation, curriculum registry metadata, administrator audit view, and manual import of Android study-export JSON into tenant-scoped records.

Security design: bearer credentials are never saved to browser persistence; the UI requires HTTPS outside localhost; CSP locks console scripts, CSS and API requests to the same origin; no CDN or third-party scripts; API still enforces tenant scope and roles; all user strings enter DOM through `textContent`; `no-store`, anti-framing, no-sniff and no-referrer response headers; explicit destructive-action confirmation. The console does **not** certify scores or enable automatic Android sync.

## Verification (source-level, NOT deployment qualification)

- Python API tests including console/security-contract tests; Node JS parser check.
- Interactive Chromium DOM smoke with real FastAPI TestClient behind a simulated browser API transport (navigation blocked by sandbox). Smoke covers login, roster, assignment, teacher credential issuance, XSS escaping, role hiding, logout and teacher re-login.
- GitHub Action `.github/workflows/control-plane-tests.yml` runs control-plane tests and Node parsing on each relevant push.

## Not delivered

Production SSO/OIDC, MFA, TLS reverse proxy, credential expiry/rotation, rate limiting, class-granular permissions, cryptographically protected audit trail, data protection impact assessment, consent/retention program, encrypted backup and disaster recovery, Postgres/HA hosting, automated Android synchronisation, independent Chemistry content review, or device AI accuracy validation. This remains an **institutional pilot**, not enterprise-production-ready.
