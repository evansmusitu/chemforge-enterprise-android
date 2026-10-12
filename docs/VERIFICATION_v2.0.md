# CHEMFORGE v2.0-alpha — staff identity gate verification

Date: 12 October 2026. Source-only control-plane change: Android binary and emulator qualification are **not** new in this release.

## Local tests completed

- `python -m pytest -q tests`: **52 passed, 7 subtests passed** (exit 0).
- `node --test tests/*.test.cjs`: **40 passed** (exit 0).
- `python tests/check_package.py`: static Android/offline/source gates **passed** (exit 0).
- `python tests/control_plane/dashboard_browser_smoke.py`: Chromium DOM with real in-process FastAPI handlers **passed** (exit 0). This browser smoke does not traverse a network socket, and secure-origin policy is bypassed inside the test harness only.

Focused regression cycles observed failing before implementation: missing `Database.link_oidc_subject`; OIDC configuration accepted with missing settings; multi-audience token accepted; missing operator `link-oidc` command; dashboard max length 120; RFC9068-invalid token type accepted; OIDC-mode teacher creation exposed obsolete pilot tokens. After implementing the requirements the same focused tests passed.

## Supported identity rules

- Opt-in `oidc` mode rejects all `cfcp_` pilot staff bearer tokens.
- Config pins RSA verification keys via an operator-supplied *local* public JWKS. Rejects absent/oversized/malformed sets, private signing keys, duplicate `kid`, and weak RSA keys.
- Explicit `RS256`, `typ=at+jwt`/`application/at+jwt`, issuer, *single* service audience, subject, client ID, JTI, issued/not-before/expiry, `amr` containing `mfa`, <=1 hour token lifetime.
- Unknown, duplicate, foreign-tenant, and revoked issuer+subject bindings cannot authenticate.
- Untrusted JWT role/email/tenant claims never grant local permissions. Local cohort access controls remain enforced by the same API.
- Device-upload tokens are a separate credential scheme; default `pilot` mode still passes older tests and should never be mistaken for enterprise authentication.

## Not verified or shipped

No real external IdP configured; no interactive Authorization Code + PKCE login, token renewal, refresh token handling, SSO browser redirection, automatic JWKS rotation, production TLS proxy, penetration test, real student data or production database deployment. Even a provider-asserted MFA claim needs independent provider policy verification.

GitHub CI results will be recorded separately after the pushed commit runs; local tests cannot stand in for them.
