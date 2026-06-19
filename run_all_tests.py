import os
import json
import datetime
from engine import run_test_case

HISTORY_FILE = "results_history.json"

def _load_history() -> list:
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def _append_to_history(run_record: dict):
    history = _load_history()
    history.append(run_record)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)

def run_suite():
    test_folders = [
        "test_cases/manual",
        "test_cases/generated",
        "test_cases/tax",
        "test_cases/payroll",
        "test_cases/adversarial",
    ]

    results = {"passed": 0, "failed": 0, "by_agent_type": {}, "details": []}

    print(f"\n STARTING TEST SUITE 🚀\n")

    for folder in test_folders:
        if not os.path.exists(folder):
            continue

        print(f" Scanning folder: {folder}")

        for filename in sorted(os.listdir(folder)):
            if filename.endswith(".json"):
                file_path = os.path.join(folder, filename)
                print(f"--- Running: {filename} ---")

                result = run_test_case(file_path)

                agent_type = result.get("agent_type", "ap_match")
                if agent_type not in results["by_agent_type"]:
                    results["by_agent_type"][agent_type] = {"passed": 0, "failed": 0}

                if result["passed"]:
                    results["passed"] += 1
                    results["by_agent_type"][agent_type]["passed"] += 1
                    status = "✅ PASSED"
                else:
                    results["failed"] += 1
                    results["by_agent_type"][agent_type]["failed"] += 1
                    status = "❌ FAILED"

                results["details"].append({
                    "test_file": filename,
                    "folder": folder,
                    "status": status,
                    "agent_type": agent_type,
                    "checks": result["checks"],
                    "deterministic_truth": result["deterministic_truth"],
                    "ai_response": result["ai_response"],
                    "error": result["error"],
                })
                print("-" * 50)

    total = results["passed"] + results["failed"]
    pass_rate = round((results["passed"] / total * 100), 1) if total > 0 else 0.0

    print(f"\n🏁 SUITE FINISHED 🏁")
    print(f"✅ Passed: {results['passed']}")
    print(f"❌ Failed: {results['failed']}")
    print(f"   Total:  {total}")
    print(f"📊 Pass Rate: {pass_rate}%")
    for atype, counts in results["by_agent_type"].items():
        print(f"   [{atype}] Passed: {counts['passed']} | Failed: {counts['failed']}")
    print()

    now = str(datetime.datetime.now())
    results["timestamp"] = now
    results["pass_rate"] = pass_rate
    results["total"] = total

    # Persist latest run (for backward compat)
    with open("latest_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print("💾 Results saved to latest_results.json for the dashboard.")

    # Append to history
    run_id = "RUN-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    run_record = {
        "run_id": run_id,
        "timestamp": now,
        "passed": results["passed"],
        "failed": results["failed"],
        "total": total,
        "pass_rate": pass_rate,
    }
    _append_to_history(run_record)
    print(f"📈 Run {run_id} appended to {HISTORY_FILE}.")

if __name__ == "__main__":
    run_suite()