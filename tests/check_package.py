"""Reproducible non-SDK checks for the Android source package."""
from pathlib import Path
import json
import re
import xml.etree.ElementTree as ET

BASE=Path(__file__).resolve().parents[1]
assets=BASE/'app/src/main/assets'
seed=json.loads((assets/'data.json').read_text())
js=(assets/'data.js').read_text()
assert js.startswith('/* Original unreviewed editorial pilot')
assert json.loads(js.split('window.CF_DATA=',1)[1].rsplit(';',1)[0]) == seed
assert len(seed['questions'])==44 and len(seed['objectives'])==28
assert all(q['review_status']=='unreviewed' for q in seed['questions'])
assert seed['scope']=='limited_editorial_pilot_not_full_syllabus'
manifest=(BASE/'app/src/main/AndroidManifest.xml').read_text()
ET.fromstring(manifest)
assert '<uses-permission android:name="android.permission.INTERNET" tools:node="remove" />' in manifest
assert 'android:allowBackup="false"' in manifest
source=(BASE/'app/src/main/java/ai/chemforge/mobile/MainActivity.java').read_text()
assert 'setAllowFileAccess(false)' in source
assert 'setDomStorageEnabled(true)' in source
assert 'setJavaScriptEnabled(true)' in source
assert "connect-src 'none'" in source
assert 'MAX_BACKUP_BYTES = 2_000_000' in source
assert 'ACTION_CREATE_DOCUMENT' in source and 'ACTION_OPEN_DOCUMENT' in source
assert set(re.findall(r'"(index\.html|styles\.css|data\.js|engine\.js|coach\.js|lessons\.js|mock\.js|app\.js)"',source))=={
    'index.html','styles.css','data.js','engine.js','coach.js','lessons.js','mock.js','app.js'}
workflow=(BASE/'.github/workflows/android-debug-apk.yml').read_text()
assert 'run: bash scripts/build_debug_apk.sh' in workflow and 'upload-artifact@v4' in workflow
assert 'gradle :app:assembleDebug :app:lintDebug' in (BASE/'scripts/build_debug_apk.sh').read_text()
assert 'build-tools;35.0.0' in workflow
print('Android source checks: PASS — 44/28 content, original seed parity, valid manifest, offline policy, backup boundary, workflow.')

model=(BASE/'app/src/main/java/ai/chemforge/mobile/OfflineModelHost.kt').read_text()
assert 'com.google.ai.edge.litertlm.Engine' in model
assert 'Backend.CPU()' in model
assert 'StatFs' in model and 'SHA-256' in model and 'REPLACE_EXISTING' in model
assert 'File(context.filesDir,' in model and 'newFixedThreadPool' not in model
assert 'modelHost.ask' in source and 'modelHost.install' in source
assert 'JSONObject.quote(payload)' in source
assert '"coach.js"' in source
assert "0.17.1" in (BASE/'app/build.gradle').read_text()
assert "id 'org.jetbrains.kotlin.android'" in (BASE/'build.gradle').read_text()
assert "java-version: '21'" in workflow
print('On-device AI source checks: PASS — bridge, constrained import, pinned LiteRT-LM, offline policy.')

# Constrained device operation: explicit headroom check and controllable model lifetime.
assert 'ActivityManager.MemoryInfo' in model and 'availMem' in model and 'lowMemory' in model
assert 'MIN_AVAILABLE_BYTES' in model
assert 'maxOutputToken = 160' in model
assert 'modelHost.release()' in source
assert 'onTrimMemory' in source
assert 'CHEMFORGE Enterprise Android' in (BASE/'README.md').read_text()
assert 'APPROVED_MODEL_SHA256' in (BASE/'app/build.gradle').read_text()
print('4 GB protection checks: PASS.')

# v1.1: AndroidKeyStore envelope is the only production storage path on Android.
cipher=(BASE/'app/src/main/java/ai/chemforge/mobile/RecordCipher.java').read_text()
record=(BASE/'app/src/main/java/ai/chemforge/mobile/AndroidRecordStore.java').read_text()
ui=(assets/'app.js').read_text()
engine=(assets/'engine.js').read_text()
assert 'AES/GCM/NoPadding' in cipher and 'updateAAD' in cipher
assert 'cipher.init(Cipher.ENCRYPT_MODE,key);' in cipher and 'cipher.getIV()' in cipher
assert 'RANDOM.nextBytes(iv)' not in cipher and 'cipher.init(Cipher.ENCRYPT_MODE,key,new GCMParameterSpec' not in cipher
assert 'AndroidKeyStore' in record and 'AES' in record and 'ATOMIC_MOVE' in record
assert 'loadRecords' in source and 'saveRecords' in source
assert 'nativeRecordStore' in ui and 'if(storageLocked)' in ui
assert ",'external'" in ui and "unverified_import" in engine
assert 'scripts/verify_apk.sh' in (BASE/'scripts/build_debug_apk.sh').read_text()
print('Enterprise secure storage checks: PASS — AndroidKeyStore, AES-GCM, no plaintext native persistence, imported-evidence discipline.')
