"""
PhonePe Transaction Insights - Streamlit dashboard.

Data source (auto-selected):
  1. PostgreSQL if the DATABASE_URL env var / Streamlit secret is set
     e.g. postgresql+psycopg2://user:pw@host:5432/phonepe
  2. Otherwise the CSVs in data/processed/ (works on Streamlit Community Cloud).

Run:  streamlit run app/app.py
"""
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
TABLES = ["aggregated_transaction", "aggregated_user", "aggregated_merchant",
          "map_transaction", "map_user", "map_merchant"]
VIOLET, SAFFRON = "#5F259F", "#E8A33D"
SCALE = ["#EFE9F8", "#9B6BD0", "#2E0F5C"]

st.set_page_config(page_title="PhonePe Transaction Insights", page_icon="💜", layout="wide")


# ------------------------------------------------------------------ data
@st.cache_data(show_spinner="Loading data...")
def load() -> dict[str, pd.DataFrame]:
    url = os.getenv("DATABASE_URL")
    if not url:
        try:
            url = st.secrets["DATABASE_URL"]
        except Exception:  # no secrets file configured -> use CSVs
            url = None
    if url:
        try:
            from sqlalchemy import create_engine
            eng = create_engine(url)
            return {t: pd.read_sql(f"SELECT * FROM {t}", eng) for t in TABLES}
        except Exception as exc:  # fall back to CSVs rather than crash the app
            st.warning(f"Database unavailable ({exc.__class__.__name__}); using bundled CSVs.")
    return {t: pd.read_csv(ROOT / "data" / "processed" / f"{t}.csv") for t in TABLES}


@st.cache_data
def geojson() -> dict:
    return json.loads((ROOT / "geo" / "india_states.geojson").read_text(encoding="utf-8"))


def fmt(v: float) -> str:
    for div, suf in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if abs(v) >= div:
            return f"{v / div:,.1f}{suf}"
    return f"{v:,.0f}"


T = load()
at, au, am, mt, mu = (T[k] for k in ["aggregated_transaction", "aggregated_user",
                                     "aggregated_merchant", "map_transaction", "map_user"])
at["period"] = at.year.astype(str) + " Q" + at.quarter.astype(str)
periods = sorted(at.period.unique())
years = sorted(at.year.unique())
latest = at.sort_values(["year", "quarter"]).iloc[-1][["year", "quarter"]].astype(int)

# --------------------------------------------------------------- sidebar
st.sidebar.title("PhonePe Insights")
year = st.sidebar.selectbox("Year", years, index=years.index(2025))
quarter = st.sidebar.selectbox("Quarter", [0, 1, 2, 3, 4], format_func=lambda q: "Full year" if q == 0 else f"Q{q}")
st.sidebar.caption("Source: PhonePe Pulse open data. Amounts in INR; 1 crore = 10 million.")


def sel(df: pd.DataFrame) -> pd.DataFrame:
    df = df[df.year == year]
    return df if quarter == 0 else df[df.quarter == quarter]


st.title("PhonePe Transaction Insights")
tab1, tab2, tab3, tab4, tab5 = st.tabs(["Overview", "Trends", "Geography", "Segments", "Users and merchants"])

# ------------------------------------------------------------- Overview
with tab1:
    sat, smt = sel(at), sel(mt)
    uq = quarter or au[au.year == year].quarter.max()      # year-end (or latest) snapshot
    users = au[(au.year == year) & (au.quarter == uq)]
    c = st.columns(4)
    c[0].metric("Transactions", fmt(sat.txn_count.sum()))
    c[1].metric("Value", f"₹{smt.txn_amount.sum() / 1e7:,.0f} cr")
    c[2].metric("Average ticket", f"₹{smt.txn_amount.sum() / max(smt.txn_count.sum(), 1):,.0f}")
    c[3].metric("Registered users", fmt(users.registered_users.sum()))

    metric = st.radio("Map metric", ["Transactions", "Value (₹ cr)"], horizontal=True)
    by = (sat.groupby("state", as_index=False).txn_count.sum().rename(columns={"txn_count": "v"})
          if metric == "Transactions" else
          smt.groupby("state", as_index=False).txn_amount.sum().assign(v=lambda d: d.txn_amount / 1e7)[["state", "v"]])
    by["log"] = np.log10(by.v.clip(lower=1))                # log colour scale: a few states dominate
    left, right = st.columns([3, 2])
    fig = px.choropleth(by, geojson=geojson(), featureidkey="properties.state", locations="state",
                        color="log", color_continuous_scale=SCALE, hover_name="state", hover_data={"v": ":,.0f", "log": False})
    fig.update_geos(fitbounds="locations", visible=False)
    fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), coloraxis_showscale=False, height=520)
    left.plotly_chart(fig, width="stretch")
    top = by.nlargest(10, "v").sort_values("v")
    right.plotly_chart(px.bar(top, x="v", y="state", orientation="h", text=top.v.map(fmt), color_discrete_sequence=[VIOLET],
                              labels={"v": metric, "state": ""}).update_layout(height=520, margin=dict(l=0, r=10, t=10, b=0)),
                       width="stretch")

# --------------------------------------------------------------- Trends
with tab2:
    q = at.groupby("period", as_index=False).txn_count.sum()
    amt = mt.assign(period=mt.year.astype(str) + " Q" + mt.quarter.astype(str)).groupby("period", as_index=False).txn_amount.sum()
    q = q.merge(amt, on="period").sort_values("period")
    q["qoq_pct"] = q.txn_count.pct_change() * 100
    st.plotly_chart(px.bar(q, x="period", y="txn_count", color_discrete_sequence=[VIOLET],
                           title="National transactions per quarter").update_layout(xaxis_tickangle=-60), width="stretch")
    a, b = st.columns(2)
    cat = at.groupby(["year", "payment_category"], as_index=False).txn_count.sum()
    cat = cat[cat.year < latest.year]  # full calendar years only
    a.plotly_chart(px.bar(cat, x="year", y="txn_count", color="payment_category", title="Transactions by category (full years)",
                          color_discrete_map={"P2P": "#9B6BD0", "Retail": VIOLET, "Utility": SAFFRON}), width="stretch")
    b.plotly_chart(px.line(q.dropna(), x="period", y="qoq_pct", title="Quarter-on-quarter growth (%)",
                           color_discrete_sequence=[SAFFRON]).update_layout(xaxis_tickangle=-60), width="stretch")

# ------------------------------------------------------------ Geography
with tab3:
    state = st.selectbox("State", sorted(at.state.unique()), index=sorted(at.state.unique()).index("Maharashtra"))
    s = at[at.state == state].groupby("period", as_index=False).txn_count.sum().sort_values("period")
    a, b = st.columns(2)
    a.plotly_chart(px.line(s, x="period", y="txn_count", markers=True, title=f"{state}: transactions",
                           color_discrete_sequence=[VIOLET]).update_layout(xaxis_tickangle=-60), width="stretch")
    d = sel(mt[mt.state == state]).groupby("district", as_index=False).agg(txns=("txn_count", "sum"), amount=("txn_amount", "sum"))
    d = d.nlargest(15, "txns").sort_values("txns")
    b.plotly_chart(px.bar(d, x="txns", y="district", orientation="h", title=f"Top districts in {state}",
                          color_discrete_sequence=[SAFFRON]), width="stretch")
    full = sel(mt).groupby(["state", "district"], as_index=False).agg(txns=("txn_count", "sum"), amount=("txn_amount", "sum"))
    st.plotly_chart(px.treemap(full.nlargest(60, "amount"), path=["state", "district"], values="amount",
                               color="state", title="Top 60 districts by value (area = rupees)"), width="stretch")

# ------------------------------------------------------------- Segments
with tab4:
    d = mt[mt.year == year].groupby(["state", "district"], as_index=False).agg(txns=("txn_count", "sum"), amount=("txn_amount", "sum"))
    u = mu[(mu.year == year) & (mu.quarter == mu[mu.year == year].quarter.max())][["state", "district", "registered_users"]]
    d = d.merge(u, on=["state", "district"]).query("registered_users > 0")
    d["txns_per_user"], d["ticket"] = d.txns / d.registered_users, d.amount / d.txns
    fm, tm = d.txns_per_user.median(), d.ticket.median()
    d["segment"] = d.apply(lambda r: ("Power hubs" if r.ticket >= tm else "Everyday spenders") if r.txns_per_user >= fm
                           else ("Big-ticket occasional" if r.ticket >= tm else "Emerging / under-engaged"), axis=1)
    st.caption(f"Districts split at the median: {fm:,.0f} transactions per user and ₹{tm:,.0f} average ticket ({year}).")
    st.plotly_chart(px.scatter(d, x="txns_per_user", y="ticket", color="segment", size="registered_users", hover_name="district",
                               log_x=True, labels={"txns_per_user": "Transactions per user", "ticket": "Average ticket (₹)"},
                               size_max=30, opacity=0.7), width="stretch")
    st.dataframe(d.groupby("segment").agg(districts=("district", "count"), users_mn=("registered_users", lambda x: x.sum() / 1e6),
                                          value_share_pct=("amount", lambda x: 100 * x.sum() / d.amount.sum())).round(1))

# ---------------------------------------------------- Users & merchants
with tab5:
    last = au.sort_values(["year", "quarter"]).groupby("year").tail(1)[["year", "quarter"]]
    ny = au.merge(last).groupby("year", as_index=False).registered_users.sum().merge(
        am.merge(last).groupby("year", as_index=False).registered_merchants.sum())
    a, b = st.columns(2)
    a.plotly_chart(px.bar(ny, x="year", y="registered_users", title="Registered users (year-end)",
                          color_discrete_sequence=[VIOLET]), width="stretch")
    b.plotly_chart(px.bar(ny, x="year", y="registered_merchants", title="Registered merchants (year-end)",
                          color_discrete_sequence=[SAFFRON]), width="stretch")
    p = au.merge(am, on=["state", "year", "quarter"])
    p = p[(p.year == latest.year) & (p.quarter == latest.quarter)]
    p["merchants_per_1k_users"] = 1000 * p.registered_merchants / p.registered_users
    st.plotly_chart(px.bar(p.sort_values("merchants_per_1k_users"), x="merchants_per_1k_users", y="state", orientation="h",
                           title=f"Merchants per 1,000 users ({latest.year} Q{latest.quarter})", height=800,
                           color_discrete_sequence=[VIOLET]), width="stretch")
