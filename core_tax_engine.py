# core_tax_engine.py
# Deterministic tax calculation validator

def calculate_tax(transaction: dict) -> dict:
    gross_amount     = transaction.get("gross_amount", 0)
    tax_rate         = transaction.get("tax_rate", 0)        # decimal e.g. 0.15
    declared_tax     = transaction.get("declared_tax_amount", 0)

    expected_tax     = round(gross_amount * tax_rate, 2)
    variance         = round(abs(declared_tax - expected_tax), 2)
    expected_net     = round(gross_amount + expected_tax, 2)

    # Reject if tax amount is wrong by more than $0.01
    status = "APPROVED" if variance <= 0.01 else "REJECTED"

    return {
        "status": status,
        "expected_tax_amount": expected_tax,
        "declared_tax_amount": round(declared_tax, 2),
        "tax_variance": variance,
        "expected_gross_plus_tax": expected_net,
    }
