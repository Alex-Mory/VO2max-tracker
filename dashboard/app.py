"""
dashboard/app.py — VO2max Tracker Dashboard

Run with:  streamlit run dashboard/app.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta

from backend import database as db
from backend.config import ATHLETE_HRMAX, ATHLETE_HR_REST, ATHLETE_WEIGHT_KG

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="VO2max Tracker",
    page_icon="🫁",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Custom CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Syne:wght@400;600;700;800&display=swap');

  html, body, [class*="css"] {
    font-family: 'Syne', sans-serif;
    background-color: #0a0a0f;
    color: #e8e8f0;
  }

  .main { background-color: #0a0a0f; }

  .block-container {
    padding-top: 2rem;
    padding-bottom: 2rem;
    max-width: 1400px;
  }

  h1, h2, h3 {
    font-family: 'Syne', sans-serif;
    font-weight: 800;
    letter-spacing: -0.02em;
  }

  .metric-card {
    background: linear-gradient(135deg, #13131f 0%, #1a1a2e 100%);
    border: 1px solid #2a2a4a;
    border-radius: 16px;
    padding: 1.5rem;
    text-align: center;
  }

  .metric-value {
    font-family: 'DM Mono', monospace;
    font-size: 2.8rem;
    font-weight: 500;
    color: #7fffb2;
    line-height: 1;
  }

  .metric-label {
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    color: #6060a0;
    margin-top: 0.4rem;
  }

  .metric-sub {
    font-family: 'DM Mono', monospace;
    font-size: 0.85rem;
    color: #9090c0;
    margin-top: 0.3rem;
  }

  .run-row {
    background: #13131f;
    border: 1px solid #1e1e3a;
    border-radius: 10px;
    padding: 0.8rem 1rem;
    margin-bottom: 0.4rem;
    display: flex;
    align-items: center;
    gap: 1rem;
  }

  .confidence-high   { color: #7fffb2; }
  .confidence-medium { color: #ffd97d; }
  .confidence-low    { color: #ff8f8f; }

  .zone-bar {
    height: 8px;
    border-radius: 4px;
    background: linear-gradient(90deg, #2040ff, #20c0ff, #20ff80, #ffd700, #ff4040);
  }

  div[data-testid="stMetric"] {
    background: #13131f;
    border: 1px solid #2a2a4a;
    border-radius: 12px;
    padding: 1rem;
  }

  div[data-testid="stMetric"] label {
    color: #6060a0 !important;
    font-size: 0.7rem !important;
    text-transform: uppercase;
    letter-spacing: 0.1em;
  }

  div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
    font-family: 'DM Mono', monospace;
    color: #7fffb2 !important;
    font-size: 1.8rem !important;
  }
</style>
""", unsafe_allow_html=True)

# ── Data loading ───────────────────────────────────────────────────────────────
db.init_db()

@st.cache_data(ttl=60)
def load_data():
    runs    = db.get_all_runs(limit=500)
    history = db.get_vo2max_history()
    return runs, history

runs_raw, history_raw = load_data()

runs_df    = pd.DataFrame(runs_raw)    if runs_raw    else pd.DataFrame()
history_df = pd.DataFrame(history_raw) if history_raw else pd.DataFrame()

# ── Header ─────────────────────────────────────────────────────────────────────
st.markdown("# 🫁 VO2max Tracker")
st.markdown(
    "<p style='color:#6060a0; margin-top:-0.5rem; font-size:0.9rem;'>"
    "Calibrated from your 10K (32:55) and HM (1:13:52) · "
    f"HRmax {ATHLETE_HRMAX} · {ATHLETE_WEIGHT_KG}kg"
    "</p>",
    unsafe_allow_html=True,
)

st.divider()

# ── Top metrics ────────────────────────────────────────────────────────────────
col1, col2, col3, col4, col5 = st.columns(5)

if not history_df.empty:
    latest_smooth = history_df["smoothed"].dropna().iloc[-1]
    latest_raw    = history_df["vo2max"].iloc[-1]
    latest_date   = history_df["date"].iloc[-1]

    # Trend: compare last 4 weeks vs previous 4 weeks
    recent = history_df[history_df["confidence"].isin(["high","medium"])].tail(8)
    if len(recent) >= 4:
        mid = len(recent) // 2
        trend = recent["vo2max"].tail(mid).mean() - recent["vo2max"].head(mid).mean()
        trend_str = f"+{trend:.1f}" if trend >= 0 else f"{trend:.1f}"
    else:
        trend_str = "—"

    high_conf = history_df[history_df["confidence"] == "high"]["vo2max"]
    peak_vo2  = high_conf.max() if not high_conf.empty else latest_smooth
    n_runs    = len(runs_df) if not runs_df.empty else 0

    with col1:
        st.metric("Current VO2max", f"{latest_smooth:.1f}", help="4-week rolling average")
    with col2:
        st.metric("Latest estimate", f"{latest_raw:.1f}", delta=trend_str, help="Most recent run")
    with col3:
        st.metric("Peak VO2max", f"{peak_vo2:.1f}", help="Best high-confidence estimate")
    with col4:
        days_since = (datetime.now() - datetime.fromisoformat(latest_date)).days
        st.metric("Last updated", f"{days_since}d ago", help=latest_date)
    with col5:
        st.metric("Runs tracked", str(n_runs))
else:
    st.info("No data yet. Run `python scripts/backfill.py` to import your Strava history.")

st.markdown("<br>", unsafe_allow_html=True)

# ── Main trend chart ───────────────────────────────────────────────────────────
st.markdown("### VO2max Over Time")

if not history_df.empty:
    history_df["date"] = pd.to_datetime(history_df["date"])

    # Filter controls
    col_f1, col_f2, _ = st.columns([1, 1, 3])
    with col_f1:
        period = st.selectbox("Period", ["All time", "Last 6 months", "Last 3 months", "Last month"], index=1)
    with col_f2:
        show_all = st.checkbox("Show all estimates (incl. easy runs)", value=False)

    if period == "Last month":
        cutoff = datetime.now() - timedelta(days=30)
    elif period == "Last 3 months":
        cutoff = datetime.now() - timedelta(days=90)
    elif period == "Last 6 months":
        cutoff = datetime.now() - timedelta(days=180)
    else:
        cutoff = datetime(2000, 1, 1)

    h = history_df[history_df["date"] >= cutoff].copy()

    if not show_all:
        h = h[h["confidence"].isin(["high", "medium"])]

    fig = go.Figure()

    # Band: low confidence
    low = history_df[(history_df["confidence"] == "low") & (history_df["date"] >= cutoff)]
    if not low.empty and show_all:
        fig.add_trace(go.Scatter(
            x=low["date"], y=low["vo2max"],
            mode="markers",
            name="Easy run (low conf.)",
            marker=dict(color="#ff8f8f", size=5, opacity=0.5, symbol="circle-open"),
        ))

    # Medium confidence
    med = h[h["confidence"] == "medium"]
    if not med.empty:
        fig.add_trace(go.Scatter(
            x=med["date"], y=med["vo2max"],
            mode="markers",
            name="Tempo (medium conf.)",
            marker=dict(color="#ffd97d", size=7, opacity=0.8),
            text=med.get("name", ""),
            hovertemplate="<b>%{text}</b><br>%{x|%d %b %Y}<br>VO2max: %{y:.1f}<extra></extra>",
        ))

    # High confidence (races)
    hi = h[h["confidence"] == "high"]
    if not hi.empty:
        fig.add_trace(go.Scatter(
            x=hi["date"], y=hi["vo2max"],
            mode="markers",
            name="Race (high conf.)",
            marker=dict(color="#7fffb2", size=11, symbol="diamond"),
            text=hi.get("name", ""),
            hovertemplate="<b>%{text}</b><br>%{x|%d %b %Y}<br>VO2max: %{y:.1f}<extra></extra>",
        ))

    # Smoothed line
    smooth = h.dropna(subset=["smoothed"])
    if not smooth.empty:
        fig.add_trace(go.Scatter(
            x=smooth["date"], y=smooth["smoothed"],
            mode="lines",
            name="Rolling average",
            line=dict(color="#7fffb2", width=2.5, dash="solid"),
            opacity=0.9,
        ))

    # Reference zones
    fig.add_hrect(y0=60, y1=70, fillcolor="#7fffb2", opacity=0.04, line_width=0)
    fig.add_hline(y=65, line=dict(color="#7fffb2", width=1, dash="dot"), opacity=0.3,
                  annotation_text="Your baseline ~65", annotation_position="right")

    fig.update_layout(
        paper_bgcolor="#0a0a0f",
        plot_bgcolor="#0a0a0f",
        font=dict(family="Syne, sans-serif", color="#e8e8f0"),
        height=380,
        margin=dict(l=10, r=10, t=20, b=20),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02,
            bgcolor="rgba(0,0,0,0)",
            font=dict(size=11),
        ),
        xaxis=dict(
            gridcolor="#1a1a2e", showgrid=True,
            zeroline=False, tickfont=dict(size=11),
        ),
        yaxis=dict(
            gridcolor="#1a1a2e", showgrid=True,
            zeroline=False, tickfont=dict(size=11),
            title="VO2max (ml/kg/min)",
            range=[
                max(40, h["vo2max"].min() - 5) if not h.empty else 40,
                min(85, h["vo2max"].max() + 5) if not h.empty else 80,
            ],
        ),
        hovermode="x unified",
    )

    st.plotly_chart(fig, use_container_width=True)

else:
    st.info("No history yet.")

# ── HR Zones reference ─────────────────────────────────────────────────────────
st.markdown("### Your Training Zones")

zones = [
    ("Z1 — Recovery",      115, 138, "#2040ff", "Easy runs, warm-up/cool-down"),
    ("Z2 — Aerobic base",  138, 157, "#20c0ff", "Long runs, fat burning — LT1 ceiling: ~148"),
    ("Z3 — Tempo",         157, 172, "#20ff80", "Marathon pace, comfortably hard"),
    ("Z4 — Threshold",     172, 181, "#ffd700", "HM effort, LT2 intervals — LT2: ~172-173"),
    ("Z5 — VO2max",        181, 192, "#ff4040", "Short hard intervals, 3-8 min"),
]

cols = st.columns(5)
for i, (name, lo, hi, color, desc) in enumerate(zones):
    with cols[i]:
        st.markdown(
            f"""<div class="metric-card">
              <div style="color:{color}; font-size:0.7rem; text-transform:uppercase; letter-spacing:0.1em; font-weight:700">{name}</div>
              <div style="font-family:'DM Mono',monospace; font-size:1.4rem; color:#e8e8f0; margin:0.3rem 0">{lo}–{hi}</div>
              <div style="font-size:0.65rem; color:#6060a0">bpm</div>
              <div style="font-size:0.7rem; color:#9090c0; margin-top:0.5rem">{desc}</div>
            </div>""",
            unsafe_allow_html=True,
        )

st.markdown("<br>", unsafe_allow_html=True)

# ── Run history table ──────────────────────────────────────────────────────────
st.markdown("### Run History")

if not runs_df.empty:
    col_t1, col_t2, col_t3 = st.columns([1, 1, 2])
    with col_t1:
        conf_filter = st.multiselect(
            "Confidence", ["high", "medium", "low"],
            default=["high", "medium"],
        )
    with col_t2:
        type_filter = st.multiselect(
            "Run type",
            ["race_10k", "race_hm_plus", "race_5k", "tempo", "moderate", "easy"],
            default=[],
            placeholder="All types",
        )

    display = runs_df.copy()
    if conf_filter:
        display = display[display["confidence"].isin(conf_filter)]
    if type_filter:
        display = display[display["run_type"].isin(type_filter)]

    display = display.sort_values("date", ascending=False).head(100)

    # Format for display
    def fmt_pace(row):
        if row["duration_s"] and row["distance_m"]:
            pace_s = (row["duration_s"] / 60) / (row["distance_m"] / 1000)
            return f"{int(pace_s)}:{int((pace_s%1)*60):02d}/km"
        return "—"

    def fmt_time(s):
        if not s: return "—"
        m, sec = divmod(int(s), 60)
        h, m = divmod(m, 60)
        return f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"

    display["Pace"]     = display.apply(fmt_pace, axis=1)
    display["Time"]     = display["duration_s"].apply(fmt_time)
    display["dist_km"]  = (display["distance_m"] / 1000).round(2)

    CONF_ICON = {"high": "🟢", "medium": "🟡", "low": "🔴", None: "⚪"}
    TYPE_ICON = {
        "race_10k": "🏁", "race_hm_plus": "🏁", "race_5k": "🏁",
        "tempo": "⚡", "moderate": "🏃", "easy": "🚶", "short": "•",
    }

    display["conf_icon"] = display["confidence"].map(lambda x: CONF_ICON.get(x, "⚪"))
    display["type_icon"] = display["run_type"].map(lambda x: TYPE_ICON.get(x, "🏃"))

    show_cols = {
        "date":     "Date",
        "name":     "Activity",
        "dist_km":  "Dist (km)",
        "Time":     "Time",
        "Pace":     "Pace",
        "avg_hr":   "Avg HR",
        "avg_power": "Power (W)",
        "vo2max":   "VO2max",
        "vdot":     "VDOT",
        "run_type": "Type",
        "confidence": "Conf.",
        "method":   "Method",
    }

    table = display[[c for c in show_cols if c in display.columns]].rename(columns=show_cols)

    st.dataframe(
        table,
        use_container_width=True,
        height=400,
        column_config={
            "VO2max": st.column_config.NumberColumn(format="%.1f", help="Estimated VO2max"),
            "VDOT":   st.column_config.NumberColumn(format="%.1f"),
            "Conf.":  st.column_config.TextColumn(),
        },
    )

    # Download
    csv = table.to_csv(index=False)
    st.download_button(
        "⬇ Download CSV",
        data=csv,
        file_name=f"vo2max_history_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv",
    )

else:
    st.info("No runs yet.")

# ── Method explanation ─────────────────────────────────────────────────────────
with st.expander("ℹ️ How VO2max is estimated"):
    st.markdown("""
**Three methods are used and blended based on what data is available:**

| Method | When used | Weight |
|--------|-----------|--------|
| **Jack Daniels VDOT** | All runs with distance + time | Primary for races |
| **Power-based** | When Suunto running power is available | Secondary |
| **HR-adjusted VDOT** (Swain 1994) | When HR data is available | Secondary |

**Confidence levels:**
- 🟢 **High** — Race effort (>88% HRmax): VDOT is very reliable
- 🟡 **Medium** — Tempo effort: HR-adjusted VDOT, accurate ±2-3
- 🔴 **Low** — Easy/moderate run: sub-maximal estimate, less reliable

**Why this is better than Suunto's estimate:**
Suunto's Firstbeat algorithm underestimates by 6-8 points on race files
because it applies a submaximal HR-speed model to near-maximal efforts,
and doesn't account for cardiac drift over long races.

Your calibration points:
- 10K 32:55 → VDOT 65.6 (high confidence)
- HM 1:13:52 → VDOT 64.2 (high confidence)
- Consensus: **~65 ml/kg/min**
""")

# ── Footer ─────────────────────────────────────────────────────────────────────
st.markdown(
    "<br><p style='color:#3a3a5a; font-size:0.7rem; text-align:center;'>"
    "VO2max Tracker · Built for Alex Mory · "
    f"HRmax {ATHLETE_HRMAX} bpm · LT2 ~172 bpm · LT1 ~148 bpm"
    "</p>",
    unsafe_allow_html=True,
)
