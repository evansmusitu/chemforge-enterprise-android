import json
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1] / 'tools'))
from content_pack import create_pack, verify_pack, validate_content

SEED = json.loads((Path(__file__).resolve().parents[1] / 'app/src/main/assets/data.json').read_text())

class PackTests(unittest.TestCase):
    def setUp(self):
        self.d=tempfile.TemporaryDirectory()
        self.addCleanup(self.d.cleanup)
        self.root=Path(self.d.name)
        self.key=ec.generate_private_key(ec.SECP256R1())
        self.pvt=self.root/'private.pem'
        self.pvt.write_bytes(self.key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
        self.pub=self.root/'public.pem'
        self.pub.write_bytes(self.key.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo))
        self.content=dict(SEED,content_version='school-r2',scope='institutional_editorial_not_officially_endorsed')
        self.src=self.root/'content.json';self.src.write_text(json.dumps(self.content))
        self.pkg=self.root/'pack.cfpack'
    def test_valid_roundtrip_and_org_binding(self):
        create_pack(self.src,self.pvt,self.pkg,'school-one',2)
        details=verify_pack(self.pkg,self.pub,tenant='school-one')
        self.assertEqual(details['content_version'],'school-r2')
        with self.assertRaisesRegex(ValueError,'tenant'):
            verify_pack(self.pkg,self.pub,tenant='another-school')
    def test_tampered_content_rejected(self):
        create_pack(self.src,self.pvt,self.pkg,'school-one',2)
        with ZipFile(self.pkg) as z: objects={k:z.read(k) for k in z.namelist()}
        objects['content.json']+=b' '
        with ZipFile(self.pkg,'w') as z:
            for k,v in objects.items(): z.writestr(k,v)
        with self.assertRaisesRegex(ValueError,'digest'):
            verify_pack(self.pkg,self.pub,tenant='school-one')
    def test_modified_manifest_rejected(self):
        create_pack(self.src,self.pvt,self.pkg,'school-one',2)
        with ZipFile(self.pkg) as z: objects={k:z.read(k) for k in z.namelist()}
        objects['manifest.json']=objects['manifest.json'].replace(b'school-one',b'school-two')
        with ZipFile(self.pkg,'w') as z:
            for k,v in objects.items():z.writestr(k,v)
        with self.assertRaisesRegex(ValueError,'signature'):
            verify_pack(self.pkg,self.pub)
    def test_invalid_question_structure_prevented(self):
        broken=json.loads(json.dumps(self.content)); broken['questions'][0]['objective_id']='missing'
        with self.assertRaisesRegex(ValueError,'objective'):
            validate_content(broken)
    def test_negative_or_empty_rubric_points_rejected(self):
        q=next(q for q in self.content['questions'] if q['type']=='constructed')
        original=list(q['rubric'])
        q['rubric']=[{'id':'m1','text':'Bad marking point','marks':-1},{'id':'m2','text':'Another bad point','marks':q['max_marks']+1}]
        with self.assertRaisesRegex(ValueError,'rubric'):
            validate_content(self.content)
        q['rubric']=original
    def test_pack_not_secret_material(self):
        create_pack(self.src,self.pvt,self.pkg,'school-one',2)
        with ZipFile(self.pkg) as z:
            self.assertEqual(set(z.namelist()),{'manifest.json','content.json','signature.der'})
            self.assertNotIn(b'PRIVATE KEY',b''.join(z.read(n) for n in z.namelist()))
if __name__=='__main__': unittest.main()
