# CHEMFORGE v2.1 verification and release gates

Status: locally testable source hardening; no provider/staging deployment or production-readiness claim.

Source is the verified full-product Google Drive handoff (2026-10-13, archive SHA-256 `e2bf2b19d06682cc61b85535d39cafc524a209e0f1d8b0f6cece5601d54a50c6`), not an unverified reconstruction. Initial GitHub `main` before edits matched `9f63b4f2f1047279af669301af3046e0e8dd5455` exactly.

## Local repeatable qualification

```bash
python -m pytest -q tests
node --test tests/*.test.cjs
node --check control_plane/dashboard/app.js
python tests/check_package.py
python tools/staging_preflight.py --db /path/to/owner-only-synthetic-sqlite --synthetic-only
```

The new browser test `tests/control_plane/test_oidc_browser_v21.py` uses a fake provider, generated **synthetic** RS256 keys and isolated local schools. It covers state/PKCE challenge, cookie binding, one-use callback, nonce, `at+jwt` and client binding, MFA rejection, session lifecycle, CSRF/Origin, admin/teacher/cohort/tenant filtering and revoked subjects. Existing tests cover revocable student-device credentials, atomic unverified imports and offline Android manifest policy. This is not a network-facing provider E2E test.

## Pending / blocked gates

- External provider: operator-supplied IdP registration and approved issuer/audience/redirect URI, public pinned JWKS and provider metadata; provider MFA policy and actual Authorization Code + PKCE E2E; unresolved.
- Production: PostgreSQL schema migration and rollback rehearsal, remote secrets manager, rate limiting, retention, secure backups with successful restore, TLS proxy trust, network access control and verified staging; unresolved.
- Android: re-run GitHub Actions for offline APK build/lint, connected QA manifest and synthetic HTTPS Android-to-teacher e2e after the v2.1 code commit. A local container cannot substitute for a real emulator or signed release.
- Product: ZIMSEC expert/legal review, licensed model performance benchmark, independent security assessment and production signing; unresolved.

Do **not** present any fixture-generated identity or score as an actual student, staff member or certified examination result.
