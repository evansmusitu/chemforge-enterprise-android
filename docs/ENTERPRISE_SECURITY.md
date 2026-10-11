# CHEMFORGE Android Enterprise 1.0-alpha — security and trust

## Implemented offline boundaries

- `AndroidManifest.xml` explicitly removes `INTERNET`, disables auto backup, and prohibits cleartext traffic.
- WebView serves a local allowlist of assets via a virtual HTTPS origin; file access, remote fetches, remote navigation, frames, and network connections are blocked by configuration/CSP.
- Student progress persists in WebView localStorage on the Android device. It is **not application-encrypted** beyond Android's normal app sandbox and device storage protections. Treat exports as sensitive records; managed policy may disable them.
- Curricula enter through Android Storage Access Framework. ZIP content is bounded, has exactly three allowlisted members, is SHA-256 bound to its manifest, and uses ECDSA P-256 signatures verified against an APK-pinned public key.
- The app does not embed a private signing key. Missing pinned public keys cause content imports to fail closed.
- Content importer validates mapped objectives/questions, tenant policy, positive package revision, and monotonic revision numbers. The WebView receives parsed JSON rather than executable code from the package.
- An institutional pack stores a content fingerprint in assessment records. Attempts from different institutions, versions, or hashes are rejected on backup import.
- The native JavaScript bridge enforces administrator policy for local AI, curriculum import, and student record export regardless of frontend controls.
- Imported LiteRT-LM files must match the exact SHA-256 digest configured at build time; the model is rehashed before first load per runtime lifecycle. Without an approved digest, inference and model installation fail closed.

## Managed configuration keys

Define managed app restrictions using `app/src/main/res/xml/app_restrictions.xml`:

| Key | Meaning | Unmanaged default |
| --- | --- | --- |
| `tenant_id` | Institution identifier; restricts content imports/backup scope | empty (standalone) |
| `enable_local_ai` | Allow local model import/inference | true, but requires approved hash |
| `allow_data_export` | Allow SAF JSON learning record exports | true |
| `allow_content_import` | Allow SAF signed institution pack installation | true, but requires pinned public key |

The app re-reads policies on foreground/resume and listens for restrictions change broadcasts while active. An invalid tenant string disables AI, exports and imports.

## Limitations / security gates before enterprise production

1. APK is not yet compiled or tested on physical Android devices in this environment. SDK/Gradle must build and tests must pass in CI.
2. Trust key rotation/revocation, long-term anti-rollback under backup/restore/compromised devices, and concurrent pack installation across administrative profiles require a transactional deployment design and a threat-model review.
3. WebView `localStorage` is not a multi-user secure database. Production requires explicit learner identity, encryption at rest where appropriate, retention policy, and per-user isolation.
4. No server, user directory, cloud sync, analytics pipeline, EMM certification, compliance audit, or high-stakes exam security is implemented.
5. Cryptographic signature verifies *publisher authority and file integrity only*. It is not scientific content accuracy validation or ZIMSEC endorsement.
6. Model content and responses are unvalidated scientifically. LLM suggestions cannot mark exams or modify scores.
7. Commercial use requires licensing review of the app, the model, and educational materials, and appropriate student privacy and safeguarding measures.
