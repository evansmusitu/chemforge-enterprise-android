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

## Enterprise administration pilot (v1.5)

`control_plane/` now contains **CHEMFORGE Control**, a separate local/hosted FastAPI and SQLite service for institutional provisioning, teacher access, pseudonymous rosters, assignments, version registry metadata, audit logs and explicit import of Android JSON learning backups. It has its own testing workflow, `.github/workflows/control-plane-tests.yml`. Imported study evidence is always unverified; this control service does **not** grant high-stakes grades or provide automatic mobile/cloud sync.

See [control_plane/README.md](control_plane/README.md), [docs/RELEASE_v1.5.md](docs/RELEASE_v1.5.md), and [docs/VERIFICATION_v1.5.md](docs/VERIFICATION_v1.5.md). The Android APK remains the v1.4 debug release; **no new Android APK was built for the separate administration service**.


## CHEMFORGE Control institutional dashboard (v1.6)

The control-plane server now serves a self-contained school console at `http://127.0.0.1:8020/console` with in-memory credentials, admin/teacher role awareness, pseudonymous student registration, cohorts and counts, teacher issuance/revocation, assignments, explicit offline learning-backup import, curriculum metadata registration and audit views. Browser imports **never** certify study evidence. The Android v1.4 APK is unchanged.

**Local quickstart:**

```bash
python -m pip install -r control_plane/requirements.txt
python -m control_plane.cli bootstrap --db ./control.sqlite --tenant school-demo --admin-label "Admin"
CHEMFORGE_CONTROL_DB=./control.sqlite uvicorn control_plane.app:create_app --factory --host 127.0.0.1 --port 8020
# open http://127.0.0.1:8020/console
```

See [docs/RELEASE_v1.6.md](docs/RELEASE_v1.6.md) and [control_plane/README.md](control_plane/README.md). **Do not expose this pilot to the public internet or use it for real minors' records without production identity, consent/legal-basis, security and privacy work.**
