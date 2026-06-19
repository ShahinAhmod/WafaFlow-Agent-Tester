"""
Comprehensive unit + property-based tests for core_tax_engine and core_payroll_engine.
Run with: venv/Scripts/python.exe -m pytest test_core_engines.py -v
"""
import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from core_tax_engine import calculate_tax
from core_payroll_engine import calculate_payroll


# ════════════════════════════════════════════════════════════════════════════
# HELPERS
# ════════════════════════════════════════════════════════════════════════════

def tax_input(gross, rate, declared):
    return {"gross_amount": gross, "tax_rate": rate, "declared_tax_amount": declared}

def payroll_input(gross, deductions, declared_net):
    return {"gross_pay": gross, "deductions": deductions, "declared_net_pay": declared_net}


# ════════════════════════════════════════════════════════════════════════════
# TAX ENGINE — PARAMETRIZED BUSINESS SCENARIOS
# ════════════════════════════════════════════════════════════════════════════

TAX_APPROVED_CASES = [
    # (gross, rate, declared,  label)
    (10_000,  0.15, 1_500.00,  "standard 15% VAT"),
    (25_000,  0.15, 3_750.00,  "large invoice 15%"),
    (5_000,   0.05,   250.00,  "5% reduced rate"),
    (8_000,   0.20, 1_600.00,  "20% UK VAT"),
    (1_000,   0.10,   100.00,  "10% GST"),
    (100,     0.15,    15.00,  "small transaction"),
    (1,       0.15,     0.15,  "minimum transaction"),
    (999_999, 0.15, 149_999.85,"very large invoice"),
    (10_000,  0.00,     0.00,  "zero-rated"),
    (333.33,  0.15,    50.00,  "repeating decimal — within tolerance"),
    (10_000,  0.15, 1_500.01,  "penny over — still within $0.01 tolerance"),
    (10_000,  0.15, 1_499.99,  "penny under — still within $0.01 tolerance"),
    (7_777,   0.07,   544.39,  "7% rate — rounded correctly"),
    (2_500,   0.15,   375.00,  "mid-range invoice"),
    (50_000,  0.20, 10_000.00, "high-value 20%"),
    (12_345,  0.15, 1_851.75,  "non-round gross amount"),
    (99.99,   0.15,    15.00,  "sub-$100 within tolerance"),
    (10_000,  0.175, 1_750.00, "17.5% legacy UK VAT"),
    (6_000,   0.05,   300.00,  "5% rate mid-size"),
    (3_600,   0.10,   360.00,  "10% on $3,600"),
]

@pytest.mark.parametrize("gross,rate,declared,label", TAX_APPROVED_CASES)
def test_tax_approved_scenarios(gross, rate, declared, label):
    result = calculate_tax(tax_input(gross, rate, declared))
    assert result["status"] == "APPROVED", (
        f"[{label}] Expected APPROVED. "
        f"Expected tax=${result['expected_tax_amount']}, declared=${declared}, "
        f"variance=${result['tax_variance']}"
    )


TAX_REJECTED_CASES = [
    # (gross, rate, declared,  label)
    (25_000,  0.15, 3_200.00,  "under-declared by $550"),
    (10_000,  0.15, 2_000.00,  "over-declared by $500"),
    (10_000,  0.15, 1_500.02,  "two-penny over tolerance"),
    (10_000,  0.15, 1_499.98,  "two-penny under tolerance"),
    (5_000,   0.20,   500.00,  "wrong rate applied (5% instead of 20%)"),
    (10_000,  0.15,     0.00,  "zero declared on taxable transaction"),
    (10_000,  0.15, 10_000.00, "declared gross instead of tax"),
    (8_000,   0.15, 1_000.00,  "significant shortfall"),
    (1_000,   0.10,   150.00,  "wrong rate (15% vs 10%)"),
    (50_000,  0.20, 9_000.00,  "underpaid by $1,000"),
    (12_345,  0.15, 1_900.00,  "overcharged on non-round amount"),
    (100,     0.15,    20.00,  "small over-charge"),
    (999_999, 0.15, 100_000.00,"massive underpayment"),
    (10_000,  0.05, 1_500.00,  "applied 15% instead of 5%"),
    (7_000,   0.10,   770.02,  "two pennies over"),
]

@pytest.mark.parametrize("gross,rate,declared,label", TAX_REJECTED_CASES)
def test_tax_rejected_scenarios(gross, rate, declared, label):
    result = calculate_tax(tax_input(gross, rate, declared))
    assert result["status"] == "REJECTED", (
        f"[{label}] Expected REJECTED. "
        f"Expected tax=${result['expected_tax_amount']}, declared=${declared}, "
        f"variance=${result['tax_variance']}"
    )


# ── Tax Engine — Structural / Invariant Tests ────────────────────────────────

def test_tax_result_has_all_required_keys():
    result = calculate_tax(tax_input(1000, 0.15, 150))
    for key in ("status", "expected_tax_amount", "declared_tax_amount", "tax_variance", "expected_gross_plus_tax"):
        assert key in result, f"Missing key: {key}"

def test_tax_variance_is_always_non_negative():
    for gross, rate, declared in [(1000, 0.15, 100), (1000, 0.15, 200), (1000, 0.15, 150)]:
        assert calculate_tax(tax_input(gross, rate, declared))["tax_variance"] >= 0

def test_tax_gross_plus_tax_equals_gross_plus_expected():
    result = calculate_tax(tax_input(10_000, 0.15, 1_500))
    assert abs(result["expected_gross_plus_tax"] - (10_000 + result["expected_tax_amount"])) < 0.01

def test_tax_empty_input_does_not_crash():
    result = calculate_tax({})
    assert "status" in result

def test_tax_status_is_always_approved_or_rejected():
    for declared in [0, 500, 1500, 9999]:
        result = calculate_tax(tax_input(10_000, 0.15, declared))
        assert result["status"] in ("APPROVED", "REJECTED")


# ════════════════════════════════════════════════════════════════════════════
# PAYROLL ENGINE — PARAMETRIZED BUSINESS SCENARIOS
# ════════════════════════════════════════════════════════════════════════════

PAYROLL_APPROVED_CASES = [
    # (gross, deductions_dict, declared_net, label)
    (8_000,  {"income_tax": 1_200, "social_insurance": 400, "pension": 200},          6_200.00, "standard 3-deduction"),
    (12_000, {"income_tax": 2_400, "social_insurance": 600, "pension": 360, "health": 150}, 8_490.00, "4 deductions"),
    (5_000,  {},                                                                        5_000.00, "no deductions"),
    (5_000,  {"income_tax": 1_000},                                                    4_000.00, "single deduction"),
    (3_000,  {"income_tax": 500},                                                      2_500.00, "basic salary"),
    (15_000, {"income_tax": 4_500, "pension": 750},                                    9_750.00, "senior employee"),
    (1_000,  {"income_tax": 100},                                                        900.00, "minimum wage"),
    (50_000, {"income_tax": 15_000, "social_insurance": 2_500, "pension": 1_500},     31_000.00, "executive salary"),
    (8_000,  {"income_tax": 1_200, "social_insurance": 400, "pension": 200},          6_200.01, "penny over — in tolerance"),
    (8_000,  {"income_tax": 1_200, "social_insurance": 400, "pension": 200},          6_199.99, "penny under — in tolerance"),
    (7_777,  {"income_tax": 1_000, "pension": 200},                                    6_577.00, "non-round gross"),
    (4_500,  {"income_tax": 675, "social_insurance": 225},                             3_600.00, "mid-range"),
    (10_000, {"income_tax": 2_000, "social_insurance": 500, "health": 200, "pension": 300}, 7_000.00, "5 deductions"),
    (6_000,  {"income_tax": 900},                                                      5_100.00, "15% flat tax"),
    (2_000,  {"income_tax": 200, "pension": 100},                                      1_700.00, "part-time"),
    (20_000, {"income_tax": 6_000, "social_insurance": 1_000, "pension": 600},        12_400.00, "high earner"),
    (3_500,  {"income_tax": 525, "social_insurance": 175},                             2_800.00, "exact split"),
    (9_999,  {"income_tax": 1_499.85},                                                 8_499.15, "near-$10k salary"),
    (100,    {"income_tax": 10},                                                           90.00, "tiny salary"),
    (8_000,  {"a": 100, "b": 100, "c": 100, "d": 100, "e": 100},                      7_500.00, "many small deductions"),
]

@pytest.mark.parametrize("gross,deductions,declared_net,label", PAYROLL_APPROVED_CASES)
def test_payroll_approved_scenarios(gross, deductions, declared_net, label):
    result = calculate_payroll(payroll_input(gross, deductions, declared_net))
    assert result["status"] == "APPROVED", (
        f"[{label}] Expected APPROVED. "
        f"Expected net=${result['expected_net_pay']}, declared=${declared_net}, "
        f"variance=${result['net_pay_variance']}"
    )


PAYROLL_REJECTED_CASES = [
    # (gross, deductions_dict, declared_net, label)
    (12_000, {"income_tax": 2_400, "social_insurance": 600, "pension": 360, "health": 150}, 8_000.00, "wrong net — underpaid by $490"),
    (8_000,  {"income_tax": 1_200, "social_insurance": 400, "pension": 200},          6_201.00, "overpaid by $1"),
    (8_000,  {"income_tax": 1_200, "social_insurance": 400, "pension": 200},          6_199.00, "underpaid by $1"),
    (8_000,  {"income_tax": 1_200, "social_insurance": 400, "pension": 200},          8_000.00, "declared gross instead of net"),
    (8_000,  {"income_tax": 1_200, "social_insurance": 400, "pension": 200},             0.00, "declared zero net"),
    (5_000,  {"income_tax": 1_000},                                                    5_000.00, "deductions not applied"),
    (10_000, {"income_tax": 3_000},                                                    5_000.00, "wrong net — major shortfall"),
    (3_000,  {"income_tax": 500},                                                      3_000.00, "no deduction applied"),
    (8_000,  {"income_tax": 1_200, "social_insurance": 400, "pension": 200},          6_200.02, "two-penny over"),
    (8_000,  {"income_tax": 1_200, "social_insurance": 400, "pension": 200},          6_199.98, "two-penny under"),
    (15_000, {"income_tax": 4_500, "pension": 750},                                   10_000.00, "rounded up incorrectly"),
    (50_000, {"income_tax": 15_000, "social_insurance": 2_500, "pension": 1_500},     30_000.00, "executive — $1,000 wrong"),
    (4_500,  {"income_tax": 675, "social_insurance": 225},                             4_500.00, "deductions ignored"),
    (2_000,  {"income_tax": 200, "pension": 100},                                      2_000.00, "zero-deduction declared"),
    (7_000,  {"income_tax": 1_050},                                                    6_100.00, "wrong by $150"),
]

@pytest.mark.parametrize("gross,deductions,declared_net,label", PAYROLL_REJECTED_CASES)
def test_payroll_rejected_scenarios(gross, deductions, declared_net, label):
    result = calculate_payroll(payroll_input(gross, deductions, declared_net))
    assert result["status"] == "REJECTED", (
        f"[{label}] Expected REJECTED. "
        f"Expected net=${result['expected_net_pay']}, declared=${declared_net}, "
        f"variance=${result['net_pay_variance']}"
    )


# ── Payroll Engine — Structural / Invariant Tests ────────────────────────────

def test_payroll_result_has_all_required_keys():
    result = calculate_payroll(payroll_input(5000, {"tax": 500}, 4500))
    for key in ("status", "gross_pay", "total_deductions", "expected_net_pay", "declared_net_pay", "net_pay_variance"):
        assert key in result, f"Missing key: {key}"

def test_payroll_variance_is_always_non_negative():
    for declared in [0, 3000, 5000, 8000]:
        result = calculate_payroll(payroll_input(5000, {"tax": 500}, declared))
        assert result["net_pay_variance"] >= 0

def test_payroll_total_deductions_summed_correctly():
    deductions = {"a": 100, "b": 200.50, "c": 300}
    result = calculate_payroll(payroll_input(10_000, deductions, 9_399.50))
    assert abs(result["total_deductions"] - 600.50) < 0.01

def test_payroll_expected_net_equals_gross_minus_deductions():
    deductions = {"tax": 1_000, "pension": 200}
    result = calculate_payroll(payroll_input(8_000, deductions, 6_800))
    assert abs(result["expected_net_pay"] - (8_000 - 1_200)) < 0.01

def test_payroll_empty_input_does_not_crash():
    result = calculate_payroll({})
    assert "status" in result

def test_payroll_status_is_always_approved_or_rejected():
    for declared in [0, 3000, 5000, 9999]:
        result = calculate_payroll(payroll_input(5_000, {"tax": 500}, declared))
        assert result["status"] in ("APPROVED", "REJECTED")


# ════════════════════════════════════════════════════════════════════════════
# PROPERTY-BASED TESTS (hypothesis)
# Generates hundreds of random inputs each run to find unexpected failures.
# ════════════════════════════════════════════════════════════════════════════

REASONABLE_AMOUNT = st.floats(min_value=1.0, max_value=1_000_000.0,
                               allow_nan=False, allow_infinity=False)
TAX_RATE          = st.floats(min_value=0.01, max_value=0.50,
                               allow_nan=False, allow_infinity=False)


@given(gross=REASONABLE_AMOUNT, rate=TAX_RATE)
@settings(max_examples=100)
def test_tax_exact_calculation_always_approved(gross, rate):
    """If declared == gross * rate exactly (to nearest cent), status must be APPROVED."""
    expected = round(gross * rate, 2)
    result = calculate_tax(tax_input(gross, rate, expected))
    assert result["status"] == "APPROVED", (
        f"gross={gross}, rate={rate}, expected_tax={expected}, "
        f"variance={result['tax_variance']}"
    )


@given(gross=REASONABLE_AMOUNT, rate=TAX_RATE,
       error=st.floats(min_value=0.02, max_value=50_000.0,
                       allow_nan=False, allow_infinity=False))
@settings(max_examples=100)
def test_tax_wrong_amount_always_rejected(gross, rate, error):
    """If declared differs by more than $0.01, must always be REJECTED."""
    expected = round(gross * rate, 2)
    declared = round(expected + error, 2)
    result = calculate_tax(tax_input(gross, rate, declared))
    assert result["status"] == "REJECTED"


@given(gross=REASONABLE_AMOUNT, rate=TAX_RATE)
@settings(max_examples=100)
def test_tax_variance_equals_abs_difference(gross, rate):
    """tax_variance must equal abs(declared - expected), to the cent."""
    declared = round(gross * rate * 1.1, 2)  # always 10% over
    result   = calculate_tax(tax_input(gross, rate, declared))
    expected = round(gross * rate, 2)
    assert abs(result["tax_variance"] - abs(declared - expected)) < 0.02


@given(gross=REASONABLE_AMOUNT,
       deductions=st.dictionaries(
           keys=st.text(min_size=1, max_size=20),
           values=st.floats(min_value=0.01, max_value=10_000.0,
                             allow_nan=False, allow_infinity=False),
           min_size=1, max_size=6,
       ))
@settings(max_examples=100)
def test_payroll_exact_net_always_approved(gross, deductions):
    """If declared_net == gross - sum(deductions) exactly (to cent), must be APPROVED."""
    total_ded    = sum(deductions.values())
    assume(total_ded < gross)          # net pay must be positive
    expected_net = round(gross - total_ded, 2)
    result = calculate_payroll(payroll_input(gross, deductions, expected_net))
    assert result["status"] == "APPROVED", (
        f"gross={gross}, deductions={deductions}, "
        f"expected_net={expected_net}, variance={result['net_pay_variance']}"
    )


@given(gross=REASONABLE_AMOUNT,
       deductions=st.dictionaries(
           keys=st.text(min_size=1, max_size=20),
           values=st.floats(min_value=0.01, max_value=5_000.0,
                             allow_nan=False, allow_infinity=False),
           min_size=1, max_size=6,
       ),
       error=st.floats(min_value=0.02, max_value=10_000.0,
                       allow_nan=False, allow_infinity=False))
@settings(max_examples=100)
def test_payroll_wrong_net_always_rejected(gross, deductions, error):
    """If declared net differs from correct by > $0.01, must always be REJECTED."""
    total_ded    = sum(deductions.values())
    assume(total_ded < gross)
    expected_net = round(gross - total_ded, 2)
    declared_net = round(expected_net + error, 2)
    # Guard: rounding may shrink the gap to <= 0.01 at the boundary — skip those
    assume(abs(declared_net - expected_net) > 0.01)
    result = calculate_payroll(payroll_input(gross, deductions, declared_net))
    assert result["status"] == "REJECTED"


@given(gross=REASONABLE_AMOUNT,
       deductions=st.dictionaries(
           keys=st.text(min_size=1, max_size=20),
           values=st.floats(min_value=0.01, max_value=5_000.0,
                             allow_nan=False, allow_infinity=False),
           min_size=0, max_size=6,
       ))
@settings(max_examples=100)
def test_payroll_variance_never_negative(gross, deductions):
    """net_pay_variance must always be >= 0 regardless of input."""
    declared = round(gross * 0.8, 2)
    result   = calculate_payroll(payroll_input(gross, deductions, declared))
    assert result["net_pay_variance"] >= 0


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
