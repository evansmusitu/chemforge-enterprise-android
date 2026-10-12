# CHEMFORGE v1.8 — Manual connected-sync qualification

**October 12, 2026.** This describes only verified engineering gates; no external school deployment has been performed.

## Local evidence

- Source test added before implementation: `python -m unittest discover -s tests -p test_connected_variant_v18.py -v` initially returned **failures/errors** for absent connected manifest, native client and journal action; the suite now passes **4/4**.
- `python -m pytest -q tests/control_plane tests/test_*.py` **45 passed, 7 subtests passed**, including device-scoped HTTP 201 created / 200 idempotent upload response contract.
- `node --test tests/*.test.cjs`: **40 passed**.
- `python tests/check_package.py`: **passed**, including preservation of the default manifest's no-INTERNET rule and WebView network denial.
- `python tests/control_plane/dashboard_browser_smoke.py`: **passed** with the in-process FastAPI bridge, not real HTTPS network.
- `bash scripts/run_source_gates.sh`: previous command passed (source, Java, Chromium simulations).

## Separate Android build gates (CI-dependent)

- Default `assembleDebug` remains no-network and must pass `scripts/verify_apk.sh`.
- Connected `assembleConnected` requests `android.permission.INTERNET` and must pass `scripts/verify_connected_apk.sh`.
- CI `CHEMFORGE_SYNC_HOST=sync.example.invalid` is deliberately unusable for real student-data transfers. Real host must be provisioned in a separate, authorised build.
- No actual HTTPS client-to-server data transfer, network-recovery, or connected-build physical-device qualification is asserted by source tests alone.

## Security boundary

- Native HTTPS client has no redirects or arbitrary URL input; only build-configured domain.
- Teacher/admin credentials are not accepted by student sync endpoint; Android requests `Device` token manually at each upload.
- Native bridge uploads the **encrypted-on-disk local history**, not a WebView-supplied arbitrary payload. No credential is intentionally persisted.
- Every transfer needs an explicit user confirmation; policy and tenant are rechecked before upload; server records remain **unverified**.

## Outstanding production gates

Managed enrollment at an actual institution, verified TLS endpoint, server-side rate limiting, production OIDC/MFA, resilient database/backup, privacy and consent audit, independent security evaluation, complete expert-reviewed Chemistry content, and independent AI scientific evaluation.
