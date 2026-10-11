# CHEMFORGE Enterprise v1.5-alpha — Control Plane Pilot

## Scope

Added a separately operated FastAPI/SQLite institutional administration service. It provides tenant-scoped staff identities, rosters, assignments, offline backup ingestion, de-identified cohort activity counts, content release metadata, scoped audit logs and student erasure. The Android application source is retained from v1.4; there is **no new Android runtime release or rebuilt APK in this change**.

## Academic and security boundaries

Imported Android JSON is not secure exam evidence. Every imported item is labelled `unverified_import`; verified report count stays zero. Content release hashes constitute registry metadata only; no claim of actual publisher signature verification or educational review. The service is a research/pilot component, **not production-certified enterprise software**.

The user reported a successful physical Android test; this does not independently establish model compatibility, curriculum accuracy or performance across devices. Reference `control_plane/README.md` for provisioning and pilot restrictions.

## Next gates

1. Produce institution-controlled teacher/staff SSO with MFA, class-level RBAC and privacy review.
2. Implement a verified signed batch handoff and an explicit, consent-aware sync protocol without changing the student's offline requirement.
3. Obtain independent Chemistry/content expert review and model inference benchmark data.
4. Run representative school pilot and load/recovery/security testing, then migrate to a production database.
