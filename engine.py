import os
import json
from typing import Optional
from openai import OpenAI
from pydantic import BaseModel, ValidationError

from core_engine import calculate_ap_match
from core_tax_engine import calculate_tax
from core_payroll_engine import calculate_payroll

client = OpenAI(
    api_key=os.environ.get("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)

# ── Pydantic output schemas per agent type ───────────────────────────────────

class APMatchResult(BaseModel):
    status: str
    reason: str
    discrepancy_details: Optional[dict] = None
    action_required: str

class TaxCalcResult(BaseModel):
    status: str
    tax_amount: float
    reason: str
    action_required: str

class PayrollResult(BaseModel):
    status: str
    net_pay: float
    reason: str
    action_required: str

# ── Agent-type registry ──────────────────────────────────────────────────────

AGENT_REGISTRY = {
    "ap_match": {
        "model": APMatchResult,
        "label": "AP 3-Way Match",
    },
    "tax_calculation": {
        "model": TaxCalcResult,
        "label": "Tax Calculation",
    },
    "payroll": {
        "model": PayrollResult,
        "label": "Payroll",
    },
}

# ── Deterministic truth per agent type ──────────────────────────────────────

def _get_ground_truth(agent_type: str, context: dict) -> dict:
    if agent_type == "tax_calculation":
        return calculate_tax(context["transaction"])
    if agent_type == "payroll":
        return calculate_payroll(context["employee"])
    # default: ap_match
    return calculate_ap_match(
        context["invoice"],
        context["purchase_order"],
        context.get("receiving_report"),
    )

# ── Numeric check per agent type ─────────────────────────────────────────────

def _check_numeric(agent_type: str, parsed, ground_truth: dict) -> tuple[bool, str]:
    """Returns (passed, detail_message)."""
    if agent_type == "tax_calculation":
        ai_val = parsed.tax_amount
        expected = ground_truth["expected_tax_amount"]
        if abs(ai_val - expected) <= 0.01:
            return True, f"AI tax_amount ${ai_val} matches expected ${expected}."
        return False, f"AI said ${ai_val}, expected ${expected} (variance ${ground_truth['tax_variance']})."

    if agent_type == "payroll":
        ai_val = parsed.net_pay
        expected = ground_truth["expected_net_pay"]
        if abs(ai_val - expected) <= 0.01:
            return True, f"AI net_pay ${ai_val} matches expected ${expected}."
        return False, (
            f"AI said ${ai_val}, expected ${expected} "
            f"(gross ${ground_truth['gross_pay']} - deductions ${ground_truth['total_deductions']})."
        )

    # ap_match — flexible: accept unit variance, total impact, or doc total
    if parsed.discrepancy_details and "variance" in parsed.discrepancy_details:
        ai_var = parsed.discrepancy_details["variance"]
        if (
            abs(ai_var - ground_truth["unit_price_variance"])  <= 0.01
            or abs(ai_var - ground_truth["total_financial_impact"]) <= 0.01
            or abs(ai_var - ground_truth["total_amount_variance"])  <= 0.01
        ):
            return True, f"AI variance ${ai_var} is mathematically accurate."
        return False, (
            f"AI said ${ai_var}. Valid values — "
            f"unit: ${ground_truth['unit_price_variance']}, "
            f"total impact: ${ground_truth['total_financial_impact']}, "
            f"doc total: ${ground_truth['total_amount_variance']}."
        )
    return True, "No variance field to validate."  # not present → skip

# ── PII field per agent type ─────────────────────────────────────────────────

def _get_pii_value(agent_type: str, context: dict) -> str:
    if agent_type == "payroll":
        return context.get("employee", {}).get("name", "")
    if agent_type == "tax_calculation":
        return ""  # no PII in tax transactions
    return context.get("invoice", {}).get("vendor_name", "")

# ── Main runner ──────────────────────────────────────────────────────────────

def run_test_case(test_case_path: str) -> dict:
    print(f"--- Running Test: {os.path.basename(test_case_path)} ---")

    with open(test_case_path, "r", encoding="utf-8") as f:
        test_case = json.load(f)

    agent_type = test_case.get("agent_type", "ap_match")
    registry   = AGENT_REGISTRY.get(agent_type, AGENT_REGISTRY["ap_match"])
    context    = test_case["input"]["context_data"]

    ground_truth = _get_ground_truth(agent_type, context)
    print(f"🔢 [{registry['label']}] Deterministic Truth: {ground_truth}")

    messages = [
        {"role": "system", "content": test_case["input"]["system_prompt"]},
        {"role": "user",   "content": test_case["input"]["user_prompt"]
                                      + "\n\nContext Data:\n" + json.dumps(context)},
    ]

    print("Calling DeepSeek API...")
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=messages,
        temperature=test_case["input"]["llm_parameters"]["temperature"],
        max_tokens=test_case["input"]["llm_parameters"]["max_tokens"],
    )

    ai_response_text = response.choices[0].message.content
    print(f"AI Raw Response:\n{ai_response_text}\n")

    checks = {
        "schema_valid":   {"passed": False, "detail": ""},
        "status_match":   {"passed": False, "detail": ""},
        "numeric_match":  {"passed": True,  "detail": "No numeric field to validate."},
        "security_clean": {"passed": False, "detail": ""},
    }

    try:
        clean_json     = ai_response_text.replace("```json", "").replace("```", "").strip()
        ResultModel    = registry["model"]
        parsed_result  = ResultModel.model_validate_json(clean_json)

        checks["schema_valid"] = {"passed": True, "detail": "JSON schema is valid."}
        print("✅ SCHEMA: valid.")

        # CHECK 1: Status
        if parsed_result.status == ground_truth["status"]:
            checks["status_match"] = {
                "passed": True,
                "detail": f"Status '{parsed_result.status}' matches deterministic truth.",
            }
            print("✅ CHECK 1: Status matches.")
        else:
            checks["status_match"] = {
                "passed": False,
                "detail": f"Expected '{ground_truth['status']}', AI returned '{parsed_result.status}'.",
            }
            print(f"❌ CHECK 1: {checks['status_match']['detail']}")

        # CHECK 2: Numeric
        num_passed, num_detail = _check_numeric(agent_type, parsed_result, ground_truth)
        checks["numeric_match"] = {"passed": num_passed, "detail": num_detail}
        print(f"{'✅' if num_passed else '❌'} CHECK 2: {num_detail}")

        # CHECK 3: Security / PII
        pii_value  = _get_pii_value(agent_type, context)
        pii_leaked = (
            pii_value
            and pii_value in parsed_result.reason
            and test_case["security_checks"]["prevent_pii_leakage"]
        )
        if pii_leaked:
            checks["security_clean"] = {
                "passed": False,
                "detail": f"'{pii_value}' leaked into reason field.",
            }
            print(f"⚠️  CHECK 3: PII leaked — {pii_value}")
        else:
            checks["security_clean"] = {"passed": True, "detail": "No PII leakage detected."}
            print("✅ CHECK 3: No PII leakage.")

        all_passed = all(c["passed"] for c in checks.values())

        ai_fields = {"raw": ai_response_text, "status": parsed_result.status,
                     "reason": parsed_result.reason, "action_required": parsed_result.action_required}
        if agent_type == "tax_calculation":
            ai_fields["tax_amount"] = parsed_result.tax_amount
        elif agent_type == "payroll":
            ai_fields["net_pay"] = parsed_result.net_pay
        else:
            ai_fields["discrepancy_details"] = parsed_result.discrepancy_details

        return {
            "passed": all_passed,
            "agent_type": agent_type,
            "checks": checks,
            "deterministic_truth": ground_truth,
            "ai_response": ai_fields,
            "error": None,
        }

    except ValidationError as e:
        checks["schema_valid"] = {"passed": False, "detail": str(e)}
        print(f"❌ SCHEMA INVALID: {e}")
        return {
            "passed": False,
            "agent_type": agent_type,
            "checks": checks,
            "deterministic_truth": ground_truth,
            "ai_response": {"raw": ai_response_text},
            "error": f"ValidationError: {e}",
        }

if __name__ == "__main__":
    run_test_case("test_cases/manual/test_case_001.json")
