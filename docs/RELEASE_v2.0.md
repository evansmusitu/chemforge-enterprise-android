# CHEMFORGE Enterprise v2.0-alpha — Staff OIDC Token Gate

Date: 12 October 2026. This is a **server-side identity-hardening alpha**, not a commercial release.

## Implemented

- Optional `CHEMFORGE_STAFF_AUTH=oidc` mode, with **pilot bearer tokens refused** on all staff endpoints.
- JWT access tokens verified using operator-pinned, public-only local JWKS (one to twenty **RSA RS256** keys at least 2048-bit; no token-directed remote key lookup). Explicit `at+jwt` type, issuer, API-only single-value audience, `sub`, `iat`, `nbf`, `exp`, `jti`, `client_id`, and `amr: ["mfa", ...]` required. Access-token lifetime ≤ 60 minutes; up to 15 seconds clock skew.
- Fail-closed startup if OIDC mode is requested but required provider settings or JWKS are invalid.
- Existing local school/teacher roles and cohort permissions remain authoritative. Operator-only `link-oidc` CLI binds issuer+immutable `sub` to a pre-created actor, with duplicate and cross-tenant bindings rejected. Revocation is enforced on every request.
- OIDC-mode teacher creation does not emit unusable legacy bearer credentials; UI directs an operator to link the subject separately.
- Dashboard accepts manually provided JWTs, keeps credentials in tab memory, and continues to reject non-HTTPS transport outside localhost.
- Student-scoped device sync remains separate. Offline Android application, on-device data grading and scientific content are unchanged.

## Verified behavior

Tests exercise two tenants, good signed tokens, invalid signatures, expiry, incorrect issuer/audience, absent MFA, unlinked subjects, foreign school, revoked actors, duplicate/cross-tenant links, and invalid startup config. New regression tests require explicit RFC 9068 access-token typing and single-service audience. Operator CLI and dashboard JWT length are tested. Prior pilot tests continue to run with the default mode.

## Explicit non-goals and deployment blockers

**This release does not provide an interactive enterprise SSO login.** The browser does not redirect to an IdP using Authorization Code + PKCE; it only accepts a short-lived **pre-acquired access token**. Production needs IdP onboarding, verified provider metadata and lifecycle, secure user authentication and token acquisition/refresh, key-rotation automation, HTTP response security review, user session logout, deployed HTTPS, rate-limiting, PostgreSQL/migrations, privacy and independent security review. Provider must certify the `amr` MFA value correctly. The system does not magically gain MFA by merely accepting an `amr` claim.

The `CHEMFORGE_STAFF_AUTH=pilot` default and SQLite remain for synthetic/non-public development. Enabling OIDC mode never makes the pilot API safe for unrestricted production use. Do not use real student personal data in qualification runs. No production provider is configured; tests use synthetic RSA keys.

## Verify

`python -m pytest -q tests/control_plane` and `node --test tests/*.test.cjs` (plus the repository's existing Android/emulator workflows where available). The control CI workflow includes OIDC tests through the existing `tests/control_plane` path.
