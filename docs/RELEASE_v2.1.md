# CHEMFORGE v2.1 enterprise hardening — synthetic qualification candidate

**2026-10-13. NOT a production deployment or certified educational release.**

## Staff browser sign-in (opt-in, fail-closed)

The old v2.0 server `CHEMFORGE_STAFF_AUTH=oidc` mode validates provider-signed RS256 `at+jwt` API access tokens through operator-pinned public JWKS. v2.1 adds a **separate opt-in** `CHEMFORGE_OIDC_BROWSER=enabled` server-side Authorization Code + PKCE (S256) flow, with operator-reviewed **local** OIDC provider discovery metadata, no runtime JWKS/discovery fetch, browser-binding cookie + one-use state, nonce-checked signed ID token, access token type/MFA/client/subject checks, and no automatic actor provisioning.

Staff API access in interactive mode uses an opaque **15-minute absolute-expiry, revocable `Secure; HttpOnly; SameSite=Lax; Path=/` session cookie** whose hash is stored in the server SQLite pilot database. Same-origin CSRF tokens and strict Origin validation protect mutations. Callback URLs contain no access tokens. No refresh tokens are requested or stored. Browser credentials are never placed into localStorage/sessionStorage, URL fragments, or JavaScript variables. Pasting provider bearer tokens is **disabled** in browser mode. The older bearer-only OIDC setting is retained for isolated API-pilot compatibility, not a general public sign-in solution.

**No real identity provider is configured, verified or connected.** The synthetic tests use generated RSA keys and a fake provider response; they do not contact an external service. Operators must obtain from their actual IdP and review the issuer, API audience, browser client ID, exact HTTPS callback URL, JWKS public verification file and vetted OIDC discovery JSON, and confirm that the provider issues `at+jwt` RS256 with MFA `amr` plus ID tokens with `nonce`. Provider metadata endpoints are restricted to the issuer's HTTPS origin; providers with different endpoint hosts require a separately reviewed change. Neither IdP policy, SSO operation nor credential lifecycle has been audited.

## Configuration (do NOT apply the example as real provider settings)

These are **names**, not valid example secrets or service endpoints:

```text
CHEMFORGE_STAFF_AUTH=oidc
CHEMFORGE_OIDC_BROWSER=enabled
CHEMFORGE_OIDC_ISSUER=<OPERATOR-VERIFIED HTTPS ISSUER>
CHEMFORGE_OIDC_AUDIENCE=<DEDICATED API AUDIENCE>
CHEMFORGE_OIDC_JWKS_FILE=<OPERATOR-PINNED PUBLIC-ONLY JWKS FILE>
CHEMFORGE_OIDC_DISCOVERY_FILE=<OPERATOR-REVIEWED JSON METADATA FILE>
CHEMFORGE_OIDC_BROWSER_CLIENT_ID=<REGISTERED BROWSER CLIENT ID>
CHEMFORGE_OIDC_REDIRECT_URI=<EXACT HTTPS ORIGIN>/auth/callback
```

Pinned metadata must contain `issuer`, `authorization_endpoint`, `token_endpoint`, `response_types_supported: ["code"]`, and `code_challenge_methods_supported: ["S256"]`. Token exchange uses a public PKCE client; **do not assume the IdP supports this registration profile**. Provider must issue accessible access tokens matching pinned verifier claims. Register the exact callback URL at the real provider only after organisational approval. Never put an IdP client secret, private signing key, staging credential or real student identifier into this public repository.

The ASGI server must see its canonical external **HTTPS scheme and host**, including behind an explicitly trusted TLS reverse proxy; otherwise login fails closed. Reject open forwarded-host and proxy-header spoofing. `__Host-` cookies require secure HTTPS. Browser-mode cookies do not make a public single-node SQLite pilot suitable for student data. The production deployment remains blocked.

## Institutional access and offline safety

- All session requests re-check local actor revocation and the exact pinned issuer-subject link; tenant and teacher-cohort checks remain in the existing API service. Server-side tests cover cross-school students, teacher cohort revocation, staff revocation, CSRF/origin violations, token injection, MFA, nonce and state replay.
- Android offline package remains untouched: **no `INTERNET` permission**, no network background sync; separate connected QA only, with explicit manual upload consent and revocable student-scoped credentials. Synthetic `.invalid` host still disabled for real uploads.
- Imported marks remain `unverified_import`, **never** certified grades, exam marks or externally validated learning mastery.

## Database and staging prerequisites (not completed production migrations)

SQLite now has additive tables for short-lived OIDC login transactions and server sessions, and newly created pilot database files are created with owner-only permissions. The offline `tools/staging_preflight.py --db <synthetic-sqlite-path> --synthetic-only` checks private file permissions, schema, foreign keys and integrity. It does not perform deployment, database conversion or backups.

**Before any authorised private synthetic staging:** review tenant composite foreign keys and DB migrations for PostgreSQL, secret/key rotation, schema versioning, transactional backup/restore drills, TLS ingress/proxy trust, rate limiting, session cleanup/expiry, audit log controls, encryption at rest, incident recovery, consent/retention controls, performance and independent threat modelling. Stage only with synthetic datasets and restricted ingress; do not reuse the SQLite pilot DB as production storage.

**Before any real student data:** obtain institutional permission and legal basis/child-data privacy review, production PostgreSQL migration evidence and rollback, IdP integration/MFA audit, independent penetration/security review, hosted endpoint and e2e device verification, signed Android release procedure, legitimate content licences/education review. No such evidence exists here.

See `VERIFICATION_v2.1.md` for tests and specific unverified gates.
