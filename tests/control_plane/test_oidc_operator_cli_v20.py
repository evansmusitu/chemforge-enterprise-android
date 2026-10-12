"""Operator provisioning must remain offline and explicit."""
import subprocess
import sys
from control_plane.db import Database


def test_operator_cli_links_existing_staff_only(tmp_path):
    path=tmp_path/'school.sqlite'
    db=Database(str(path))
    db.bootstrap_tenant('school-alpha','Administrator')
    with db.connect() as cx:
        actor=cx.execute("SELECT id FROM actors WHERE tenant_id='school-alpha'").fetchone()['id']
    args=[sys.executable,'-m','control_plane.cli','link-oidc','--db',str(path),
          '--tenant','school-alpha','--actor-id',actor,
          '--issuer','https://login.example.invalid/chemforge','--subject','staff-operator-100']
    r=subprocess.run(args, capture_output=True,text=True)
    assert r.returncode==0,r.stderr
    assert 'staff-operator-100' not in r.stdout
    with db.connect() as cx:
        row=cx.execute('SELECT issuer,subject,tenant_id FROM oidc_actor_links WHERE actor_id=?',(actor,)).fetchone()
        assert dict(row)=={'issuer':'https://login.example.invalid/chemforge','subject':'staff-operator-100','tenant_id':'school-alpha'}
    repeated=subprocess.run(args,capture_output=True,text=True)
    assert repeated.returncode!=0


def test_operator_cli_cannot_link_nonexistent_or_foreign_actor(tmp_path):
    path=tmp_path/'school.sqlite'
    db=Database(str(path))
    db.bootstrap_tenant('school-alpha','Administrator')
    db.bootstrap_tenant('school-bravo','Administrator')
    with db.connect() as cx:
        foreign=cx.execute("SELECT id FROM actors WHERE tenant_id='school-bravo'").fetchone()['id']
    args=[sys.executable,'-m','control_plane.cli','link-oidc','--db',str(path),
          '--tenant','school-alpha','--actor-id',foreign,
          '--issuer','https://login.example.invalid/chemforge','--subject','malicious-cross-tenant']
    r=subprocess.run(args,capture_output=True,text=True)
    assert r.returncode!=0
    with db.connect() as cx:
        assert cx.execute('SELECT COUNT(*) AS n FROM oidc_actor_links').fetchone()['n']==0
