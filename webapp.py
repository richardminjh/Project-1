from __future__ import annotations

import os
import logging
from datetime import datetime, timezone
from typing import Dict

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

# -------------------------------------------------------------------
# Environment + logging safety
# -------------------------------------------------------------------
# Prevent yfinance from attempting SciPy-dependent repair paths
os.environ["YFINANCE_NO_SCI"] = "1"

logging.getLogger("yfinance").setLevel(logging.CRITICAL)

# -------------------------------------------------------------------
# App config
# -------------------------------------------------------------------
st.set_page_config(
    page_title="Commodities Dashboard",
    layout="wide",
)

st.title("📈 Commodities Dashboard")
st.caption("Data: Yahoo Finance (via yfinance) • Interactive charts via Plotly")

# -------------------------------------------------------------------
# Tickers
# -------------------------------------------------------------------
COMMODITIES: Dict[str, str] = {
    "Gold (GC=F)": "GC=F",
    "Silver (SI=F)": "SI=F",
    "WTI Crude (CL=F)": "CL=F",
    "Brent Crude (BZ=F)": "BZ=F",
    "Natural Gas (NG=F)": "NG=F",
    "Copper (HG=F)": "HG=F",
    "Corn (ZC=F)": "ZC=F",
    "Wheat (ZW=F)": "ZW=F",
    "Soybeans (ZS=F)": "ZS=F",
    "Coffee (KC=F)": "KC=F",
    "Cocoa (CC=F)": "CC=F",
    "Cotton (CT=F)": "CT=F",
}

PERIOD_MAP = {
    "1M": "1mo",
    "3M": "3mo",
    "6M": "6mo",
    "1Y": "1y",
    "2Y": "2y",
    "5Y": "5y",
}

INTERVAL_MAP = {
    "Daily": "1d",
    "Hourly": "1h",
    "15 min": "15m",
}

# -------------------------------------------------------------------
# Sidebar controls
# -------------------------------------------------------------------
with st.sidebar:
    st.header("Controls")

    label = st.selectbox("Commodity", list(COMMODITIES.keys()), index=0)
    period_ui = st.selectbox("Period", list(PERIOD_MAP.keys()), index=2)
    interval_ui = st.selectbox("Interval", list(INTERVAL_MAP.keys()), index=0)

    show_ohlc = st.toggle("Candlesticks (OHLC)", value=True)
    show_volume = st.toggle("Show Volume", value=False)

ticker = COMMODITIES[label]
period = PERIOD_MAP[period_ui]
interval = INTERVAL_MAP[interval_ui]

# Yahoo limitation: intraday only works for recent windows
if interval in {"15m", "1h"} and period not in {"1mo", "3mo"}:
    st.warning("Intraday intervals only support recent windows on Yahoo. Switching to 3M.")
    period = "3mo"

# -------------------------------------------------------------------
# Data fetching
# -------------------------------------------------------------------
@st.cache_data(ttl=60)
def fetch_history(ticker: str, period: str, interval: str) -> pd.DataFrame:
    try:
        df = yf.download(
            tickers=ticker,
            period=period,
            interval=interval,
            auto_adjust=False,
            actions=False,
            progress=False,
            threads=True,
        )
    except Exception as e:
        out = pd.DataFrame()
        out.attrs["error"] = str(e)
        return out

    if df is None or df.empty:
        return pd.DataFrame()

    return df.dropna(how="all")

with st.spinner(f"Loading {label} ({ticker}) • period={period_ui} • interval={interval_ui}"):
    df = fetch_history(ticker, period, interval)

# -------------------------------------------------------------------
# Metrics
# -------------------------------------------------------------------
def metrics_from_df(df: pd.DataFrame) -> dict:
    if df.empty or "Close" not in df.columns:
        return dict.fromkeys(["last", "chg", "chg_pct", "hi", "lo", "vol"])

    close = df["Close"].dropna()
    if len(close) == 0:
        return dict.fromkeys(["last", "chg", "chg_pct", "hi", "lo", "vol"])

    last = float(close.iloc[-1].item())
    prev = float(close.iloc[-2].item()) if len(close) >= 2 else None

    chg = (last - prev) if prev is not None else None
    chg_pct = (chg / prev * 100.0) if prev not in (None, 0.0) else None

    hi = float(df["High"].max().item()) if "High" in df.columns else None
    lo = float(df["Low"].min().item()) if "Low" in df.columns else None
    vol = (
        float(df["Volume"].iloc[-1].item())
        if "Volume" in df.columns and not df["Volume"].empty
        else None
    )

    return {
        "last": last,
        "chg": chg,
        "chg_pct": chg_pct,
        "hi": hi,
        "lo": lo,
        "vol": vol,
    }

m = metrics_from_df(df)

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Last", "—" if m["last"] is None else f"{m['last']:,.2f}")
c2.metric("Change", "—" if m["chg"] is None else f"{m['chg']:,.2f}")
c3.metric("Change %", "—" if m["chg_pct"] is None else f"{m['chg_pct']:.2f}%")
c4.metric("Period High", "—" if m["hi"] is None else f"{m['hi']:,.2f}")
c5.metric("Period Low", "—" if m["lo"] is None else f"{m['lo']:,.2f}")

st.caption(f"Last refresh: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")

# -------------------------------------------------------------------
# Chart
# -------------------------------------------------------------------
if df.empty:
    err = df.attrs.get("error") if hasattr(df, "attrs") else None
    st.error(
        f"No data returned for {label} ({ticker}).\n\n"
        + (f"Details: {err}" if err else "")
    )
    st.stop()

fig = go.Figure()

if show_ohlc and {"Open", "High", "Low", "Close"}.issubset(df.columns):
    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df["Open"],
            high=df["High"],
            low=df["Low"],
            close=df["Close"],
            name=label,
            increasing_line_color="#26a69a",
            decreasing_line_color="#ef5350",
        )
    )
else:
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df["Close"],
            mode="lines",
            name=label,
            line=dict(color="#42a5f5", width=2),
        )
    )

fig.update_layout(
    height=650,
    margin=dict(l=20, r=20, t=40, b=40),
    template="plotly_dark",
    hovermode="x unified",
    dragmode="zoom",
    xaxis=dict(
        title="Date",
        rangeslider=dict(visible=False),
        showspikes=True,
        spikemode="across",
        spikesnap="cursor",
        tickformat="%b %d",
    ),
    yaxis=dict(
        title="Price",
        side="right",
        showspikes=True,
        spikemode="across",
        spikesnap="cursor",
        tickformat=",.2f",
    ),
)

st.plotly_chart(
    fig,
    width="stretch",
    config={
        "scrollZoom": True,
        "displayModeBar": True,
        "displaylogo": False,
    },
)

# -------------------------------------------------------------------
# Volume + Stats
# -------------------------------------------------------------------
colA, colB = st.columns([1, 1])

with colA:
    if show_volume and "Volume" in df.columns:
        st.subheader("Volume")
        st.bar_chart(df["Volume"].fillna(0))

with colB:
    st.subheader("Stats")

    if "Close" in df.columns and not df["Close"].dropna().empty:
        desc = df["Close"].describe()
        if isinstance(desc, pd.Series):
            stats = desc.to_frame(name="Close")
        else:
            stats = desc
        st.dataframe(stats, width="stretch")
    else:
        st.info("No statistics available for this selection.")