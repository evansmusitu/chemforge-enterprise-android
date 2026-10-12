# CHEMFORGE v1.9 — Verification log

## Local verification

- `python -m pytest -q tests`: **46 passed, 7 subtests passed**.
- `node --test tests/*.test.cjs`: **40 passed**.
- `python tests/check_package.py`: **PASS**.
- Real TLS synthetic HTTP: `python -m pytest -q tests/integration/test_staging_https.py` returns **1 passed**; self-signed certificate is rejected by default trust, accepted only with explicitly supplied test cert. First device-upload returns 201 with 1 imported, second returns 200 with 1 unchanged; revoked credential gives 401; foreign school device gives 422; assigned teacher sees 1 unverified event, other institution 0.

## Android CI

Not yet recorded. Consult `.github/workflows/staging-e2e-https.yml` after GitHub execution. *A green Python test is not proof of Android-to-server integration.*
