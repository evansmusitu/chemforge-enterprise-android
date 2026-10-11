#!/usr/bin/env bash
# Runs only when an Android SDK/emulator is available, e.g. Actions emulator job.
set -euo pipefail
APK="${1:-app/build/outputs/apk/debug/app-debug.apk}"
[[ -f "$APK" ]] || { echo "Missing compiled APK: $APK" >&2; exit 2; }
command -v adb >/dev/null || { echo 'adb unavailable' >&2; exit 2; }
PKG='ai.chemforge.mobile.debug'
adb install -r "$APK"
adb shell cmd connectivity airplane-mode enable >/dev/null
MODE="$(adb shell settings get global airplane_mode_on | tr -d '\r')"
[[ "$MODE" == "1" ]] || { echo "Offline gate failed: airplane mode is $MODE, expected 1" >&2; exit 1; }
adb shell am force-stop "$PKG" || true
adb logcat -c
adb shell am start -n "$PKG/ai.chemforge.mobile.MainActivity" >/dev/null
sleep 8
adb shell pidof "$PKG" >/dev/null || { echo 'Android process exited immediately' >&2; adb logcat -d -t 250; exit 1; }
if adb logcat -d -t 500 | grep -A6 'FATAL EXCEPTION' | grep -q "${PKG}"; then
  echo 'App fatal exception' >&2
  exit 1
fi
adb shell screencap -p /sdcard/chemforge-smoke.png
adb pull /sdcard/chemforge-smoke.png /tmp/chemforge-smoke.png >/dev/null
echo 'Android emulator smoke: airplane mode confirmed; application process survives offline launch; screenshot saved to /tmp/chemforge-smoke.png'
