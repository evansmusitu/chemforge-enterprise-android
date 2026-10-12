# CHEMFORGE Enterprise v1.9 — Isolated HTTPS end-to-end qualification

The student remains offline-first; connected Android is still an explicit opt-in QA build. This release adds a **true HTTPS synthetic-staging integration gate**: a live FastAPI server on runner loopback, real Android emulator native HTTPS calls, per-student device tokens, a verified teacher analytics read and negative access-control checks. A synthetic one-day self-signed test cert is accepted only by the instrumentation process; default Android TLS rejects it. There is no TLS bypass in the shipping app.

## Proof architecture

1. GitHub runner generates a disposable staging database with two institution tenants, an assigned teacher, unassigned cohort, student and active/revoked/foreign device credentials. Synthetic only.
2. Runner creates an ephemeral RSA self-signed certificate with SAN IP addresses `127.0.0.1` and `10.0.2.2`, starts FastAPI under HTTPS on **127.0.0.1:443**, and runs host Python TLS tests. The Android emulator reaches host loopback through its special `10.0.2.2` alias.
3. The connected Android APK is built for `CHEMFORGE_SYNC_HOST=10.0.2.2`; neither its general WebView nor the default offline APK gains arbitrary web access. The test APK alone contains the temporary synthetic TLS cert and token fixture.
4. An instrumentation test confirms stock Android trust rejects the private test certificate, temporarily installs *only that test certificate* for HttpsURLConnection, and invokes **production `InstitutionSyncClient.upload`** for the synthetic backup. It asserts first upload, duplicate retry, rejected revoked token and foreign-tenant denial, then restores the original TLS trust manager.
5. A final independent HTTPS query checks that the assigned teacher sees exactly one **unverified** import; other institution cannot see that event.

## Restrictions

This is an **ephemeral GitHub-hosted staging environment**, not a permanently hosted staging URL and not an end-to-end UI consent-click test on a physical phone. It exercises production native HTTP transport but supplies synthetic backup bytes in instrumentation instead of driving the complete record-creation and consent dialogs. No real enrolment or public school data are present. It must not be used as evidence of production SSO, MFA, secure certificate issuance, privacy-policy acceptance, performance, or school deployment. Credentials are ephemeral and excluded from uploaded CI artifacts.

Before deployment with real student data: establish a school-operated HTTPS domain and trustworthy certificate, configure secure production build signing and provisioning, independently test Android UI consent on devices, implement robust identity/rate limiting, backup and database migrations, document privacy/legal basis, and complete expert-reviewed Chemistry content and AI validation.
