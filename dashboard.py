import streamlit as st
import json
import os
import pandas as pd

HISTORY_FILE = "results_history.json"

# Page configuration
st.set_page_config(page_title="WafaFlow Agent Tester", layout="wide", page_icon="🤖")

st.title("🤖 WafaFlow Accounting Agent Test Dashboard")
st.markdown("Automated CI/CD Testing Platform for AI Agents")

# ── Historical Trend ────────────────────────────────────────────────────────
st.subheader("📈 Pass Rate — Historical Trend")

if not os.path.exists(HISTORY_FILE):
    st.info("No history yet. Run `run_all_tests.py` at least once to start tracking trends.")
else:
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        history = json.load(f)

    df = pd.DataFrame(history)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp")

    # Trend line chart
    chart_df = df.set_index("timestamp")[["pass_rate"]]
    st.line_chart(chart_df, y="pass_rate", use_container_width=True)

    # Summary table of all runs
    display_cols = ["run_id", "timestamp", "total", "passed", "failed", "pass_rate"]
    display_df = df[display_cols].copy()
    display_df["timestamp"] = display_df["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")
    display_df = display_df.rename(columns={
        "run_id": "Run ID",
        "timestamp": "Timestamp",
        "total": "Total",
        "passed": "Passed",
        "failed": "Failed",
        "pass_rate": "Pass Rate (%)",
    })
    st.dataframe(display_df, use_container_width=True, hide_index=True)

st.divider()

# ── Latest Run ──────────────────────────────────────────────────────────────
st.subheader("🕒 Latest Run Details")

if not os.path.exists("latest_results.json"):
    st.warning("No test results found. Please run `run_all_tests.py` in your terminal first.")
else:
    with open("latest_results.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    st.caption(f"Run at: {data['timestamp']}")

    total = data.get("total", data["passed"] + data["failed"])
    pass_rate = data.get("pass_rate", round(data["passed"] / total * 100, 1) if total else 0)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Tests", total)
    col2.metric("Passed ✅", data["passed"])
    col3.metric("Failed ❌", data["failed"])
    col4.metric("Pass Rate", f"{pass_rate}%")

    st.divider()

    # Detailed Test Cases
    st.subheader("📂 Test Case Details")

    CHECK_LABELS = {
        "schema_valid":   "Schema Valid",
        "status_match":   "Status Match",
        "numeric_match":  "Numeric Variance",
        "security_clean": "Security / PII",
    }

    for test in data["details"]:
        with st.expander(f"{test['status']} — {test['test_file']}"):
            st.write(f"**Folder:** `{test['folder']}`")

            # ── Per-check breakdown (new) ───────────────────────────────
            checks = test.get("checks")
            if checks:
                st.markdown("**Check Results**")
                cols = st.columns(len(checks))
                for col, (key, label) in zip(cols, CHECK_LABELS.items()):
                    c = checks.get(key, {})
                    icon = "✅" if c.get("passed") else "❌"
                    col.metric(label, icon)
                    col.caption(c.get("detail", ""))

            st.divider()

            # ── Side-by-side: deterministic truth vs AI response ────────
            col_truth, col_ai = st.columns(2)

            with col_truth:
                st.markdown("**Deterministic Truth**")
                truth = test.get("deterministic_truth")
                if truth:
                    st.json(truth)
                else:
                    st.caption("Not available (legacy result).")

            with col_ai:
                st.markdown("**AI Response**")
                ai = test.get("ai_response")
                if ai:
                    # Show structured fields if parsed, raw text otherwise
                    if "status" in ai:
                        st.json({k: v for k, v in ai.items() if k != "raw"})
                    else:
                        st.code(ai.get("raw", ""), language="json")
                else:
                    st.caption("Not available (legacy result).")

            if test.get("error"):
                st.error(f"Engine error: {test['error']}")

            st.divider()

            # ── Raw test case JSON (collapsed) ──────────────────────────
            test_path = os.path.join(test["folder"], test["test_file"])
            if os.path.exists(test_path):
                with open(test_path, "r", encoding="utf-8") as tf:
                    case_data = json.load(tf)
                with st.expander("📄 Raw Test Case JSON"):
                    st.json(case_data)