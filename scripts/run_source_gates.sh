#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
node --test tests/*.test.cjs
python -m unittest discover -s tests -p 'test_*.py'
mkdir -p /tmp/chemforge-java-gates
javac -d /tmp/chemforge-java-gates \
    app/src/main/java/ai/chemforge/mobile/SignedContentVerifier.java tests/ContentVerifierHarness.java \
    app/src/main/java/ai/chemforge/mobile/RecordCipher.java tests/RecordCipherHarness.java \
    app/src/main/java/ai/chemforge/mobile/EnterpriseEntitlements.java tests/EntitlementsHarness.java
java -cp /tmp/chemforge-java-gates ContentVerifierHarness
java -cp /tmp/chemforge-java-gates RecordCipherHarness
java -cp /tmp/chemforge-java-gates EntitlementsHarness
python tests/check_package.py
python tests/browser_smoke.py
python tests/secure_storage_smoke.py
node --check app/src/main/assets/app.js
bash -n scripts/verify_apk.sh
