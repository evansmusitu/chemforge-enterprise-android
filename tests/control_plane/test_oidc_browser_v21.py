"""Synthetic IdP only: no network or real staff accounts are used."""
from __future__ import annotations
import base64
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from urllib.parse import urlparse, parse_qs
import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from control_plane.app import create_app
from control_plane.db import Database

ISSUER = 'https://login.example.invalid/realm'
BASE = 'https://control.example.invalid'
CLIENT = 'chemforge-staff-web'
AUDIENCE = 'chemforge-control'

@pytest.fixture
def oidc_env(tmp_path, monkeypatch):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pub=json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
    pub['kid']='synthetic-test-key'
    (tmp_path/'jwks.json').write_text(json.dumps({'keys':[pub]}))
    discovery={'issuer': ISSUER,'authorization_endpoint':ISSUER+'/authorize',
               'token_endpoint':ISSUER+'/token','response_types_supported':['code'],
               'code_challenge_methods_supported':['S256']}
    (tmp_path/'provider.json').write_text(json.dumps(discovery))
    for n,v in {'CHEMFORGE_STAFF_AUTH':'oidc','CHEMFORGE_OIDC_BROWSER':'enabled',
                'CHEMFORGE_OIDC_ISSUER':ISSUER,'CHEMFORGE_OIDC_AUDIENCE':AUDIENCE,
                'CHEMFORGE_OIDC_JWKS_FILE':str(tmp_path/'jwks.json'),
                'CHEMFORGE_OIDC_DISCOVERY_FILE':str(tmp_path/'provider.json'),
                'CHEMFORGE_OIDC_BROWSER_CLIENT_ID':CLIENT,
                'CHEMFORGE_OIDC_REDIRECT_URI':BASE+'/auth/callback'}.items(): monkeypatch.setenv(n,v)
    db=Database(str(tmp_path/'db.sqlite'))
    admin_a=db.bootstrap_tenant('school-a','Principal A')
    db.bootstrap_tenant('school-b','Principal B')
    with db.connect() as cx:
        ids={r['tenant_id']:r['id'] for r in cx.execute('SELECT id,tenant_id FROM actors')}
    db.link_oidc_subject('school-a', ids['school-a'],ISSUER,'staff-a')
    db.link_oidc_subject('school-b', ids['school-b'],ISSUER,'staff-b')
    return {'app':create_app(str(tmp_path/'db.sqlite')),'db':db,'key':key,'ids':ids,'pilot':admin_a}

def token(key, *, sub='staff-a', nonce=None, id_token=False, amr=('pwd','mfa')):
    now=datetime.now(timezone.utc)
    claims={'iss':ISSUER,'sub':sub,'aud':CLIENT if id_token else AUDIENCE,
            'iat':now,'nbf':now-timedelta(seconds=1),'exp':now+timedelta(minutes=10)}
    if id_token: claims['nonce']=nonce
    else: claims.update(client_id=CLIENT,jti='synthetic-jti-'+str(now.timestamp()),amr=list(amr))
    return jwt.encode(claims,key,algorithm='RS256', headers={'kid':'synthetic-test-key','typ':'JWT' if id_token else 'at+jwt'})

def start(client):
    r=client.get('/auth/start',follow_redirects=False)
    assert r.status_code==302
    q=parse_qs(urlparse(r.headers['location']).query)
    assert q['code_challenge_method']==['S256']
    assert q['response_type']==['code']
    assert q['redirect_uri']==[BASE+'/auth/callback']
    assert 'code_verifier' not in r.headers['location']
    assert '__Host-cf_oidc_bind=' in r.headers['set-cookie']
    assert 'Secure' in r.headers['set-cookie'] and 'HttpOnly' in r.headers['set-cookie']
    return q

def install_provider(monkeypatch, cfg, nonce, *, sub='staff-a', mismatch=False, called=None):
    from control_plane import browser_oidc
    orig=browser_oidc.httpx.Client
    class FakeClient:
        def __init__(self, **kw):
            assert kw['follow_redirects'] is False and kw['trust_env'] is False
        def __enter__(self): return self
        def __exit__(self,*args): return False
        def post(self,url,**kwargs):
            assert url==ISSUER+'/token'
            data=kwargs['data']
            assert data['grant_type']=='authorization_code'
            assert data['redirect_uri']==BASE+'/auth/callback'
            assert data['client_id']==CLIENT
            assert len(data['code_verifier'])>=43
            if called is not None: called.append(data.copy())
            body={'token_type':'Bearer','expires_in':600,
                  'access_token':token(cfg['key'],sub=sub),
                  'id_token':token(cfg['key'],sub=sub,nonce=('wrong' if mismatch else nonce),id_token=True)}
            return httpx.Response(200,headers={'content-type':'application/json'},json=body)
    monkeypatch.setattr(browser_oidc.httpx,'Client',FakeClient)

def test_oidc_browser_pkce_cookie_session_csrf_and_logout(oidc_env, monkeypatch):
    with TestClient(oidc_env['app'],base_url=BASE) as c:
        assert c.get('/v1/me').status_code==401
        assert c.get('/auth/capabilities').json()['mode']=='oidc_browser'
        q=start(c)
        with oidc_env['db'].connect() as cx:
            flow=cx.execute('SELECT code_verifier,nonce FROM oidc_auth_flows').fetchone()
        verifier=flow['code_verifier']
        expected=base64.urlsafe_b64encode(sha256(verifier.encode()).digest()).rstrip(b'=').decode()
        assert q['code_challenge']==[expected]
        called=[]
        install_provider(monkeypatch,oidc_env,flow['nonce'],called=called)
        r=c.get('/auth/callback',params={'code':'synthetic','state':q['state'][0]},follow_redirects=False)
        assert r.status_code==303 and r.headers['location']=='/control/'
        assert '__Host-cf_staff=' in r.headers['set-cookie']
        assert 'HttpOnly' in r.headers['set-cookie'] and 'Secure' in r.headers['set-cookie']
        assert c.get('/auth/callback',params={'code':'repeat','state':q['state'][0]}).status_code==401
        current=c.get('/auth/session').json()
        assert current['actor']['tenant_id']=='school-a'
        assert 'csrf_token' in current and 'access_token' not in str(current)
        assert c.get('/v1/me').json()['role']=='admin'
        assert c.post('/v1/students',json={'pseudonym':'Synthetic 1','cohort':'A'}).status_code==403
        headers={'origin':BASE,'x-cf-csrf':current['csrf_token']}
        assert c.post('/v1/students',json={'pseudonym':'Synthetic 1','cohort':'A'},headers=headers).status_code==201
        assert c.post('/v1/students',json={'pseudonym':'Synthetic 2','cohort':'A'},headers={'origin':'https://evil.invalid','x-cf-csrf':current['csrf_token']}).status_code==403
        assert c.post('/auth/logout',headers=headers).status_code==204
        assert c.get('/v1/me').status_code==401
        assert c.get('/auth/session').status_code==401
        assert called[0]['code']=='synthetic'

def test_state_cookie_nonce_and_actor_revoke_fail_closed(oidc_env,monkeypatch):
    with TestClient(oidc_env['app'],base_url=BASE) as c:
        q=start(c)
        assert c.get('/auth/callback',params={'code':'x','state':'bad'},follow_redirects=False).status_code==401
        with oidc_env['db'].connect() as cx:
            nonce=cx.execute('SELECT nonce FROM oidc_auth_flows').fetchone()['nonce']
        install_provider(monkeypatch,oidc_env,nonce,mismatch=True)
        assert c.get('/auth/callback',params={'code':'x','state':q['state'][0]},follow_redirects=False).status_code==401
        assert c.get('/auth/session').status_code==401
        q=start(c)
        with oidc_env['db'].connect() as cx:
            nonce=cx.execute('SELECT nonce FROM oidc_auth_flows').fetchone()['nonce']
        install_provider(monkeypatch,oidc_env,nonce)
        assert c.get('/auth/callback',params={'code':'x','state':q['state'][0]},follow_redirects=False).status_code==303
        with oidc_env['db'].connect() as cx:
            cx.execute('UPDATE actors SET revoked_at=? WHERE id=?',('2026-10-13T00:00:00+00:00',oidc_env['ids']['school-a']))
        assert c.get('/v1/me').status_code==401

def test_missing_configuration_fails_closed(tmp_path,monkeypatch):
    monkeypatch.setenv('CHEMFORGE_STAFF_AUTH','oidc')
    monkeypatch.setenv('CHEMFORGE_OIDC_BROWSER','enabled')
    for key in ('CHEMFORGE_OIDC_DISCOVERY_FILE','CHEMFORGE_OIDC_BROWSER_CLIENT_ID','CHEMFORGE_OIDC_REDIRECT_URI'):
        monkeypatch.delenv(key,raising=False)
    with pytest.raises(ValueError):create_app(str(tmp_path/'fail.sqlite'))


def authenticate(c, cfg, monkeypatch, *, sub='staff-a'):
    q=start(c)
    with cfg['db'].connect() as cx:
        flow=cx.execute('SELECT nonce FROM oidc_auth_flows WHERE state_hash=?',
                        (sha256(q['state'][0].encode()).hexdigest(),)).fetchone()
    install_provider(monkeypatch,cfg,flow['nonce'],sub=sub)
    r=c.get('/auth/callback',params={'state':q['state'][0],'code':'synthetic'},follow_redirects=False)
    assert r.status_code==303
    return c.get('/auth/session').json()['csrf_token']


def test_cross_tenant_and_teacher_cohort_denied_by_server(oidc_env,monkeypatch):
    cfg=oidc_env
    with cfg['db'].connect() as cx:
        import uuid
        teacher_id=str(uuid.uuid4())
        cx.execute('''INSERT INTO actors(id,tenant_id,label,role,token_hash,created_at)
                      VALUES(?,?,?,?,?,?)''', (teacher_id,'school-a','Teacher A','teacher',
                                               sha256(b'synthetic-teacher-secret').hexdigest(),datetime.now(timezone.utc).isoformat()))
        cx.execute('''INSERT INTO teacher_cohorts(tenant_id,actor_id,cohort,granted_at)
                      VALUES(?,?,?,?)''', ('school-a',teacher_id,'Class A',datetime.now(timezone.utc).isoformat()))
    cfg['db'].link_oidc_subject('school-a',teacher_id,ISSUER,'teacher-a')
    with TestClient(cfg['app'],base_url=BASE) as admin_a, TestClient(cfg['app'],base_url=BASE) as admin_b:
        csrf_a=authenticate(admin_a,cfg,monkeypatch,sub='staff-a')
        headers_a={'Origin':BASE,'X-CF-CSRF':csrf_a}
        student_a=admin_a.post('/v1/students',json={'pseudonym':'Synthetic A','cohort':'Class A'},headers=headers_a).json()['id']
        student_b=admin_a.post('/v1/students',json={'pseudonym':'Synthetic B','cohort':'Class B'},headers=headers_a).json()['id']
        csrf_b=authenticate(admin_b,cfg,monkeypatch,sub='staff-b')
        assert admin_b.get('/v1/students').json()==[]
        assert admin_b.delete('/v1/students/'+student_a,headers={'Origin':BASE,'X-CF-CSRF':csrf_b}).status_code==404
        assert student_a in [x['id'] for x in admin_a.get('/v1/students').json()]
    with TestClient(cfg['app'],base_url=BASE) as teacher:
        csrf=authenticate(teacher,cfg,monkeypatch,sub='teacher-a')
        assert [r['id'] for r in teacher.get('/v1/students').json()]==[student_a]
        assert teacher.get('/v1/audit').status_code==403
        assert teacher.post('/v1/teachers',headers={'Origin':BASE,'X-CF-CSRF':csrf},json={'label':'X'}).status_code==403
        with cfg['db'].connect() as cx:
            cx.execute('DELETE FROM teacher_cohorts WHERE tenant_id=? AND actor_id=?',('school-a',teacher_id))
        assert teacher.get('/v1/students').json()==[]


def test_browser_rejects_access_token_injection_and_missing_cookie(oidc_env, monkeypatch):
    cfg=oidc_env
    with TestClient(cfg['app'],base_url=BASE) as a, TestClient(cfg['app'],base_url=BASE) as b:
        q=start(a)
        with cfg['db'].connect() as cx:
            nonce=cx.execute('SELECT nonce FROM oidc_auth_flows').fetchone()['nonce']
        install_provider(monkeypatch,cfg,nonce)
        assert b.get('/auth/callback',params={'state':q['state'][0],'code':'x'},follow_redirects=False).status_code==401
        assert a.get('/auth/callback',params={'state':q['state'][0],'code':'x'},follow_redirects=False).status_code==303
        bearer=token(cfg['key'])
        assert a.get('/v1/me',headers={'Authorization':'Bearer '+bearer}).status_code==401
        assert b.get('/v1/me',headers={'Authorization':'Bearer '+bearer}).status_code==401
        assert a.get('/auth/session').status_code==200
        assert a.post('/auth/logout',headers={'Origin':BASE,'X-CF-CSRF':'wrong'}).status_code==403


def test_provider_mfa_is_required_and_bad_discovery_rejected(oidc_env,monkeypatch,tmp_path):
    cfg=oidc_env
    with TestClient(cfg['app'],base_url=BASE) as c:
        q=start(c)
        with cfg['db'].connect() as cx:
            nonce=cx.execute('SELECT nonce FROM oidc_auth_flows').fetchone()['nonce']
        from control_plane import browser_oidc
        class NoMFA:
            def __init__(self,**kw):pass
            def __enter__(self):return self
            def __exit__(self,*a):return False
            def post(self,*a,**kw):
                return httpx.Response(200,json={'token_type':'Bearer','expires_in':600,
                    'access_token':token(cfg['key'],amr=('pwd',)),
                    'id_token':token(cfg['key'],nonce=nonce,id_token=True)},
                    headers={'Content-Type':'application/json'})
        monkeypatch.setattr(browser_oidc.httpx,'Client',NoMFA)
        assert c.get('/auth/callback',params={'state':q['state'][0],'code':'x'},follow_redirects=False).status_code==401
    # Reject provider-supplied endpoints redirecting token codes to a foreign host.
    metadata={'issuer':ISSUER,'authorization_endpoint':ISSUER+'/authorize',
              'token_endpoint':'https://attacker.invalid/token',
              'response_types_supported':['code'],'code_challenge_methods_supported':['S256']}
    path=tmp_path/'bad.json';path.write_text(json.dumps(metadata))
    monkeypatch.setenv('CHEMFORGE_OIDC_DISCOVERY_FILE',str(path))
    with pytest.raises(ValueError):create_app(str(tmp_path/'bad-db.sqlite'))


def test_malformed_id_token_typ_is_denied_not_internal_error(oidc_env,monkeypatch):
    """A signed ID-token header with non-string typ must fail closed with HTTP 401."""
    from control_plane import browser_oidc
    cfg=oidc_env
    with TestClient(cfg['app'],base_url=BASE) as c:
        q=start(c)
        with cfg['db'].connect() as cx:
            nonce=cx.execute('SELECT nonce FROM oidc_auth_flows').fetchone()['nonce']
        raw=token(cfg['key'],nonce=nonce,id_token=True)
        claims=jwt.decode(raw,cfg['key'].public_key(),algorithms=['RS256'],audience=CLIENT,issuer=ISSUER)
        malformed=jwt.encode(claims,cfg['key'],algorithm='RS256',
                             headers={'kid':'synthetic-test-key','typ': 42})
        assert jwt.get_unverified_header(malformed)['typ']==42
        monkeypatch.setattr(browser_oidc.StaffBrowserOIDC,'_exchange',
                            lambda self,code,verifier: {'id_token':malformed,'access_token':token(cfg['key'])})
        response=c.get('/auth/callback',params={'code':'synthetic','state':q['state'][0]},follow_redirects=False)
        assert response.status_code==401
        assert c.get('/auth/session').status_code==401


def test_optional_id_token_at_hash_must_bind_exchanged_access_token(oidc_env,monkeypatch):
    """Do not accept a provider ID token with a mismatched at_hash."""
    from control_plane import browser_oidc
    cfg=oidc_env
    with TestClient(cfg['app'],base_url=BASE) as c:
        q=start(c)
        with cfg['db'].connect() as cx:
            nonce=cx.execute('SELECT nonce FROM oidc_auth_flows').fetchone()['nonce']
        raw=token(cfg['key'],nonce=nonce,id_token=True)
        claims=jwt.decode(raw,cfg['key'].public_key(),algorithms=['RS256'],audience=CLIENT,issuer=ISSUER)
        claims['at_hash']='attacker-supplied-mismatch'
        signed=jwt.encode(claims,cfg['key'],algorithm='RS256',headers={'kid':'synthetic-test-key','typ':'JWT'})
        monkeypatch.setattr(browser_oidc.StaffBrowserOIDC,'_exchange',
                            lambda self,code,verifier: {'id_token':signed,'access_token':token(cfg['key'])})
        response=c.get('/auth/callback',params={'code':'synthetic','state':q['state'][0]},follow_redirects=False)
        assert response.status_code==401
        assert c.get('/v1/me').status_code==401


def test_browser_api_rejects_spoofed_host_even_with_valid_cookie(oidc_env,monkeypatch):
    """Cookie authorization must be scoped to the configured external HTTPS origin."""
    from control_plane.browser_oidc import SESSION_COOKIE
    cfg=oidc_env
    with TestClient(cfg['app'],base_url=BASE) as c:
        authenticate(c,cfg,monkeypatch)
        assert c.get('/v1/me').status_code==200
        value=c.cookies.get(SESSION_COOKIE)
        response=c.get('/v1/me',headers={'host':'evil.example.invalid',
                                           'cookie':f'{SESSION_COOKIE}={value}'})
        assert response.status_code==403


def test_valid_optional_at_hash_allows_matching_access_token(oidc_env,monkeypatch):
    """The optional OIDC at_hash path accepts correctly bound synthetic tokens."""
    from control_plane import browser_oidc
    cfg=oidc_env
    with TestClient(cfg['app'],base_url=BASE) as c:
        q=start(c)
        with cfg['db'].connect() as cx:
            nonce=cx.execute('SELECT nonce FROM oidc_auth_flows').fetchone()['nonce']
        access=token(cfg['key'])
        raw=token(cfg['key'],nonce=nonce,id_token=True)
        claims=jwt.decode(raw,cfg['key'].public_key(),algorithms=['RS256'],audience=CLIENT,issuer=ISSUER)
        claims['at_hash']=base64.urlsafe_b64encode(sha256(access.encode('ascii')).digest()[:16]).rstrip(b'=').decode()
        signed=jwt.encode(claims,cfg['key'],algorithm='RS256',headers={'kid':'synthetic-test-key','typ':'JWT'})
        monkeypatch.setattr(browser_oidc.StaffBrowserOIDC,'_exchange',
                            lambda self,code,verifier: {'id_token':signed,'access_token':access})
        assert c.get('/auth/callback',params={'code':'synthetic','state':q['state'][0]},follow_redirects=False).status_code==303
        assert c.get('/v1/me').status_code==200


def test_non_ascii_access_token_is_denied_without_internal_error(oidc_env,monkeypatch):
    """Malformed provider token bodies must never cause Unicode error 500s."""
    from control_plane import browser_oidc
    cfg=oidc_env
    with TestClient(cfg['app'],base_url=BASE) as c:
        q=start(c)
        with cfg['db'].connect() as cx:
            nonce=cx.execute('SELECT nonce FROM oidc_auth_flows').fetchone()['nonce']
        raw=token(cfg['key'],nonce=nonce,id_token=True)
        claims=jwt.decode(raw,cfg['key'].public_key(),algorithms=['RS256'],audience=CLIENT,issuer=ISSUER)
        claims['at_hash']='attacker-supplied-mismatch'
        signed=jwt.encode(claims,cfg['key'],algorithm='RS256',headers={'kid':'synthetic-test-key'})
        monkeypatch.setattr(browser_oidc.StaffBrowserOIDC,'_exchange',
                            lambda self,code,verifier: {'id_token':signed,'access_token':'●'})
        assert c.get('/auth/callback',params={'code':'synthetic','state':q['state'][0]},follow_redirects=False).status_code==401
