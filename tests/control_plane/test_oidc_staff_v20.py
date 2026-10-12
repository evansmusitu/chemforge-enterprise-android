"""Behavioral OIDC gate tests: no pilot bypass, no actor auto-provisioning."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
import base64
import json
import pytest
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from control_plane.db import Database
from control_plane.app import create_app

ISSUER = 'https://login.example.invalid/chemforge'
AUDIENCE = 'chemforge-control'

def _fixture(tmp_path, monkeypatch):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pub = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
    pub['kid'] = '2026-test-rsa-key'
    jwks_file = tmp_path / 'jwks.json'
    jwks_file.write_text(json.dumps({'keys':[pub]}))
    monkeypatch.setenv('CHEMFORGE_STAFF_AUTH', 'oidc')
    monkeypatch.setenv('CHEMFORGE_OIDC_ISSUER', ISSUER)
    monkeypatch.setenv('CHEMFORGE_OIDC_AUDIENCE', AUDIENCE)
    monkeypatch.setenv('CHEMFORGE_OIDC_JWKS_FILE', str(jwks_file))
    db = Database(str(tmp_path / 'control.sqlite'))
    legacy_a = db.bootstrap_tenant('school-a', 'Admin A')
    legacy_b = db.bootstrap_tenant('school-b', 'Admin B')
    with db.connect() as cx:
        admins = cx.execute("SELECT id,tenant_id FROM actors WHERE role='admin' ORDER BY tenant_id").fetchall()
    for row in admins:
        db.link_oidc_subject(row['tenant_id'],row['id'],ISSUER,'identity-'+row['tenant_id'])
    return db, key, legacy_a, legacy_b

def _token(key, *, sub='identity-school-a', aud=AUDIENCE, iss=ISSUER, amr=None, expires=15, extra=None, signing_key=None):
    now = datetime.now(timezone.utc)
    payload={'iss':iss,'aud':aud,'sub':sub,'iat':now,'nbf':now-timedelta(seconds=1),
             'exp':now+timedelta(minutes=expires),'amr':amr if amr is not None else ['pwd','mfa'],
             'client_id':'chemforge-staff-dashboard','jti':'unit-test-'+str(now.timestamp())}
    payload.update(extra or {})
    return jwt.encode(payload, signing_key or key, algorithm='RS256', headers={'kid':'2026-test-rsa-key','typ':'at+jwt'})

def _auth(token): return {'Authorization':'Bearer '+token}

def test_oidc_requires_valid_provider_token_mfa_and_mapped_actor(tmp_path,monkeypatch):
    db,key,legacy_a,legacy_b = _fixture(tmp_path,monkeypatch)
    with TestClient(create_app(db.path)) as client:
        assert client.get('/v1/me',headers=_auth(legacy_a)).status_code==401, 'legacy admin token must not bypass SSO'
        good=_token(key)
        res=client.get('/v1/me',headers=_auth(good))
        assert res.status_code==200,res.text
        assert res.json()['tenant_id']=='school-a' and res.json()['role']=='admin'
        created=client.post('/v1/students',headers=_auth(good),json={'pseudonym':'demo','cohort':'U6-A'})
        assert created.status_code==201,created.text
        teacher=client.post('/v1/teachers',headers=_auth(good),json={'label':'Teacher OIDC'})
        assert teacher.status_code==201,teacher.text
        assert 'token' not in teacher.json(), 'OIDC mode must never reveal unused pilot bearer tokens'
        cases=[
            _token(key,amr=['pwd']),
            _token(key,sub='unknown-user'),
            _token(key,sub='identity-school-b',aud='wrong-audience'),
            _token(key,iss='https://evil.example.invalid'),
            _token(key,expires=-1),
            _token(key,signing_key=rsa.generate_private_key(public_exponent=65537,key_size=2048)),
            jwt.encode({'iss':ISSUER,'aud':AUDIENCE,'sub':'identity-school-a',
                        'iat':datetime.now(timezone.utc),'exp':datetime.now(timezone.utc)+timedelta(minutes=5),
                        'nbf':datetime.now(timezone.utc),'amr':['mfa'],
                        'client_id':'chemforge-staff-dashboard','jti':'id-token'},key,
                        algorithm='RS256',headers={'kid':'2026-test-rsa-key','typ':'JWT'}),
            _token(key,extra={'client_id':None}),
            _token(key,extra={'jti':None}),
        ]
        for bad in cases:
            response=client.get('/v1/me',headers=_auth(bad))
            assert response.status_code==401,(response.status_code,response.text)
        assert client.get('/v1/me',headers=_auth(_token(key,sub='identity-school-b'))).json()['tenant_id']=='school-b'
        assert client.get('/v1/students',headers=_auth(_token(key,sub='identity-school-b'))).json()==[]
        # A token valid for multiple services is never an API-specific credential.
        assert client.get('/v1/me',headers=_auth(_token(key,aud=[AUDIENCE,'unrelated-app']))).status_code==401
        # Identity assertions never override immutable, pre-authorised subject mappings.
        assert client.get('/v1/me',headers=_auth(_token(key,sub='unknown-user',extra={
            'tenant_id':'school-a','role':'admin','email':'admin@example.invalid'}))).status_code==401


def test_oidc_link_cross_tenant_rejected_and_revocation_enforced(tmp_path,monkeypatch):
    db,key,_,_= _fixture(tmp_path,monkeypatch)
    with db.connect() as cx:
        admin_a=cx.execute("SELECT id FROM actors WHERE tenant_id='school-a' AND role='admin'").fetchone()['id']
        admin_b=cx.execute("SELECT id FROM actors WHERE tenant_id='school-b' AND role='admin'").fetchone()['id']
    with pytest.raises(ValueError):
        db.link_oidc_subject('school-b',admin_b,ISSUER,'identity-school-a')
    with pytest.raises(ValueError):
        db.link_oidc_subject('school-a',admin_b,ISSUER,'another-sub')
    with TestClient(create_app(db.path)) as client:
        token=_token(key)
        assert client.get('/v1/me',headers=_auth(token)).status_code==200
        with db.connect() as cx:cx.execute('UPDATE actors SET revoked_at=? WHERE id=?',(datetime.now(timezone.utc).isoformat(),admin_a))
        assert client.get('/v1/me',headers=_auth(token)).status_code==401


def test_bad_identity_configuration_fails_application_startup(tmp_path,monkeypatch):
    monkeypatch.setenv('CHEMFORGE_STAFF_AUTH','oidc')
    for key in ('CHEMFORGE_OIDC_ISSUER','CHEMFORGE_OIDC_AUDIENCE','CHEMFORGE_OIDC_JWKS_FILE'):
        monkeypatch.delenv(key,raising=False)
    with pytest.raises(ValueError,match='OIDC'):
        create_app(str(tmp_path/'control.sqlite'))
    monkeypatch.setenv('CHEMFORGE_STAFF_AUTH','nonsense')
    with pytest.raises(ValueError):create_app(str(tmp_path/'control.sqlite'))
