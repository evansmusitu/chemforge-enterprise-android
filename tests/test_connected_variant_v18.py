"""v1.8 connected opt-in contract; deliberately fail against v1.7 source."""
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
class ConnectedSyncVariantTests(unittest.TestCase):
    def test_offline_manifest_remains_networkless(self):
        manifest=(ROOT/'app/src/main/AndroidManifest.xml').read_text()
        self.assertIn('android.permission.INTERNET" tools:node="remove"',manifest)
        self.assertIn('connect-src \'none\'', (ROOT/'app/src/main/java/ai/chemforge/mobile/MainActivity.java').read_text())

    def test_separate_connected_build_has_network_permission(self):
        target=ROOT/'app/src/connected/AndroidManifest.xml'
        ET.parse(target)
        self.assertIn('android.permission.INTERNET',target.read_text())
        build=(ROOT/'app/build.gradle').read_text()
        self.assertIn('connected {',build)
        self.assertIn('SYNC_CONNECTED',build)
        self.assertIn('CHEMFORGE_SYNC_HOST',build)

    def test_sync_is_native_opt_in_with_pinned_destination(self):
        source=(ROOT/'app/src/main/java/ai/chemforge/mobile/InstitutionSyncClient.java').read_text()
        activity=(ROOT/'app/src/main/java/ai/chemforge/mobile/MainActivity.java').read_text()
        self.assertIn('HttpsURLConnection',source)
        self.assertIn('setInstanceFollowRedirects(false)',source)
        self.assertIn('connectTimeout',source)
        self.assertIn('BuildConfig.SYNC_HOST',activity)
        self.assertIn('recordStore.read(tenant,fingerprint)',activity)
        self.assertIn('AlertDialog.Builder',activity)
        self.assertIn('@JavascriptInterface public void syncBackup(',activity)
        self.assertNotIn('localStorage.setItem("sync',activity)

    def test_journal_communicates_unverified_manual_sync(self):
        ui=(ROOT/'app/src/main/assets/index.html').read_text()
        script=(ROOT/'app/src/main/assets/app.js').read_text()
        self.assertIn('id="sync-now"',ui)
        self.assertIn('unverified',ui.lower())
        self.assertIn('syncBackup',script)

if __name__=='__main__':unittest.main()
