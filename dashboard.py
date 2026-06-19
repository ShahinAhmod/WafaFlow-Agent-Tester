import streamlit as st
import json
import os
import pandas as pd
import math

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
    base_cols = ["run_id", "timestamp", "total", "passed", "failed", "pass_rate"]
    perf_cols = [c for c in ["avg_latency_ms", "total_tokens", "total_cost_usd"] if c in df.columns]
    display_cols = base_cols + perf_cols
    display_df = df[display_cols].copy()
    display_df["timestamp"] = display_df["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")
    display_df = display_df.rename(columns={
        "run_id":          "Run ID",
        "timestamp":       "Timestamp",
        "total":           "Total",
        "passed":          "Passed",
        "failed":          "Failed",
        "pass_rate":       "Pass Rate (%)",
        "avg_latency_ms":  "Avg Latency (ms)",
        "total_tokens":    "Total Tokens",
        "total_cost_usd":  "Est. Cost ($)",
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

    # ── Performance Metrics ─────────────────────────────────────────────
    perf = data.get("performance", {})
    if perf and perf.get("total_tokens", 0) > 0:
        st.markdown("**Performance**")
        pc1, pc2, pc3, pc4 = st.columns(4)
        pc1.metric("Avg Latency",   f"{perf.get('avg_latency_ms', 0)} ms")
        pc2.metric("Total Tokens",  f"{perf.get('total_tokens', 0):,}")
        pc3.metric("Est. Cost",     f"${perf.get('total_cost_usd', 0):.5f}")
        pc4.metric("Slowest Test",  f"{perf.get('max_latency_ms', 0)} ms")

        # Per-test latency bar chart
        latencies = [
            {"test": t["test_file"], "latency_ms": t.get("performance", {}).get("latency_ms", 0)}
            for t in data["details"]
            if t.get("performance", {}).get("latency_ms", 0) > 0
        ]
        if latencies:
            lat_df = pd.DataFrame(latencies).set_index("test")
            st.bar_chart(lat_df, use_container_width=True)

    # Per-agent-type breakdown
    by_type = data.get("by_agent_type", {})
    if by_type:
        st.markdown("**By Agent Type**")
        AGENT_LABELS = {
            "ap_match":        "AP 3-Way Match",
            "tax_calculation": "Tax Calculation",
            "payroll":         "Payroll",
            "adversarial":     "Adversarial / Security",
        }
        type_cols = st.columns(len(by_type))
        for col, (atype, counts) in zip(type_cols, by_type.items()):
            t = counts["passed"] + counts["failed"]
            rate = round(counts["passed"] / t * 100, 1) if t else 0
            label = AGENT_LABELS.get(atype, atype)
            col.metric(label, f"{counts['passed']}/{t}", f"{rate}% pass")

    st.divider()

    # Detailed Test Cases
    st.subheader("📂 Test Case Details")

    # Agent type filter
    all_types = sorted({t.get("agent_type", "ap_match") for t in data["details"]})
    AGENT_LABELS = {
        "ap_match":        "AP 3-Way Match",
        "tax_calculation": "Tax Calculation",
        "payroll":         "Payroll",
        "adversarial":     "Adversarial / Security",
    }
    filter_options = ["All"] + [AGENT_LABELS.get(t, t) for t in all_types]
    selected_label = st.selectbox("Filter by agent type:", filter_options)
    selected_type  = None if selected_label == "All" else next(
        (k for k, v in AGENT_LABELS.items() if v == selected_label), selected_label
    )

    CHECK_LABELS = {
        "schema_valid":       "Schema Valid",
        "status_match":       "Status Match",
        "numeric_match":      "Numeric Variance",
        "security_clean":     "Security / PII",
        "injection_resisted": "Injection Resisted",
        "json_only_output":   "JSON-Only Output",
    }

    filtered = [
        t for t in data["details"]
        if selected_type is None or t.get("agent_type", "ap_match") == selected_type
    ]

    for test in filtered:
        atype_label = AGENT_LABELS.get(test.get("agent_type", "ap_match"), test.get("agent_type", ""))
        with st.expander(f"{test['status']} — {test['test_file']}  `{atype_label}`"):
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

            # ── Per-test performance ────────────────────────────────────
            tp = test.get("performance", {})
            if tp and tp.get("total_tokens", 0) > 0:
                st.markdown("**Performance**")
                lc1, lc2, lc3 = st.columns(3)
                lc1.metric("Latency",      f"{tp.get('latency_ms', 0)} ms")
                lc2.metric("Tokens",       f"{tp.get('total_tokens', 0):,}")
                lc3.metric("Est. Cost",    f"${tp.get('cost_usd', 0):.5f}")

            st.divider()

            # ── Raw test case JSON (collapsed) ──────────────────────────
            test_path = os.path.join(test["folder"], test["test_file"])
            if os.path.exists(test_path):
                with open(test_path, "r", encoding="utf-8") as tf:
                    case_data = json.load(tf)
                with st.expander("📄 Raw Test Case JSON"):
                    st.json(case_data)