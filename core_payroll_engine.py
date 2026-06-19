# core_payroll_engine.py
# Deterministic payroll / net-pay validator

def calculate_payroll(employee: dict) -> dict:
    gross_pay        = employee.get("gross_pay", 0)
    deductions       = employee.get("deductions", {})
    declared_net     = employee.get("declared_net_pay", 0)

    total_deductions = round(sum(deductions.values()), 2)
    expected_net     = round(gross_pay - total_deductions, 2)
    variance         = round(abs(declared_net - expected_net), 2)

    # Reject if net pay is wrong by more than $0.01
    status = "APPROVED" if variance <= 0.01 else "REJECTED"

    return {
        "status": status,
        "gross_pay": round(gross_pay, 2),
        "total_deductions": total_deductions,
        "expected_net_pay": expected_net,
        "declared_net_pay": round(declared_net, 2),
        "net_pay_variance": variance,
    }
