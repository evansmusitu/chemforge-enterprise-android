"""Pinned-key OIDC *staff access-token* verifier for the CHEMFORGE pilot API.

Enterprise mode refuses all legacy staff bearer credentials. The operator pins a
local, vetted JWKS file from the institutional issuer. No token can select a
remote JWKS URL. This is not the OIDC authorisation-code browser login flow.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

import jwt
from jwt import exceptions as jwt_errors


class StaffAuthenticationError(ValueError):
    """Opaque denial: do not disclose identity or token parsing details to clients."""


@dataclass(frozen=True)
class OIDCConfiguration:
    issuer: str
    audience: str
    keys: dict[str, object]

    @classmethod
    def from_environment(cls, env):
        issuer = env.get('CHEMFORGE_OIDC_ISSUER', '').strip()
        audience = env.get('CHEMFORGE_OIDC_AUDIENCE', '').strip()
        location = env.get('CHEMFORGE_OIDC_JWKS_FILE', '').strip()
        parsed = urlsplit(issuer)
        if (not issuer or parsed.scheme != 'https' or not parsed.netloc
                or parsed.query or parsed.fragment or issuer.endswith('/')
                or not audience or len(audience)>200 or not location):
            raise ValueError('OIDC requires an HTTPS issuer, audience, and pinned JWKS file')
        path = Path(location).resolve()
        if not path.is_file() or path.stat().st_size > 131072:
            raise ValueError('OIDC pinned JWKS file is missing or too large')
        try:
            jwks = json.loads(path.read_text(encoding='utf-8'))
            if not isinstance(jwks, dict) or not isinstance(jwks.get('keys'), list):
                raise ValueError('Invalid pinned key set')
            keys={}
            for item in jwks['keys']:
                if not isinstance(item, dict):
                    raise ValueError('Invalid OIDC key entry')
                kid=item.get('kid')
                if (not isinstance(kid, str) or not 1 <= len(kid) <= 120
                        or kid in keys or not re.fullmatch(r'[A-Za-z0-9_.:-]+', kid)
                        or item.get('kty') != 'RSA'
                        or item.get('alg', 'RS256') != 'RS256'
                        or item.get('use', 'sig') != 'sig'
                        or any(k in item for k in ('d','p','q','dp','dq','qi','oth'))):
                    raise ValueError('OIDC JWKS must contain unique RSA verification keys only')
                key=jwt.PyJWK.from_dict(item, algorithm='RS256').key
                if key.key_size < 2048:
                    raise ValueError('OIDC signing key must have at least 2048 bits')
                keys[kid]=key
            if not keys or len(keys)>20:
                raise ValueError('OIDC JWKS must contain 1–20 signing keys')
        except (OSError, UnicodeError, json.JSONDecodeError, jwt_errors.PyJWTError, KeyError, TypeError) as exc:
            raise ValueError('OIDC pinned JWKS is invalid') from exc
        return cls(issuer, audience, keys)

    def verify_claims(self, token: str) -> dict:
        if not isinstance(token,str) or len(token)>12000 or token.count('.') != 2:
            raise StaffAuthenticationError('Invalid OIDC access token')
        try:
            header=jwt.get_unverified_header(token)
            kid=header.get('kid')
            typ=header.get('typ')
            if (header.get('alg') != 'RS256' or not isinstance(typ,str)
                    or typ.lower() not in ('at+jwt','application/at+jwt')
                    or not isinstance(kid,str)
                    or kid not in self.keys or header.get('crit')):
                raise StaffAuthenticationError('Invalid OIDC access token')
            payload=jwt.decode(token,self.keys[kid],algorithms=['RS256'],
                    issuer=self.issuer,audience=self.audience,
                    options={'require':['iss','aud','sub','exp','iat','nbf','client_id','jti'],'strict_aud':True},
                    leeway=15)
            sub=payload.get('sub')
            amr=payload.get('amr')
            if (not isinstance(sub,str) or not 1<=len(sub)<=255 or not sub.strip()
                    or not isinstance(payload.get('client_id'),str) or not payload['client_id']
                    or not isinstance(payload.get('jti'),str) or not payload['jti']
                    or not isinstance(amr,list) or not all(isinstance(x,str) for x in amr)
                    or 'mfa' not in amr):
                raise StaffAuthenticationError('Invalid OIDC access token')
            if payload['exp'] - payload['iat'] > 3600:
                raise StaffAuthenticationError('OIDC access token lifetime exceeds one hour')
            return payload
        except (jwt_errors.PyJWTError,ValueError,TypeError,KeyError) as exc:
            raise StaffAuthenticationError('Invalid OIDC access token') from exc

    def verify(self, token: str) -> str:
        return self.verify_claims(token)['sub']
