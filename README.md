# CHEMFORGE Enterprise Android v1.4-alpha

An **offline-first Android Chemistry revision prototype**, with optional on-device LiteRT-LM tutoring and source-level institutional controls. Not an official ZIMSEC application, not scientifically validated, and not a secure high-stakes examination platform.

**This is an Android source tree.** A previous v1.3 debug APK has passed Android compilation and emulator offline smoke, but v1.4 modifications require a new CI build and emulator check. A debug APK is not suitable as a production-signed enterprise release.

## Current features

- 44 original unreviewed pilot questions, 28 provisional competencies and 28 short editorial lessons.
- Offline learning, adaptive practice, multiple-choice and numeric auto-marking, written-response self-review, short timed mock drills, a competency map and learning history.
- Optional model import, SHA-256 model approval, LiteRT-LM CPU inference integration, memory-aware loading and unloading; **actual model inference on a device is still untested**. AI never awards marks.
- Per-institution and content-fingerprint scoped local records protected with Android Keystore AES-256-GCM in the Android app.
- Publisher-signed `.cfpack` curriculum packages, monotonic content pack version checks and trust-key pinning.
- v1.4: compile-time required enterprise enrollment option, fail-closed managed permissions, separate backup-import policy, and race-safe policy recheck during model import.
- v1.4: source tests and real Android instrumentation test sources, combined with an emulator gate (not yet executed).

## Run source gates

Requires Java 21, Node.js, Python, Playwright Chromium and the Python `cryptography` dependency as configured in `scripts/run_source_gates.sh` / `.github/workflows/android-debug-apk.yml`.

```bash
bash scripts/run_source_gates.sh
```

## Compile the debug APK

Requires JDK 21, Android SDK Platform 35, Android Build Tools 35.0.0, Gradle 8.9 and access to pinned dependencies (including Google Maven LiteRT-LM 0.17.1).

```bash
bash scripts/build_debug_apk.sh
```

On a compatible build host, this creates `app/build/outputs/apk/debug/app-debug.apk`, runs Android lint and verifies APK structure, signing and the absence of INTERNET permission. This file **does not exist** in the provided ZIP.

To build in GitHub Actions, place the files at the root of a **new repository dedicated to CHEMFORGE** and run the `Verify and build CHEMFORGE Enterprise v1.4` workflow. After a successful run, the 14-day workflow artifact contains the debug APK. Run `Android Emulator Offline Functional Gate` for emulator and instrumentation tests before sharing a beta build.

## Enterprise provisioning

Build with `CHEMFORGE_REQUIRE_PROVISIONING=true` and an authorised `CHEMFORGE_PACK_PUBLIC_KEY_BASE64` to enforce institutional enrolment. A managed device cannot enable local AI, import/export records or install content unless it has a valid tenant and the necessary restrictions are explicitly granted. See [docs/ENTERPRISE_PROVISIONING_v1.4.md](docs/ENTERPRISE_PROVISIONING_v1.4.md).

## Validation and limitations

Read [docs/RELEASE_v1.4.md](docs/RELEASE_v1.4.md) and [docs/VERIFICATION_v1.4.md](docs/VERIFICATION_v1.4.md). This release does not include a cloud administration server, verified complete curriculum, production signing, or device performance measurements from an actual running model. See `docs/ON_DEVICE_AI_DIAGNOSTICS_v1.4.md`.
