"""Fail-closed synthetic-only PostgreSQL native-backup restore qualification."""
from __future__ import annotations

import os

import pytest

from control_plane.postgres_synthetic import ACKNOWLEDGEMENT

SYNTHETIC = {
    'CHEMFORGE_POSTGRES_SYNTHETIC_ONLY': ACKNOWLEDGEMENT,
    'CHEMFORGE_PG_CI': '1',
    'CHEMFORGE_PG_DSN': 'postgresql://synthetic:mock@127.0.0.1:5432/chemforge_synthetic?sslmode=disable',
    'CHEMFORGE_PG_RESTORE_DSN': 'postgresql://synthetic:mock@127.0.0.1:5432/chemforge_synthetic_restore?sslmode=disable',
}


def test_restore_drill_requires_disposable_ci_acknowledgement():
    from tools.postgres_restore_drill import validate_restore_config
    for field in ('CHEMFORGE_POSTGRES_SYNTHETIC_ONLY','CHEMFORGE_PG_CI'):
        env = dict(SYNTHETIC)
        env.pop(field)
        with pytest.raises(ValueError, match='synthetic|CI'):
            validate_restore_config(env)


def test_restore_drill_denies_same_database_and_remote_target():
    from tools.postgres_restore_drill import validate_restore_config
    for target in (
        SYNTHETIC['CHEMFORGE_PG_DSN'],
        'postgresql://synthetic:mock@neon.example.invalid:5432/chemforge_synthetic_restore?sslmode=disable',
        'postgresql://synthetic:mock@127.0.0.1:5432/chemforge_synthetic_restore?sslmode=require',
        'postgresql://synthetic:mock@127.0.0.1:5432/chemforge_synthetic_restore?sslmode=disable&application_name=other',
        'postgresql://synthetic:mock@127.0.0.1:5432/school_prod?sslmode=disable',
    ):
        with pytest.raises(ValueError, match='restore|disposable'):
            validate_restore_config({**SYNTHETIC, 'CHEMFORGE_PG_RESTORE_DSN': target})


def test_restore_drill_denies_wrong_source_or_credential_pair():
    from tools.postgres_restore_drill import validate_restore_config
    for field,value in (
        ('CHEMFORGE_PG_DSN','postgresql://synthetic:mock@127.0.0.1:5432/student_prod?sslmode=disable'),
        ('CHEMFORGE_PG_RESTORE_DSN','postgresql://another:mock@127.0.0.1:5432/chemforge_synthetic_restore?sslmode=disable'),
    ):
        with pytest.raises(ValueError, match='dedicated|same'):
            validate_restore_config({**SYNTHETIC,field:value})


def test_restore_drill_does_not_include_credentials_in_errors():
    from tools.postgres_restore_drill import validate_restore_config
    sample = 'DELIBERATE_TEST_VALUE'
    env = {**SYNTHETIC, 'CHEMFORGE_PG_RESTORE_DSN':f'postgresql://synthetic:{sample}@remote.example.invalid:5432/chemforge_synthetic_restore?sslmode=disable'}
    with pytest.raises(ValueError) as exc:
        validate_restore_config(env)
    assert sample not in str(exc.value)


def test_restore_drill_rejects_unexpected_table_names_without_connecting():
    from tools.postgres_restore_drill import table_inventory
    expected = table_inventory()
    assert 'students' in expected and 'audit' in expected and 'chemforge_schema_versions' in expected
    assert 'private_users' not in expected
    assert len(expected) == len(set(expected))


def test_restore_pg_integrity_with_live_container_only():
    if os.environ.get('CHEMFORGE_PG_CI') != '1':
        pytest.skip('GitHub hosted disposable PostgreSQL container only')
    from tools.postgres_restore_drill import validate_restore_config
    # This tests the admission preflight only; actual full backup and restore
    # must be run by the CI workflow AFTER tenant regression tests populate DB.
    validate_restore_config(os.environ)
