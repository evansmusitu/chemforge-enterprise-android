"""OIDC access tokens must fit the login form without local credential persistence."""
import re
from fastapi.testclient import TestClient
from control_plane.app import create_app


def test_dashboard_accepts_short_lived_oidc_jwt_format_and_keeps_in_memory(tmp_path, monkeypatch):
    monkeypatch.setenv('CHEMFORGE_STAFF_AUTH','pilot')
    with TestClient(create_app(str(tmp_path/'school.db'))) as client:
        html=client.get('/control/').text
        js=client.get('/control/app.js').text
    match=re.search(r'<input[^>]+id="credential"[^>]*>',html)
    assert match
    assert int(re.search(r'maxlength="(\d+)"',match.group(0)).group(1)) >= 4096
    assert 'short-lived' in html.lower() and 'oidc' in html.lower()
    assert 'localStorage' not in js and 'sessionStorage' not in js
