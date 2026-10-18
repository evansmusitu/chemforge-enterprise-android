"""v2.8 dry-run TLS profile: no credentials, connection, or public admission."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from control_plane.postgres_synthetic import ACKNOWLEDGEMENT, validate_configuration
from tools.neon_tls_preflight import evaluate_neon_tls_candidate

ROOT = Path(__file__).resolve().parents[2]
# Deliberately nonexistent synthetic host and token, never a real Neon credential.
SECRET = 'FAKE_TEST_PWD_NEVER_USE_123456'
HOST = 'ep-chemforge-example.c-7.us-east-2.aws.neon.tech'
GOOD = (f'postgresql://chemforge_synthetic:{SECRET}@{HOST}:5432/'
        'chemforge_synthetic?sslmode=verify-full&sslrootcert=system')


@pytest.fixture
def policy():
    contract = json.loads((ROOT / 'deployment/zero_budget_contract.json').read_text())
    attestation = json.loads((ROOT / 'deployment/neon_synthetic_staging_evidence_v27.json').read_text())
    return contract, attestation


def test_valid_tls_dry_run_never_allows_network_or_deployment(policy, monkeypatch):
    import socket
    def unexpected_network(*_args, **_kwargs):
        raise AssertionError('No network calls allowed in offline TLS preflight')
    monkeypatch.setattr(socket, 'socket', unexpected_network)
    result = evaluate_neon_tls_candidate(GOOD, *policy)
    assert result['status'] == 'TLS_PROFILE_VALID_NOT_CONNECTED'
    assert result['deployment_allowed'] is False
    assert result['certificate_verified'] is False
    assert result['connection_attempted'] is False
    assert result['real_student_data_allowed'] is False
    assert SECRET not in json.dumps(result)
    assert HOST not in json.dumps(result)


@pytest.mark.parametrize('dsn', [
    '',
    'postgresql://chemforge_synthetic:PASSWORD@localhost:5432/chemforge_synthetic?sslmode=verify-full&sslrootcert=system',
    'postgresql://chemforge_synthetic:PASSWORD@127.0.0.1:5432/chemforge_synthetic?sslmode=verify-full&sslrootcert=system',
    'postgresql://chemforge_synthetic:PASSWORD@ep-x.c-7.us-east-2.aws.neon.tech.evil.org:5432/chemforge_synthetic?sslmode=verify-full&sslrootcert=system',
    'postgresql://chemforge_synthetic:PASSWORD@ep-x.c-2.us-east-2.aws.neon.tech:5432/chemforge_synthetic?sslmode=verify-full&sslrootcert=system',
    'postgresql://nexus_live_runtime:PASSWORD@ep-x.c-7.us-east-2.aws.neon.tech:5432/chemforge_synthetic?sslmode=verify-full&sslrootcert=system',
    'postgresql://chemforge_synthetic:PASSWORD@ep-x.c-7.us-east-2.aws.neon.tech:5432/nexus_live_runtime?sslmode=verify-full&sslrootcert=system',
    'postgresql://chemforge_synthetic:PASSWORD@ep-x.c-7.us-east-2.aws.neon.tech:5432/chemforge_synthetic?sslmode=disable&sslrootcert=system',
    'postgresql://chemforge_synthetic:PASSWORD@ep-x.c-7.us-east-2.aws.neon.tech:5432/chemforge_synthetic?sslmode=require&sslrootcert=system',
    'postgresql://chemforge_synthetic:PASSWORD@ep-x.c-7.us-east-2.aws.neon.tech:5432/chemforge_synthetic?sslmode=verify-ca&sslrootcert=system',
    'postgresql://chemforge_synthetic:PASSWORD@ep-x.c-7.us-east-2.aws.neon.tech:5432/chemforge_synthetic?sslmode=verify-full',
    'postgresql://chemforge_synthetic:PASSWORD@ep-x.c-7.us-east-2.aws.neon.tech:5432/chemforge_synthetic?sslmode=verify-full&sslrootcert=system&sslmode=disable',
    'postgresql://chemforge_synthetic:PASSWORD@ep-x.c-7.us-east-2.aws.neon.tech:5432/chemforge_synthetic?sslmode=verify-full&sslrootcert=system&options=-csearch_path%3Dpublic',
    'postgresql://chemforge_synthetic:PASSWORD@ep-x.c-7.us-east-2.aws.neon.tech:5432/chemforge_synthetic?sslmode=verify-full&sslrootcert=system#fragment',
    'postgresql://chemforge_synthetic@ep-x.c-7.us-east-2.aws.neon.tech:5432/chemforge_synthetic?sslmode=verify-full&sslrootcert=system',
    'postgresql://chemforge_synthetic:PASSWORD@ep-x.c-7.us-east-2.aws.neon.tech:9999/chemforge_synthetic?sslmode=verify-full&sslrootcert=system',
    'postgresql://chemforge_synthetic:PASSWORD@ep-x.c-7.us-east-2.aws.neon.tech:99999/chemforge_synthetic?sslmode=verify-full&sslrootcert=system',
    'postgresql://chemforge_synthetic:PASSWORD@ep-x.c-7.us-east-2.aws.neon.tech:5432/chemforge_synthetic?sslmode=verify-full&sslrootcert=system&',
])
def test_rejects_unsafe_or_ambiguous_urls_without_echoing_secrets(policy, dsn):
    result = evaluate_neon_tls_candidate(dsn, *policy)
    assert result['status'] == 'BLOCKED'
    assert result['deployment_allowed'] is False
    assert 'PASSWORD' not in json.dumps(result)
    assert result['connection_attempted'] is False


@pytest.mark.parametrize('mutation', [
    lambda c, a: c.update({'provider_deploy_enabled': True}),
    lambda c, a: c.update({'max_monthly_spend_usd': 1}),
    lambda c, a: a.update({'public_connections_blocked': False}),
    lambda c, a: a.update({'project_id': 'quiet-thunder-10380542'}),
    lambda c, a: a.update({'secret_values_present': True}),
])
def test_project_and_zero_budget_flags_override_valid_profile(policy, mutation):
    contract, attestation = policy
    mutation(contract, attestation)
    result = evaluate_neon_tls_candidate(GOOD, contract, attestation)
    assert result['status'] == 'BLOCKED'
    assert result['deployment_allowed'] is False
    assert SECRET not in json.dumps(result)


def test_existing_backend_still_refuses_same_remote_dsn(policy):
    """A successful lint is NOT permission to connect, even in synthetic mode."""
    env = {'CHEMFORGE_POSTGRES_SYNTHETIC_ONLY': ACKNOWLEDGEMENT, 'CHEMFORGE_PG_DSN': GOOD}
    with pytest.raises(ValueError, match='disposable database'):
        validate_configuration(env)


def test_module_cli_does_not_print_credential_and_has_no_connection_side_effects(policy):
    """The public CI command only accepts an env var, never argv DSNs."""
    import os
    import subprocess
    import sys

    env = {**os.environ, 'CHEMFORGE_NEON_TLS_DRY_RUN_DSN': GOOD}
    result = subprocess.run([sys.executable, '-m', 'tools.neon_tls_preflight'],
                            cwd=str(ROOT), env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['status'] == 'TLS_PROFILE_VALID_NOT_CONNECTED'
    assert SECRET not in (result.stdout + result.stderr)
    assert HOST not in (result.stdout + result.stderr)

    no_secret = subprocess.run([sys.executable, '-m', 'tools.neon_tls_preflight'],
                               cwd=str(ROOT), env={k:v for k,v in env.items() if k != 'CHEMFORGE_NEON_TLS_DRY_RUN_DSN'},
                               capture_output=True, text=True)
    assert no_secret.returncode == 2
    assert json.loads(no_secret.stdout)['status'] == 'BLOCKED'
