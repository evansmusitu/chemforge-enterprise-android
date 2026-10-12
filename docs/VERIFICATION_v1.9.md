# CHEMFORGE v1.9 — Verification log

## Local verification

- `python -m pytest -q tests`: **46 passed, 7 subtests passed**.
- `node --test tests/*.test.cjs`: **40 passed**.
- `python tests/check_package.py`: **PASS**.
- Real TLS synthetic HTTP: `python -m pytest -q tests/integration/test_staging_https.py` returns **1 passed**; self-signed certificate is rejected by default trust, accepted only with explicitly supplied test cert. First device-upload returns 201 with 1 imported, second returns 200 with 1 unchanged; revoked credential gives 401; foreign school device gives 422; assigned teacher sees 1 unverified event, other institution 0.

## Android CI

- Initial Android integration CI workflow **PASS**, run `38249700843`, commit `ceee19c365f51927095b430ee773f3c7e60871f9`: connected Android compilation, emulator native HTTP upload, TLS-negative test, HTTP 201+200 and 401+422, teacher API proof, 6 Android instrumentation tests.
- A follow-up workflow adds a **true HTTPS Chromium teacher dashboard check**; pending independent CI verification. The local container blocks Chromium navigation to localhost (`ERR_BLOCKED_BY_ADMINISTRATOR`), so it was not possible to qualify that browser network test locally. It is not counted as passed until GitHub CI confirms it.
- The staging server is temporary and runner-local, **not** a permanent hosted endpoint.
