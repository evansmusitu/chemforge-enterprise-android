"""Disposable synthetic HTTPS staging for CHEMFORGE Control.

Never binds publicly unless invoked deliberately. Creates ephemeral TLS material
and test-only school records. Not a replacement for an internet-accessible,
production-hardened staging service.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import socket
import ssl
import subprocess
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from fastapi.testclient import TestClient
from control_plane.db import Database
from control_plane.app import create_app


def generate_self_signed_cert(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    cert, key = root / 'staging-cert.pem', root / 'staging-key.pem'
    subprocess.run([
        'openssl', 'req', '-x509', '-newkey', 'rsa:2048',
        '-sha256', '-nodes', '-days', '1', '-keyout', str(key),
        '-out', str(cert), '-subj', '/CN=CHEMFORGE synthetic CI staging',
        '-addext', 'subjectAltName=IP:127.0.0.1,IP:10.0.2.2,DNS:localhost',
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    key.chmod(0o600)
    return cert


def _auth(token: str, kind: str = 'Bearer') -> dict:
    return {'Authorization': kind + ' ' + token}


def prepare(root: Path) -> dict:
    """Prepare two schools, one teacher grant, live/revoked/cross-school device tokens."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    generate_self_signed_cert(root)
    db_path = str(root / 'synthetic.sqlite')
    db = Database(db_path)
    admin = db.bootstrap_tenant('school-e2e', 'Synthetic School Admin')
    other_admin = db.bootstrap_tenant('school-other', 'Other Synthetic Admin')
    with TestClient(create_app(db_path)) as client:
        def post(route: str, token: str, body: dict) -> dict:
            res = client.post(route, headers=_auth(token), json=body)
            assert res.status_code == 201, f'{route}: {res.status_code} {res.text}'
            return res.json()

        learner = post('/v1/students', admin, {'pseudonym': 'Synthetic Student A', 'cohort': 'U6-A'})
        post('/v1/students', admin, {'pseudonym': 'Synthetic Student B', 'cohort': 'U6-B'})
        post('/v1/students', other_admin, {'pseudonym': 'Other Student', 'cohort': 'U6-A'})
        teacher = post('/v1/teachers', admin, {'label': 'Synthetic Chemistry Teacher'})
        assert client.post(f"/v1/teachers/{teacher['actor_id']}/cohorts", headers=_auth(admin),
                           json={'cohort': 'U6-A'}).status_code == 201
        device = post('/v1/devices', admin, {'student_id': learner['id'], 'label': 'Synthetic emulator', 'valid_days': 1})
        revoked = post('/v1/devices', admin, {'student_id': learner['id'], 'label': 'Revoked synthetic device', 'valid_days': 1})
        assert client.delete('/v1/devices/' + revoked['device_id'], headers=_auth(admin)).status_code == 204
        other_student = client.get('/v1/students', headers=_auth(other_admin)).json()[0]
        other_device = post('/v1/devices', other_admin, {'student_id': other_student['id'], 'label': 'Foreign synthetic device', 'valid_days': 1})

    attempt = {
        'id': 'emulator-e2e-event-001', 'question_id': 'CF-Q-001',
        'mark': 1, 'max_marks': 1, 'assessment_source': 'deterministic_key',
        'hints_used': 0, 'mode': 'practice', 'recorded_at': '2026-10-12T09:00:00Z',
        'tenant_id': 'school-e2e', 'content_version': 'pilot-0.1',
        'content_fingerprint': 'pilot-0.1',
    }
    backup = {
        'app': 'CHEMFORGE_ANDROID', 'schema_version': 1,
        'tenant_id': 'school-e2e', 'content_version': 'pilot-0.1',
        'content_fingerprint': 'pilot-0.1', 'attempts': [attempt],
    }
    bundle = {
        'tenant': 'school-e2e', 'admin': admin, 'teacher': teacher['token'],
        'foreign_admin': other_admin, 'token': device['token'],
        'revoked_token': revoked['token'], 'foreign_token': other_device['token'],
        'student_id': learner['id'], 'backup': backup,
    }
    (root / 'fixture.json').write_text(json.dumps(bundle, sort_keys=True), encoding='utf-8')
    (root / 'backup.json').write_text(json.dumps(backup, sort_keys=True), encoding='utf-8')
    for fname in ('fixture.json', 'backup.json'):
        (root / fname).chmod(0o600)
    return bundle


def _port() -> int:
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return int(sock.getsockname()[1])


def _request(url: str, ctx: ssl.SSLContext, method='GET', token=None, body=None):
    headers = {'Accept': 'application/json'}
    if token:
        headers['Authorization'] = token
    data = None
    if body is not None:
        data = json.dumps(body).encode('utf-8')
        headers['Content-Type'] = 'application/json'
    request = Request(url, method=method, headers=headers, data=data)
    try:
        with urlopen(request, context=ctx, timeout=7) as response:
            return response.status, json.loads(response.read()) if response.status != 204 else None
    except HTTPError as err:
        err.read()
        return err.code, None


def inspect_https(base: str, root: Path, *, perform_upload: bool = False) -> dict:
    bundle = json.loads((Path(root) / 'fixture.json').read_text())
    ctx = ssl.create_default_context(cafile=str(Path(root) / 'staging-cert.pem'))
    assert _request(base + '/health', ctx) == (200, {'status': 'ok'})
    # Test-only certificate MUST NOT be silently trusted by ordinary HTTPS.
    rejected = False
    try:
        _request(base + '/health', ssl.create_default_context())
    except (ssl.SSLError, URLError) as exc:
        if isinstance(exc, URLError) and not isinstance(exc.reason, ssl.SSLError):
            raise
        rejected = True
    assert rejected, 'Untrusted synthetic staging cert must be rejected by default TLS'
    with urlopen(base + '/control/', context=ctx, timeout=7) as response:
        assert response.status == 200 and b'CHEMFORGE' in response.read()
    if perform_upload:
        first = _request(base + '/v1/sync/backups', ctx, 'POST',
                         'Device ' + bundle['token'], bundle['backup'])
        retry = _request(base + '/v1/sync/backups', ctx, 'POST',
                         'Device ' + bundle['token'], bundle['backup'])
        assert first[1]['verified'] == retry[1]['verified'] == 0
        first_r = (first[0], first[1]['imported'], first[1]['unchanged'])
        retry_r = (retry[0], retry[1]['imported'], retry[1]['unchanged'])
    else:
        first_r = retry_r = None
    revoked = _request(base + '/v1/sync/backups', ctx, 'POST',
                       'Device ' + bundle['revoked_token'], bundle['backup'])[0]
    foreign = _request(base + '/v1/sync/backups', ctx, 'POST',
                       'Device ' + bundle['foreign_token'], bundle['backup'])[0]
    teacher = _request(base + '/v1/analytics/cohorts', ctx, token='Bearer ' + bundle['teacher'])
    foreign_analytics = _request(base + '/v1/analytics/cohorts', ctx,
                                 token='Bearer ' + bundle['foreign_admin'])
    assert teacher[0] == foreign_analytics[0] == 200
    assert all(row['verified_attempts'] == 0 for row in teacher[1])
    assert all(row['cohort'] == 'U6-A' for row in teacher[1])
    return {'first': first_r, 'retry': retry_r, 'revoked': revoked,
            'wrong_school': foreign, 'teacher_count': sum(x['unverified_attempts'] for x in teacher[1]),
            'foreign_count': sum(x['unverified_attempts'] for x in foreign_analytics[1]),
            'cert_rejected': rejected}


def exercise_https(root: Path) -> dict:
    root = Path(root)
    port = _port()
    env = dict(os.environ, CHEMFORGE_CONTROL_DB=str(root / 'synthetic.sqlite'))
    proc = subprocess.Popen([
        sys.executable, '-m', 'uvicorn', 'control_plane.app:create_app', '--factory',
        '--host', '127.0.0.1', '--port', str(port),
        '--ssl-certfile', str(root / 'staging-cert.pem'),
        '--ssl-keyfile', str(root / 'staging-key.pem'), '--no-access-log',
    ], cwd=Path(__file__).resolve().parents[2], env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    try:
        base = 'https://127.0.0.1:' + str(port)
        ctx = ssl.create_default_context(cafile=str(root / 'staging-cert.pem'))
        for i in range(60):
            try:
                if _request(base + '/health', ctx)[0] == 200:
                    break
            except (URLError, ConnectionError):
                if proc.poll() is not None:
                    raise RuntimeError('Staging process exited early: ' + proc.stderr.read()[-600:])
                time.sleep(0.1)
        else:
            raise RuntimeError('Staging HTTPS did not start')
        return inspect_https(base, root, perform_upload=True)
    finally:
        proc.terminate()
        try:
            proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()


def main():
    parser = argparse.ArgumentParser(description='CHEMFORGE synthetic staging (NEVER real student data)')
    parser.add_argument('action', choices=['prepare', 'verify', 'demo'])
    parser.add_argument('--dir', default='/tmp/chemforge-staging')
    parser.add_argument('--url', default='https://127.0.0.1')
    args = parser.parse_args()
    root = Path(args.dir)
    if args.action == 'prepare':
        result = prepare(root)
        print('Prepared synthetic school, teacher, student, and device fixtures (secrets hidden).')
    elif args.action == 'demo':
        result = prepare(root)
        result = exercise_https(root)
        assert result == {'first': (201, 1, 0), 'retry': (200, 0, 1),
                          'revoked': 401, 'wrong_school': 422,
                          'teacher_count': 1, 'foreign_count': 0,
                          'cert_rejected': True}, result
        print('Synthetic HTTPS real-transport roundtrip: PASS', result)
    else:
        result = inspect_https(args.url, root)
        assert result['teacher_count'] == 1, result
        assert result['foreign_count'] == 0 and result['revoked'] == 401 and result['wrong_school'] == 422, result
        print('Android-origin upload is visible only to assigned teacher: PASS', result)

if __name__ == '__main__':
    main()
