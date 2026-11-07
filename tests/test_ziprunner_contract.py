"""Regression against the mandatory effective-root Workboard intake and plan."""
import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from verify_contracts import ContractError, check_contracts, check_required_tasks, read_json, validate_workboard


class ZipRunnerSourceContractTests(unittest.TestCase):
    def test_effective_root_contracts(self):
        message = check_contracts(ROOT)
        self.assertIn("Workboard IDs", message)

    def test_incorrect_project_fails_closed(self):
        document = read_json(ROOT / ".ziprunner-workboard-update.json")
        document["project"] = "a-different-project"
        with self.assertRaises(ContractError):
            validate_workboard(document)

    def test_missing_original_ticket_fails_closed(self):
        document = read_json(ROOT / ".ziprunner-workboard-update.json")
        document["remaining"][0]["id"] = "renamed-ticket"
        with self.assertRaises(ContractError):
            check_required_tasks(document)

    def test_windows_gate_must_remain_open(self):
        document = read_json(ROOT / ".ziprunner-workboard-update.json")
        document["remaining"] = [i for i in document["remaining"] if i["id"] != "TA-012"]
        with self.assertRaises(ContractError):
            check_required_tasks(document)

    def test_duplicate_identity_rejected(self):
        document = read_json(ROOT / ".ziprunner-workboard-update.json")
        document["remaining"].append(copy.deepcopy(document["implemented"][0]))
        with self.assertRaises(ContractError):
            validate_workboard(document)

    def test_empty_operator_checks_rejected(self):
        document = read_json(ROOT / ".ziprunner-workboard-update.json")
        document["implemented"][0]["operator_checks"] = []
        with self.assertRaises(ContractError):
            validate_workboard(document)

    def test_invalid_priority_rejected(self):
        document = read_json(ROOT / ".ziprunner-workboard-update.json")
        document["remaining"][0]["priority"] = "urgent-now"
        with self.assertRaises(ContractError):
            validate_workboard(document)

    def test_unknown_workboard_key_rejected(self):
        document = read_json(ROOT / ".ziprunner-workboard-update.json")
        document["auto_approve_release"] = True
        with self.assertRaises(ContractError):
            validate_workboard(document)


if __name__ == "__main__":
    unittest.main()
