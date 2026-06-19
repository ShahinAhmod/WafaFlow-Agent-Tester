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

    raw_text = response.choices[0].message.content
    clean_text = raw_text.replace("```json", "").replace("```", "").strip()
    
    try:
        test_cases = json.loads(clean_text)
        print(f"✅ Successfully parsed {len(test_cases)} scenarios from AI.")
    except json.JSONDecodeError:
        print("❌ AI returned invalid JSON. Please try again.")
        return

    # Define the new generated folder path
    test_folder = "test_cases/generated"
    
    # Create the folder if it doesn't exist
    os.makedirs(test_folder, exist_ok=True)
    
    # Clean up ONLY old generated tests (Manual tests are safe in their own folder)
    for f in os.listdir(test_folder):
        if f.endswith(".json"):
            os.remove(os.path.join(test_folder, f))

    for i, case in enumerate(test_cases):
        filename = f"test_case_{i+1:02d}.json"
        file_path = os.path.join(test_folder, filename)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(case, f, indent=2)
        print(f"💾 Saved: {os.path.join(test_folder, filename)}")

    print(f"\n Generation complete! Run 'run_all_tests.py' to test them.")

if __name__ == "__main__":
    generate_test_cases(10)