# Build CHEMFORGE Enterprise Android 1.1-alpha

## Prerequisites

- JDK 21, Android SDK platform 35/build-tools 35.0.0, Gradle 8.9, Android Gradle Plugin 8.7.3, Kotlin plugin 2.3.0.
- Python 3.10+ with `cryptography` to sign institutional content packs.
- A trusted publisher-controlled ECDSA P-256 private signing key, stored **outside** the app/repository/CI source. For example, an isolated publisher workstation or HSM.

## Make the offline content publisher key (example only)

Generate the key on the authorised publisher's secure computer:

```bash
openssl ecparam -name prime256v1 -genkey -noout -out publisher-ec-private.pem
openssl pkcs8 -topk8 -nocrypt -in publisher-ec-private.pem -out publisher-private-pkcs8.pem
openssl pkey -in publisher-private-pkcs8.pem -pubout -out publisher-public.pem
```

**Production keys need appropriate encryption at rest, access controls and rotation procedures.** Do not commit these private files.

To calculate the public key input used by the Android build:

```bash
openssl pkey -pubin -in publisher-public.pem -outform DER | base64 -w0
```

Put the resulting string in the build secret `CHEMFORGE_PACK_PUBLIC_KEY_BASE64`. It's a **public** verification key; safe to distribute within the APK. Never use a private key here.

To sign a structured corpus (use authentic institution-owned, independently reviewed content):

```bash
python tools/content_pack.py sign --content institution-content.json \
  --private-key publisher-private-pkcs8.pem --output institution-v1.cfpack \
  --tenant institution-123 --version 1
python tools/content_pack.py verify --pack institution-v1.cfpack \
  --public-key publisher-public.pem --tenant institution-123
```

Pack members are `manifest.json`, `content.json`, `signature.der`. The signed manifest contains the institution ID, monotonically increasing integer `pack_version`, content version, and exact SHA-256 of `content.json`. `content.json` must follow the existing `data.json` objective/question schema. The included default pack is **not** expertly verified.

## Local model approval

Hash the exact `.litertlm` model artifact intended for the institution:

```bash
sha256sum institution-approved.litertlm
```

Supply the 64-character lowercase hex digest as `CHEMFORGE_APPROVED_MODEL_SHA256` at Android compile time. Models are not bundled by default. A different model file, even if similarly named, is rejected.

## Offline tests (without Android SDK)

```bash
python -m pip install cryptography
node --test tests/engine.test.cjs tests/coach.test.cjs
python -m unittest discover -s tests -p 'test_*.py'
mkdir -p /tmp/cf-java
javac -d /tmp/cf-java app/src/main/java/ai/chemforge/mobile/SignedContentVerifier.java tests/ContentVerifierHarness.java
java -cp /tmp/cf-java ContentVerifierHarness
python tests/check_package.py
python tests/browser_smoke.py # Requires playwright + Chromium
```

## Secure offline study history

On Android, v1.1 uses nonexportable AndroidKeyStore AES-256-GCM encryption rather than JavaScript localStorage. The app automatically migrates earlier plaintext records and only deletes them if the new encrypted save succeeds. Untrusted JSON imports do not count toward demonstrated mastery. See [`SECURE_STUDY_STORAGE.md`](SECURE_STUDY_STORAGE.md).

Run all source-level checks on a machine with Node, Python, Java and Chromium/Playwright:

```bash
bash scripts/run_source_gates.sh
```

## APK from Android SDK / GitHub Actions

```bash
export CHEMFORGE_PACK_PUBLIC_KEY_BASE64="$(openssl pkey -pubin -in publisher-public.pem -outform DER | base64 -w0)"
export CHEMFORGE_APPROVED_MODEL_SHA256="$(sha256sum institution-approved.litertlm | awk '{print $1}')"
gradle :app:assembleDebug :app:lintDebug --no-daemon
bash scripts/verify_apk.sh app/build/outputs/apk/debug/app-debug.apk
```

Expected debug output: `app/build/outputs/apk/debug/app-debug.apk`. The workflow `.github/workflows/android-debug-apk.yml` performs these checks on supported GitHub runners and uploads its debug APK only after success.

The compiled APK verification additionally rejects an INTERNET permission, checks its debug signature and package ID, verifies offline assets are embedded, and writes `apk-sha256.txt`.

**Not a production release:** Android app signing with a protected app-signing key, Play/App Distribution review, accessibility, device security testing and all product qualification remain outstanding. Do not ship debug keys to enterprises.
