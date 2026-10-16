"""Fail-closed zero-cash deployment contract regression tests."""
import json
from pathlib import Path
import unittest
from tools.zero_budget_gate import load_contract, validate_contract


ROOT = Path(__file__).resolve().parents[2]


class BudgetContractTests(unittest.TestCase):
    def setUp(self):
        self.contract = load_contract(ROOT / "deployment" / "zero_budget_contract.json")

    def test_safe_synthetic_contract_passes(self):
        self.assertEqual([], validate_contract(self.contract))

    def test_budget_cannot_increase(self):
        bad = {**self.contract, "max_monthly_spend_usd": 0.01}
        self.assertIn("budget_must_be_zero", validate_contract(bad))

    def test_real_student_data_cannot_be_enabled(self):
        bad = {**self.contract, "real_student_data_allowed": True}
        self.assertIn("student_data_must_remain_disabled", validate_contract(bad))

    def test_public_api_cannot_be_enabled_by_plan(self):
        bad = {**self.contract, "public_api_enabled": True}
        self.assertIn("public_api_must_remain_disabled", validate_contract(bad))

    def test_external_real_sso_cannot_be_claimed(self):
        bad = {**self.contract, "real_oidc_verified": True}
        self.assertIn("real_sso_claim_disallowed", validate_contract(bad))

    def test_no_reuse_of_nexus_secrets_or_database(self):
        bad = {**self.contract, "reuse_nexus_credentials_or_data": True}
        self.assertIn("cross_product_resources_forbidden", validate_contract(bad))

    def test_unknown_contract_key_is_rejected(self):
        bad = {**self.contract, "production_ready": True}
        self.assertIn("unrecognized_fields", validate_contract(bad))

    def test_absent_safety_flag_is_rejected(self):
        bad = dict(self.contract)
        del bad["real_student_data_allowed"]
        self.assertIn("missing_fields", validate_contract(bad))

    def test_unverified_cost_controls_block_provider_deploy(self):
        bad = {**self.contract, "provider_deploy_enabled": True}
        self.assertIn("provider_deploy_must_remain_disabled", validate_contract(bad))

    def test_stack_is_architecture_only(self):
        self.assertEqual("Cloudflare Workers Free (optional)", self.contract["cloudflare_edge"])
        self.assertEqual("Modal Starter (only with verified $0 spend controls)", self.contract["python_runtime"])
        self.assertEqual("Dedicated Neon Free PostgreSQL (empty, publicly blocked; no API/runtime)", self.contract["postgres"])


if __name__ == "__main__":
    unittest.main()
