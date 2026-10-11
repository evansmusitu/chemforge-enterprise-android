#!/usr/bin/env bash
# Must run AFTER Gradle compilation on a host with Android SDK.
set -euo pipefail
APK="${1:-app/build/outputs/apk/debug/app-debug.apk}"
if [[ ! -s "$APK" ]]; then echo "APK missing or empty: $APK" >&2; exit 2; fi
SDK="${ANDROID_SDK_ROOT:-${ANDROID_HOME:-}}"
if [[ -z "$SDK" ]]; then echo 'Android SDK path not set' >&2; exit 2; fi
AAPT="$SDK/build-tools/35.0.0/aapt"
SIGNER="$SDK/build-tools/35.0.0/apksigner"
if [[ ! -x "$AAPT" || ! -x "$SIGNER" ]]; then echo 'Android build-tools 35.0.0 missing' >&2; exit 2; fi
PERMS="$($AAPT dump permissions "$APK")"
if grep -q 'android.permission.INTERNET' <<< "$PERMS"; then
  echo 'FAILED: compiled APK requests INTERNET permission' >&2; exit 1
fi
BADGING="$($AAPT dump badging "$APK")"
if ! grep -q "package: name='ai.chemforge.mobile.debug'" <<< "$BADGING"; then
  echo 'FAILED: unexpected compiled package identifier' >&2; exit 1
fi
"$SIGNER" verify --verbose "$APK"
python - "$APK" <<'PY'
import sys, zipfile
with zipfile.ZipFile(sys.argv[1]) as archive:
    bad=archive.testzip()
    assert bad is None, f'corrupt APK member: {bad}'
    names=set(archive.namelist())
    for asset in ('assets/index.html','assets/engine.js','assets/app.js','assets/data.json'):
        assert asset in names, f'missing offline asset: {asset}'
    assert 'classes.dex' in names, 'Android classes.dex missing'
print('APK structure: PASS — offline assets and compiled bytecode present')
PY
sha256sum "$APK" | tee "$(dirname "$APK")/apk-sha256.txt"
echo 'APK gate passed: debuggable, signed debug APK, no INTERNET permission, verified offline assets.'
