# CHEMFORGE Enterprise v1.8 — Opt-in connected client (qualification build)

The standard Android **debug/offline** APK is unchanged in network scope: **NO INTERNET permission**. New **connected** build type compiles separately with its own package identifier and INTERNET permission. Its WebView continues to deny all remote URLs; only the native upload client is network-capable.

## Manual upload flow

For a **managed institution** with `tenant_id`, `allow_data_export=true`, a connected APK built with a valid, actual `CHEMFORGE_SYNC_HOST`, and an administrator-issued device token:

1. The student learns and stores history locally, unchanged.
2. Journal > **Send unverified history** saves the current record into Android Keystore storage before continuing.
3. Native code rereads the encrypted file, checks tenant/content coherence and limits attempts to 1,000 and payload size to 2 MB.
4. The student enters a one-time-use-in-the-UI (not single-use on server) student-scoped **Device** bearer token in a native Android password field. The client **does not store** the token.
5. A second native confirmation discloses the institution server host, count, and **unverified** nature of study evidence.
6. One outbound HTTPS POST to the build-configured host's `/v1/sync/backups` endpoint. Redirects are denied, TLS validation uses Android system trust, 8s connect and 15s read timeout; no automatic retries.
7. The server idempotently imports unverified records, scoped to the device token's student and institution; local evidence is never deleted by sync.

`sync.example.invalid` is **intentionally disabled** and is used for CI QA only. Connected build must be signed, configured with a real institution-operated HTTPS host, and evaluated before deployment. The user-visible sync control remains absent in offline builds or where institution policy does not permit export.

## Security and limits

- This is **not automatic synchronisation**. The student must explicitly confirm every upload.
- A device token permits import for an individual student; it does not authenticate exam performance. Server records are `unverified_import` and cannot certify marks.
- The client never exposes tokens to JavaScript, localStorage, or server logs in application code; a token does temporarily exist in process memory while uploading.
- External web content is still blocked by WebView; no remote navigation or generic web requests.
- The server has **pilot-level authentication**, not production OIDC/MFA. No certificate pinning, background refresh or automatic credential rotation is supplied.
- This release is NOT institution-production-ready. It requires real HTTPS end-to-end testing, MDM policy review, consent/privacy assessment, penetration testing, Android real-device testing for the connected variant, and OIDC/MFA integration.

## Build

```
# Default offline build (no INTERNET permission)
gradle :app:assembleDebug
# Opt-in QA/deployment variant. Must provide an authorised DNS hostname.
CHEMFORGE_SYNC_HOST=sync.your-institution.edu gradle :app:assembleConnected
```

`connected` is a debug-signed QA build type, not a production release. Never place live device tokens into the repository or build environment.
