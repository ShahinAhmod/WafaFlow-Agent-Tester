"""
Unit tests for core_tax_engine.py and core_payroll_engine.py.
Run with: venv/Scripts/python.exe -m pytest test_core_engines.py -v
"""
import unittest
from core_tax_engine import calculate_tax
from core_payroll_engine import calculate_payroll


# ── Tax Engine Tests ─────────────────────────────────────────────────────────

class TestCalculateTax(unittest.TestCase):

    def _txn(self, gross, rate, declared):
        return {"gross_amount": gross, "tax_rate": rate, "declared_tax_amount": declared}

    def test_correct_vat_approved(self):
        """Exact match → APPROVED."""
        result = calculate_tax(self._txn(10000, 0.15, 1500))
        self.assertEqual(result["status"], "APPROVED")
        self.assertEqual(result["expected_tax_amount"], 1500.00)
        self.assertEqual(result["tax_variance"], 0.00)

    def test_wrong_tax_rejected(self):
        """Declared tax is too low → REJECTED."""
        result = calculate_tax(self._txn(25000, 0.15, 3200))
        self.assertEqual(result["status"], "REJECTED")
        self.assertEqual(result["expected_tax_amount"], 3750.00)
        self.assertEqual(result["tax_variance"], 550.00)

    def test_penny_within_tolerance_approved(self):
        """$0.01 variance is within tolerance → APPROVED."""
        result = calculate_tax(self._txn(10000, 0.15, 1500.01))
        self.assertEqual(result["status"], "APPROVED")

    def test_penny_over_tolerance_rejected(self):
        """$0.02 variance exceeds tolerance → REJECTED."""
        result = calculate_tax(self._txn(10000, 0.15, 1500.02))
        self.assertEqual(result["status"], "REJECTED")
        self.assertAlmostEqual(result["tax_variance"], 0.02, places=2)

    def test_five_percent_rate(self):
        result = calculate_tax(self._txn(5000, 0.05, 250))
        self.assertEqual(result["status"], "APPROVED")
        self.assertEqual(result["expected_tax_amount"], 250.00)

    def test_twenty_percent_rate(self):
        result = calculate_tax(self._txn(8000, 0.20, 1600))
        self.assertEqual(result["status"], "APPROVED")
        self.assertEqual(result["expected_tax_amount"], 1600.00)

    def test_overcharged_tax_rejected(self):
        """Declared tax is too high → REJECTED."""
        result = calculate_tax(self._txn(10000, 0.15, 2000))
        self.assertEqual(result["status"], "REJECTED")
        self.assertEqual(result["expected_tax_amount"], 1500.00)
        self.assertEqual(result["tax_variance"], 500.00)

    def test_zero_rate(self):
        """Zero-rated transaction → expected tax is 0."""
        result = calculate_tax(self._txn(10000, 0.00, 0))
        self.assertEqual(result["status"], "APPROVED")
        self.assertEqual(result["expected_tax_amount"], 0.00)

    def test_gross_plus_tax_field(self):
        """expected_gross_plus_tax = gross + expected_tax."""
        result = calculate_tax(self._txn(10000, 0.15, 1500))
        self.assertAlmostEqual(result["expected_gross_plus_tax"], 11500.00, places=2)

    def test_missing_fields_default_to_zero(self):
        """Engine must not crash on empty input."""
        result = calculate_tax({})
        self.assertIn("status", result)
        self.assertEqual(result["expected_tax_amount"], 0.00)


# ── Payroll Engine Tests ─────────────────────────────────────────────────────

class TestCalculatePayroll(unittest.TestCase):

    def _emp(self, gross, deductions, declared_net):
        return {"gross_pay": gross, "deductions": deductions, "declared_net_pay": declared_net}

    def test_correct_net_pay_approved(self):
        """Exact match → APPROVED."""
        deductions = {"income_tax": 1200, "social_insurance": 400, "pension": 200}
        result = calculate_payroll(self._emp(8000, deductions, 6200))
        self.assertEqual(result["status"], "APPROVED")
        self.assertEqual(result["expected_net_pay"], 6200.00)
        self.assertEqual(result["net_pay_variance"], 0.00)

    def test_wrong_net_pay_rejected(self):
        """Declared net pay is wrong → REJECTED."""
        deductions = {"income_tax": 2400, "social_insurance": 600, "pension": 360, "health_insurance": 150}
        result = calculate_payroll(self._emp(12000, deductions, 8000))
        self.assertEqual(result["status"], "REJECTED")
        self.assertEqual(result["expected_net_pay"], 8490.00)
        self.assertEqual(result["total_deductions"], 3510.00)
        self.assertAlmostEqual(result["net_pay_variance"], 490.00, places=2)

    def test_penny_within_tolerance_approved(self):
        result = calculate_payroll(self._emp(8000, {"income_tax": 1200}, 6800.01))
        self.assertEqual(result["status"], "APPROVED")

    def test_penny_over_tolerance_rejected(self):
        result = calculate_payroll(self._emp(8000, {"income_tax": 1200}, 6800.02))
        self.assertEqual(result["status"], "REJECTED")
        self.assertAlmostEqual(result["net_pay_variance"], 0.02, places=2)

    def test_no_deductions_approved(self):
        """No deductions → net pay equals gross pay."""
        result = calculate_payroll(self._emp(5000, {}, 5000))
        self.assertEqual(result["status"], "APPROVED")
        self.assertEqual(result["expected_net_pay"], 5000.00)
        self.assertEqual(result["total_deductions"], 0.00)

    def test_total_deductions_summed_correctly(self):
        deductions = {"a": 100, "b": 200, "c": 300}
        result = calculate_payroll(self._emp(1000, deductions, 400))
        self.assertEqual(result["total_deductions"], 600.00)
        self.assertEqual(result["expected_net_pay"], 400.00)
        self.assertEqual(result["status"], "APPROVED")

    def test_overpaid_employee_rejected(self):
        """Declared net pay higher than expected → REJECTED."""
        deductions = {"income_tax": 500}
        result = calculate_payroll(self._emp(3000, deductions, 3000))
        self.assertEqual(result["status"], "REJECTED")
        self.assertEqual(result["expected_net_pay"], 2500.00)
        self.assertEqual(result["net_pay_variance"], 500.00)

    def test_underpaid_employee_rejected(self):
        """Declared net pay lower than expected → REJECTED."""
        deductions = {"income_tax": 500}
        result = calculate_payroll(self._emp(3000, deductions, 2000))
        self.assertEqual(result["status"], "REJECTED")
        self.assertEqual(result["net_pay_variance"], 500.00)

    def test_missing_fields_default_to_zero(self):
        """Engine must not crash on empty input."""
        result = calculate_payroll({})
        self.assertIn("status", result)
        self.assertEqual(result["total_deductions"], 0.00)

    def test_gross_pay_stored_in_result(self):
        result = calculate_payroll(self._emp(5000, {"tax": 1000}, 4000))
        self.assertEqual(result["gross_pay"], 5000.00)


if __name__ == "__main__":
    unittest.main(verbosity=2)
