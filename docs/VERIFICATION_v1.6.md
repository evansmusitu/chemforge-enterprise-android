# CHEMFORGE Control v1.6 — Verification Record

Recorded in the development container on 2026-10-11.

- `python -m pytest -q tests/control_plane/test_dashboard.py`: **4 passed**; red cases observed for missing UI, insecure hidden content behaviour, and over-broad CSP before fixes.
- `python -m pytest -q`: **38 passed, 7 subtests passed**.
- `node --check control_plane/console/app.js`: exit **0**.
- `PYTHONPATH=. python tests/control_plane/browser_smoke.py`: **PASS**. This test uses Playwright Chromium, real DOM events, and FastAPI TestClient API responses intercepted by an in-page fetch bridge because Chromium navigation is forbidden in the execution sandbox. The production HTTPS origin guard is conditionally disabled **in the harness only** and remains unchanged in shipped source. Test coverage includes login, roster, assignment, teacher issuance, text-only rendering of malicious input, role restrictions and logout.

Important: Successful source tests do not establish production deployment security, real TLS operation, browser/device compatibility or school readiness. Android v1.4 APK is unchanged in this release.
