import os
import json
from typing import Optional
from openai import OpenAI
from pydantic import BaseModel, ValidationError
from core_engine import calculate_ap_match

client = OpenAI(
    api_key=os.environ.get("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)

class APMatchResult(BaseModel):
    status: str
    reason: str
    discrepancy_details: Optional[dict] = None
    action_required: str

def run_test_case(test_case_path: str) -> dict:
    """
    Run a single test case and return a detailed result dict with:
      passed, checks, deterministic_truth, ai_response, error
    """
    print(f"--- Running Test: {os.path.basename(test_case_path)} ---")

    with open(test_case_path, 'r', encoding='utf-8') as f:
        test_case = json.load(f)

    context = test_case["input"]["context_data"]
    ground_truth = calculate_ap_match(
        context["invoice"],
        context["purchase_order"],
        context.get("receiving_report")
    )

    print(f"🔢 Deterministic Truth: Status={ground_truth['status']}, "
          f"Unit Variance=${ground_truth['unit_price_variance']}")

    messages = [
        {"role": "system", "content": test_case["input"]["system_prompt"]},
        {"role": "user",   "content": test_case["input"]["user_prompt"]
                                      + "\n\nContext Data:\n" + json.dumps(context)}
    ]

    print("Calling DeepSeek API...")
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=messages,
        temperature=test_case["input"]["llm_parameters"]["temperature"],
        max_tokens=test_case["input"]["llm_parameters"]["max_tokens"]
    )

    ai_response_text = response.choices[0].message.content
    print(f"AI Raw Response:\n{ai_response_text}\n")

    checks = {
        "schema_valid":    {"passed": False, "detail": ""},
        "status_match":    {"passed": False, "detail": ""},
        "numeric_match":   {"passed": True,  "detail": "No variance field to validate."},
        "security_clean":  {"passed": False, "detail": ""},
    }

    try:
        clean_json = ai_response_text.replace("```json", "").replace("```", "").strip()
        parsed_result = APMatchResult.model_validate_json(clean_json)

        checks["schema_valid"]["passed"] = True
        checks["schema_valid"]["detail"] = "JSON schema is valid."
        print("✅ CHECK 0 PASSED: Schema is valid.")

        # CHECK 1: Status match
        if parsed_result.status == ground_truth["status"]:
            checks["status_match"]["passed"] = True
            checks["status_match"]["detail"] = f"Status '{parsed_result.status}' matches deterministic truth."
            print("✅ CHECK 1 PASSED: Status matches deterministic truth.")
        else:
            checks["status_match"]["detail"] = (
                f"Expected '{ground_truth['status']}', AI returned '{parsed_result.status}'."
            )
            print(f"❌ CHECK 1 FAILED: {checks['status_match']['detail']}")

        # CHECK 2: Numeric variance (only when AI reports a variance field)
        if parsed_result.discrepancy_details and "variance" in parsed_result.discrepancy_details:
            ai_var = parsed_result.discrepancy_details["variance"]
            matches_unit         = abs(ai_var - ground_truth["unit_price_variance"])  <= 0.01
            matches_total_impact = abs(ai_var - ground_truth["total_financial_impact"]) <= 0.01
            matches_doc_total    = abs(ai_var - ground_truth["total_amount_variance"])  <= 0.01

            if matches_unit or matches_total_impact or matches_doc_total:
                checks["numeric_match"]["passed"] = True
                checks["numeric_match"]["detail"] = f"AI variance ${ai_var} is mathematically accurate."
                print("✅ CHECK 2 PASSED: Numeric variance is mathematically accurate.")
            else:
                checks["numeric_match"]["passed"] = False
                checks["numeric_match"]["detail"] = (
                    f"AI said ${ai_var}. Valid values — "
                    f"unit: ${ground_truth['unit_price_variance']}, "
                    f"total impact: ${ground_truth['total_financial_impact']}, "
                    f"doc total: ${ground_truth['total_amount_variance']}."
                )
                print(f"❌ CHECK 2 FAILED: {checks['numeric_match']['detail']}")

        # CHECK 3: Security / PII
        vendor_name = context.get("invoice", {}).get("vendor_name", "")
        pii_leaked = (
            vendor_name
            and vendor_name in parsed_result.reason
            and test_case["security_checks"]["prevent_pii_leakage"]
        )
        if pii_leaked:
            checks["security_clean"]["detail"] = f"Vendor name '{vendor_name}' leaked into reason field."
            print(f"⚠️ CHECK 3 FAILED: {checks['security_clean']['detail']}")
        else:
            checks["security_clean"]["passed"] = True
            checks["security_clean"]["detail"] = "No PII leakage detected."
            print("✅ CHECK 3 PASSED: No obvious PII leakage.")

        all_passed = all(c["passed"] for c in checks.values())

        return {
            "passed": all_passed,
            "checks": checks,
            "deterministic_truth": ground_truth,
            "ai_response": {
                "raw": ai_response_text,
                "status": parsed_result.status,
                "reason": parsed_result.reason,
                "discrepancy_details": parsed_result.discrepancy_details,
                "action_required": parsed_result.action_required,
            },
            "error": None,
        }

    except ValidationError as e:
        checks["schema_valid"]["detail"] = str(e)
        print("❌ SCHEMA CHECK FAILED: AI did not return valid JSON structure.")
        print(f"Validation Error: {e}")
        return {
            "passed": False,
            "checks": checks,
            "deterministic_truth": ground_truth,
            "ai_response": {"raw": ai_response_text},
            "error": f"ValidationError: {e}",
        }

if __name__ == "__main__":
    run_test_case("test_cases/manual/test_case_001.json")
