# CHEMFORGE — strict $0 staging architecture decision (2026-10-13)

**Decision status (updated 2026-10-16): an empty dedicated Neon Free project exists and has external connections blocked. The backend and public API remain non-deployed and NOT production-approved.**
**Budget:** $0 cash per month, **no automatic paid upgrades or overage exposure**.

## Reference pattern inspected

MUSITU Education Nexus (not CHEMFORGE) has a GitHub Actions orchestration, Cloudflare Worker ingress, Modal Python execution, and Neon PostgreSQL database pattern in `evansmusitu/mft-education-nexus-executor`. Its deployment workflow depends on Nexus-specific GitHub secrets and an existing project-specific domain and database. **Reuse its architectural separation, NEVER reuse its Cloudflare/Modal/Neon identity, tokens, secrets, database, project files, domain, or production assertions.** Nexus' workflow definitions are evidence of an approach, not proof that it is free or that CHEMFORGE can operate on them.

## Chosen zero-cash path

1. **Today:** Keep CHEMFORGE Android's default APK fully offline. Keep the connected QA variant disabled outside synthetic CI. Use the current GitHub public repository and existing no-cost Actions checks for source and synthetic-device testing. This is the sole currently qualified deployment-related execution path.
2. **Optional public information page:** GitHub Pages can host *read-only*, reviewed documentation with no logins, student data, backend calls, cookies or exam-certification claims. Pages **cannot** host FastAPI/Postgres. Do not publish an admin dashboard or claim a live service.
3. **Optional private staging, after specific evidence:** Cloudflare Workers **Free** edge → isolated Modal Starter Python ASGI instance → a **new dedicated** Neon Free PostgreSQL project; deploy only after confirming zero-pay spend controls and separately qualifying a PostgreSQL adapter, migrations, restore procedure, HTTPS-proxy/canonical-origin behavior, rate limiting, and OIDC provider integration. Begin with synthetic-only records and restricted access. The Neon project has been allocated free, publicly blocked and verified empty (see NEON_SYNTHETIC_STAGING_v2.7.md). Cloudflare and Modal runtimes remain NOT deployed or enabled; no remotely accessible app is qualified.
4. **If any service demands payment/card/overages:** stop. Do not silently switch to a paid plan or assume promotional credits guarantee a $0 bill. Modal's $30 compute allowance is a credit, not a hard $0 invoice guarantee; usage or other services can cost money.

## Why nothing live was deployed

CHEMFORGE Control is currently **SQLite-backed**, with SQL and sessions bound to its local pilot database. Modal's scale-to-zero/restart model does not provide SQLite durability. Neon Free was reserved and deliberately locked; it is not yet connected to the app. A Neon connection is **not** a drop-in substitute; the schema, transactions, OIDC/browser sessions, tenants, migrations, backups and authorization checks must be ported and independently tested. Cloudflare Workers cannot directly run the current Python FastAPI/SQLite implementation. The staff OIDC flow has only synthetic IdP verification and is not provider-configured. Public exposure of this server is not authorized. No real student, institution, or teacher credentials can enter this environment.

## Required checks before a provider deployment

- Confirm accounts are on free tiers with no overage charges enabled, with an operator-confirmed hard spending stop where possible (particularly Modal); choose default providers' free subdomains, not a paid domain. Dedicated CHEMFORGE resources only.
- Complete a real PostgreSQL adapter and versioned reversible migrations; test tenant isolation and permission revocation on Postgres; confirm encrypted backups and an actual restore drill (Neon Free's instant-restore window alone is not a retention policy).
- Verify custom origin/scheme handling across Cloudflare → Modal for secure cookies/CSRF, reject forged forwarded headers, and validate the actual external OIDC provider's MFA/token profile. No real IdP is currently available.
- Put all secrets only in restricted provider/GitHub secret stores with least privileges. Never copy Nexus tokens or state. Do not use paid or public production data.
- Require separate independent security and privacy approval before allowing actual institutions, children, or unverified student score uploads.
- Android offline flavor must keep no `INTERNET` permission; connected QA flavor remains opt-in; imported study marks must remain explicitly **unverified**.

## Reproducible non-deploying check

`python tools/zero_budget_gate.py --contract deployment/zero_budget_contract.json`

Returns `PLAN_VALID_NOT_DEPLOYED` with exit 0 only for the exact safe, non-deployed plan. `--request-deploy` always exits 2. This is **not** a production deployment preflight or grant of release authority.

## Provider documentation (verified as of 2026-10-13)

- GitHub Pages Free for public repositories: https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages
- Cloudflare Workers Free: https://developers.cloudflare.com/workers/platform/pricing/ — limited requests/CPU, not a general always-on Python host.
- Neon Free: https://neon.com/blog/neon-free-plan-1-gb-per-project — published Oct 2, 2026; quotas and availability can change.
- Modal Starter: https://modal.com/pricing — $0 base plan plus compute, monthly credits; **overages are possible**. Do not enable without enforceable zero-spend controls.
