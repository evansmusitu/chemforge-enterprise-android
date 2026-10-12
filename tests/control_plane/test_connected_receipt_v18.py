"""Regression contract used by Android native sync receipt parsing."""
from fastapi.testclient import TestClient
from control_plane.db import Database
from control_plane.app import create_app
from tests.control_plane.test_institution_sync_v17 import backup,H


def test_native_receipt_supports_created_and_repeat_without_certification(tmp_path):
    path=str(tmp_path/'db.sqlite')
    token=Database(path).bootstrap_tenant('school-one','Principal')
    c=TestClient(create_app(path))
    learner=c.post('/v1/students',headers=H(token),json={'pseudonym':'Study learner','cohort':'Upper6A'}).json()['id']
    device=c.post('/v1/devices',headers=H(token),json={'student_id':learner,'label':'Phone','valid_days':1}).json()
    request=backup('school-one',identity='native-bridge-v18-001')
    receipts=[]
    for expected_status in (201,200):
        result=c.post('/v1/sync/backups',headers=H(device['token'],'Device'),json=request)
        assert result.status_code==expected_status,result.text
        body=result.json()
        assert body['student_id']==learner and body['verified']==0
        assert body['imported']+body['unchanged']==len(request['attempts'])
        assert 'token' not in str(body)
        receipts.append((body['imported'],body['unchanged']))
    assert receipts==[(1,0),(0,1)]
