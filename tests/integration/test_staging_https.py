"""Exercise real HTTPS transport, not FastAPI TestClient, using disposable records."""
from tests.integration.staging_https import prepare, exercise_https, generate_self_signed_cert
from pathlib import Path
import ssl
import urllib.request
import urllib.error
from subprocess import Popen
import os
import socket
import sys
import time


def test_ephemeral_https_real_roundtrip(tmp_path):
    bundle = prepare(tmp_path)
    assert bundle['tenant'] == 'school-e2e'
    assert bundle['backup']['attempts'][0]['mark'] == 1
    assert 'cfsync_' in bundle['token']
    result = exercise_https(tmp_path)
    assert result['first'] == (201, 1, 0)
    assert result['retry'] == (200, 0, 1)
    assert result['revoked'] == 401
    assert result['wrong_school'] == 422
    assert result['teacher_count'] == 1
    assert result['foreign_count'] == 0
    assert result['cert_rejected'] is True
