"""End-to-end static contracts in addition to portable Java permission tests."""
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
JAVA=ROOT/'app/src/main/java/ai/chemforge/mobile'
NS='{http://schemas.android.com/apk/res/android}'

class DeploymentTests(unittest.TestCase):
    def test_native_restricts_json_import_at_invocation_and_after_picker(self):
        source=(JAVA/'MainActivity.java').read_text()
        self.assertIn('if (!policy.allowImport)',source)
        self.assertIn('if (requestCode == IMPORT_JSON && !policy.allowImport)',source)
    def test_provisioning_is_compile_time_enforceable(self):
        gradle=(ROOT/'app/build.gradle').read_text()
        self.assertIn('REQUIRE_ENTERPRISE_PROVISIONING',gradle)
        self.assertIn('CHEMFORGE_REQUIRE_PROVISIONING',gradle)
        manager=(JAVA/'ManagedPolicy.java').read_text()
        self.assertIn('BuildConfig.REQUIRE_ENTERPRISE_PROVISIONING',manager)
    def test_managed_restrictions_include_separate_import_permission(self):
        root=ET.parse(ROOT/'app/src/main/res/xml/app_restrictions.xml').getroot()
        config={element.attrib[NS+'key']:element for element in root}
        self.assertIn('allow_data_import',config)
        self.assertEqual(config['allow_data_import'].attrib[NS+'defaultValue'],'false')
    def test_model_import_rechecks_institution_after_copy(self):
        model=(JAVA/'OfflineModelHost.kt').read_text()
        self.assertIn('val initialPolicy = ManagedPolicy.read(context)',model)
        self.assertIn('val currentPolicy = ManagedPolicy.read(context)',model)
        self.assertIn('currentPolicy.localAi && currentPolicy.tenantId == initialPolicy.tenantId',model)
    def test_instrumented_smoke_gate_declared(self):
        gradle=(ROOT/'app/build.gradle').read_text()
        self.assertIn('testInstrumentationRunner',gradle)
        path=ROOT/'app/src/androidTest/java/ai/chemforge/mobile/OfflineLaunchTest.java'
        self.assertTrue(path.is_file())
        self.assertIn('assertOfflineHomeLoads',path.read_text())
        self.assertIn('assertLearnNavigation',path.read_text())
        workflow=(ROOT/'.github/workflows/android-emulator-smoke.yml').read_text()
        self.assertIn('connectedDebugAndroidTest',workflow)
if __name__=='__main__':unittest.main()
