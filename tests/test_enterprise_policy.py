"""Source-contract checks that complement, not substitute for, Android compilation."""
from pathlib import Path
import xml.etree.ElementTree as ET
import unittest
BASE=Path(__file__).resolve().parents[1]
SRC=(BASE/'app/src/main/java/ai/chemforge/mobile/MainActivity.java')
NS='{http://schemas.android.com/apk/res/android}'
class PolicyTests(unittest.TestCase):
    def test_restrictions_declared(self):
        root=ET.parse(BASE/'app/src/main/res/xml/app_restrictions.xml').getroot()
        self.assertEqual({el.attrib[NS+'key'] for el in root}, {'tenant_id','enable_local_ai','allow_data_export','allow_data_import','allow_content_import'})
        manifest=(BASE/'app/src/main/AndroidManifest.xml').read_text()
        self.assertIn('android.content.APP_RESTRICTIONS',manifest)
    def test_native_bridge_enforces_admin_policy(self):
        source=SRC.read_text()
        self.assertIn('if (!policy.allowExport)',source)
        self.assertIn('if (!policy.localAi)',source)
        self.assertIn('if (!policy.allowContentImport)',source)
        self.assertIn('IMPORT_PACK',source)
    def test_signed_bundle_served_only_as_bounded_json(self):
        source=SRC.read_text()
        self.assertIn('packManager.webViewContentScript',source)
        self.assertIn('enterprise_pack.js',source)
        self.assertIn('enterprise_policy.js',source)
        html=(BASE/'app/src/main/assets/index.html').read_text()
        self.assertIn('src="enterprise_pack.js"',html)
        self.assertIn('src="enterprise_policy.js"',html)
if __name__=='__main__':unittest.main()

class ModelIntegrityTests(unittest.TestCase):
    def test_model_load_and_import_require_approved_hash(self):
        model=(BASE/'app/src/main/java/ai/chemforge/mobile/OfflineModelHost.kt').read_text()
        self.assertIn('BuildConfig.APPROVED_MODEL_SHA256',model)
        self.assertIn('model file does not match the approved institutional digest',model)
        self.assertIn('approved institutional model not configured',model)
        self.assertIn('verifyInstalledModel()',model)
