# CHEMFORGE v1.6 — Verification record

Source baseline: v1.5 control plane, v1.4 offline Android.

## TDD observed red / green

Dashboard-focused test initially failed (`3 failed`) because `/control/`, `/control/app.js`, and `/control/styles.css` did not exist (HTTP 404). After adding routes and local UI assets, `python -m pytest -q tests/control_plane/test_dashboard.py` returned `3 passed`.

## Local verification — October 12, 2026

- `python -m pytest -q tests`: **37 passed, 7 subtests passed**.
- `node --test tests/*.test.cjs`: **40 passed, 0 failed**.
- `python -m compileall -q control_plane`: passed.
- `node --check control_plane/dashboard/app.js`: passed.
- `python tests/control_plane/dashboard_browser_smoke.py`: passed, using Chromium DOM + real FastAPI TestClient handlers with artificial test-only HTTPS guard bypass; tested admin login, roster, assignment, issuing and dismissing a teacher credential, backup import, unverified counters, teacher role hiding, and XSS-safe text rendering. 390-pixel layout had no page-level overflow.

## Not verified

Production deployment, real HTTPS reverse proxy, SSO/MFA, mobile screen readers, student-data privacy compliance, third-party security audit, full browser network E2E, or educational validity. Existing Android APK is not rebuilt by server-only changes.
