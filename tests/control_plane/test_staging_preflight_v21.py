"""DB prerequisites are executable locally, without real student data."""
from pathlib import Path
import pytest
from control_plane.db import Database
from tools.staging_preflight import check


def test_preflight_only_existing_private_synthetic_pilot_database(tmp_path):
    path=tmp_path/'synthetic.sqlite'
    Database(str(path)).bootstrap_tenant('school-a','Synthetic Principal')
    assert path.stat().st_mode & 0o077 == 0
    assert check(path,synthetic=True)['production_readiness']=='NOT_ASSESSED'
    with pytest.raises(ValueError,match='synthetic-only'):
        check(path)
    path.chmod(0o644)
    with pytest.raises(ValueError,match='owner-only'):
        check(path,synthetic=True)


def test_preflight_rejects_missing_and_symlinked_database(tmp_path):
    with pytest.raises(ValueError):
        check(tmp_path/'notfound.sqlite',synthetic=True)
    real=tmp_path/'real.sqlite'; Database(str(real))
    link=tmp_path/'link.sqlite';link.symlink_to(real)
    with pytest.raises(ValueError,match='symlink'):
        check(link,synthetic=True)
