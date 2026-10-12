#!/usr/bin/env bash
# Ensures only the explicit connected APK has network capability.
set -euo pipefail
APK="${1:-app/build/outputs/apk/connected/app-connected.apk}"
test -s "$APK" || { echo "Missing connected QA APK: $APK" >&2; exit 2; }
SDK="${ANDROID_SDK_ROOT:-${ANDROID_HOME:-}}"
AAPT="$SDK/build-tools/35.0.0/aapt"
SIGNER="$SDK/build-tools/35.0.0/apksigner"
test -x "$AAPT" && test -x "$SIGNER"
"$AAPT" dump permissions "$APK" | grep -q 'android.permission.INTERNET' || {
  echo 'Connected variant must explicitly request INTERNET permission' >&2; exit 1;
}
"$AAPT" dump badging "$APK" | grep -q "package: name='ai.chemforge.mobile.connected'" || {
  echo 'Unexpected connected QA application identifier' >&2; exit 1;
}
"$SIGNER" verify --verbose "$APK"
python - "$APK" <<'PY'
import sys,zipfile
with zipfile.ZipFile(sys.argv[1]) as a:
    assert a.testzip() is None
    for name in ('assets/index.html','assets/app.js','classes.dex'):
        assert name in a.namelist(),name
print('Connected variant: compiled resources and signature verified')
PY
sha256sum "$APK" | tee "$(dirname "$APK")/connected-sha256.txt"
echo 'Connected QA manifest verified; REAL SERVER TRANSFER IS NOT YET TESTED.'
