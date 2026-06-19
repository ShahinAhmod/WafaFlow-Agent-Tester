"""
CI gate: reads latest_results.json and exits with code 1 if any tests failed.
Called by the GitHub Actions workflow after run_all_tests.py.
"""
import json
import sys

RESULTS_FILE = "latest_results.json"

def main():
    try:
        with open(RESULTS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"❌ CI GATE: {RESULTS_FILE} not found. Did run_all_tests.py complete?")
        sys.exit(1)

    passed    = data.get("passed", 0)
    failed    = data.get("failed", 0)
    total     = data.get("total", passed + failed)
    pass_rate = data.get("pass_rate", 0)

    print("\n" + "=" * 50)
    print("  WAFAFLOW CI GATE — RESULTS SUMMARY")
    print("=" * 50)
    print(f"  Total   : {total}")
    print(f"  Passed  : {passed}")
    print(f"  Failed  : {failed}")
    print(f"  Pass Rate: {pass_rate}%")

    if failed > 0:
        print("\n❌ CI GATE FAILED — one or more agent tests did not pass.")
        print("   Failing tests:")
        for detail in data.get("details", []):
            if "FAILED" in detail.get("status", ""):
                checks = detail.get("checks", {})
                failed_checks = [
                    label for label, info in checks.items() if not info.get("passed")
                ]
                print(f"   • {detail['test_file']} — failed checks: {', '.join(failed_checks) or 'unknown'}")
                for label in failed_checks:
                    detail_msg = checks[label].get("detail", "")
                    if detail_msg:
                        print(f"       └─ {label}: {detail_msg}")
        print()
        sys.exit(1)
    else:
        print(f"\n✅ CI GATE PASSED — all {total} tests passed.")
        sys.exit(0)

if __name__ == "__main__":
    main()
