# CHEMFORGE Control v1.7 — Verification Record

2026-10-12. Local qualification of source changes prior to GitHub CI.

## Tests executed

- `python -m pytest -q tests/control_plane tests/test_*.py`: **40 passed, 7 subtests passed**. The three new v1.7 acceptance tests were first run on the previous implementation and failed on the intended missing behavior (default-deny classroom access and device-enrollment API). They pass on the implementation.
- `node --test tests/*.test.cjs`: **40 passed**, zero failed.
- `python tests/control_plane/dashboard_browser_smoke.py`: **passed**, covers admin login, cohort grant, device credential creation, teacher restrictions, manual backup import, XSS rendering and responsive viewport. **Limitation:** API requests are bridged through FastAPI TestClient because localhost navigation is unavailable in the container; this is not a deployed HTTPS end-to-end browser test.
- `python tests/check_package.py`: **passed**; confirms offline Android manifest remains unchanged.
- `bash scripts/run_source_gates.sh`: **passed** including original JavaScript/Python, Java ECDSA and AES-GCM harnesses, Chromium Android-WebView UI simulations and source policy checks.
- Android APK compilation: **not repeated locally** for this control-plane-only release. The server/dashboard modifications do not change Android application source; GitHub CI will verify after commit. Device synchronization is not proven on Android.

## Behavioral safety evidence

- Teacher permissions: no grant -> no records or writes; grants permit only the named cohort; revocation removes access; unrelated institutions cannot grant or read.
- Device tokens: stored as one-way SHA-256 digest, linked to one tenant + student, issued only by tenant administrator, expire in 1–90 days, revocable. Device secrets cannot call human admin/teacher APIs.
- Import: typed CHEMFORGE Android envelope, tenant match, transactionally atomic batch, idempotent duplicate handling, conflicting event IDs rejected, recorded as unverified only.
- Erasure: deleting a learner cascades to the learner's device credentials and imported evidence.

## Outstanding gates

- Actual HTTPS deployment and an independent security review; OIDC/MFA, rate limiting and resilient production database.
- Optional connected Android client and working consent-driven sync; current APK has no INTERNET permission.
- Independent Chemistry question/content verification, local-model accuracy and production hardware inference benchmarks.
