# CHEMFORGE v1.9 — Verification log

## Local verification

- `python -m pytest -q tests`: **46 passed, 7 subtests passed**.
- `node --test tests/*.test.cjs`: **40 passed**.
- `python tests/check_package.py`: **PASS**.
- Real TLS synthetic HTTP: `python -m pytest -q tests/integration/test_staging_https.py` returns **1 passed**; self-signed certificate is rejected by default trust, accepted only with explicitly supplied test cert. First device-upload returns 201 with 1 imported, second returns 200 with 1 unchanged; revoked credential gives 401; foreign school device gives 422; assigned teacher sees 1 unverified event, other institution 0.

## Android CI

- Initial Android integration CI workflow **PASS**, run `38249700843`, commit `ceee19c365f51927095b430ee773f3c7e60871f9`: connected Android compilation, emulator native HTTP upload, TLS-negative test, HTTP 201+200 and 401+422, teacher API proof, 6 Android instrumentation tests.
- **Final synthetic Android-to-teacher E2E CI**: workflow run `38250549933`, commit `8e7d2ffdcb56c77170319b5630fb02c1a83fe3d2`, conclusion **success**. Android instrumentation XML: **6 tests, 0 failures, 0 errors, 0 skipped**. Test name `ConnectedHttpsStagingTest.uploadViaRealHttpsAndVerifyReceipts` passes.
- The **real HTTPS Chromium teacher dashboard** verification step also passed in the same run: signed in as synthetic teacher, saw only `U6-A` cohort and exactly **1 unverified attempt**, and had no admin-only access. Screenshot exported from GitHub Actions artifact. The local container itself blocks Chromium localhost navigation (`ERR_BLOCKED_BY_ADMINISTRATOR`), so the browser verification was performed on the GitHub-hosted runner instead.
- CI evidence artifact: `chemforge-v19-synthetic-android-https-tests` (artifact `11747449225`, digest `sha256:818017ab6962c0e1813874591f72221d64540678dfe464d9a1bda4fec3b4d1f0`). This holds instrumented Android test reports and a screenshot with synthetic school data.
- Additional CI on the same change: offline APK build **success** run `38250549856`; connected variant QA **success** run `38250549799`. Offline APK SHA-256: `be959cc6dfd4e78b84d17205198b6162f61bf6962d1ea7ada0a8fc7543ba95af`.
- The staging server is temporary and runner-local, **not** a permanent hosted endpoint. The test-only certificate is not a publicly trusted CA. No real school data used. No test user secrets or server private keys are committed or deliberately retained.

