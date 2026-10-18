"""Validate CHEMFORGE's future Neon TLS profile OFFLINE, without connecting.

A syntactically valid connection profile is not a staging admission and never
relaxes the existing local-only Postgres adapter or locked Neon project.

Only pass DSNs via environment variables. Never commit or print credentials.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
from urllib.parse import parse_qsl, unquote, urlsplit

from tools.neon_staging_gate import validate_attestation
from tools.zero_budget_gate import validate_contract

# The first part of the hostname is not proof of this project's identity. It
# is only the observed provider+regional DNS profile; project/branch identity
# must be independently validated against Neon before any network admission.
_HOST = re.compile(r'^ep-[a-z0-9]+(?:-[a-z0-9]+)*\.c-7\.us-east-2\.aws\.neon\.tech$', re.ASCII)
_EXACT_QUERY = {'sslmode': 'verify-full', 'sslrootcert': 'system'}


def _matches_tls_profile(dsn: object) -> bool:
    """Parse only; never import a DB driver, open sockets or return a secret."""
    if not isinstance(dsn, str) or not (32 <= len(dsn) <= 4096):
        return False
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in dsn):
        return False
    try:
        parsed = urlsplit(dsn)
        # Enforce exact username/database/region/profile. Reject query overrides
        # rather than relying on libpq's last-value-wins duplicate handling.
        pairs = parse_qsl(parsed.query, strict_parsing=True, keep_blank_values=True)
        if len(pairs) != 2 or len({key for key, _ in pairs}) != 2:
            return False
        if dict(pairs) != _EXACT_QUERY:
            return False
        return bool(
            parsed.scheme == 'postgresql'
            and parsed.hostname is not None and _HOST.fullmatch(parsed.hostname)
            and parsed.port == 5432
            and parsed.username is not None
            and unquote(parsed.username) == 'chemforge_synthetic'
            and parsed.password is not None
            and bool(unquote(parsed.password))
            and parsed.path == '/chemforge_synthetic'
            and not parsed.fragment
        )
    except (ValueError, UnicodeError):
        return False


def evaluate_neon_tls_candidate(dsn: object, contract: object, attestation: object) -> dict:
    """Non-connecting, credential-redacted evaluation. NOT a launch token.

    The historical v2.7 attestation is NOT an up-to-date provider/billing check;
    this function never attempts to turn it into a live authorization.
    """
    issues: list[str] = []
    if validate_contract(contract):
        issues.append('zero_budget_contract_invalid')
    if validate_attestation(attestation):
        issues.append('historical_neon_attestation_invalid')
    if not _matches_tls_profile(dsn):
        issues.append('remote_tls_profile_rejected')
    status = 'BLOCKED' if issues else 'TLS_PROFILE_VALID_NOT_CONNECTED'
    return {
        'status': status,
        'issues': issues,
        'connection_attempted': False,
        'certificate_verified': False,
        'provider_project_identity_verified': False,
        'provider_policy_verified_live': False,
        'deployment_allowed': False,
        'public_api_enabled': False,
        'real_student_data_allowed': False,
        'budget_usd': 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--contract', type=Path, default=Path('deployment/zero_budget_contract.json'))
    parser.add_argument('--evidence', type=Path, default=Path('deployment/neon_synthetic_staging_evidence_v27.json'))
    args = parser.parse_args()
    try:
        contract = json.loads(args.contract.read_text(encoding='utf-8'))
        evidence = json.loads(args.evidence.read_text(encoding='utf-8'))
    except (OSError, ValueError, UnicodeError):
        print(json.dumps({'status': 'BLOCKED', 'issues': ['required_policy_missing_or_invalid'],
                          'deployment_allowed': False, 'connection_attempted': False}))
        return 2
    result = evaluate_neon_tls_candidate(os.getenv('CHEMFORGE_NEON_TLS_DRY_RUN_DSN'), contract, evidence)
    print(json.dumps(result, sort_keys=True))
    return 2 if result['status'] == 'BLOCKED' else 0


if __name__ == '__main__':
    raise SystemExit(main())
