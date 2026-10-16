"""Validate one historical, secret-free Neon free-tier provisioning snapshot.

OFFLINE ONLY. Never contacts Neon, connects a DB, migrates, or authorizes deploy.
An old valid snapshot does NOT prove current provider configuration or billing.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

# Deliberately pinned to a verified CHEMFORGE-owned resource and to a frozen
# observation. Changing any value requires separate live provider verification.
EXPECTED = {
    'schema': 'chemforge.neon.synthetic_staging_attestation.v1',
    'observed_on_utc': '2026-10-16',
    'provider': 'Neon',
    'plan': 'free_v3',
    'org_id': 'org-frosty-morning-97872293',
    'project_id': 'delicate-haze-29026531',
    'project_name': 'CHEMFORGE Synthetic Staging - No Student Data',
    'branch_id': 'br-wandering-boat-b5o4f2ty',
    'branch_name': 'synthetic-staging',
    'database_name': 'chemforge_synthetic',
    'role_name': 'chemforge_synthetic',
    'region_id': 'aws-us-east-2',
    'pg_version': 17,
    'public_connections_blocked': True,
    'observed_public_table_count': 0,
    'autoscaling_limit_max_cu': 0.25,
    'real_student_data_allowed': False,
    'public_api_enabled': False,
    'runtime_deployment_enabled': False,
    'secret_values_present': False,
}


def validate_attestation(attestation: dict) -> list[str]:
    """Conservative immutable observation; no credentials or runtime effects."""
    if not isinstance(attestation, dict):
        return ['invalid_attestation_type']
    issues = []
    for key in sorted(set(EXPECTED) - set(attestation)):
        issues.append('missing_' + key)
    for key in sorted(set(attestation) - set(EXPECTED)):
        issues.append('unrecognized_' + key)
    for key, expected in EXPECTED.items():
        if key in attestation and (type(attestation[key]) is not type(expected) or attestation[key] != expected):
            issues.append('mismatch_' + key)
    return issues


def evaluate_readiness(attestation: dict) -> dict:
    issues = validate_attestation(attestation)
    return {
        'status': 'BLOCKED' if issues else 'EVIDENCE_VALID_NOT_DEPLOYED',
        'stage': 'BLOCKED' if issues else 'PROVISIONED_LOCKED_EMPTY',
        'production_ready': False,
        'public_api_enabled': False,
        'real_student_data_allowed': False,
        'deployment_allowed': False,
        'errors': issues,
        'evidence_is_live': False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', type=Path, default=Path('deployment/neon_synthetic_staging_evidence_v27.json'))
    args = parser.parse_args()
    try:
        observation = json.loads(args.evidence.read_text(encoding='utf-8'))
    except (OSError, ValueError, UnicodeError):
        observation = None
    result = evaluate_readiness(observation)
    print(json.dumps(result, sort_keys=True))
    return 2 if result['status'] == 'BLOCKED' else 0


if __name__ == '__main__':
    raise SystemExit(main())
