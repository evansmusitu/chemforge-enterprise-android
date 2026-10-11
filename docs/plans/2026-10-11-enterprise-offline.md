# Enterprise Offline Foundation Implementation Plan

> **For agentic workers:** Use the host's available task-by-task implementation workflow. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Extend the existing CHEMFORGE Android offline prototype with cryptographically authenticated institution-specific content packs, on-device enterprise policy enforcement, and version-safe student progress.

**Architecture:** Keep the existing WebView and LiteRT-LM implementation, and add a native Android policy and content import boundary. Sign the exact offline pack manifest using P-256 ECDSA, hash the content, enforce tenant and anti-rollback restrictions in the native layer, then expose only validated JSON to the offline WebView. Bind recorded learner attempts to content versions.

**Tech Stack:** Android Java/Kotlin, WebView, Java Security ECDSA, Python cryptography for publisher CLI, Node built-in test runner, GitHub Actions.

## Global Constraints

- Remain offline; no INTERNET permission.
- No shipped private keys; absent public key disables signed imports.
- Treat signature validation as provenance/authorization, not Chemistry expertise verification.
- Stronger enterprise restrictions must be enforced in the native bridge.
- Never label source-only artifacts as installable APKs.

---

### Task 1: Version-bound learner evidence

**Files:** Modify `app/src/main/assets/engine.js`, `app/src/main/assets/app.js`; test `tests/engine.test.cjs`.

**Interfaces:** Consumes `content.content_version`, attempts and backup format. Produces `safeImport(raw, content)` accepting only matching content attempts (legacy pilot permitted only on pilot).

- [x] Add test rejecting attempts from other content versions and preserving pilot backups.
- [x] Observe expected failing assertions with `node --test tests/engine.test.cjs`.
- [x] Add version field to future attempts, enforce version on import.
- [x] Rerun focused tests and affected JS suite.

### Task 2: Offline pack authenticity and delivery

**Files:** Create `app/src/main/java/ai/chemforge/mobile/SignedContentVerifier.java`, `EnterprisePackManager.java`, `tools/content_pack.py`; modify `MainActivity.java`, `index.html`; test `tests/ContentVerifierHarness.java`, `tests/test_content_pack.py`.

**Interfaces:** Inputs are a ZIP with exactly `manifest.json`, `content.json`, and `signature.der`. `manifest.json` is signed by trusted P-256 public key; `content.json` SHA-256 must match manifest; `EnterprisePackManager.install(Uri,tenant)` installs atomically. Produces a WebView-local JS asset containing only escaped JSON.

- [x] Write signature-tamper tests and Python packaging validation tests.
- [x] Observe red failure before implementation.
- [x] Implement publisher CLI with private key supplied externally and exact manifest signature.
- [x] Implement bounded ZIP import, signature and tenant validation, atomic private install and WebView content switching.
- [x] Verify focused tests using JDK and Python and regenerate research fixture.

### Task 3: Managed enterprise controls

**Files:** Create `ManagedPolicy.java`, `app/src/main/res/xml/app_restrictions.xml`; modify `AndroidManifest.xml`, `MainActivity.java`, `app.js`, `index.html`; test `tests/check_package.py`, `tests/test_content_pack.py`.

**Interfaces:** `tenant_id`, `enable_local_ai`, `allow_data_export`, `allow_content_import` from Android managed restrictions; native bridges enforce restrictions even when WebView JS calls directly.

- [x] Add source-contract tests requiring native policy guards.
- [x] Observe failing tests before implementation.
- [x] Add managed restrictions XML and update policy at resume / on-change, with read-only UI status.
- [x] Verify policy guard tests and UI smoke checks.

### Task 4: Release verification and delivery

**Files:** Modify `.github/workflows/android-debug-apk.yml`, `README.md`, `docs/BUILD_AND_RELEASE.md`; create `docs/ENTERPRISE_SECURITY.md`, `docs/VERIFICATION_v1.0.md`.

**Interfaces:** `python tools/content_pack.py sign` / `verify` and `gradle :app:assembleDebug`, with expected debug APK only after successful CI; no production signing key embedded.

- [x] Add test commands to workflow and document key handling.
- [x] Run all available tests, syntax checks, content integrity and zip extraction checks.
- [x] Record whether actual SDK compilation and phone validation ran.
- [x] Package a reproducible source ZIP with recorded checksum.
- [ ] Verify the APK compiles with a real Android SDK and run Android device instrumentation (blocked in this environment).

## Decisions

Offline content import requires the distributor's pinned public key at build time. Managed restrictions default to allowing local study, model import and backup export; institutions may disable model, import and export. Incompatible content versions do not share mastery evidence. No networking or background sync is introduced in this release.
