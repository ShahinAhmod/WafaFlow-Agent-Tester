import os
import json
from openai import OpenAI

client = OpenAI(
    api_key=os.environ.get("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)

def generate_test_cases(num_tests=10):
    print(f"🤖 Asking DeepSeek to generate {num_tests} diverse accounting stress-test scenarios...")
    
    strict_system_prompt = "You are a strict accounting AI. You must output ONLY a valid JSON object. The JSON object MUST contain exactly these four keys: 'status' (which must be exactly 'APPROVED' or 'REJECTED'), 'reason', 'discrepancy_details' (which must be an object like {\"variance\": 0.0}, or null if no discrepancy), and 'action_required'. Do not output any text outside the JSON."

    prompt = f"""
    You are an expert QA Engineer. Generate exactly {num_tests} highly diverse test scenarios for an Accounts Payable 3-Way Matching agent.
    
    CRITICAL FIELD NAMES: All invoice and PO line items MUST use these exact keys:
    - "vendor_name" (NOT "vendor")
    - "total_price" (NOT "total")
    - "quantity_received" for receiving_report line items

    CRITICAL: Make them diverse! Include:
    1. Multi-line item invoices (e.g., 3 different items on one invoice).
    2. Massive quantity orders (e.g., 5,000 units).
    3. Tiny penny differences (e.g., $10.00 vs $10.01).
    4. Perfect matches (Happy paths).
    5. Quantity mismatches (Invoice says 10, PO says 8).
    6. Total amount typos (Unit prices match, but the final total is typed wrong).
    
    CRITICAL RULE: Do NOT include an 'expected_output' or 'ground_truth' in your JSON. We will calculate the truth deterministically using Python. Only provide the input scenario.
    
    AGENT SYSTEM PROMPT TO USE:
    "{strict_system_prompt}"
    
    Output ONLY a valid JSON array. Do not include markdown formatting like ```json. 
    Each object in the array must follow this exact structure:
    {{
      "test_id": "AP-STRESS-00X",
      "input": {{
        "system_prompt": "{strict_system_prompt}",
        "user_prompt": "Verify the provided documents.",
        "context_data": {{ "invoice": {{...}}, "purchase_order": {{...}}, "receiving_report": {{...}} }},
        "llm_parameters": {{ "temperature": 0, "max_tokens": 500 }}
      }},
      "security_checks": {{ "prevent_pii_leakage": true }}
    }}
    """

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.8 
    )

    _save_generated(response, "test_cases/generated", "test_case")

def generate_tax_test_cases(num_tests=5):
    print(f"🤖 Generating {num_tests} Tax Calculation test scenarios...")

    prompt = f"""
    You are an expert QA Engineer. Generate exactly {num_tests} diverse test scenarios
    for a Tax Calculation agent that verifies VAT/GST on business transactions.

    CRITICAL FIELD NAMES: Use exactly these keys:
    - "gross_amount", "tax_rate" (decimal, e.g. 0.15), "declared_tax_amount", "tax_type", "jurisdiction"

    Include a mix of: correct calculations, wrong tax amounts, different tax rates (0.05, 0.10, 0.15, 0.20).

    CRITICAL: Do NOT include expected_output. We calculate truth deterministically in Python.

    Output ONLY a valid JSON array. No markdown. Each object must follow:
    {{
      "test_id": "TAX-STRESS-00X",
      "agent_type": "tax_calculation",
      "input": {{
        "system_prompt": "You are a strict tax calculation AI. You must output ONLY a valid JSON object with exactly these four keys: 'status' (must be exactly 'APPROVED' or 'REJECTED'), 'tax_amount' (a number), 'reason' (a string), 'action_required' (a string). Do not output any text outside the JSON.",
        "user_prompt": "Verify the tax calculation for the following transaction. Is the declared tax amount correct?",
        "context_data": {{ "transaction": {{ "transaction_id": "...", "description": "...", "gross_amount": 0.0, "tax_type": "VAT", "tax_rate": 0.15, "declared_tax_amount": 0.0, "jurisdiction": "..." }} }},
        "llm_parameters": {{ "temperature": 0, "max_tokens": 500 }}
      }},
      "security_checks": {{ "prevent_pii_leakage": false }}
    }}
    """

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.8
    )
    _save_generated(response, "test_cases/tax", "tax_stress")


def generate_payroll_test_cases(num_tests=5):
    print(f"🤖 Generating {num_tests} Payroll test scenarios...")

    prompt = f"""
    You are an expert QA Engineer. Generate exactly {num_tests} diverse test scenarios
    for a Payroll agent that verifies employee net pay calculations.

    CRITICAL FIELD NAMES: Use exactly these keys:
    - "employee_id", "name", "pay_period", "gross_pay"
    - "deductions" (object with named keys like "income_tax", "social_insurance", "pension", "health_insurance")
    - "declared_net_pay"

    Include a mix of: correct net pay, wrong net pay (over/under paid), different deduction combinations.

    CRITICAL: Do NOT include expected_output. We calculate truth deterministically in Python.

    Output ONLY a valid JSON array. No markdown. Each object must follow:
    {{
      "test_id": "PAY-STRESS-00X",
      "agent_type": "payroll",
      "input": {{
        "system_prompt": "You are a strict payroll calculation AI. You must output ONLY a valid JSON object with exactly these four keys: 'status' (must be exactly 'APPROVED' or 'REJECTED'), 'net_pay' (a number), 'reason' (a string), 'action_required' (a string). Do not output any text outside the JSON.",
        "user_prompt": "Verify the payroll record for this employee. Is the declared net pay correct?",
        "context_data": {{ "employee": {{ "employee_id": "...", "name": "...", "pay_period": "...", "gross_pay": 0.0, "deductions": {{}}, "declared_net_pay": 0.0 }} }},
        "llm_parameters": {{ "temperature": 0, "max_tokens": 500 }}
      }},
      "security_checks": {{ "prevent_pii_leakage": true }}
    }}
    """

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.8
    )
    _save_generated(response, "test_cases/payroll", "pay_stress")


def _save_generated(response, folder: str, prefix: str):
    raw_text   = response.choices[0].message.content
    clean_text = raw_text.replace("```json", "").replace("```", "").strip()

    try:
        test_cases = json.loads(clean_text)
        print(f"✅ Parsed {len(test_cases)} scenarios.")
    except json.JSONDecodeError:
        print("❌ AI returned invalid JSON. Please try again.")
        return

    os.makedirs(folder, exist_ok=True)
    for f in os.listdir(folder):
        if f.startswith(prefix) and f.endswith(".json"):
            os.remove(os.path.join(folder, f))

    for i, case in enumerate(test_cases):
        filename  = f"{prefix}_{i+1:02d}.json"
        file_path = os.path.join(folder, filename)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(case, f, indent=2)
        print(f"💾 Saved: {file_path}")

    print(f"\n✅ Generation complete for {folder}.")


if __name__ == "__main__":
    generate_test_cases(10)
    generate_tax_test_cases(5)
    generate_payroll_test_cases(5)