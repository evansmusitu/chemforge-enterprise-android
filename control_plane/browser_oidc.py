"""Opt-in *server-side* staff Authorization Code + PKCE for a pinned synthetic/provider config.

Never fetch discovery or JWKS from untrusted token metadata. Not a real IdP
installation: operator must validate the pinned discovery and JWKS externally.
Sessions are short-lived, opaque, revocable and re-authorised against local actors.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import secrets
from urllib.parse import urlencode, urlsplit

import httpx
import jwt
from fastapi import HTTPException, Request
from fastapi.responses import RedirectResponse, JSONResponse, Response

from .db import token_digest, utcnow
from .identity import StaffAuthenticationError

SESSION_COOKIE = '__Host-cf_staff'
BIND_COOKIE = '__Host-cf_oidc_bind'
FLOW_SECONDS = 300
SESSION_SECONDS = 900
# Last-resort bounded state for the $0 synthetic pilot; not an IP rate limiter.
MAX_ACTIVE_FLOWS = 256


def _origin(url):
    parsed = urlsplit(url)
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
            or parsed.query or parsed.fragment or parsed.path not in ('', '/')):
        raise ValueError('Expected canonical HTTPS origin')
    return f'{parsed.scheme}://{parsed.netloc}'


def _endpoint(url, issuer):
    parsed = urlsplit(url)
    root = urlsplit(issuer)
    if (not isinstance(url, str) or parsed.scheme != 'https' or not parsed.hostname
            or parsed.netloc != root.netloc or parsed.username or parsed.password
            or parsed.query or parsed.fragment or not parsed.path.startswith('/')):
        raise ValueError('OIDC endpoint must be a fixed HTTPS URL on issuer origin')
    return url


@dataclass(frozen=True)
class BrowserConfig:
    issuer: str
    client_id: str
    redirect_uri: str
    origin: str
    authorize: str
    token: str

    @classmethod
    def from_environment(cls, env, oidc):
        client_id = env.get('CHEMFORGE_OIDC_BROWSER_CLIENT_ID', '').strip()
        redirect_uri = env.get('CHEMFORGE_OIDC_REDIRECT_URI', '').strip()
        location = env.get('CHEMFORGE_OIDC_DISCOVERY_FILE', '').strip()
        url = urlsplit(redirect_uri)
        if (not re.fullmatch(r'[A-Za-z0-9_.:-]{3,150}',client_id)
                or url.scheme != 'https' or not url.netloc or url.username or url.password
                or url.query or url.fragment or url.path != '/auth/callback'
                or not location):
            raise ValueError('OIDC browser login needs client ID, canonical HTTPS callback and pinned discovery')
        path=Path(location).resolve()
        if not path.is_file() or path.stat().st_size > 65536:
            raise ValueError('OIDC discovery file must be a small local file')
        try:
            doc=json.loads(path.read_text(encoding='utf-8'))
            if doc['issuer'] != oidc.issuer or 'code' not in doc['response_types_supported'] \
                    or 'S256' not in doc['code_challenge_methods_supported']:
                raise ValueError('Pinned provider metadata disagrees with issuer or PKCE requirements')
            authorize=_endpoint(doc['authorization_endpoint'],oidc.issuer)
            token=_endpoint(doc['token_endpoint'],oidc.issuer)
        except (OSError,UnicodeError,KeyError,TypeError,json.JSONDecodeError) as exc:
            raise ValueError('Invalid pinned provider metadata') from exc
        return cls(oidc.issuer, client_id, redirect_uri, f'https://{url.netloc}', authorize, token)


class StaffBrowserOIDC:
    def __init__(self, db, oidc, config):
        self.db=db
        self.oidc=oidc
        self.config=config

    def _require_origin(self, request):
        if _origin(str(request.base_url).rstrip('/')) != self.config.origin:
            raise HTTPException(403,'Untrusted dashboard origin')

    @staticmethod
    def _no_store(response):
        response.headers['Cache-Control']='no-store'
        response.headers['Referrer-Policy']='no-referrer'
        response.headers['X-Content-Type-Options']='nosniff'
        return response

    def start(self, request: Request):
        self._require_origin(request)
        state=secrets.token_urlsafe(32)
        binding=secrets.token_urlsafe(32)
        verifier=secrets.token_urlsafe(64)
        nonce=secrets.token_urlsafe(32)
        challenge=base64.urlsafe_b64encode(sha256(verifier.encode('ascii')).digest()).rstrip(b'=').decode()
        expire=(datetime.now(timezone.utc)+timedelta(seconds=FLOW_SECONDS)).isoformat()
        with self.db.connect() as cx:
            cx.execute('BEGIN IMMEDIATE')
            now = utcnow()
            cx.execute('DELETE FROM oidc_auth_flows WHERE expires_at <= ?', (now,))
            cx.execute('DELETE FROM oidc_browser_sessions WHERE expires_at <= ?', (now,))
            active = cx.execute('SELECT COUNT(*) AS active_flows FROM oidc_auth_flows').fetchone()['active_flows']
            if active < MAX_ACTIVE_FLOWS:
                cx.execute('''INSERT INTO oidc_auth_flows(state_hash,binding_hash,code_verifier,nonce,expires_at)
                              VALUES(?,?,?,?,?)''',(token_digest(state),token_digest(binding),verifier,nonce,expire))
        # Leave the transaction successfully so expiry cleanup persists even
        # when new login capacity has been exhausted.
        if active >= MAX_ACTIVE_FLOWS:
            raise HTTPException(429, 'Login temporarily unavailable',
                headers={'Retry-After': str(FLOW_SECONDS), 'Cache-Control': 'no-store'})
        url=self.config.authorize+'?'+urlencode({'response_type':'code','client_id':self.config.client_id,
            'redirect_uri':self.config.redirect_uri,'scope':'openid','state':state,
            'code_challenge_method':'S256','code_challenge':challenge,'nonce':nonce})
        response=RedirectResponse(url,status_code=302)
        response.set_cookie(BIND_COOKIE,binding,max_age=FLOW_SECONDS,secure=True,httponly=True,samesite='lax',path='/')
        return self._no_store(response)

    def _consume(self, state, binding):
        if not isinstance(state,str) or len(state)>256 or not isinstance(binding,str) or len(binding)>256:
            raise HTTPException(401,'Invalid login transaction')
        with self.db.connect() as cx:
            cx.execute('BEGIN IMMEDIATE')
            row=cx.execute('''SELECT code_verifier,nonce FROM oidc_auth_flows
                WHERE state_hash=? AND binding_hash=? AND expires_at>?''',
                (token_digest(state),token_digest(binding),utcnow())).fetchone()
            if row is None:
                raise HTTPException(401,'Invalid or expired login transaction')
            cx.execute('DELETE FROM oidc_auth_flows WHERE state_hash=?',(token_digest(state),))
            return dict(row)

    def _exchange(self, code, verifier):
        if not code or len(code)>2048:
            raise HTTPException(401,'Invalid authorization response')
        try:
            with httpx.Client(timeout=5,follow_redirects=False,trust_env=False) as client:
                response=client.post(self.config.token, data={'grant_type':'authorization_code','code':code,
                    'redirect_uri':self.config.redirect_uri,'client_id':self.config.client_id,
                    'code_verifier':verifier},headers={'Accept':'application/json'})
            if (response.status_code != 200 or len(response.content)>131072 or
                    'application/json' not in response.headers.get('content-type','')):
                raise HTTPException(401,'Identity provider rejected authorization')
            body=response.json()
            if (not isinstance(body,dict) or not isinstance(body.get('token_type'),str) or body['token_type'].lower()!='bearer'
                    or type(body.get('expires_in')) is not int or not 0<body['expires_in']<=3600
                    or not isinstance(body.get('id_token'),str) or not isinstance(body.get('access_token'),str)):
                raise HTTPException(401,'Invalid identity provider response')
            return body
        except (httpx.HTTPError, ValueError, TypeError, KeyError) as exc:
            raise HTTPException(401,'Identity provider authorization failed') from exc

    def _verify_id_token(self, token, nonce, access_token):
        if not isinstance(token,str) or len(token)>12000:
            raise HTTPException(401,'OIDC ID token rejected')
        try:
            header=jwt.get_unverified_header(token)
            kid=header.get('kid')
            typ=header.get('typ','JWT')
            if (header.get('alg')!='RS256' or not isinstance(kid,str) or kid not in self.oidc.keys
                    or header.get('crit') or not isinstance(typ,str) or typ.lower()!='jwt'):
                raise ValueError('ID token header')
            body=jwt.decode(token,self.oidc.keys[kid],algorithms=['RS256'],
                    issuer=self.config.issuer,audience=self.config.client_id,
                    options={'require':['iss','sub','aud','exp','iat','nbf','nonce'],'strict_aud':True},leeway=15)
            if (not isinstance(body.get('sub'),str) or not 1<=len(body['sub'])<=255
                    or not secrets.compare_digest(str(body.get('nonce','')),nonce)):
                raise ValueError('ID token nonce or subject')
            if 'at_hash' in body:
                # Optional in OIDC code flow; mandatory to verify if the issuer includes it.
                expected=base64.urlsafe_b64encode(sha256(access_token.encode('ascii')).digest()[:16]).rstrip(b'=').decode('ascii')
                at_hash=body['at_hash']
                if (not isinstance(at_hash,str) or not re.fullmatch(r'[A-Za-z0-9_-]{22}',at_hash)
                        or not secrets.compare_digest(at_hash,expected)):
                    raise ValueError('OIDC ID token access-token hash mismatch')
            return body['sub']
        except (jwt.PyJWTError,ValueError,KeyError,TypeError) as exc:
            raise HTTPException(401,'OIDC ID token rejected') from exc

    def callback(self, request: Request, code: str='', state: str='', error: str=''):
        self._require_origin(request)
        if error:
            raise HTTPException(401,'Identity provider authorization was not granted')
        flow=self._consume(state,request.cookies.get(BIND_COOKIE,''))
        body=self._exchange(code,flow['code_verifier'])
        sub=self._verify_id_token(body['id_token'],flow['nonce'],body['access_token'])
        try:
            claims=self.oidc.verify_claims(body['access_token'])
            if (not secrets.compare_digest(sub,claims['sub']) or
                    claims['client_id'] != self.config.client_id):
                raise ValueError('Access-token subject or client mismatch')
        except (StaffAuthenticationError,ValueError) as exc:
            raise HTTPException(401,'OIDC staff access denied') from exc
        with self.db.connect() as cx:
            row=cx.execute('''SELECT a.id,a.tenant_id FROM actors a JOIN oidc_actor_links o
                ON o.actor_id=a.id AND o.tenant_id=a.tenant_id
                WHERE o.issuer=? AND o.subject=? AND a.revoked_at IS NULL''',
                (self.config.issuer,sub)).fetchone()
            if row is None:
                raise HTTPException(401,'OIDC staff access denied')
            session=secrets.token_urlsafe(48)
            csrf=secrets.token_urlsafe(32)
            ttl=min(SESSION_SECONDS, int(claims['exp']-datetime.now(timezone.utc).timestamp()))
            if ttl<1:
                raise HTTPException(401,'OIDC access token has expired')
            expiry=(datetime.now(timezone.utc)+timedelta(seconds=ttl)).isoformat()
            old=request.cookies.get(SESSION_COOKIE,'')
            if old:
                cx.execute('DELETE FROM oidc_browser_sessions WHERE session_hash=?',(token_digest(old),))
            cx.execute('''INSERT INTO oidc_browser_sessions(session_hash,actor_id,tenant_id,
                issuer,subject,csrf_token,expires_at,created_at) VALUES(?,?,?,?,?,?,?,?)''',
                (token_digest(session),row['id'],row['tenant_id'],self.config.issuer,sub,csrf,expiry,utcnow()))
        response=RedirectResponse('/control/',status_code=303)
        response.set_cookie(SESSION_COOKIE,session,max_age=ttl,secure=True,httponly=True,samesite='lax',path='/')
        response.delete_cookie(BIND_COOKIE,secure=True,httponly=True,samesite='lax',path='/')
        return self._no_store(response)

    def _lookup(self, request, check_csrf=False):
        self._require_origin(request)
        session=request.cookies.get(SESSION_COOKIE,'')
        if not isinstance(session,str) or not 10<len(session)<256:
            raise HTTPException(401,'Staff session required')
        with self.db.connect() as cx:
            row=cx.execute('''SELECT a.id,a.tenant_id,a.label,a.role,s.csrf_token FROM oidc_browser_sessions s
                JOIN actors a ON a.id=s.actor_id AND a.tenant_id=s.tenant_id
                JOIN oidc_actor_links o ON o.actor_id=a.id AND o.tenant_id=a.tenant_id
                WHERE s.session_hash=? AND s.expires_at>? AND a.revoked_at IS NULL
                AND s.issuer=? AND o.issuer=s.issuer AND o.subject=s.subject''',
                (token_digest(session),utcnow(),self.config.issuer)).fetchone()
        if row is None:
            raise HTTPException(401,'Invalid or expired staff session')
        if check_csrf:
            if (request.headers.get('origin')!=self.config.origin
                    or not secrets.compare_digest(request.headers.get('x-cf-csrf',''),row['csrf_token'])):
                raise HTTPException(403,'Session CSRF protection required')
        return dict(row)

    def actor(self, request):
        row=self._lookup(request,check_csrf=request.method not in ('GET','HEAD','OPTIONS'))
        row.pop('csrf_token')
        return row

    def session(self, request):
        self._require_origin(request)
        row=self._lookup(request)
        return self._no_store(JSONResponse({'actor':{k:v for k,v in row.items() if k!='csrf_token'},
                                              'csrf_token':row['csrf_token']}))

    def logout(self, request):
        self._require_origin(request)
        self._lookup(request,check_csrf=True)
        with self.db.connect() as cx:
            cx.execute('DELETE FROM oidc_browser_sessions WHERE session_hash=?',
                       (token_digest(request.cookies[SESSION_COOKIE]),))
        response=Response(status_code=204)
        response.delete_cookie(SESSION_COOKIE,secure=True,httponly=True,samesite='lax',path='/')
        return self._no_store(response)
