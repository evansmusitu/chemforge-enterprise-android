#!/usr/bin/env bash
# Offline study debug APK build. Execution requires Android SDK and Gradle 8.9.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
if ! command -v gradle >/dev/null; then
  echo 'BUILD_BLOCKED: Gradle 8.9 is not installed. Run the included GitHub Actions workflow or install a Gradle 8.9 toolchain.' >&2
  exit 2
fi
if [[ -z "${ANDROID_SDK_ROOT:-${ANDROID_HOME:-}}" ]]; then
  echo 'BUILD_BLOCKED: ANDROID_SDK_ROOT or ANDROID_HOME must reference Android SDK Platform 35.' >&2
  exit 2
fi
# Strict, deterministic on Android SDK hosts; no false APK success when compilation fails.
bash scripts/run_source_gates.sh
gradle :app:assembleDebug :app:lintDebug --no-daemon --stacktrace
bash scripts/verify_apk.sh app/build/outputs/apk/debug/app-debug.apk
printf '\nCHEMFORGE DEBUG APK: %s\n' "$ROOT/app/build/outputs/apk/debug/app-debug.apk"
