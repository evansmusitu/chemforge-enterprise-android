"""Content pack quality gates beyond signature authenticity."""
from pathlib import Path
import copy, json, sys, unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from content_pack import validate_content
SEED=json.loads((ROOT/'app/src/main/assets/data.json').read_text())

class ContentV12Tests(unittest.TestCase):
    def test_six_choices_aligned_to_marking_engine(self):
        data=copy.deepcopy(SEED); q=next(q for q in data['questions'] if q['type']=='mcq')
        q['choices']=[{'id':x,'text':x} for x in 'ABCDEF'];q['answer']='F'
        validate_content(data)
    def test_rejects_arbitrary_html_choice_ids(self):
        data=copy.deepcopy(SEED); q=next(q for q in data['questions'] if q['type']=='mcq')
        q['choices'][0]['id']='"><script>alert(1)</script>'; q['answer']=q['choices'][0]['id']
        with self.assertRaises(ValueError):validate_content(data)
    def test_rejects_duplicate_alias_units(self):
        data=copy.deepcopy(SEED);q=next(q for q in data['questions'] if q['type']=='numeric'); q['accepted_units']=[{'unit':q['unit'],'multiplier':1}]
        with self.assertRaises(ValueError): validate_content(data)
    def test_accepts_explicit_conversions(self):
        data=copy.deepcopy(SEED);q=next(q for q in data['questions'] if q['type']=='numeric' and q['unit']=='cm³');q['accepted_units']=[{'unit':'dm³','multiplier':1000}]
        validate_content(data)
    def test_rejects_nonfinite_or_negative_unit_multipliers(self):
        for mult in (float('inf'),float('nan'),-1,0,'1000'):
            data=copy.deepcopy(SEED);q=next(q for q in data['questions'] if q['type']=='numeric');q['accepted_units']=[{'unit':'cm³','multiplier':mult}]
            with self.subTest(mult=mult),self.assertRaises(ValueError): validate_content(data)
    def test_rejects_circular_prerequisites(self):
        data=copy.deepcopy(SEED)
        a,b=data['objectives'][:2]
        a['prerequisites']=[b['id']]
        b['prerequisites']=[a['id']]
        with self.assertRaises(ValueError): validate_content(data)

class LessonPackValidationTests(unittest.TestCase):
    def test_approved_schema_accepts_optional_editorial_lessons(self):
        data=copy.deepcopy(SEED)
        data['lessons']=[{'objective_id':data['objectives'][0]['id'],'domain':'Physical','title':'Atoms','principle':'The mole measures amount.','example':'One mol contains N_A entities.','common_error':'Confusing moles and mass.','review_status':'unreviewed'}]
        validate_content(data)
    def test_rejects_orphaned_or_oversized_lessons(self):
        for key,value in [('objective_id','not-an-objective'),('principle','a'*7000)]:
            data=copy.deepcopy(SEED)
            data['lessons']=[{'objective_id':data['objectives'][0]['id'],'domain':'Physical','title':'Atoms','principle':'Mole is amount.','example':'x','common_error':'y','review_status':'unreviewed'}]
            data['lessons'][0][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):validate_content(data)
