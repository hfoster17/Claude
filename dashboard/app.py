"""
Multi-Regime Trading Dashboard — Streamlit-based monitoring UI.

Usage:
    streamlit run dashboard/app.py
    streamlit run dashboard/app.py -- --status-file engine_status.json
"""

import json
import os
import sys
import time
from pathlib import Path

import streamlit as st
import numpy as np

# Add engine to path for imports
ENGINE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "engine")
sys.path.insert(0, ENGINE_DIR)

STATUS_FILE = os.environ.get("ENGINE_STATUS_FILE", "engine_status.json")
MODEL_DIR = os.environ.get("MODEL_DIR", "models")

SYMBOLS = ["NQ", "ES", "CL", "NG", "GC", "SI", "ZB"]
REGIME_COLORS = {"low_vol": "#808080", "trending": "#1E90FF", "high_vol": "#FF4444"}

st.set_page_config(
    page_title="Multi-Regime Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)


def load_status() -> dict:
    """Load engine status from JSON file."""
    for path in [STATUS_FILE, os.path.join(ENGINE_DIR, STATUS_FILE)]:
        if os.path.exists(path):
            try:
                with open(path) as f:
                    return json.load(f)
            except Exception:
                pass
    return {}


def load_model(symbol: str) -> dict:
    """Load a model JSON file."""
    for base in [MODEL_DIR, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models")]:
        path = os.path.join(base, f"{symbol}_model.json")
        if os.path.exists(path):
            try:
                with open(path) as f:
                    return json.load(f)
            except Exception:
                pass
    return {}


# --- SIDEBAR ---
st.sidebar.title("Multi-Regime Monitor")
st.sidebar.markdown("---")
auto_refresh = st.sidebar.checkbox("Auto Refresh (5s)", value=True)
if auto_refresh:
    time.sleep(0.1)  # Prevent tight loop
    st.rerun() if False else None  # Placeholder for auto-refresh

status = load_status()

# Engine health
st.sidebar.subheader("Engine Health")
if status:
    uptime = status.get("uptime_s", 0)
    hours = int(uptime // 3600)
    minutes = int((uptime % 3600) // 60)
    st.sidebar.metric("Uptime", f"{hours}h {minutes}m")
    st.sidebar.metric("Total Requests", status.get("total_requests", 0))
    st.sidebar.metric("Total Errors", status.get("total_errors", 0))
    st.sidebar.metric("Avg Latency", f"{status.get('avg_latency_ms', 0):.3f}ms")
    st.sidebar.metric("Models Loaded", len(status.get("models_loaded", [])))
else:
    st.sidebar.warning("Engine status not available")

# --- MAIN ---
st.title("Multi-Regime Trading Dashboard")

# Regime overview
st.header("Regime Overview")
cols = st.columns(len(SYMBOLS))

for i, symbol in enumerate(SYMBOLS):
    model = load_model(symbol)
    with cols[i]:
        st.subheader(symbol)

        if model:
            labels = model.get("regime_labels", [])
            k = model.get("k", 0)
            trained = model.get("metadata", {}).get("trained_at", "N/A")

            st.caption(f"K={k} | Trained: {trained[:10] if len(trained) > 10 else trained}")

            # Show regime labels with colors
            for j, label in enumerate(labels):
                color = REGIME_COLORS.get(label, "#AAAAAA")
                st.markdown(
                    f'<span style="color:{color}; font-weight:bold;">State {j}: {label}</span>',
                    unsafe_allow_html=True,
                )

            # Request count
            per_sym = status.get("per_symbol_requests", {})
            req_count = per_sym.get(symbol, 0)
            st.metric("Requests", req_count)
        else:
            st.warning("No model loaded")

# Transition matrices
st.header("Transition Matrices")
matrix_cols = st.columns(min(4, len(SYMBOLS)))

for i, symbol in enumerate(SYMBOLS):
    model = load_model(symbol)
    col_idx = i % 4
    with matrix_cols[col_idx]:
        if model and "transition_matrix" in model:
            st.subheader(symbol)
            trans = np.array(model["transition_matrix"])
            labels = model.get("regime_labels", [f"S{j}" for j in range(len(trans))])

            # Display as styled table
            import pandas as pd
            df = pd.DataFrame(trans, index=labels, columns=labels)
            st.dataframe(df.style.format("{:.3f}").background_gradient(cmap="Blues"),
                         use_container_width=True)

# Model metadata
st.header("Model Details")
model_data = []
for symbol in SYMBOLS:
    model = load_model(symbol)
    if model:
        meta = model.get("metadata", {})
        model_data.append({
            "Symbol": symbol,
            "K": model.get("k", "?"),
            "Trained": meta.get("trained_at", "N/A")[:19],
            "Bars": meta.get("training_bars", 0),
            "Log-Likelihood": f"{meta.get('log_likelihood', 0):.2f}",
            "Converged": meta.get("converged", False),
        })

if model_data:
    import pandas as pd
    st.dataframe(pd.DataFrame(model_data), use_container_width=True)
else:
    st.info("No models found. Train models first with: python train.py --all")

# Per-symbol request stats
st.header("Request Statistics")
per_sym = status.get("per_symbol_requests", {})
if per_sym:
    import pandas as pd
    df = pd.DataFrame([
        {"Symbol": k, "Requests": v} for k, v in per_sym.items()
    ])
    st.bar_chart(df.set_index("Symbol"))
else:
    st.info("No request data yet. Start the engine and connect NT8.")

# Footer
st.markdown("---")
st.caption("Multi-Regime Trading Stack | Dashboard v1.0")

# Auto-refresh via rerun
if auto_refresh:
    import time as t
    t.sleep(5)
    st.rerun()
