"""AAPT2 only accepts resource references for managed-configuration descriptions."""
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
ANDROID = '{http://schemas.android.com/apk/res/android}'

class AndroidRestrictionResourceTests(unittest.TestCase):
    def test_managed_config_descriptions_resolve_to_string_resources(self):
        rules = ET.parse(ROOT / 'app/src/main/res/xml/app_restrictions.xml').getroot()
        resource_path = ROOT / 'app/src/main/res/values/restriction_strings.xml'
        self.assertTrue(resource_path.is_file(), 'String resources file required by Android AAPT2')
        resources = {x.get('name') for x in ET.parse(resource_path).getroot().findall('string')}
        self.assertGreaterEqual(len(list(rules.findall('restriction'))), 5)
        for rule in rules.findall('restriction'):
            name = rule.attrib[ANDROID + 'key']
            for field in ('title', 'description'):
                reference = rule.attrib.get(ANDROID + field, '')
                self.assertTrue(reference.startswith('@string/'), f'{name}: {field} must reference a string')
                self.assertIn(reference.removeprefix('@string/'), resources, f'{name}: resource missing')

if __name__ == '__main__':
    unittest.main()
