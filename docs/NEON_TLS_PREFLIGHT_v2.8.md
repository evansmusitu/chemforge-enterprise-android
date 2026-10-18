# CHEMFORGE v2.8: locked-Neon TLS connection profile (offline dry run)

**2026-10-18. Not a deployed API, migration, student-data environment, or SSO qualification.**

## Scope and provider state

A live, authenticated provider metadata read on 2026-10-18 confirmed the dedicated
CHEMFORGE project `delicate-haze-29026531` remained on Neon's `free_v3` plan,
with **public database connections blocked** and a 0.25 CU compute ceiling. The
project remains isolated from MUSITU Education Nexus projects and credentials.
The historical **empty table** observation was obtained on 2026-10-16, before
blocking public access; because the provider blocks SQL connections from this
network now, the absence of tables cannot be re-attested on 2026-10-18.

No hosted runtime, direct database connection, real institutional IdP, student
fixture, deploy action, or billing-plan modification took place in v2.8.

## Transport preflight: profile validation, NOT a connection

`tools/neon_tls_preflight.py` checks a *candidate future* DSN without
connecting or logging credentials. It is a **dry run** that never makes a
production/staging admission decision. It expects a dedicated CHEMFORGE
synthetic role and database, the observed Neon AWS region and proxy class,
explicit port 5432, `sslmode=verify-full`, and `sslrootcert=system`.
It blocks malformed URL structures, weaker TLS modes, duplicate or extra
query parameters, reused Nexus role/database, unexpected DNS suffixes,
and changed $0 or historical locked-project safety contracts.

The profile is not evidence that the DNS name belongs to *our* Neon project,
that libpq in the final runtime supports system CAs, or that a real certificate
has been verified. A syntactically valid profile is **not** evidence of an
operational TLS link, and the existing `postgres_synthetic` runtime still
**rejects every remote database hostname**.

Example for tests only, never use as an actual credential:

```bash
export CHEMFORGE_NEON_TLS_DRY_RUN_DSN='postgresql://chemforge_synthetic:FAKE_NONSECRET_TEST_ONLY@ep-chemforge-example.c-7.us-east-2.aws.neon.tech:5432/chemforge_synthetic?sslmode=verify-full&sslrootcert=system'
python -m tools.neon_tls_preflight
unset CHEMFORGE_NEON_TLS_DRY_RUN_DSN
```

The resulting `TLS_PROFILE_VALID_NOT_CONNECTED` is only a static test pass;
`deployment_allowed`, `public_api_enabled`, `certificate_verified`, and
`real_student_data_allowed` remain false. The CLI returns exit 2 when the
environment variable is absent or the input is unsafe. **Never place an
actual DSN in a command-line argument, CI source, or handoff archive.**

## Next gates (not fulfilled here)

1. Independently verify a hard $0 budget boundary for the entire provider stack.
   Neon Free usage suspends/fails at quota, but that does **not** establish
   zero-overage limits for separate hosting services. No Modal or Cloudflare
   compute runtime was deployed.
2. Decide and audit the *operator-controlled* access path to the locked database.
   Do not unblock public connections merely to get green CI. This stage requires
   secret isolation, least-privilege roles, network allowlisting/private path,
   genuine TLS `verify-full` trust and bound Neon project/branch identity.
3. Design and qualify versioned migrations, checksums, backup/restore and
   error handling on an approved **synthetic** remote environment.
4. Configure and audit institutional OIDC with MFA, proxy trust, rate limiting,
   retention, consent/privacy governance and independent security review **before**
   any student data or institutional launch.
5. Keep the original offline Android APK without `INTERNET`; connected QA
   remains a distinct manual-consent release. Imported evidence remains
   `unverified_import`, not certified grades.

Provider Free pricing is subject to the provider's current terms. The account
plan is currently Free; the 0.25 CU ceiling reduces usage, but is not a
service-level availability or security guarantee.
