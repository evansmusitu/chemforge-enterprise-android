"""Local, deterministic checks for an externally verified Neon account snapshot."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from tools.neon_staging_gate import validate_attestation, evaluate_readiness

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def evidence():
    return json.loads((ROOT / 'deployment/neon_synthetic_staging_evidence_v27.json').read_text())


def test_real_checked_free_project_is_recorded_but_runtime_stays_disabled(evidence):
    assert validate_attestation(evidence) == []
    status = evaluate_readiness(evidence)
    assert status['stage'] == 'PROVISIONED_LOCKED_EMPTY'
    assert status['production_ready'] is False
    assert status['public_api_enabled'] is False
    assert status['real_student_data_allowed'] is False
    assert status['status'] == 'EVIDENCE_VALID_NOT_DEPLOYED'


@pytest.mark.parametrize('key,unsafe', [
    ('plan','launch'),
    ('project_id','quiet-thunder-10380542'),  # Education Nexus, strictly separate
    ('org_id','someone-else'),
    ('database_name','nexus_live_runtime'),
    ('role_name','nexus_live_runtime'),
    ('pg_version',16),
    ('public_connections_blocked',False),
    ('observed_public_table_count',1),
    ('autoscaling_limit_max_cu',2.0),
    ('real_student_data_allowed',True),
    ('public_api_enabled',True),
    ('runtime_deployment_enabled',True),
    ('secret_values_present',True),
])
def test_fail_closed_on_staging_escape(evidence,key,unsafe):
    bad = copy.deepcopy(evidence)
    bad[key] = unsafe
    assert validate_attestation(bad), f'accepted dangerous {key}={unsafe}'
    assert evaluate_readiness(bad)['status'] == 'BLOCKED'


def test_unknown_fields_and_missing_identity_block(evidence):
    for change in ('unknown', 'missing'):
        bad = copy.deepcopy(evidence)
        if change == 'unknown':
            bad['database_password'] = 'SHOULD_NOT_APPEAR_IN_A_REPO'
        else:
            del bad['branch_id']
        assert validate_attestation(bad)


def test_gate_never_provides_a_go_live_signal(evidence):
    result = evaluate_readiness(evidence)
    assert 'GO_LIVE' not in json.dumps(result)
    assert not result.get('deployment_allowed',False)
