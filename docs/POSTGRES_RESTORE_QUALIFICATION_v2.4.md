# CHEMFORGE Enterprise v2.4 — PostgreSQL native restore drill (strictly synthetic)

**2026-10-13 · qualification only · NOT DEPLOYED · NOT PRODUCTION READY**

## Scope and architectural continuity

The v2.3 adapter remains permitted **only** against the disposable PostgreSQL 17
service running on the GitHub Actions runner at `127.0.0.1:5432`, after an
explicit synthetic-only acknowledgement. The default production-facing API is
**not enabled**. No CHEMFORGE Neon database, Cloudflare Worker, Modal workload,
OIDC provider or real student-data service is provisioned or exercised here.
The $0-only `deployment/zero_budget_contract.json` remains unchanged.

This milestone adds an **actual** PostgreSQL-native custom-format `pg_dump` to
`pg_restore` round-trip in the existing ephemeral GitHub CI service container,
using two distinct disposable databases. Unlike an export/import mock, this
checks whether the schema and test records can be restored into an empty target.

The CI steps do the following, in strict order:

1. Execute existing PostgreSQL 17 API regressions with two *synthetic* schools,
   default-deny teacher cohort rules, revocations and unverified student marks.
2. Create a second empty disposable database (`chemforge_synthetic_restore`)
   owned by the synthetic test role. Preflight rejects missing CI acknowledgement,
   remote/Neon DSNs, unintended names/credentials and any preexisting tables.
3. Run `pg_dump --format=custom --no-owner --no-acl` using the PostgreSQL 17
   service image's own utility; save the archive to a private (`umask 077`),
   temporary runner file. **Never publish this archive as an Actions artifact.**
4. Run `pg_restore --single-transaction --exit-on-error --no-owner --no-acl`
   into the separate database with no `--clean`, no `--create`, and no drop.
5. Independently compare the inventories of **13 tables**, versioned schema
   checksum, per-table deterministic row fingerprints, constraints and index
   definitions between original and restored databases. Reject mismatches.
6. Erase the runner archive in an `if: always()` cleanup step. CI containers
   are disposable and not configured for long-term backups.

No username, password, token, DSN or student payload is printed by the checker;
only the status, table count and synthetic row count are reported.

### Reproducible checks

Local (no PostgreSQL required):

```bash
python -m pytest -q tests/control_plane tests/deployment tests/postgresql/test_postgres_contract.py tests/postgresql/test_pg_restore_v24.py
python tools/zero_budget_gate.py --contract deployment/zero_budget_contract.json
python -m compileall -q control_plane tools/postgres_restore_drill.py
```

The full PostgreSQL-native restore check is automatically executed by the
`.github/workflows/postgres-synthetic-qualification.yml` workflow on source
changes. It uses only non-reusable synthetic CI credentials and GitHub's
PostgreSQL container. The application does **not** gain network access or
staging authorisation through this check.

### Security boundaries / what was NOT qualified

- This is a **single-run** recoverability smoke test, not a scheduled encrypted
  production backup, regional replication, retention policy, point-in-time
  recovery, or disaster-recovery SLA.
- The synthetic adapter deliberately refuses hosted PostgreSQL and does not
  qualify Neon authentication, TLS, pooling, migrations of real data, live
  concurrency, secret rotation, least-privilege roles or multi-instance locking.
- The check compares data and schema metadata for small synthetic datasets;
  it does not prove restore performance on large databases.
- Real staff OIDC provider/MFA, HTTPS proxy trust, institutional privacy and
  child-data authorisation, independent penetration testing, and release signing
  remain genuine external blockers. Do not claim them complete.
- Offline default Android APK has **no INTERNET permission**. The separate
  connected QA APK retains manual consent and student-scoped revocable tokens;
  imported marks remain **unverified**, never certified ZIMSEC results.

**Next safe work:** independently review tenant locks/concurrency, devise
versioned reversible PostgreSQL production migrations, verify no-overage
provider account controls and private synthetic hosted staging. Do not deploy
or enter real students until these and operational/legal gates are met.
