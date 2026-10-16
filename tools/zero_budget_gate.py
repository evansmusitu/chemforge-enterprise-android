"""Offline CHEMFORGE zero-cash planning gate: verifies a NON-DEPLOYING contract.

This module never contacts a provider and is deliberately not a production
release authorization. A passing check only establishes that the public
source still declares the conservative $0 synthetic-only boundary.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

EXPECTED = {
    "schema": "chemforge.zero_budget.synthetic_staging.v1",
    "environment": "synthetic-staging-only",
    "max_monthly_spend_usd": 0,
    "real_student_data_allowed": False,
    "public_api_enabled": False,
    "provider_deploy_enabled": False,
    "real_oidc_verified": False,
    "reuse_nexus_credentials_or_data": False,
    "github_plane": "Public GitHub Actions for source verification only",
    "public_static": "GitHub Pages read-only project information (optional)",
    "cloudflare_edge": "Cloudflare Workers Free (optional)",
    "python_runtime": "Modal Starter (only with verified $0 spend controls)",
    "postgres": "Dedicated Neon Free PostgreSQL (empty, publicly blocked; no API/runtime)",
}


def validate_contract(contract: dict) -> list[str]:
    """Return deterministic violation codes. The only admitted config is safe."""
    if not isinstance(contract, dict):
        return ["invalid_contract_type"]
    issues: list[str] = []
    if set(EXPECTED) - set(contract):
        issues.append("missing_fields")
    if set(contract) - set(EXPECTED):
        issues.append("unrecognized_fields")
    if type(contract.get("max_monthly_spend_usd")) is not int or contract.get("max_monthly_spend_usd") != 0:
        issues.append("budget_must_be_zero")
    for key, issue in (
        ("real_student_data_allowed", "student_data_must_remain_disabled"),
        ("public_api_enabled", "public_api_must_remain_disabled"),
        ("provider_deploy_enabled", "provider_deploy_must_remain_disabled"),
        ("real_oidc_verified", "real_sso_claim_disallowed"),
        ("reuse_nexus_credentials_or_data", "cross_product_resources_forbidden"),
    ):
        if contract.get(key) is not False:
            issues.append(issue)
    if contract.get("schema") != EXPECTED["schema"] or contract.get("environment") != EXPECTED["environment"]:
        issues.append("synthetic_only_schema_required")
    for key in ("github_plane", "public_static", "cloudflare_edge", "python_runtime", "postgres"):
        if contract.get(key) != EXPECTED[key]:
            issues.append("provider_blueprint_mismatch")
            break
    return issues


def load_contract(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, default=Path("deployment/zero_budget_contract.json"))
    parser.add_argument("--request-deploy", action="store_true", help="Deliberate negative control; always blocks cloud deployment")
    args = parser.parse_args()
    if args.request_deploy:
        print(json.dumps({"status": "BLOCKED", "reason": "Production/cloud deployment requires independent external authorization; this tool cannot authorize it"}))
        return 2
    try:
        issues = validate_contract(load_contract(args.contract))
    except (OSError, ValueError, UnicodeError) as exc:
        print(json.dumps({"status": "BLOCKED", "errors": [type(exc).__name__]}))
        return 2
    print(json.dumps({"status": "PLAN_VALID_NOT_DEPLOYED" if not issues else "BLOCKED", "errors": issues, "budget_usd": 0}))
    return 0 if not issues else 2


if __name__ == "__main__":
    raise SystemExit(main())
