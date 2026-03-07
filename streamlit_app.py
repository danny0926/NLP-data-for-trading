"""
Political Alpha Monitor — Interactive Dashboard (Streamlit)
Congressional Trading Intelligence System

Usage:
    pip install -r requirements_dashboard.txt
    streamlit run streamlit_app.py
"""

import os
import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ── 設定 ──
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "data.db")

# ── 色彩主題 (Dark Premium) ──
COLORS = {
    "primary": "#38bdf8",
    "green": "#4ade80",
    "red": "#f87171",
    "yellow": "#fbbf24",
    "purple": "#a78bfa",
    "orange": "#fb923c",
    "teal": "#2dd4bf",
    "pink": "#f472b6",
    "gold": "#eab308",
    "bg_card": "#1e293b",
}
PLOTLY_COLORS = [
    "#38bdf8", "#4ade80", "#fbbf24", "#a78bfa", "#f87171",
    "#fb923c", "#2dd4bf", "#e879f9", "#818cf8", "#34d399",
]

# ── Plotly Template (dark premium) ──
PLOTLY_TEMPLATE = dict(
    layout=dict(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#e2e8f0", family="Segoe UI, system-ui, sans-serif"),
        xaxis=dict(gridcolor="rgba(148,163,184,0.1)"),
        yaxis=dict(gridcolor="rgba(148,163,184,0.1)"),
        margin=dict(t=30, b=40, l=50, r=20),
    )
)


# ── 資料庫工具 ──
@st.cache_data(ttl=300)
def query_db(sql: str, params: tuple = ()) -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(sql, conn, params=params)
    conn.close()
    return df


def get_table_count(table: str) -> int:
    try:
        df = query_db(f"SELECT COUNT(*) as cnt FROM {table}")
        return int(df.iloc[0]["cnt"])
    except Exception:
        return 0


def get_db_size_mb() -> float:
    try:
        return os.path.getsize(DB_PATH) / (1024 * 1024)
    except Exception:
        return 0.0


def get_last_etl_time() -> str:
    try:
        df = query_db("SELECT MAX(created_at) as last_run FROM extraction_log")
        val = df.iloc[0]["last_run"]
        return str(val) if val else "N/A"
    except Exception:
        return "N/A"


# ── Custom CSS ──
CUSTOM_CSS = """
<style>
/* Dark premium theme */
[data-testid="stAppViewContainer"] {
    background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%);
}
[data-testid="stSidebar"] {
    background: #0f172a;
    border-right: 1px solid #334155;
}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h1 {
    background: linear-gradient(90deg, #38bdf8, #a78bfa);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    font-size: 1.4rem;
}

/* KPI metric cards */
[data-testid="stMetric"] {
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 12px;
    padding: 12px 16px;
    box-shadow: 0 4px 6px -1px rgba(0,0,0,0.3);
}
[data-testid="stMetricValue"] {
    font-weight: 700;
}

/* Hero banner styling */
.hero-banner {
    background: linear-gradient(135deg, #1e293b 0%, #0f172a 50%, #1e1b4b 100%);
    border: 1px solid #334155;
    border-radius: 16px;
    padding: 2rem 2.5rem;
    margin-bottom: 1.5rem;
    box-shadow: 0 8px 32px rgba(0,0,0,0.3);
}
.hero-banner h1 {
    font-size: 2rem;
    background: linear-gradient(90deg, #38bdf8, #a78bfa, #f472b6);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 0.3rem;
}
.hero-banner p {
    color: #94a3b8;
    font-size: 1rem;
    margin: 0;
}
.hero-tagline {
    color: #4ade80;
    font-size: 0.85rem;
    font-weight: 600;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    margin-bottom: 0.5rem;
}

/* Signal badge */
.signal-badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 20px;
    font-size: 0.75rem;
    font-weight: 700;
}
.badge-long { background: rgba(74,222,128,0.15); color: #4ade80; }
.badge-short { background: rgba(248,113,113,0.15); color: #f87171; }
.badge-bullish { background: rgba(74,222,128,0.15); color: #4ade80; }
.badge-bearish { background: rgba(248,113,113,0.15); color: #f87171; }

/* Section divider */
.section-divider {
    border: none;
    border-top: 1px solid #334155;
    margin: 1.5rem 0;
}

/* Footer */
.footer-text {
    text-align: center;
    color: #475569;
    font-size: 0.75rem;
    padding: 2rem 0 1rem 0;
    border-top: 1px solid #1e293b;
}
</style>
"""


# ── 頁面配置 ──
st.set_page_config(
    page_title="PAM | Political Alpha Monitor",
    page_icon="https://raw.githubusercontent.com/danny0926/NLP-data-for-trading/main/docs/favicon.ico",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# ── 側邊欄 ──
def render_sidebar():
    st.sidebar.title("Political Alpha Monitor")
    st.sidebar.caption("Congressional Trading Intelligence")

    page = st.sidebar.radio(
        "Navigation",
        [
            "🎯 Today's Action",
            "Executive Dashboard",
            "Alpha Signals",
            "Portfolio",
            "Politician Ranking",
            "Convergence",
            "Trade Explorer",
            "Signal Quality",
            "Performance",
            "Sector Rotation",
            "Social Intelligence",
        ],
    )

    st.sidebar.markdown("---")
    st.sidebar.subheader("Filters")

    # Date range
    try:
        date_df = query_db(
            "SELECT MIN(transaction_date) as min_d, MAX(transaction_date) as max_d FROM congress_trades WHERE transaction_date IS NOT NULL"
        )
        min_date = pd.to_datetime(date_df.iloc[0]["min_d"], errors="coerce")
        max_date = pd.to_datetime(date_df.iloc[0]["max_d"], errors="coerce")
        if pd.isna(min_date):
            min_date = datetime.now() - timedelta(days=365)
        if pd.isna(max_date):
            max_date = datetime.now()
    except Exception:
        min_date = datetime.now() - timedelta(days=365)
        max_date = datetime.now()

    date_range = st.sidebar.date_input(
        "Date Range",
        value=(min_date.date(), max_date.date()),
        min_value=min_date.date(),
        max_value=max_date.date(),
    )

    chamber_filter = st.sidebar.multiselect(
        "Chamber", ["House", "Senate"], default=["House", "Senate"]
    )

    st.sidebar.markdown("---")
    st.sidebar.subheader("System Status")

    col1, col2 = st.sidebar.columns(2)
    col1.metric("Trades", f"{get_table_count('congress_trades'):,}")
    col2.metric("Signals", f"{get_table_count('alpha_signals'):,}")

    col3, col4 = st.sidebar.columns(2)
    col3.metric("Holdings", get_table_count("portfolio_positions"))
    col4.metric("DB Size", f"{get_db_size_mb():.1f} MB")

    social_count = get_table_count("social_posts")
    st.sidebar.caption(f"Social Posts: {social_count} | Last ETL: {get_last_etl_time()}")

    if st.sidebar.button("Refresh Data"):
        st.cache_data.clear()
        st.rerun()

    st.sidebar.markdown("---")
    st.sidebar.markdown(
        '<div style="text-align:center;color:#475569;font-size:0.7rem;">'
        'PAM v2.3 | Research Use Only<br>Not Investment Advice<br>'
        '<a href="http://localhost:8000/docs" target="_blank" style="color:#38bdf8;">API Docs (Swagger)</a>'
        '</div>',
        unsafe_allow_html=True,
    )

    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = date_range
    else:
        start_date = min_date.date()
        end_date = max_date.date()

    return page, str(start_date), str(end_date), chamber_filter


# ══════════════════════════════════════════════
# Page 1: Executive Dashboard
# ══════════════════════════════════════════════
def page_overview(start_date: str, end_date: str, chambers: List[str]):
    # Hero banner
    st.markdown(
        '<div class="hero-banner">'
        '<div class="hero-tagline">Congressional Trading Intelligence</div>'
        '<h1>Political Alpha Monitor</h1>'
        '<p>AI-powered signal extraction from U.S. congressional trading disclosures, '
        'SEC Form 4 filings, and social media intelligence. '
        'Powered by Gemini 2.5 Flash + Fama-French 3-Factor validation.</p>'
        '</div>',
        unsafe_allow_html=True,
    )

    # KPI cards
    total_trades = get_table_count("congress_trades")
    active_signals = get_table_count("alpha_signals")
    enhanced = get_table_count("enhanced_signals")
    portfolio_pos = get_table_count("portfolio_positions")
    convergence = get_table_count("convergence_signals")
    social_posts = get_table_count("social_posts")

    # Performance stats
    perf_df = query_db("SELECT AVG(hit_5d) as hr5, AVG(actual_alpha_5d) as aa5 FROM signal_performance WHERE hit_5d IS NOT NULL")
    hr5 = perf_df.iloc[0]["hr5"]
    aa5 = perf_df.iloc[0]["aa5"]

    # NSM: weekly signal count
    weekly_df = query_db("SELECT COUNT(*) as cnt FROM alpha_signals WHERE created_at >= date('now', '-7 days')")
    weekly_signals = int(weekly_df.iloc[0]["cnt"]) if not weekly_df.empty else 0

    k1, k2, k3, k4, k5, k6, k7 = st.columns(7)
    k1.metric("Trades Tracked", f"{total_trades:,}")
    k2.metric("Alpha Signals", f"{active_signals:,}")
    k3.metric("Enhanced (PACS)", f"{enhanced:,}")
    k4.metric("Portfolio", f"{portfolio_pos} holdings")
    k5.metric("5d Hit Rate", f"{hr5*100:.0f}%" if hr5 else "N/A")
    k6.metric("Signals/Week", f"{weekly_signals}", help="NSM: Actionable Text Signals per Week")
    k7.metric("Social Intel", f"{social_posts} posts")

    st.markdown("---")

    # Charts row
    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("板塊配置 (Sector Allocation)")
        pos_df = query_db("SELECT sector, SUM(weight) as total_weight FROM portfolio_positions GROUP BY sector ORDER BY total_weight DESC")
        if not pos_df.empty:
            fig = px.pie(
                pos_df, names="sector", values="total_weight",
                color_discrete_sequence=PLOTLY_COLORS,
                hole=0.4,
            )
            fig.update_layout(
                margin=dict(t=20, b=20, l=20, r=20),
                legend=dict(font=dict(size=11)),
                height=350,
            )
            fig.update_traces(textinfo="percent+label", textfont_size=11)
            st.plotly_chart(fig, width="stretch")
        else:
            st.info("尚無持倉資料")

    with col_right:
        st.subheader("訊號強度分布")
        sig_df = query_db("SELECT signal_strength FROM alpha_signals WHERE signal_strength IS NOT NULL")
        if not sig_df.empty:
            fig = px.histogram(
                sig_df, x="signal_strength", nbins=20,
                color_discrete_sequence=[COLORS["primary"]],
                labels={"signal_strength": "訊號強度"},
            )
            fig.update_layout(
                margin=dict(t=20, b=40, l=40, r=20),
                xaxis_title="訊號強度",
                yaxis_title="數量",
                height=350,
            )
            st.plotly_chart(fig, width="stretch")
        else:
            st.info("尚無訊號資料")

    # Top PACS-Enhanced Picks
    st.markdown('<hr class="section-divider">', unsafe_allow_html=True)
    st.subheader("Top PACS-Enhanced Signals")
    top_enhanced = query_db("""
        SELECT e.ticker, e.politician_name, e.chamber, e.direction,
               e.enhanced_strength, e.confidence_v2, e.pacs_score, e.vix_zone,
               e.has_convergence
        FROM enhanced_signals e
        WHERE e.direction = 'LONG'
        ORDER BY e.enhanced_strength DESC
        LIMIT 8
    """)
    if not top_enhanced.empty:
        top_enhanced['convergence'] = top_enhanced['has_convergence'].apply(
            lambda x: 'Yes' if x else ''
        )
        display_cols = top_enhanced[['ticker', 'politician_name', 'chamber', 'enhanced_strength',
                                      'confidence_v2', 'pacs_score', 'vix_zone', 'convergence']].copy()
        display_cols.columns = ['Ticker', 'Politician', 'Chamber', 'Strength', 'Confidence', 'PACS', 'VIX Zone', 'Convergence']
        st.dataframe(display_cols, width="stretch", hide_index=True)
    else:
        st.info("No enhanced signals yet. Run signal enhancer.")

    # Data sources overview
    st.markdown('<hr class="section-divider">', unsafe_allow_html=True)
    st.subheader("Data Sources & Coverage")
    src1, src2, src3, src4 = st.columns(4)
    with src1:
        sec_count = get_table_count("sec_form4_trades")
        st.metric("SEC Form 4 Trades", f"{sec_count:,}")
    with src2:
        contract_count = get_table_count("government_contracts")
        st.metric("Gov Contracts", f"{contract_count:,}")
    with src3:
        ff3_count = get_table_count("fama_french_results")
        st.metric("FF3 Backtests", f"{ff3_count:,}")
    with src4:
        st.metric("Convergence Events", f"{convergence}")

    # Data Freshness
    st.markdown('<hr class="section-divider">', unsafe_allow_html=True)
    st.subheader("Data Freshness")
    fresh_df = query_db("""
        SELECT
            MAX(transaction_date) as latest_trade,
            MAX(filing_date) as latest_filing,
            CAST(julianday('now') - julianday(MAX(filing_date)) AS INTEGER) as days_since_filing,
            CAST(julianday('now') - julianday(MAX(transaction_date)) AS INTEGER) as days_since_trade
        FROM congress_trades
    """)
    if not fresh_df.empty:
        fc1, fc2, fc3, fc4 = st.columns(4)
        latest_trade = fresh_df.iloc[0]["latest_trade"]
        latest_filing = fresh_df.iloc[0]["latest_filing"]
        days_trade = int(fresh_df.iloc[0]["days_since_trade"]) if pd.notna(fresh_df.iloc[0]["days_since_trade"]) else 999
        days_filing = int(fresh_df.iloc[0]["days_since_filing"]) if pd.notna(fresh_df.iloc[0]["days_since_filing"]) else 999
        fc1.metric("Latest Trade", str(latest_trade)[:10] if latest_trade else "N/A")
        fc2.metric("Latest Filing", str(latest_filing)[:10] if latest_filing else "N/A")
        freshness_status = "FRESH" if days_filing <= 7 else ("STALE" if days_filing <= 30 else "OUTDATED")
        freshness_color = "#4ade80" if freshness_status == "FRESH" else ("#fbbf24" if freshness_status == "STALE" else "#f87171")
        fc3.metric("Filing Age", f"{days_filing}d")
        fc4.markdown(
            f'<div style="background:{freshness_color};color:#000;font-weight:700;text-align:center;'
            f'border-radius:8px;padding:0.5rem;margin-top:0.5rem;">{freshness_status}</div>',
            unsafe_allow_html=True,
        )

    # Filing lag distribution
    st.markdown('<hr class="section-divider">', unsafe_allow_html=True)
    st.subheader("Filing Lag 分布 (交易日→申報日)")
    lag_df = query_db("""
        SELECT CAST(julianday(filing_date) - julianday(transaction_date) AS INTEGER) as lag_days
        FROM congress_trades
        WHERE filing_date IS NOT NULL AND transaction_date IS NOT NULL
          AND filing_date > transaction_date
          AND julianday(filing_date) - julianday(transaction_date) <= 120
    """)
    if not lag_df.empty:
        col_lag1, col_lag2, col_lag3 = st.columns(3)
        median_lag = int(lag_df["lag_days"].median())
        mean_lag = lag_df["lag_days"].mean()
        under_45 = (lag_df["lag_days"] <= 45).mean() * 100
        col_lag1.metric("中位數 Lag", f"{median_lag} 天")
        col_lag2.metric("平均 Lag", f"{mean_lag:.0f} 天")
        col_lag3.metric("≤45天 (合規)", f"{under_45:.0f}%")
        fig_lag = px.histogram(
            lag_df, x="lag_days", nbins=50,
            color_discrete_sequence=[COLORS["primary"]],
            labels={"lag_days": "Filing Lag (天)"},
        )
        fig_lag.add_vline(x=45, line_dash="dash", line_color=COLORS["red"],
                          annotation_text="STOCK Act 45天", annotation_position="top right")
        fig_lag.add_vline(x=median_lag, line_dash="dot", line_color=COLORS["green"],
                          annotation_text=f"Median {median_lag}d", annotation_position="top left")
        fig_lag.update_layout(
            height=280, margin=dict(t=30, b=40),
            xaxis_title="Filing Lag (天)", yaxis_title="交易數",
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#e2e8f0"),
            xaxis=dict(gridcolor="rgba(148,163,184,0.1)"),
            yaxis=dict(gridcolor="rgba(148,163,184,0.1)"),
        )
        st.plotly_chart(fig_lag, use_container_width=True)

    # Signal generation timeline
    st.markdown('<hr class="section-divider">', unsafe_allow_html=True)
    st.subheader("Signal Generation Timeline")
    timeline_df = query_db("""
        SELECT date(created_at) as day, COUNT(*) as signals,
               SUM(CASE WHEN direction='LONG' THEN 1 ELSE 0 END) as buy_signals,
               SUM(CASE WHEN direction='SHORT' THEN 1 ELSE 0 END) as sell_signals
        FROM alpha_signals
        WHERE created_at >= date('now', '-30 days')
        GROUP BY date(created_at)
        ORDER BY day
    """)
    if not timeline_df.empty:
        fig_tl = go.Figure()
        fig_tl.add_trace(go.Bar(
            x=timeline_df["day"], y=timeline_df["buy_signals"],
            name="BUY", marker_color=COLORS["green"],
        ))
        fig_tl.add_trace(go.Bar(
            x=timeline_df["day"], y=timeline_df["sell_signals"],
            name="SELL", marker_color=COLORS["red"],
        ))
        fig_tl.update_layout(
            barmode="stack", height=250,
            margin=dict(t=20, b=40, l=40, r=20),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#e2e8f0"),
            xaxis=dict(gridcolor="rgba(148,163,184,0.1)"),
            yaxis=dict(gridcolor="rgba(148,163,184,0.1)", title="Signals"),
            legend=dict(orientation="h", y=1.1),
        )
        st.plotly_chart(fig_tl, width="stretch")
    else:
        st.info("No signals in last 30 days")

    # Recent activity timeline
    st.markdown('<hr class="section-divider">', unsafe_allow_html=True)
    st.subheader("Latest Filings")
    chamber_clause = "AND chamber IN ({})".format(",".join(f"'{c}'" for c in chambers)) if chambers else ""
    recent_df = query_db(f"""
        SELECT politician_name, ticker, transaction_type, amount_range,
               transaction_date, filing_date, chamber
        FROM congress_trades
        WHERE ticker IS NOT NULL AND ticker != ''
          AND transaction_date BETWEEN ? AND ?
          {chamber_clause}
        ORDER BY filing_date DESC
        LIMIT 10
    """, (start_date, end_date))

    if not recent_df.empty:
        st.dataframe(
            recent_df.rename(columns={
                "politician_name": "Politician",
                "ticker": "Ticker",
                "transaction_type": "Type",
                "amount_range": "Amount",
                "transaction_date": "Trade Date",
                "filing_date": "Filed",
                "chamber": "Chamber",
            }),
            width="stretch",
            hide_index=True,
        )
    else:
        st.info("No trades in current date range")

    # Party Breakdown
    party_df = query_db("""
        SELECT party, COUNT(*) as signals,
               AVG(enhanced_strength) as avg_strength,
               AVG(pacs_score) as avg_pacs
        FROM enhanced_signals
        WHERE party != '' AND party IS NOT NULL
        GROUP BY party ORDER BY signals DESC
    """)
    if not party_df.empty:
        st.subheader("黨派信號分布")
        pcol1, pcol2 = st.columns(2)
        with pcol1:
            fig_party = px.pie(
                party_df, names="party", values="signals",
                color="party",
                color_discrete_map={"Republican": "#ef4444", "Democrat": "#3b82f6", "Independent": "#a855f7"},
            )
            fig_party.update_layout(height=250, margin=dict(t=20, b=20))
            st.plotly_chart(fig_party, use_container_width=True)
        with pcol2:
            fig_pbar = px.bar(
                party_df, x="party", y=["avg_strength", "avg_pacs"],
                barmode="group",
                color_discrete_sequence=[COLORS["green"], COLORS["purple"]],
                labels={"value": "Score", "variable": "Metric", "party": "Party"},
            )
            fig_pbar.update_layout(height=250, margin=dict(t=20, b=20),
                                   paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                                   font=dict(color="#e2e8f0"))
            st.plotly_chart(fig_pbar, use_container_width=True)
        st.caption("RB-016: 共和黨短期(5d) alpha 略高 (p=0.02)，但 20d 無顯著差異。")

    # Net Congressional Flow
    flow_df = query_db("""
        SELECT strftime('%Y-W%W', transaction_date) as week,
               SUM(CASE WHEN transaction_type IN ('Purchase','Buy') THEN 1 ELSE 0 END) as buys,
               SUM(CASE WHEN transaction_type IN ('Sale','Sale (Full)','Sale (Partial)','Sell') THEN 1 ELSE 0 END) as sells
        FROM congress_trades
        WHERE transaction_date >= date('now', '-180 days')
        GROUP BY week ORDER BY week
    """)
    if not flow_df.empty:
        st.subheader("國會淨買賣壓力 (Net Flow)")
        flow_df["net"] = flow_df["buys"] - flow_df["sells"]
        flow_df["color"] = flow_df["net"].apply(lambda x: COLORS["green"] if x > 0 else COLORS["red"])
        fig_flow = go.Figure()
        fig_flow.add_trace(go.Bar(
            x=flow_df["week"], y=flow_df["net"],
            marker_color=flow_df["color"].tolist(),
            name="Net Flow",
            hovertemplate="Week: %{x}<br>Net: %{y}<br>Buys: %{customdata[0]}<br>Sells: %{customdata[1]}",
            customdata=flow_df[["buys", "sells"]].values,
        ))
        fig_flow.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
        fig_flow.update_layout(
            height=300, margin=dict(t=20, b=40),
            xaxis_title="Week", yaxis_title="Net Flow (Buys - Sells)",
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#e2e8f0"),
            xaxis=dict(gridcolor="rgba(148,163,184,0.1)"),
            yaxis=dict(gridcolor="rgba(148,163,184,0.1)"),
        )
        st.plotly_chart(fig_flow, use_container_width=True)
        st.caption("正值=淨買入(Bullish)，負值=淨賣出(Bearish)。Unusual Whales 2025 報告顯示國會整體淨賣出 $45M。")

    # Footer
    st.markdown(
        '<div class="footer-text">'
        'Political Alpha Monitor v2.1 | Congressional Trading Intelligence System<br>'
        'Research use only. Not investment advice. Past performance does not guarantee future results.'
        '</div>',
        unsafe_allow_html=True,
    )


# ══════════════════════════════════════════════
# Page 2: Alpha 訊號
# ══════════════════════════════════════════════
def page_alpha_signals(start_date: str, end_date: str, chambers: List[str]):
    st.header("Alpha 訊號")

    # Filters
    fcol1, fcol2, fcol3 = st.columns(3)
    with fcol1:
        direction_filter = st.multiselect("方向", ["LONG", "SHORT"], default=["LONG", "SHORT"])
    with fcol2:
        chamber_sig = st.multiselect("院別 (訊號)", ["House", "Senate"], default=chambers)
    with fcol3:
        min_strength = st.slider("最低訊號強度", 0.0, 1.0, 0.0, 0.05)

    dir_clause = "AND direction IN ({})".format(",".join(f"'{d}'" for d in direction_filter)) if direction_filter else ""
    ch_clause = "AND chamber IN ({})".format(",".join(f"'{c}'" for c in chamber_sig)) if chamber_sig else ""

    signals_df = query_db(f"""
        SELECT ticker, asset_name, politician_name, chamber, direction,
               signal_strength, expected_alpha_5d, expected_alpha_20d,
               confidence, sqs_score, sqs_grade, filing_lag_days, created_at
        FROM alpha_signals
        WHERE signal_strength >= ?
          AND transaction_date BETWEEN ? AND ?
          {dir_clause} {ch_clause}
        ORDER BY signal_strength DESC
    """, (min_strength, start_date, end_date))

    if signals_df.empty:
        st.info("目前篩選條件下無訊號")
        return

    st.caption(f"共 {len(signals_df)} 筆訊號")

    # Add intuitive labels
    signals_df["strength_label"] = signals_df["signal_strength"].apply(
        lambda x: "🔥 Strong" if x >= 1.0 else ("⭐ Moderate" if x >= 0.5 else "📊 Weak")
    )
    signals_df["confidence_label"] = signals_df["confidence"].apply(
        lambda x: "🟢 High" if x >= 0.7 else ("🟡 Medium" if x >= 0.5 else "🔴 Low") if pd.notna(x) else "—"
    )

    display_df = signals_df.rename(columns={
        "ticker": "代碼", "asset_name": "資產名稱", "politician_name": "政治人物",
        "chamber": "院別", "direction": "方向", "signal_strength": "訊號強度",
        "strength_label": "強度", "confidence_label": "信心",
        "expected_alpha_5d": "Alpha 5d%", "expected_alpha_20d": "Alpha 20d%",
        "confidence": "信心度", "sqs_score": "SQS", "sqs_grade": "等級",
        "filing_lag_days": "申報延遲(天)", "created_at": "建立時間",
    })
    st.dataframe(
        display_df[["代碼", "資產名稱", "政治人物", "院別", "方向", "強度", "信心",
                     "訊號強度", "Alpha 5d%", "Alpha 20d%", "等級", "申報延遲(天)"]],
        width="stretch",
        hide_index=True,
        height=400,
    )

    # PACS Distribution + Insider Confirmation + Whale Trades
    enh_df = query_db("SELECT pacs_score, insider_confirmed, whale_trade, ticker, politician_name, enhanced_strength FROM enhanced_signals WHERE pacs_score IS NOT NULL")
    if not enh_df.empty:
        pacs_col1, pacs_col2 = st.columns(2)
        with pacs_col1:
            st.subheader("PACS Score 分布")
            fig_pacs = px.histogram(
                enh_df, x="pacs_score", nbins=30,
                color_discrete_sequence=[COLORS["purple"]],
                labels={"pacs_score": "PACS Score"},
            )
            # Add quartile lines
            q1 = enh_df["pacs_score"].quantile(0.25)
            q3 = enh_df["pacs_score"].quantile(0.75)
            fig_pacs.add_vline(x=q1, line_dash="dot", line_color=COLORS["yellow"],
                              annotation_text=f"Q1={q1:.2f}")
            fig_pacs.add_vline(x=q3, line_dash="dot", line_color=COLORS["green"],
                              annotation_text=f"Q3={q3:.2f}")
            fig_pacs.update_layout(
                height=300, margin=dict(t=30, b=40),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#e2e8f0"),
            )
            st.plotly_chart(fig_pacs, use_container_width=True)
        with pacs_col2:
            insider_count = int(enh_df["insider_confirmed"].sum()) if "insider_confirmed" in enh_df.columns else 0
            total_enh = len(enh_df)
            st.subheader("Insider 確認")
            st.metric("Insider 確認訊號", f"{insider_count} / {total_enh}",
                       help="國會議員 + SEC Form 4 內部人同向交易")
            whale_count = int(enh_df["whale_trade"].sum()) if "whale_trade" in enh_df.columns else 0
            st.metric("Whale Trades ($500K+)", f"{whale_count}",
                       help="RB-015b: $500K+ trades show +0.83~4.4% 20d alpha")
            if insider_count > 0:
                insider_df = enh_df[enh_df["insider_confirmed"] == 1].sort_values("enhanced_strength", ascending=False).head(10)
                st.dataframe(
                    insider_df[["ticker", "politician_name", "pacs_score", "enhanced_strength"]].rename(
                        columns={"ticker": "Ticker", "politician_name": "Politician",
                                 "pacs_score": "PACS", "enhanced_strength": "Strength"}
                    ),
                    hide_index=True, use_container_width=True,
                )

    # Top 10 bar chart
    st.subheader("前 10 強訊號")
    top10 = signals_df.head(10)
    fig = px.bar(
        top10, x="ticker", y="signal_strength",
        color="direction",
        color_discrete_map={"LONG": COLORS["green"], "SHORT": COLORS["red"]},
        text="signal_strength",
        labels={"ticker": "代碼", "signal_strength": "訊號強度", "direction": "方向"},
    )
    fig.update_traces(texttemplate="%{text:.2f}", textposition="outside")
    fig.update_layout(margin=dict(t=30, b=40), height=350)
    st.plotly_chart(fig, width="stretch")


# ══════════════════════════════════════════════
# Page 3: 投資組合
# ══════════════════════════════════════════════
def page_portfolio():
    st.header("投資組合")

    pos_df = query_db("SELECT * FROM portfolio_positions ORDER BY weight DESC")
    if pos_df.empty:
        st.info("尚無持倉資料")
        return

    # Summary
    total_alpha = pos_df["expected_alpha"].sum()
    avg_sharpe = pos_df["sharpe_estimate"].mean()
    total_positions = len(pos_df)

    k1, k2, k3 = st.columns(3)
    k1.metric("持倉數量", total_positions)
    k2.metric("總預期 Alpha", f"{total_alpha:.4f}")
    k3.metric("平均 Sharpe", f"{avg_sharpe:.2f}")

    st.markdown("---")

    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("板塊配置")
        sector_df = pos_df.groupby("sector")["weight"].sum().reset_index()
        fig = px.pie(
            sector_df, names="sector", values="weight",
            color_discrete_sequence=PLOTLY_COLORS,
            hole=0.4,
        )
        fig.update_layout(margin=dict(t=20, b=20), height=350)
        fig.update_traces(textinfo="percent+label", textfont_size=11)
        st.plotly_chart(fig, width="stretch")

    with col_right:
        st.subheader("持倉權重")
        fig = px.bar(
            pos_df.head(15), x="ticker", y="weight",
            color="sector",
            color_discrete_sequence=PLOTLY_COLORS,
            labels={"ticker": "代碼", "weight": "權重", "sector": "板塊"},
            text=pos_df.head(15)["weight"].apply(lambda x: f"{x:.2%}"),
        )
        fig.update_traces(textposition="outside")
        fig.update_layout(margin=dict(t=20, b=40), height=350)
        st.plotly_chart(fig, width="stretch")

    # Conviction vs Expected Alpha scatter
    st.subheader("信念分數 vs 預期 Alpha")
    fig_conv = px.scatter(
        pos_df, x="conviction_score", y="expected_alpha",
        size="weight", color="sector", hover_data=["ticker"],
        labels={"conviction_score": "信念分數", "expected_alpha": "預期 Alpha", "sector": "板塊"},
        color_discrete_sequence=PLOTLY_COLORS,
    )
    fig_conv.update_layout(
        height=350, margin=dict(t=20, b=40),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#e2e8f0"),
    )
    st.plotly_chart(fig_conv, use_container_width=True)

    # Rebalance history summary
    rebal_df = query_db("SELECT action, COUNT(*) as cnt FROM rebalance_history GROUP BY action ORDER BY cnt DESC")
    if not rebal_df.empty:
        st.subheader("最新再平衡建議")
        rb1, rb2 = st.columns(2)
        with rb1:
            for _, row in rebal_df.iterrows():
                icon = {"BUY": "🟢", "SELL": "🔴", "INCREASE": "📈", "DECREASE": "📉", "HOLD": "⚪"}.get(row["action"], "•")
                st.metric(f"{icon} {row['action']}", int(row["cnt"]))
        with rb2:
            fig_rb = px.pie(rebal_df, names="action", values="cnt",
                           color="action",
                           color_discrete_map={"BUY": COLORS["green"], "SELL": COLORS["red"],
                                               "INCREASE": COLORS["primary"], "DECREASE": COLORS["orange"],
                                               "HOLD": "#475569"})
            fig_rb.update_layout(height=250, margin=dict(t=20, b=20))
            st.plotly_chart(fig_rb, use_container_width=True)

    # Positions table with intuitive ratings
    st.subheader("所有持倉")
    display_pos = pos_df[["ticker", "sector", "weight", "conviction_score",
                           "expected_alpha", "volatility_30d", "sharpe_estimate"]].copy()
    display_pos["rating"] = display_pos["conviction_score"].apply(
        lambda x: "⭐⭐⭐" if x >= 70 else ("⭐⭐" if x >= 55 else "⭐")
    )
    display_pos["weight"] = display_pos["weight"].apply(lambda x: f"{x:.2%}" if pd.notna(x) else "-")
    display_pos["expected_alpha"] = display_pos["expected_alpha"].apply(lambda x: f"{x:.4f}" if pd.notna(x) else "-")
    display_pos["volatility_30d"] = display_pos["volatility_30d"].apply(lambda x: f"{x:.2%}" if pd.notna(x) else "-")
    display_pos.rename(columns={
        "ticker": "代碼", "sector": "板塊", "weight": "權重", "rating": "評級",
        "conviction_score": "信念分數", "expected_alpha": "預期 Alpha",
        "volatility_30d": "30日波動率", "sharpe_estimate": "Sharpe",
    }, inplace=True)
    st.dataframe(display_pos[["代碼", "評級", "板塊", "權重", "信念分數", "預期 Alpha", "30日波動率", "Sharpe"]],
                 width="stretch", hide_index=True)


# ══════════════════════════════════════════════
# Page 4: 政治人物排名
# ══════════════════════════════════════════════
def page_politicians(start_date: str, end_date: str, chambers: List[str]):
    st.header("政治人物排名 (PIS)")

    rank_df = query_db("SELECT * FROM politician_rankings ORDER BY pis_total DESC")
    if rank_df.empty:
        st.info("尚無排名資料")
        return

    # Grade distribution
    def pis_grade(score):
        if score >= 50:
            return "Gold"
        elif score >= 40:
            return "Silver"
        elif score >= 30:
            return "Bronze"
        return "Discard"

    rank_df["grade"] = rank_df["pis_total"].apply(pis_grade)

    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("等級分布")
        grade_counts = rank_df["grade"].value_counts().reset_index()
        grade_counts.columns = ["grade", "count"]
        fig = px.pie(
            grade_counts, names="grade", values="count",
            color="grade",
            color_discrete_map={
                "Gold": COLORS["yellow"], "Silver": "#94a3b8",
                "Bronze": COLORS["orange"], "Discard": "#475569",
            },
        )
        fig.update_layout(margin=dict(t=20, b=20), height=300)
        st.plotly_chart(fig, width="stretch")

    with col_right:
        st.subheader("院別比較")
        chamber_avg = rank_df.groupby("chamber")["pis_total"].mean().reset_index()
        fig = px.bar(
            chamber_avg, x="chamber", y="pis_total",
            color="chamber",
            color_discrete_map={"House": COLORS["primary"], "Senate": COLORS["purple"]},
            labels={"chamber": "院別", "pis_total": "平均 PIS"},
            text="pis_total",
        )
        fig.update_traces(texttemplate="%{text:.1f}", textposition="outside")
        fig.update_layout(margin=dict(t=20, b=40), height=300, showlegend=False)
        st.plotly_chart(fig, width="stretch")

    # Top 10 Leaderboard with trade activity
    st.subheader("Top 10 政治人物 — 交易活躍度")
    top10 = rank_df.head(10)
    top10_names = top10["politician_name"].tolist()
    if top10_names:
        placeholders = ",".join("?" for _ in top10_names)
        monthly_df = query_db(f"""
            SELECT politician_name,
                   strftime('%Y-%m', transaction_date) as month,
                   COUNT(*) as trades
            FROM congress_trades
            WHERE politician_name IN ({placeholders})
              AND transaction_date >= date('now', '-12 months')
            GROUP BY politician_name, month
            ORDER BY month
        """, tuple(top10_names))

        if not monthly_df.empty:
            fig_lb = go.Figure()
            for name in top10_names:
                person = monthly_df[monthly_df["politician_name"] == name]
                if not person.empty:
                    pis = float(top10[top10["politician_name"] == name]["pis_total"].iloc[0])
                    fig_lb.add_trace(go.Bar(
                        x=person["month"], y=person["trades"],
                        name=f"{name} ({pis:.0f})",
                    ))
            fig_lb.update_layout(
                barmode="group", height=400, margin=dict(t=30, b=40),
                xaxis_title="Month", yaxis_title="Trades",
                legend=dict(font=dict(size=9), orientation="h", yanchor="bottom", y=1.02),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#e2e8f0"),
                xaxis=dict(gridcolor="rgba(148,163,184,0.1)"),
                yaxis=dict(gridcolor="rgba(148,163,184,0.1)"),
            )
            st.plotly_chart(fig_lb, use_container_width=True)

    # Rankings table
    st.subheader("完整排名")
    display_rank = rank_df[["rank", "politician_name", "chamber", "total_trades",
                             "pis_activity", "pis_conviction", "pis_diversification",
                             "pis_timing", "pis_total", "grade"]].copy()
    display_rank.rename(columns={
        "rank": "排名", "politician_name": "政治人物", "chamber": "院別",
        "total_trades": "交易數", "pis_activity": "活躍度", "pis_conviction": "信念",
        "pis_diversification": "分散度", "pis_timing": "時機", "pis_total": "PIS 總分",
        "grade": "等級",
    }, inplace=True)
    st.dataframe(display_rank, width="stretch", hide_index=True)

    # Drill-down
    st.markdown("---")
    st.subheader("政治人物交易明細")
    selected = st.selectbox(
        "選擇政治人物",
        rank_df["politician_name"].tolist(),
    )

    if selected:
        ch_clause = "AND chamber IN ({})".format(",".join(f"'{c}'" for c in chambers)) if chambers else ""
        trades_df = query_db(f"""
            SELECT ticker, transaction_type, amount_range, transaction_date,
                   filing_date, chamber, asset_name
            FROM congress_trades
            WHERE politician_name = ?
              AND transaction_date BETWEEN ? AND ?
              {ch_clause}
            ORDER BY transaction_date DESC
        """, (selected, start_date, end_date))

        if not trades_df.empty:
            st.caption(f"{selected} 共 {len(trades_df)} 筆交易")
            trades_df.rename(columns={
                "ticker": "代碼", "transaction_type": "類型", "amount_range": "金額範圍",
                "transaction_date": "交易日", "filing_date": "申報日",
                "chamber": "院別", "asset_name": "資產名稱",
            }, inplace=True)
            st.dataframe(trades_df, width="stretch", hide_index=True)
        else:
            st.info(f"{selected} 在目前日期範圍內無交易記錄")


# ══════════════════════════════════════════════
# Page 5: 匯聚訊號
# ══════════════════════════════════════════════
def page_convergence():
    st.header("匯聚訊號 (Convergence)")

    conv_df = query_db("SELECT * FROM convergence_signals ORDER BY score DESC")
    if conv_df.empty:
        st.info("尚無匯聚訊號")
        return

    st.caption(f"共 {len(conv_df)} 筆匯聚事件")

    # Add intuitive labels
    conv_df["strength_label"] = conv_df["score"].apply(
        lambda x: "🔥 Very Strong" if x >= 2.0 else ("⭐ Strong" if x >= 1.5 else "📊 Moderate")
    )
    conv_df["cross_chamber"] = conv_df["chambers"].apply(
        lambda x: "🏛 Cross-chamber" if pd.notna(x) and "Senate" in str(x) and "House" in str(x) else ""
    )

    # Highlight strongest
    top = conv_df.iloc[0]
    direction_icon = "🟢" if top['direction'] == 'Buy' else "🔴"
    st.success(
        f"最強匯聚: **{top['ticker']}** {direction_icon} {top['direction']} | "
        f"{conv_df.iloc[0]['strength_label']} (分數 {top['score']:.2f}) | "
        f"{top['politician_count']} 位政治人物同向交易 {conv_df.iloc[0]['cross_chamber']}"
    )

    # Table with intuitive labels
    display_conv = conv_df[["ticker", "direction", "strength_label", "cross_chamber",
                             "politician_count", "politicians",
                             "score", "span_days", "detected_at"]].copy()
    display_conv.rename(columns={
        "ticker": "代碼", "direction": "方向", "strength_label": "強度",
        "cross_chamber": "跨院", "politician_count": "人數",
        "politicians": "涉及政治人物",
        "score": "匯聚分數", "span_days": "天數",
        "detected_at": "偵測時間",
    }, inplace=True)
    st.dataframe(display_conv, width="stretch", hide_index=True)

    # Score breakdown
    st.subheader("分數拆解")
    score_cols = ["ticker", "score", "score_base", "score_cross_chamber",
                  "score_time_density", "score_amount_weight"]
    score_df = conv_df[score_cols].copy()
    score_df.rename(columns={
        "ticker": "代碼", "score": "總分", "score_base": "基礎分",
        "score_cross_chamber": "跨院加分", "score_time_density": "時間密度",
        "score_amount_weight": "金額權重",
    }, inplace=True)
    st.dataframe(score_df, width="stretch", hide_index=True)

    # Timeline
    st.subheader("匯聚時間線")
    if "detected_at" in conv_df.columns:
        conv_df["detected_at_dt"] = pd.to_datetime(conv_df["detected_at"], errors="coerce")
        fig = px.scatter(
            conv_df, x="detected_at_dt", y="score",
            size="politician_count", color="ticker",
            hover_data=["politicians", "direction"],
            labels={"detected_at_dt": "偵測時間", "score": "匯聚分數", "ticker": "代碼"},
            color_discrete_sequence=PLOTLY_COLORS,
        )
        fig.update_layout(margin=dict(t=20, b=40), height=350)
        st.plotly_chart(fig, width="stretch")


# ══════════════════════════════════════════════
# Page 6: 交易瀏覽器
# ══════════════════════════════════════════════
def page_trade_explorer(start_date: str, end_date: str, chambers: List[str]):
    st.header("交易瀏覽器")

    # Filters
    fcol1, fcol2, fcol3, fcol4 = st.columns(4)

    with fcol1:
        explorer_chambers = st.multiselect("院別 (瀏覽)", ["House", "Senate"], default=chambers, key="explorer_chamber")
    with fcol2:
        tx_types = query_db("SELECT DISTINCT transaction_type FROM congress_trades WHERE transaction_type IS NOT NULL")
        all_types = tx_types["transaction_type"].tolist() if not tx_types.empty else []
        selected_types = st.multiselect("交易類型", all_types, default=all_types)
    with fcol3:
        amounts = query_db("SELECT DISTINCT amount_range FROM congress_trades WHERE amount_range IS NOT NULL ORDER BY amount_range")
        all_amounts = amounts["amount_range"].tolist() if not amounts.empty else []
        selected_amounts = st.multiselect("金額範圍", all_amounts, default=[])
    with fcol4:
        ticker_search = st.text_input("搜尋代碼", "")

    # Build query
    conditions = ["1=1"]
    params = []

    conditions.append("transaction_date BETWEEN ? AND ?")
    params.extend([start_date, end_date])

    if explorer_chambers:
        placeholders = ",".join("?" * len(explorer_chambers))
        conditions.append(f"chamber IN ({placeholders})")
        params.extend(explorer_chambers)

    if selected_types:
        placeholders = ",".join("?" * len(selected_types))
        conditions.append(f"transaction_type IN ({placeholders})")
        params.extend(selected_types)

    if selected_amounts:
        placeholders = ",".join("?" * len(selected_amounts))
        conditions.append(f"amount_range IN ({placeholders})")
        params.extend(selected_amounts)

    if ticker_search.strip():
        conditions.append("ticker LIKE ?")
        params.append(f"%{ticker_search.strip().upper()}%")

    where = " AND ".join(conditions)

    trades_df = query_db(f"""
        SELECT politician_name, ticker, asset_name, transaction_type,
               amount_range, transaction_date, filing_date, chamber
        FROM congress_trades
        WHERE {where}
        ORDER BY filing_date DESC
    """, tuple(params))

    st.caption(f"共 {len(trades_df)} 筆交易")

    if not trades_df.empty:
        # Filing lag calculation
        trades_df["transaction_date_dt"] = pd.to_datetime(trades_df["transaction_date"], errors="coerce")
        trades_df["filing_date_dt"] = pd.to_datetime(trades_df["filing_date"], errors="coerce")
        trades_df["filing_lag"] = (trades_df["filing_date_dt"] - trades_df["transaction_date_dt"]).dt.days

        display_trades = trades_df[["politician_name", "ticker", "asset_name",
                                     "transaction_type", "amount_range",
                                     "transaction_date", "filing_date",
                                     "chamber", "filing_lag"]].copy()
        display_trades.rename(columns={
            "politician_name": "政治人物", "ticker": "代碼", "asset_name": "資產名稱",
            "transaction_type": "類型", "amount_range": "金額範圍",
            "transaction_date": "交易日", "filing_date": "申報日",
            "chamber": "院別", "filing_lag": "申報延遲(天)",
        }, inplace=True)
        st.dataframe(display_trades, width="stretch", hide_index=True, height=500)

        # Filing lag distribution
        st.subheader("申報延遲分布")
        lag_data = trades_df["filing_lag"].dropna()
        if not lag_data.empty:
            fig = px.histogram(
                lag_data, nbins=30,
                color_discrete_sequence=[COLORS["primary"]],
                labels={"value": "申報延遲 (天)", "count": "數量"},
            )
            fig.update_layout(
                margin=dict(t=20, b=40),
                xaxis_title="申報延遲 (天)",
                yaxis_title="數量",
                height=300,
            )
            st.plotly_chart(fig, width="stretch")

        # Monthly trading activity heatmap
        st.subheader("交易活動熱力圖")
        trades_df["month"] = trades_df["transaction_date_dt"].dt.strftime("%Y-%m")
        trades_df["weekday"] = trades_df["transaction_date_dt"].dt.day_name()
        weekday_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
        hm_df = trades_df[trades_df["weekday"].isin(weekday_order)].copy()
        if not hm_df.empty:
            heatmap = hm_df.groupby(["weekday", "month"]).size().reset_index(name="count")
            heatmap_pivot = heatmap.pivot(index="weekday", columns="month", values="count").fillna(0)
            heatmap_pivot = heatmap_pivot.reindex(weekday_order)
            fig_hm = go.Figure(data=go.Heatmap(
                z=heatmap_pivot.values,
                x=heatmap_pivot.columns.tolist(),
                y=heatmap_pivot.index.tolist(),
                colorscale="Blues",
                hovertemplate="Day: %{y}<br>Month: %{x}<br>Trades: %{z}<extra></extra>",
            ))
            fig_hm.update_layout(
                height=280, margin=dict(t=30, b=40),
                xaxis_title="Month", yaxis_title="Day of Week",
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#e2e8f0"),
            )
            st.plotly_chart(fig_hm, use_container_width=True)
    else:
        st.info("目前篩選條件下無交易資料")


# ══════════════════════════════════════════════
# Page 7: 訊號品質分析
# ══════════════════════════════════════════════
def page_signal_quality():
    st.header("訊號品質分析 (SQS)")

    sqs_df = query_db("SELECT * FROM signal_quality_scores ORDER BY sqs DESC")
    if sqs_df.empty:
        st.info("尚無品質評分資料")
        return

    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("SQS 分數分布")
        fig = px.histogram(
            sqs_df, x="sqs", nbins=20,
            color_discrete_sequence=[COLORS["primary"]],
            labels={"sqs": "SQS 分數"},
        )
        fig.update_layout(
            margin=dict(t=20, b=40),
            xaxis_title="SQS 分數",
            yaxis_title="數量",
            height=350,
        )
        st.plotly_chart(fig, width="stretch")

    with col_right:
        st.subheader("等級分布")
        grade_counts = sqs_df["grade"].value_counts().reset_index()
        grade_counts.columns = ["grade", "count"]
        fig = px.pie(
            grade_counts, names="grade", values="count",
            color="grade",
            color_discrete_map={
                "Gold": COLORS["yellow"], "Silver": "#94a3b8",
                "Bronze": COLORS["orange"], "Discard": "#475569",
            },
        )
        fig.update_layout(margin=dict(t=20, b=20), height=350)
        st.plotly_chart(fig, width="stretch")

    # Radar chart for selected trade
    st.markdown("---")
    st.subheader("五維雷達圖")

    # Build selection list: ticker + politician
    sqs_df["label"] = sqs_df["ticker"].fillna("?") + " — " + sqs_df["politician_name"].fillna("?")
    selected_label = st.selectbox("選擇交易", sqs_df["label"].tolist())

    if selected_label:
        row = sqs_df[sqs_df["label"] == selected_label].iloc[0]

        categories = ["可操作性", "時效性", "信念度", "資訊優勢", "市場影響"]
        values = [
            row["actionability"],
            row["timeliness"],
            row["conviction"],
            row["information_edge"],
            row["market_impact"],
        ]
        # Close the radar
        categories_closed = categories + [categories[0]]
        values_closed = values + [values[0]]

        fig = go.Figure(data=go.Scatterpolar(
            r=values_closed,
            theta=categories_closed,
            fill="toself",
            fillcolor="rgba(56, 189, 248, 0.2)",
            line=dict(color=COLORS["primary"]),
        ))
        fig.update_layout(
            polar=dict(
                radialaxis=dict(visible=True, range=[0, 100]),
            ),
            margin=dict(t=40, b=40, l=60, r=60),
            height=400,
            title=f"{row['ticker']} — {row['politician_name']} (SQS: {row['sqs']:.1f}, {row['grade']})",
        )
        st.plotly_chart(fig, width="stretch")

    # SQS vs Actual Performance correlation (if signal_performance data exists)
    sqs_perf = query_db("""
        SELECT s.sqs, s.grade, sp.hit_5d, sp.actual_alpha_5d
        FROM signal_quality_scores s
        JOIN alpha_signals a ON s.trade_id = a.trade_id
        JOIN signal_performance sp ON sp.signal_id = a.id
        WHERE sp.hit_5d IS NOT NULL AND s.sqs IS NOT NULL
    """)
    if not sqs_perf.empty and len(sqs_perf) >= 10:
        st.subheader("SQS vs 實際表現 (驗證)")
        st.caption("RB-006 發現: SQS conviction 與實際 alpha 呈負相關 (r=-0.50)")
        fig_sqs_perf = px.scatter(
            sqs_perf, x="sqs", y="actual_alpha_5d",
            color="grade",
            color_discrete_map={"Gold": COLORS["yellow"], "Silver": "#94a3b8",
                                "Bronze": COLORS["orange"], "Discard": "#475569"},
            labels={"sqs": "SQS Score", "actual_alpha_5d": "Actual Alpha 5d (%)"},
            trendline="ols",
        )
        fig_sqs_perf.update_layout(
            height=350, margin=dict(t=20, b=40),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#e2e8f0"),
        )
        st.plotly_chart(fig_sqs_perf, use_container_width=True)

    # Top quality signals table
    st.subheader("最高品質訊號")
    top_sqs = sqs_df.head(20)[["ticker", "politician_name", "sqs", "grade",
                                 "actionability", "timeliness", "conviction",
                                 "information_edge", "market_impact"]].copy()
    top_sqs.rename(columns={
        "ticker": "代碼", "politician_name": "政治人物", "sqs": "SQS",
        "grade": "等級", "actionability": "可操作性", "timeliness": "時效性",
        "conviction": "信念度", "information_edge": "資訊優勢",
        "market_impact": "市場影響",
    }, inplace=True)
    st.dataframe(top_sqs, width="stretch", hide_index=True)


# ══════════════════════════════════════════════
# Page 8: 訊號績效追蹤
# ══════════════════════════════════════════════
def page_signal_performance():
    st.header("訊號績效追蹤")
    st.caption("追蹤已生成訊號的實際市場表現，驗證系統有效性")

    perf_df = query_db("""
        SELECT sp.*, a.politician_name, a.chamber
        FROM signal_performance sp
        LEFT JOIN alpha_signals a ON sp.signal_id = a.id
        ORDER BY sp.evaluated_at DESC
    """)

    if perf_df.empty:
        st.warning("尚無績效追蹤資料。請先執行 `python -m src.signal_tracker`。")
        return

    # KPI cards
    col1, col2, col3, col4 = st.columns(4)

    has_5d = perf_df["hit_5d"].notna()
    has_20d = perf_df["hit_20d"].notna()

    n_5d = int(has_5d.sum())
    n_20d = int(has_20d.sum())

    if n_5d > 0:
        hr_5d = perf_df.loc[has_5d, "hit_5d"].mean() * 100
        avg_alpha_5d = perf_df.loc[has_5d, "actual_alpha_5d"].mean()
        col1.metric("5 日勝率", f"{hr_5d:.1f}%", help=f"基於 {n_5d} 個樣本")
        col2.metric("5 日平均 Alpha", f"{avg_alpha_5d:+.2f}%", help=f"n={n_5d}")
    else:
        col1.metric("5 日勝率", "N/A")
        col2.metric("5 日平均 Alpha", "N/A")

    if n_20d > 0:
        hr_20d = perf_df.loc[has_20d, "hit_20d"].mean() * 100
        avg_alpha_20d = perf_df.loc[has_20d, "actual_alpha_20d"].mean()
        col3.metric("20 日勝率", f"{hr_20d:.1f}%", help=f"基於 {n_20d} 個樣本")
        col4.metric("20 日平均 Alpha", f"{avg_alpha_20d:+.2f}%", help=f"n={n_20d}")
    else:
        col3.metric("20 日勝率", "N/A")
        col4.metric("20 日平均 Alpha", "N/A")

    col5, col6 = st.columns(2)
    col5.metric("已評估訊號", f"{len(perf_df)}")
    with_returns = (perf_df["actual_alpha_5d"].notna() | perf_df["actual_alpha_20d"].notna()).sum()
    col6.metric("有實際報酬", f"{with_returns}")

    # Statistical significance warning
    min_samples = 200
    if n_5d > 0 and n_5d < min_samples:
        ci = 1.96 * (50 / (n_5d ** 0.5))
        st.warning(
            f"⚠ **Statistical Warning**: 5-day hit rate is based on only **{n_5d} samples** "
            f"(minimum {min_samples} needed for significance). "
            f"A {hr_5d:.0f}% hit rate with n={n_5d} has a 95% CI of approximately "
            f"±{ci:.0f}% — interpret with caution."
        )
    elif n_5d >= min_samples:
        ci = 1.96 * (50 / (n_5d ** 0.5))
        st.info(
            f"**{n_5d} samples evaluated** — 95% CI: {hr_5d:.0f}% ± {ci:.0f}%. "
            f"{'Statistically significant edge detected.' if hr_5d > 50 + ci else 'Edge not yet statistically significant.'}"
        )
    elif n_5d == 0:
        st.warning(
            f"⚠ No samples with actual returns yet. "
            f"Minimum {min_samples} samples needed."
        )

    # Cumulative Alpha Chart
    cum_df = perf_df[perf_df["actual_alpha_5d"].notna()].sort_values("signal_date").copy()
    if not cum_df.empty and "signal_date" in cum_df.columns:
        st.subheader("累積 Alpha 曲線 (5 日)")
        cum_df["cum_alpha"] = cum_df["actual_alpha_5d"].cumsum()
        cum_df["signal_num"] = range(1, len(cum_df) + 1)
        fig_cum = go.Figure()
        fig_cum.add_trace(go.Scatter(
            x=cum_df["signal_num"], y=cum_df["cum_alpha"],
            mode="lines+markers", name="Cumulative Alpha",
            line=dict(color=COLORS["primary"], width=2),
            marker=dict(size=5),
        ))
        fig_cum.add_hline(y=0, line_dash="dash", line_color="gray")
        fig_cum.update_layout(
            height=350, margin=dict(t=30, b=40),
            xaxis_title="Signal #", yaxis_title="Cumulative Alpha (%)",
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#e2e8f0"),
            xaxis=dict(gridcolor="rgba(148,163,184,0.1)"),
            yaxis=dict(gridcolor="rgba(148,163,184,0.1)"),
        )
        st.plotly_chart(fig_cum, width="stretch")

    # Cumulative Return vs SPY (time-series, date-averaged)
    cum_ts = perf_df[perf_df["actual_alpha_5d"].notna() & perf_df["signal_date"].notna()].copy()
    if not cum_ts.empty:
        st.subheader("Cumulative Return vs SPY")
        st.caption("Equal-weight daily average: signals on the same date are averaged, then cumulated over time.")

        # Group by date to avoid double-counting SPY on multi-signal days
        daily = cum_ts.groupby("signal_date").agg(
            avg_stock=("actual_return_5d", "mean"),
            avg_spy=("spy_return_5d", "mean"),
            avg_alpha=("actual_alpha_5d", "mean"),
            n_signals=("ticker", "count"),
        ).reset_index().sort_values("signal_date")

        daily["cum_stock"] = daily["avg_stock"].cumsum()
        daily["cum_spy"] = daily["avg_spy"].cumsum()
        daily["cum_alpha"] = daily["avg_alpha"].cumsum()

        fig_vs = go.Figure()
        fig_vs.add_trace(go.Scatter(
            x=daily["signal_date"], y=daily["cum_stock"],
            mode="lines+markers", name="PAM Signals (avg/day)",
            line=dict(color=COLORS["green"], width=2.5),
            marker=dict(size=4),
            hovertemplate="%{x}<br>Cum Return: %{y:.1f}%<extra>PAM</extra>",
        ))
        fig_vs.add_trace(go.Scatter(
            x=daily["signal_date"], y=daily["cum_spy"],
            mode="lines+markers", name="SPY (Benchmark)",
            line=dict(color=COLORS["red"], width=2, dash="dash"),
            marker=dict(size=4),
            hovertemplate="%{x}<br>Cum Return: %{y:.1f}%<extra>SPY</extra>",
        ))
        fig_vs.add_trace(go.Scatter(
            x=daily["signal_date"], y=daily["cum_alpha"],
            mode="lines", name="Alpha (PAM - SPY)",
            line=dict(color=COLORS["primary"], width=1.5, dash="dot"),
            fill="tozeroy", fillcolor="rgba(56,189,248,0.08)",
            hovertemplate="%{x}<br>Cum Alpha: %{y:.1f}%<extra>Alpha</extra>",
        ))
        fig_vs.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.3)
        fig_vs.update_layout(
            height=420, margin=dict(t=30, b=40),
            xaxis_title="Signal Date", yaxis_title="Cumulative Return (%)",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#e2e8f0"),
            xaxis=dict(gridcolor="rgba(148,163,184,0.1)"),
            yaxis=dict(gridcolor="rgba(148,163,184,0.1)"),
        )
        st.plotly_chart(fig_vs, use_container_width=True)

        # Summary metrics
        final_stock = daily["cum_stock"].iloc[-1]
        final_spy = daily["cum_spy"].iloc[-1]
        final_alpha = daily["cum_alpha"].iloc[-1]
        total_signals = int(daily["n_signals"].sum())
        n_days = len(daily)
        date_range = f'{daily["signal_date"].iloc[0]} to {daily["signal_date"].iloc[-1]}'

        mc1, mc2, mc3, mc4 = st.columns(4)
        mc1.metric("PAM Cumulative", f"{final_stock:+.1f}%")
        mc2.metric("SPY Cumulative", f"{final_spy:+.1f}%")
        mc3.metric("Total Alpha", f"{final_alpha:+.1f}%",
                    delta="Outperforming" if final_alpha > 0 else "Underperforming",
                    delta_color="normal" if final_alpha > 0 else "inverse")
        mc4.metric("Signal Days", f"{n_days}", help=f"{total_signals} signals over {date_range}")

    # Hit rate by signal strength tier
    tier_df = perf_df[perf_df["hit_5d"].notna()].copy()
    if not tier_df.empty and "signal_strength" in tier_df.columns:
        st.subheader("勝率 by 信號強度 (5 日)")
        tier_df["tier"] = tier_df["signal_strength"].apply(
            lambda x: "Strong (>=1.0)" if x >= 1.0 else ("Moderate (0.5-1.0)" if x >= 0.5 else "Weak (<0.5)")
        )
        tier_stats = tier_df.groupby("tier").agg(
            n=("hit_5d", "count"),
            hit_rate=("hit_5d", "mean"),
            avg_alpha=("actual_alpha_5d", "mean"),
        ).reset_index()
        tier_stats["hit_rate_pct"] = (tier_stats["hit_rate"] * 100).round(1)
        tier_stats["avg_alpha_pct"] = tier_stats["avg_alpha"].round(2)

        fig_tier = go.Figure()
        colors = {"Strong (>=1.0)": COLORS["green"], "Moderate (0.5-1.0)": COLORS["yellow"], "Weak (<0.5)": COLORS["red"]}
        for _, row in tier_stats.iterrows():
            fig_tier.add_trace(go.Bar(
                x=[row["tier"]], y=[row["hit_rate_pct"]],
                name=f'{row["tier"]} (n={row["n"]})',
                marker_color=colors.get(row["tier"], COLORS["primary"]),
                text=f'{row["hit_rate_pct"]:.0f}%<br>n={row["n"]}',
                textposition="outside",
            ))
        fig_tier.add_hline(y=50, line_dash="dash", line_color="gray", annotation_text="50% baseline")
        fig_tier.update_layout(
            height=300, margin=dict(t=30, b=40),
            yaxis_title="Hit Rate (%)", showlegend=False,
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#e2e8f0"),
            xaxis=dict(gridcolor="rgba(148,163,184,0.1)"),
            yaxis=dict(gridcolor="rgba(148,163,184,0.1)", range=[0, 100]),
        )
        st.plotly_chart(fig_tier, width="stretch")

    # Amount Range Performance
    amt_perf = query_db("""
        SELECT ct.amount_range, COUNT(*) as n,
               AVG(sp.hit_5d) as hit_rate,
               AVG(sp.actual_alpha_5d) as avg_alpha
        FROM signal_performance sp
        JOIN alpha_signals a ON sp.signal_id = a.id
        JOIN congress_trades ct ON a.trade_id = ct.id
        WHERE sp.hit_5d IS NOT NULL AND ct.amount_range IS NOT NULL
        GROUP BY ct.amount_range
        HAVING COUNT(*) >= 3
        ORDER BY AVG(sp.hit_5d) DESC
    """)
    if not amt_perf.empty:
        st.subheader("金額範圍 vs 績效")
        ac1, ac2 = st.columns(2)
        with ac1:
            fig_amt = go.Figure()
            fig_amt.add_trace(go.Bar(
                x=amt_perf["amount_range"], y=amt_perf["hit_rate"] * 100,
                text=[f'{r*100:.0f}%<br>n={n}' for r, n in zip(amt_perf["hit_rate"], amt_perf["n"])],
                textposition="outside",
                marker_color=[COLORS["green"] if r >= 0.5 else COLORS["red"] for r in amt_perf["hit_rate"]],
            ))
            fig_amt.add_hline(y=50, line_dash="dash", line_color="gray")
            fig_amt.update_layout(
                height=300, margin=dict(t=30, b=80),
                yaxis_title="Hit Rate (%)", yaxis=dict(range=[0, 80]),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#e2e8f0"), showlegend=False,
                xaxis=dict(tickangle=-20),
            )
            st.plotly_chart(fig_amt, use_container_width=True)
        with ac2:
            fig_amt2 = go.Figure()
            fig_amt2.add_trace(go.Bar(
                x=amt_perf["amount_range"], y=amt_perf["avg_alpha"],
                text=[f'{a:+.2f}%' for a in amt_perf["avg_alpha"]],
                textposition="outside",
                marker_color=[COLORS["green"] if a > 0 else COLORS["red"] for a in amt_perf["avg_alpha"]],
            ))
            fig_amt2.add_hline(y=0, line_dash="dash", line_color="gray")
            fig_amt2.update_layout(
                height=300, margin=dict(t=30, b=80),
                yaxis_title="Avg Alpha (%)",
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#e2e8f0"), showlegend=False,
                xaxis=dict(tickangle=-20),
            )
            st.plotly_chart(fig_amt2, use_container_width=True)
        st.caption("$15K-$100K 交易表現最佳 (RB-004 驗證)")

    # Top Politician Performance
    pol_perf = query_db("""
        SELECT a.politician_name, COUNT(*) as n,
               AVG(sp.hit_5d) as hit_rate,
               AVG(sp.actual_alpha_5d) as avg_alpha
        FROM signal_performance sp
        JOIN alpha_signals a ON sp.signal_id = a.id
        WHERE sp.hit_5d IS NOT NULL AND a.politician_name IS NOT NULL
        GROUP BY a.politician_name
        HAVING COUNT(*) >= 5
        ORDER BY AVG(sp.hit_5d) DESC
        LIMIT 10
    """)
    if not pol_perf.empty:
        st.subheader("Top 政治人物績效 (≥5 訊號)")
        pol_perf["label"] = pol_perf.apply(
            lambda r: f'{r["politician_name"]} (n={int(r["n"])})', axis=1)
        fig_pol = go.Figure()
        fig_pol.add_trace(go.Bar(
            y=pol_perf["label"], x=pol_perf["hit_rate"] * 100,
            orientation="h", name="Hit Rate",
            marker_color=[COLORS["green"] if r >= 0.5 else COLORS["red"] for r in pol_perf["hit_rate"]],
            text=[f'{r*100:.0f}% | α={a:+.1f}%' for r, a in zip(pol_perf["hit_rate"], pol_perf["avg_alpha"])],
            textposition="outside",
        ))
        fig_pol.add_vline(x=50, line_dash="dash", line_color="gray", annotation_text="50%")
        fig_pol.update_layout(
            height=400, margin=dict(t=30, b=40, l=160),
            xaxis_title="Hit Rate (%)", xaxis=dict(range=[0, 100]),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#e2e8f0"), showlegend=False,
            yaxis=dict(autorange="reversed"),
        )
        st.plotly_chart(fig_pol, use_container_width=True)

    # Scatter: expected vs actual alpha
    scatter_df = perf_df[perf_df["actual_alpha_5d"].notna()].copy()
    if not scatter_df.empty:
        st.subheader("預期 vs 實際 Alpha (5 日)")
        scatter_df["actual_alpha_5d_pct"] = scatter_df["actual_alpha_5d"]
        scatter_df["expected_alpha_5d_pct"] = scatter_df["expected_alpha_5d"]
        fig = px.scatter(
            scatter_df,
            x="expected_alpha_5d_pct",
            y="actual_alpha_5d_pct",
            color="ticker",
            hover_data=["politician_name", "signal_strength", "confidence"],
            labels={"expected_alpha_5d_pct": "預期 Alpha (%)", "actual_alpha_5d_pct": "實際 Alpha (%)"},
            color_discrete_sequence=PLOTLY_COLORS,
        )
        fig.add_shape(type="line", x0=-5, y0=-5, x1=5, y1=5, line=dict(dash="dash", color="gray"))
        fig.update_layout(height=450, margin=dict(t=30))
        st.plotly_chart(fig, width="stretch")

    # MFE/MAE analysis
    mae_mfe_df = perf_df[perf_df["max_favorable_excursion"].notna()].copy()
    if not mae_mfe_df.empty:
        st.subheader("MAE/MFE 分析")
        mae_mfe_df["MFE"] = mae_mfe_df["max_favorable_excursion"]
        mae_mfe_df["MAE"] = mae_mfe_df["max_adverse_excursion"]
        fig2 = px.scatter(
            mae_mfe_df,
            x="MAE",
            y="MFE",
            color="ticker",
            hover_data=["politician_name"],
            labels={"MAE": "最大不利偏移 (%)", "MFE": "最大有利偏移 (%)"},
            color_discrete_sequence=PLOTLY_COLORS,
        )
        fig2.add_shape(type="line", x0=-10, y0=-10, x1=10, y1=10, line=dict(dash="dash", color="gray"))
        fig2.update_layout(height=400, margin=dict(t=30))
        st.plotly_chart(fig2, width="stretch")

    # Chamber Comparison (Senate vs House)
    chamber_perf = query_db("""
        SELECT a.chamber, COUNT(*) as n,
               AVG(sp.hit_5d) as hit_rate,
               AVG(sp.actual_alpha_5d) as avg_alpha
        FROM signal_performance sp
        JOIN alpha_signals a ON sp.signal_id = a.id
        WHERE sp.hit_5d IS NOT NULL AND a.chamber IS NOT NULL
        GROUP BY a.chamber
    """)
    if not chamber_perf.empty and len(chamber_perf) >= 2:
        st.subheader("院別績效比較 (Senate vs House)")
        cc1, cc2 = st.columns(2)
        with cc1:
            fig_chr = go.Figure()
            fig_chr.add_trace(go.Bar(
                x=chamber_perf["chamber"], y=chamber_perf["hit_rate"] * 100,
                text=[f'{r*100:.1f}%<br>n={n}' for r, n in zip(chamber_perf["hit_rate"], chamber_perf["n"])],
                textposition="outside",
                marker_color=[COLORS["purple"] if c == "Senate" else COLORS["primary"] for c in chamber_perf["chamber"]],
            ))
            fig_chr.add_hline(y=50, line_dash="dash", line_color="gray", annotation_text="50% baseline")
            fig_chr.update_layout(
                height=300, margin=dict(t=30, b=40),
                yaxis_title="Hit Rate (%)", yaxis=dict(range=[0, 100]),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#e2e8f0"), showlegend=False,
            )
            st.plotly_chart(fig_chr, use_container_width=True)
        with cc2:
            fig_ca = go.Figure()
            fig_ca.add_trace(go.Bar(
                x=chamber_perf["chamber"], y=chamber_perf["avg_alpha"],
                text=[f'{a:+.2f}%' for a in chamber_perf["avg_alpha"]],
                textposition="outside",
                marker_color=[COLORS["purple"] if c == "Senate" else COLORS["primary"] for c in chamber_perf["chamber"]],
            ))
            fig_ca.add_hline(y=0, line_dash="dash", line_color="gray")
            fig_ca.update_layout(
                height=300, margin=dict(t=30, b=40),
                yaxis_title="Avg Alpha (%)",
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#e2e8f0"), showlegend=False,
            )
            st.plotly_chart(fig_ca, use_container_width=True)
        st.caption("Senate 訊號明顯優於 House (RB-004 驗證)")

    # Alpha Horizon Decay (from Fama-French results)
    ff3_df = query_db("""
        SELECT transaction_type,
               AVG(mkt_car_5d) as avg_5d, COUNT(mkt_car_5d) as n_5d,
               AVG(mkt_car_20d) as avg_20d, COUNT(mkt_car_20d) as n_20d,
               AVG(mkt_car_60d) as avg_60d, COUNT(mkt_car_60d) as n_60d
        FROM fama_french_results
        WHERE mkt_car_5d IS NOT NULL
        GROUP BY transaction_type
    """)
    if not ff3_df.empty:
        st.subheader("Alpha 時間維度分析 (Fama-French)")
        st.caption("基於事件研究法：Filing Date 後 5/20/60 交易日的市場調整累積異常報酬 (CAR)")

        fig_decay = go.Figure()
        horizons = ["5d", "20d", "60d"]
        x_labels = ["5 Trading Days", "20 Trading Days", "60 Trading Days"]

        for _, row in ff3_df.iterrows():
            tx = row["transaction_type"]
            vals = [row["avg_5d"] * 100 if row["avg_5d"] else 0,
                    row["avg_20d"] * 100 if row["avg_20d"] else 0,
                    row["avg_60d"] * 100 if row["avg_60d"] else 0]
            ns = [int(row["n_5d"]), int(row["n_20d"]), int(row["n_60d"])]
            color = COLORS["green"] if tx == "Buy" else COLORS["red"]
            fig_decay.add_trace(go.Scatter(
                x=x_labels, y=vals, mode="lines+markers+text",
                name=f"{tx}",
                line=dict(color=color, width=3),
                marker=dict(size=10),
                text=[f"{v:+.2f}%<br>(n={n})" for v, n in zip(vals, ns)],
                textposition="top center",
                textfont=dict(size=10),
            ))
        fig_decay.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
        fig_decay.update_layout(
            height=380, margin=dict(t=30, b=40),
            xaxis_title="Holding Period", yaxis_title="Market-Adjusted CAR (%)",
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#e2e8f0"),
            xaxis=dict(gridcolor="rgba(148,163,184,0.1)"),
            yaxis=dict(gridcolor="rgba(148,163,184,0.1)"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        st.plotly_chart(fig_decay, use_container_width=True)

    # Factor Correlation Analysis
    factor_df = query_db("""
        SELECT sp.signal_strength, sp.confidence, sp.actual_alpha_5d,
               a.sqs_score, a.filing_lag_days
        FROM signal_performance sp
        JOIN alpha_signals a ON sp.signal_id = a.id
        WHERE sp.actual_alpha_5d IS NOT NULL
          AND sp.signal_strength IS NOT NULL
    """)
    if not factor_df.empty and len(factor_df) >= 20:
        st.subheader("因子相關性分析")
        st.caption("哪些因子真正能預測 alpha？(相關係數)")
        numeric_cols = ["signal_strength", "confidence", "sqs_score", "filing_lag_days", "actual_alpha_5d"]
        avail = [c for c in numeric_cols if c in factor_df.columns]
        corr_matrix = factor_df[avail].corr()

        labels_map = {
            "signal_strength": "Signal Strength",
            "confidence": "Confidence",
            "sqs_score": "SQS Score",
            "filing_lag_days": "Filing Lag",
            "actual_alpha_5d": "Actual Alpha 5d",
        }
        display_labels = [labels_map.get(c, c) for c in avail]

        fig_corr = go.Figure(data=go.Heatmap(
            z=corr_matrix.values,
            x=display_labels, y=display_labels,
            colorscale="RdBu_r", zmid=0, zmin=-1, zmax=1,
            text=[[f"{v:.3f}" for v in row] for row in corr_matrix.values],
            texttemplate="%{text}",
            hovertemplate="Row: %{y}<br>Col: %{x}<br>r = %{z:.3f}<extra></extra>",
        ))
        fig_corr.update_layout(
            height=380, margin=dict(t=30, b=40),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#e2e8f0"),
        )
        st.plotly_chart(fig_corr, use_container_width=True)
        st.caption(f"Based on {len(factor_df)} evaluated signals. Confidence (r={corr_matrix.loc['confidence','actual_alpha_5d']:.3f}) is the best alpha predictor.")

    # Performance table
    st.subheader("績效明細")
    display_cols = ["ticker", "politician_name", "direction", "signal_strength", "confidence",
                    "actual_alpha_5d", "actual_alpha_20d", "hit_5d", "hit_20d",
                    "max_favorable_excursion", "max_adverse_excursion", "evaluated_at"]
    avail_cols = [c for c in display_cols if c in perf_df.columns]
    st.dataframe(perf_df[avail_cols].head(50), width="stretch", hide_index=True)


# ══════════════════════════════════════════════
# Page 9: 板塊輪動
# ══════════════════════════════════════════════
def page_sector_rotation():
    st.header("板塊輪動分析")
    st.caption("國會交易板塊聚合 — 偵測資金流向與動能變化")

    sector_df = query_db("SELECT * FROM sector_rotation_signals ORDER BY momentum_score DESC")

    if sector_df.empty:
        st.warning("尚無板塊輪動資料。請先執行 `python -m src.sector_rotation`。")
        return

    # KPI cards
    col1, col2, col3 = st.columns(3)
    col1.metric("板塊訊號數", len(sector_df))
    buy_count = (sector_df["direction"] == "BUY").sum()
    col2.metric("買入板塊", buy_count)
    avg_momentum = sector_df["momentum_score"].mean()
    col3.metric("平均動能", f"{avg_momentum:.3f}")

    # Bar chart: momentum by sector
    st.subheader("板塊動能排名")
    fig = px.bar(
        sector_df,
        x="sector",
        y="momentum_score",
        color="direction",
        hover_data=["etf", "trades", "politician_count", "rotation_type"],
        color_discrete_map={"BUY": COLORS["green"], "SELL": COLORS["red"]},
        labels={"sector": "板塊", "momentum_score": "動能分數", "direction": "方向"},
    )
    fig.update_layout(height=400, margin=dict(t=30))
    st.plotly_chart(fig, width="stretch")

    # Sector details table
    st.subheader("板塊詳細資料")
    display_cols = ["sector", "etf", "direction", "signal_strength", "expected_alpha_20d",
                    "momentum_score", "net_ratio", "trades", "buy_count", "sale_count",
                    "politician_count", "cross_chamber", "rotation_type"]
    avail = [c for c in display_cols if c in sector_df.columns]
    st.dataframe(sector_df[avail], width="stretch", hide_index=True)

    # Rotation types
    if "rotation_type" in sector_df.columns:
        st.subheader("輪動類型分布")
        rot_counts = sector_df["rotation_type"].value_counts()
        fig2 = px.pie(values=rot_counts.values, names=rot_counts.index,
                      color_discrete_sequence=PLOTLY_COLORS)
        fig2.update_layout(height=350, margin=dict(t=30))
        st.plotly_chart(fig2, width="stretch")


# ══════════════════════════════════════════════
# Page 10: Social Intelligence
# ══════════════════════════════════════════════
def page_social_intelligence():
    st.header("Social Media Intelligence")
    st.caption("Real-time KOL & politician social media monitoring with AI-powered NLP analysis")

    # KPI row
    post_count = get_table_count("social_posts")
    signal_count = get_table_count("social_signals")

    social_alpha = query_db("SELECT COUNT(*) as cnt FROM alpha_signals WHERE trade_id LIKE 'social_%'")
    social_alpha_count = int(social_alpha.iloc[0]["cnt"]) if not social_alpha.empty else 0

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Posts Collected", post_count)
    k2.metric("NLP Signals", signal_count)
    k3.metric("Alpha Signals (Social)", social_alpha_count)

    # Consistent/Contradictory
    alignment_df = query_db("""
        SELECT speech_trade_alignment, COUNT(*) as cnt
        FROM social_signals
        WHERE speech_trade_alignment IS NOT NULL
        GROUP BY speech_trade_alignment
    """)
    if not alignment_df.empty:
        consistent = alignment_df[alignment_df["speech_trade_alignment"] == "CONSISTENT"]["cnt"].sum()
        contradictory = alignment_df[alignment_df["speech_trade_alignment"] == "CONTRADICTORY"]["cnt"].sum()
        k4.metric("Speech-Trade Match", f"{consistent} / {contradictory}", delta=f"{consistent} consistent")
    else:
        k4.metric("Speech-Trade Match", "N/A")

    st.markdown('<hr class="section-divider">', unsafe_allow_html=True)

    # Social posts
    col_left, col_right = st.columns([3, 2])

    with col_left:
        st.subheader("Recent Social Posts")
        posts_df = query_db("""
            SELECT sp.platform, sp.author_name, sp.author_type,
                   sp.post_text, sp.post_time, sp.likes, sp.retweets,
                   ss.sentiment, ss.impact_score, ss.signal_type,
                   ss.tickers_implied, ss.reasoning
            FROM social_posts sp
            LEFT JOIN social_signals ss ON sp.id = ss.post_id
            ORDER BY sp.created_at DESC
            LIMIT 20
        """)

        if not posts_df.empty:
            for _, row in posts_df.iterrows():
                platform_icon = {"twitter": "X/Twitter", "truth_social": "Truth Social", "reddit": "Reddit"}.get(
                    row.get("platform", ""), row.get("platform", "")
                )
                sentiment = row.get("sentiment", "N/A")
                sentiment_color = "#4ade80" if sentiment == "Bullish" else "#f87171" if sentiment == "Bearish" else "#94a3b8"
                impact = row.get("impact_score", 0) or 0

                st.markdown(
                    f'<div style="background:#1e293b;border:1px solid #334155;border-radius:12px;padding:1rem;margin-bottom:0.8rem;">'
                    f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.5rem;">'
                    f'<span style="font-weight:700;color:#e2e8f0;">{row["author_name"]}</span>'
                    f'<span style="font-size:0.75rem;color:#64748b;">{platform_icon} | {str(row.get("post_time",""))[:16]}</span>'
                    f'</div>'
                    f'<p style="color:#cbd5e1;font-size:0.9rem;margin:0 0 0.5rem 0;">{str(row["post_text"])[:300]}</p>'
                    f'<div style="display:flex;gap:1rem;font-size:0.75rem;">'
                    f'<span style="color:{sentiment_color};font-weight:700;">{sentiment}</span>'
                    f'<span style="color:#94a3b8;">Impact: {impact:.0f}/10</span>'
                    f'<span style="color:#94a3b8;">Tickers: {row.get("tickers_implied", "[]")}</span>'
                    f'</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
        else:
            st.info("No social posts yet. Run `python run_social_analysis.py` to fetch.")

    with col_right:
        st.subheader("Signal Breakdown")

        # Sentiment distribution
        sentiment_df = query_db("""
            SELECT sentiment, COUNT(*) as cnt
            FROM social_signals
            GROUP BY sentiment
        """)
        if not sentiment_df.empty:
            fig = px.pie(
                sentiment_df, names="sentiment", values="cnt",
                color="sentiment",
                color_discrete_map={"Bullish": COLORS["green"], "Bearish": COLORS["red"], "Neutral": "#64748b"},
                hole=0.5,
            )
            fig.update_layout(height=250, margin=dict(t=10, b=10), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            fig.update_traces(textinfo="label+percent", textfont_size=12)
            st.plotly_chart(fig, width="stretch")
        else:
            st.info("No sentiment data yet")

        # Platform distribution
        platform_df = query_db("""
            SELECT platform, COUNT(*) as cnt FROM social_posts GROUP BY platform
        """)
        if not platform_df.empty:
            st.subheader("By Platform")
            fig2 = px.bar(
                platform_df, x="platform", y="cnt",
                color="platform",
                color_discrete_sequence=PLOTLY_COLORS,
                labels={"platform": "Platform", "cnt": "Posts"},
            )
            fig2.update_layout(height=200, margin=dict(t=10, b=30), showlegend=False, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig2, width="stretch")

        # Social alpha signals
        social_alpha_df = query_db("""
            SELECT ticker, direction, signal_strength, expected_alpha_5d, confidence
            FROM alpha_signals
            WHERE trade_id LIKE 'social_%'
            ORDER BY signal_strength DESC
            LIMIT 10
        """)
        if not social_alpha_df.empty:
            st.subheader("Social Alpha Signals")
            st.dataframe(
                social_alpha_df.rename(columns={
                    "ticker": "Ticker", "direction": "Dir", "signal_strength": "Strength",
                    "expected_alpha_5d": "Alpha 5d", "confidence": "Conf",
                }),
                width="stretch",
                hide_index=True,
            )

    # Ticker mentions from social signals
    ticker_mentions_df = query_db("""
        SELECT tickers_implied FROM social_signals
        WHERE tickers_implied IS NOT NULL AND tickers_implied != '[]'
    """)
    if not ticker_mentions_df.empty:
        import json as _json
        all_tickers = []
        for _, row in ticker_mentions_df.iterrows():
            try:
                tickers = _json.loads(row["tickers_implied"])
                all_tickers.extend([t for t in tickers if len(t) <= 5 and t.isupper()])
            except (ValueError, TypeError):
                pass
        if all_tickers:
            from collections import Counter
            ticker_counts = Counter(all_tickers).most_common(15)
            tc_df = pd.DataFrame(ticker_counts, columns=["ticker", "mentions"])
            st.subheader("Social Ticker Mentions")
            fig_tc = px.bar(
                tc_df, x="ticker", y="mentions",
                color_discrete_sequence=[COLORS["purple"]],
                labels={"ticker": "Ticker", "mentions": "Mentions"},
            )
            fig_tc.update_layout(
                height=300, margin=dict(t=20, b=40),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#e2e8f0"), showlegend=False,
            )
            st.plotly_chart(fig_tc, use_container_width=True)

    # Architecture explanation
    st.markdown('<hr class="section-divider">', unsafe_allow_html=True)
    st.subheader("How It Works")
    arch1, arch2, arch3, arch4 = st.columns(4)
    with arch1:
        st.markdown(
            '<div style="background:#1e293b;border:1px solid #334155;border-radius:12px;padding:1rem;text-align:center;">'
            '<div style="font-size:1.5rem;margin-bottom:0.3rem;">1</div>'
            '<div style="font-weight:700;color:#38bdf8;">Fetch</div>'
            '<div style="font-size:0.8rem;color:#94a3b8;">Gemini Search monitors 14 KOL/politician accounts across X, Truth Social, Reddit</div>'
            '</div>',
            unsafe_allow_html=True,
        )
    with arch2:
        st.markdown(
            '<div style="background:#1e293b;border:1px solid #334155;border-radius:12px;padding:1rem;text-align:center;">'
            '<div style="font-size:1.5rem;margin-bottom:0.3rem;">2</div>'
            '<div style="font-weight:700;color:#4ade80;">NLP</div>'
            '<div style="font-size:0.8rem;color:#94a3b8;">Dual-layer: FinTwitBERT (fast, local) + Gemini Flash (deep reasoning, sarcasm detection)</div>'
            '</div>',
            unsafe_allow_html=True,
        )
    with arch3:
        st.markdown(
            '<div style="background:#1e293b;border:1px solid #334155;border-radius:12px;padding:1rem;text-align:center;">'
            '<div style="font-size:1.5rem;margin-bottom:0.3rem;">3</div>'
            '<div style="font-weight:700;color:#fbbf24;">Cross-Ref</div>'
            '<div style="font-size:0.8rem;color:#94a3b8;">Match politician speech vs actual trades: CONSISTENT = alpha boost, CONTRADICTORY = alert</div>'
            '</div>',
            unsafe_allow_html=True,
        )
    with arch4:
        st.markdown(
            '<div style="background:#1e293b;border:1px solid #334155;border-radius:12px;padding:1rem;text-align:center;">'
            '<div style="font-size:1.5rem;margin-bottom:0.3rem;">4</div>'
            '<div style="font-weight:700;color:#a78bfa;">Signal</div>'
            '<div style="font-size:0.8rem;color:#94a3b8;">High-impact posts (score >= 7) generate alpha signals with convergence bonus</div>'
            '</div>',
            unsafe_allow_html=True,
        )


# ══════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════
def render_alert_banner():
    """Show a top-of-page alert if there are fresh high-priority signals."""
    fresh_strong = query_db("""
        SELECT COUNT(*) as n FROM alpha_signals
        WHERE signal_strength >= 1.0 AND created_at >= date('now', '-1 days')
    """)
    fresh_conv = query_db("""
        SELECT COUNT(*) as n FROM convergence_signals
        WHERE score >= 2.0 AND detected_at >= date('now', '-1 days')
    """)
    n_strong = int(fresh_strong['n'].iloc[0]) if not fresh_strong.empty else 0
    n_conv = int(fresh_conv['n'].iloc[0]) if not fresh_conv.empty else 0

    if n_strong > 0 or n_conv > 0:
        parts = []
        if n_strong > 0:
            parts.append(f"{n_strong} strong signal{'s' if n_strong > 1 else ''}")
        if n_conv > 0:
            parts.append(f"{n_conv} convergence alert{'s' if n_conv > 1 else ''}")
        st.markdown(
            f'<div style="background:linear-gradient(90deg,#1e3a5f,#1e293b);border:1px solid #38bdf8;'
            f'border-radius:8px;padding:0.8rem 1.2rem;margin-bottom:1rem;display:flex;'
            f'align-items:center;gap:0.5rem;">'
            f'<span style="font-size:1.2rem;">🔔</span>'
            f'<span style="color:#38bdf8;font-weight:600;">New Today:</span>'
            f'<span style="color:#e2e8f0;">{" + ".join(parts)} in the last 24h</span>'
            f'</div>',
            unsafe_allow_html=True,
        )


def main():
    page, start_date, end_date, chambers = render_sidebar()

    # Alert banner on every page
    render_alert_banner()

    if page == "🎯 Today's Action":
        page_todays_action()
    elif page == "Executive Dashboard":
        page_overview(start_date, end_date, chambers)
    elif page == "Alpha Signals":
        page_alpha_signals(start_date, end_date, chambers)
    elif page == "Portfolio":
        page_portfolio()
    elif page == "Politician Ranking":
        page_politicians(start_date, end_date, chambers)
    elif page == "Convergence":
        page_convergence()
    elif page == "Trade Explorer":
        page_trade_explorer(start_date, end_date, chambers)
    elif page == "Signal Quality":
        page_signal_quality()
    elif page == "Performance":
        page_signal_performance()
    elif page == "Sector Rotation":
        page_sector_rotation()
    elif page == "Social Intelligence":
        page_social_intelligence()

    # ── Legal Disclaimer (every page) ──
    render_disclaimer()


# ══════════════════════════════════════════════
# Legal Disclaimer
# ══════════════════════════════════════════════
def render_disclaimer():
    """Render full legal disclaimer at the bottom of every page."""
    st.markdown("---")
    st.markdown(
        '<div style="background:#0f172a;border:1px solid #334155;border-radius:8px;'
        'padding:1.2rem;margin-top:1rem;">'
        '<p style="color:#64748b;font-size:0.75rem;line-height:1.6;margin:0;">'
        '<strong style="color:#94a3b8;">⚠ Important Disclaimer</strong><br>'
        'Political Alpha Monitor (PAM) is a <strong>research tool</strong> for informational '
        'purposes only. It does <strong>not</strong> constitute investment advice, solicitation, '
        'or recommendation to buy or sell any securities.<br><br>'
        '• All signals, scores, and portfolio suggestions are <strong>algorithmically generated</strong> '
        'and have not been verified by a registered investment adviser (RIA).<br>'
        '• Past performance and backtested results do <strong>not</strong> guarantee future returns. '
        'Signal hit rates are based on limited historical samples and may not be statistically significant.<br>'
        '• Congressional trading data is sourced from public government disclosures with an inherent '
        'filing delay of 30-45 days. Information may be outdated by the time it is displayed.<br>'
        '• Social media analysis reflects AI-interpreted sentiment and may contain errors, '
        'misinterpretations, or hallucinations.<br>'
        '• Users should conduct their own due diligence and consult a qualified financial professional '
        'before making any investment decisions.<br><br>'
        '<em>By using this tool, you acknowledge that you bear full responsibility for any '
        'investment decisions made based on the information provided.</em>'
        '</p></div>',
        unsafe_allow_html=True,
    )


# ══════════════════════════════════════════════
# Page 11: Today's Action (行動清單)
# ══════════════════════════════════════════════
def page_todays_action():
    """One-page actionable summary for non-quant users."""
    st.markdown("## 🎯 Today's Action Plan")
    st.caption("AI-generated daily briefing — not investment advice. See disclaimer below.")

    # ── Morning Briefing Header ──
    from datetime import date
    today = date.today().strftime("%Y-%m-%d")
    st.markdown(
        f'<div style="background:linear-gradient(135deg,#1e293b,#0f172a);border:1px solid #334155;'
        f'border-radius:12px;padding:1.5rem;margin-bottom:1rem;">'
        f'<h3 style="color:#38bdf8;margin:0;">📋 Daily Briefing — {today}</h3>'
        f'<p style="color:#94a3b8;margin:0.3rem 0 0 0;">Auto-generated from congressional trades, '
        f'convergence signals, and social intelligence.</p></div>',
        unsafe_allow_html=True,
    )

    # ── Section 0: Market Context & Data Freshness ──
    ctx1, ctx2, ctx3, ctx4 = st.columns(4)

    # VIX regime
    try:
        import yfinance as yf
        vix_data = yf.Ticker("^VIX").history(period="2d")
        if not vix_data.empty:
            vix_val = vix_data["Close"].iloc[-1]
            if vix_val < 14:
                vix_zone, vix_color, vix_mult = "Ultra Low", "#94a3b8", "0.6x"
            elif vix_val <= 16:
                vix_zone, vix_color, vix_mult = "Goldilocks", "#4ade80", "1.3x"
            elif vix_val <= 20:
                vix_zone, vix_color, vix_mult = "Moderate", "#fbbf24", "0.8x"
            elif vix_val <= 30:
                vix_zone, vix_color, vix_mult = "High", "#fb923c", "0.5x"
            else:
                vix_zone, vix_color, vix_mult = "Extreme", "#f87171", "0.3x"
            ctx1.metric("VIX", f"{vix_val:.1f}", delta=f"{vix_zone} ({vix_mult})")
            # VIX warning banner
            if vix_val > 20:
                st.warning(
                    f"⚠ **VIX is {vix_val:.1f} ({vix_zone})** — Signal strength is reduced by "
                    f"{(1-float(vix_mult.replace('x',''))):.0%}. "
                    f"Consider smaller position sizes or waiting for lower volatility."
                )
        else:
            ctx1.metric("VIX", "N/A")
    except Exception:
        ctx1.metric("VIX", "Unavailable")

    # Data freshness
    freshness = query_db("SELECT MAX(created_at) as last FROM extraction_log")
    if not freshness.empty and pd.notna(freshness['last'].iloc[0]):
        last_str = str(freshness['last'].iloc[0])[:16]
        ctx2.metric("Last ETL", last_str)
    else:
        ctx2.metric("Last ETL", "Never")

    # Avg filing lag
    lag_df = query_db("""
        SELECT avg(julianday(filing_date) - julianday(transaction_date)) as avg_lag
        FROM congress_trades WHERE filing_date IS NOT NULL AND transaction_date IS NOT NULL
    """)
    lag_val = lag_df['avg_lag'].iloc[0] if not lag_df.empty and pd.notna(lag_df['avg_lag'].iloc[0]) else 0
    ctx3.metric("Avg Filing Lag", f"{lag_val:.0f} days", delta="30-45d typical", delta_color="off")

    # Unique politicians
    pol_count = query_db("SELECT COUNT(DISTINCT politician_name) as n FROM congress_trades")
    ctx4.metric("Politicians Tracked", int(pol_count['n'].iloc[0]) if not pol_count.empty else 0)

    st.markdown('<hr class="section-divider">', unsafe_allow_html=True)

    # ── Section 1: Top BUY Signals (PACS-enhanced, max 5) ──
    st.markdown("### 🟢 Top Buy Signals (PACS-Enhanced)")
    st.caption("🟢 High (>=0.7) = Consider acting · 🟡 Medium (0.5-0.7) = Monitor closely · 🔴 Low (<0.5) = Wait for confirmation")
    top_buys = query_db("""
        SELECT e.ticker, a.asset_name, e.politician_name, e.chamber,
               e.enhanced_strength, e.confidence_v2, e.pacs_score,
               a.expected_alpha_20d, a.reasoning,
               COALESCE(e.insider_confirmed, 0) as insider_confirmed,
               CASE
                   WHEN e.enhanced_strength >= 1.0 THEN '🔥 Strong'
                   WHEN e.enhanced_strength >= 0.5 THEN '⭐ Moderate'
                   ELSE '📊 Weak'
               END as strength_label,
               CASE
                   WHEN e.confidence_v2 >= 0.7 THEN '🟢 High'
                   WHEN e.confidence_v2 >= 0.5 THEN '🟡 Medium'
                   ELSE '🔴 Low'
               END as confidence_label,
               e.vix_zone,
               ct.filing_date,
               CAST(julianday('now') - julianday(ct.filing_date) AS INTEGER) as days_since_filing
        FROM enhanced_signals e
        LEFT JOIN alpha_signals a ON e.trade_id = a.trade_id
        LEFT JOIN congress_trades ct ON a.trade_id = ct.id
        WHERE e.direction = 'LONG'
        ORDER BY e.pacs_score DESC
        LIMIT 5
    """)

    if not top_buys.empty:
        for _, row in top_buys.iterrows():
            asset = row['asset_name'] if pd.notna(row['asset_name']) else row['ticker']
            alpha_str = f"+{row['expected_alpha_20d']:.1f}%" if pd.notna(row['expected_alpha_20d']) else "N/A"
            insider_badge = ' <span style="background:#eab308;color:#000;padding:1px 6px;border-radius:4px;font-size:0.7rem;font-weight:700;">INSIDER CONFIRMED</span>' if row.get('insider_confirmed', 0) == 1 else ""
            pacs_str = f"PACS: {row['pacs_score']:.2f}" if pd.notna(row.get('pacs_score')) else ""
            # Signal freshness badge
            days_old = int(row['days_since_filing']) if pd.notna(row.get('days_since_filing')) else 999
            if days_old <= 20:
                fresh_badge = f' <span style="background:#4ade80;color:#000;padding:1px 6px;border-radius:4px;font-size:0.65rem;font-weight:600;">FRESH {days_old}d</span>'
            elif days_old <= 40:
                decay_pct = max(0, 100 - (days_old - 20) * 5)
                fresh_badge = f' <span style="background:#fbbf24;color:#000;padding:1px 6px;border-radius:4px;font-size:0.65rem;font-weight:600;">DECAYING {decay_pct}%</span>'
            else:
                fresh_badge = ' <span style="background:#f87171;color:#000;padding:1px 6px;border-radius:4px;font-size:0.65rem;font-weight:600;">EXPIRED</span>'
            st.markdown(
                f'<div style="background:#1e293b;border-left:4px solid #4ade80;border-radius:8px;'
                f'padding:1rem;margin-bottom:0.8rem;">'
                f'<div style="display:flex;justify-content:space-between;align-items:center;">'
                f'<div>'
                f'<span style="color:#4ade80;font-size:1.3rem;font-weight:700;">{row["ticker"]}</span>'
                f'<span style="color:#94a3b8;margin-left:0.5rem;">{asset}</span>{insider_badge}{fresh_badge}'
                f'</div>'
                f'<div style="text-align:right;">'
                f'<span style="color:#e2e8f0;">{row["strength_label"]}</span>'
                f' · <span>{row["confidence_label"]}</span>'
                f'</div></div>'
                f'<div style="color:#94a3b8;font-size:0.85rem;margin-top:0.5rem;">'
                f'👤 {row["politician_name"]} ({row["chamber"]}) · '
                f'{pacs_str} · '
                f'Expected 20d Alpha: <strong style="color:#4ade80;">{alpha_str}</strong>'
                f'</div></div>',
                unsafe_allow_html=True,
            )
    else:
        st.info("No strong buy signals in the last 7 days.")

    # ── Section 2: Convergence Alerts (deduplicated: best per ticker) ──
    st.markdown("### 🔔 Convergence Alerts")
    st.caption("Multiple politicians buying the same stock — strongest signal type.")
    convergence = query_db("""
        SELECT c.ticker, c.direction, c.politician_count, c.politicians, c.chambers, c.score,
               CASE
                   WHEN c.score >= 2.0 THEN '🔥 Very Strong'
                   WHEN c.score >= 1.5 THEN '⭐ Strong'
                   ELSE '📊 Moderate'
               END as score_label
        FROM convergence_signals c
        INNER JOIN (
            SELECT ticker, direction, MAX(score) as max_score
            FROM convergence_signals
            GROUP BY ticker, direction
        ) best ON c.ticker = best.ticker AND c.direction = best.direction AND c.score = best.max_score
        ORDER BY c.score DESC
        LIMIT 5
    """)

    if not convergence.empty:
        for _, row in convergence.iterrows():
            direction_icon = "🟢 BUY" if row['direction'] == 'Buy' else "🔴 SELL"
            chambers_str = row['chambers'] if pd.notna(row['chambers']) else ""
            cross = "🏛 Cross-chamber" if "Senate" in chambers_str and "House" in chambers_str else ""
            st.markdown(
                f'<div style="background:#1e293b;border-left:4px solid #fbbf24;border-radius:8px;'
                f'padding:1rem;margin-bottom:0.8rem;">'
                f'<div style="display:flex;justify-content:space-between;">'
                f'<span style="color:#fbbf24;font-size:1.2rem;font-weight:700;">{row["ticker"]}</span>'
                f'<span>{row["score_label"]} {cross}</span>'
                f'</div>'
                f'<div style="color:#94a3b8;font-size:0.85rem;margin-top:0.3rem;">'
                f'{direction_icon} · {row["politician_count"]} politicians · '
                f'Score: {row["score"]:.2f}</div>'
                f'<div style="color:#64748b;font-size:0.8rem;margin-top:0.2rem;">'
                f'👥 {row["politicians"]}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
    else:
        st.info("No convergence signals detected.")

    # ── Section 3: Social Intelligence Highlights ──
    st.markdown("### 📱 Social Intelligence")
    st.caption("Key statements from politicians and KOLs with market impact.")
    social = query_db("""
        SELECT sp.author_name, sp.platform, ss.sentiment, ss.impact_score,
               substr(sp.post_text, 1, 200) as text_preview,
               ss.tickers_implied,
               CASE
                   WHEN ss.impact_score >= 8 THEN '🔥 High Impact'
                   WHEN ss.impact_score >= 6 THEN '⚡ Notable'
                   ELSE '📝 Low'
               END as impact_label,
               CASE
                   WHEN ss.sentiment = 'Bullish' THEN '🟢'
                   WHEN ss.sentiment = 'Bearish' THEN '🔴'
                   ELSE '⚪'
               END as sentiment_icon
        FROM social_signals ss
        JOIN social_posts sp ON ss.post_id = sp.id
        WHERE ss.impact_score >= 6
        ORDER BY ss.impact_score DESC
        LIMIT 5
    """)

    if not social.empty:
        for _, row in social.iterrows():
            tickers = row['tickers_implied'] if pd.notna(row['tickers_implied']) and row['tickers_implied'] != '[]' else "—"
            st.markdown(
                f'<div style="background:#1e293b;border-left:4px solid #a78bfa;border-radius:8px;'
                f'padding:1rem;margin-bottom:0.8rem;">'
                f'<div style="display:flex;justify-content:space-between;">'
                f'<span style="color:#a78bfa;font-weight:600;">{row["author_name"]}</span>'
                f'<span>{row["sentiment_icon"]} {row["sentiment"]} · {row["impact_label"]}</span>'
                f'</div>'
                f'<div style="color:#cbd5e1;font-size:0.85rem;margin-top:0.5rem;'
                f'font-style:italic;">"{row["text_preview"]}..."</div>'
                f'<div style="color:#94a3b8;font-size:0.8rem;margin-top:0.3rem;">'
                f'📊 Related tickers: <strong style="color:#38bdf8;">{tickers}</strong> · '
                f'Platform: {row["platform"]}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
    else:
        st.info("No high-impact social signals.")

    # ── Section 4: Portfolio Summary (simplified) ──
    st.markdown("### 💼 Current Portfolio — Top Holdings")
    portfolio = query_db("""
        SELECT ticker, weight, conviction_score, expected_alpha,
               CASE
                   WHEN conviction_score >= 70 THEN '⭐⭐⭐'
                   WHEN conviction_score >= 55 THEN '⭐⭐'
                   ELSE '⭐'
               END as stars
        FROM portfolio_positions
        ORDER BY conviction_score DESC
        LIMIT 10
    """)

    if not portfolio.empty:
        portfolio['weight_pct'] = portfolio['weight'].apply(lambda x: f"{x:.1%}")
        portfolio['alpha_str'] = portfolio['expected_alpha'].apply(
            lambda x: f"+{x:.1%}" if pd.notna(x) else "N/A"
        )
        portfolio['conviction_int'] = portfolio['conviction_score'].apply(lambda x: f"{x:.0f}")
        display_df = portfolio[['ticker', 'stars', 'weight_pct', 'conviction_int', 'alpha_str']].copy()
        display_df.columns = ['Ticker', 'Rating', 'Weight', 'Score', 'Expected Alpha']
        st.dataframe(display_df, width="stretch", hide_index=True)
    else:
        st.info("No portfolio positions.")

    # ── Section 5: Sector Momentum ──
    st.markdown("### 📊 Sector Momentum (Top 5)")
    st.caption("Congressional net buying by sector — ETF signals based on RB-007.")
    sectors = query_db("""
        SELECT sector, etf, direction, signal_strength, expected_alpha_20d,
               momentum_score, rotation_type, politician_count, trades,
               CASE
                   WHEN signal_strength >= 0.7 THEN '🔥 Strong'
                   WHEN signal_strength >= 0.4 THEN '⭐ Moderate'
                   ELSE '📊 Weak'
               END as strength_label
        FROM sector_rotation_signals
        ORDER BY created_at DESC, momentum_score DESC
        LIMIT 5
    """)
    if not sectors.empty:
        for _, row in sectors.iterrows():
            rot_color = {"ACCELERATING": "#4ade80", "DECELERATING": "#fbbf24",
                         "REVERSING_UP": "#38bdf8", "REVERSING_DOWN": "#f87171",
                         "STABLE": "#94a3b8"}.get(row['rotation_type'], "#94a3b8")
            alpha_str = f"+{row['expected_alpha_20d']:.1f}%" if pd.notna(row['expected_alpha_20d']) else "N/A"
            st.markdown(
                f'<div style="background:#1e293b;border-left:4px solid {rot_color};border-radius:8px;'
                f'padding:0.8rem;margin-bottom:0.6rem;">'
                f'<div style="display:flex;justify-content:space-between;align-items:center;">'
                f'<div>'
                f'<span style="color:#e2e8f0;font-weight:700;">{row["sector"]}</span>'
                f' <span style="color:#38bdf8;">({row["etf"]})</span>'
                f'</div>'
                f'<div style="text-align:right;">'
                f'<span style="color:{rot_color};font-size:0.85rem;">{row["rotation_type"]}</span>'
                f' · {row["strength_label"]}'
                f'</div></div>'
                f'<div style="color:#94a3b8;font-size:0.82rem;margin-top:0.3rem;">'
                f'Momentum: {row["momentum_score"]:.2f} · '
                f'Expected 20d Alpha: <strong style="color:#4ade80;">{alpha_str}</strong> · '
                f'{row["politician_count"]} politicians · {row["trades"]} trades'
                f'</div></div>',
                unsafe_allow_html=True,
            )
    else:
        st.info("No sector rotation signals available.")

    st.markdown('<hr class="section-divider">', unsafe_allow_html=True)

    # ── Section 6: Risk Warnings ──
    st.markdown("### ⚠ Risk Context")
    perf = query_db("SELECT count(*) as n, avg(hit_5d) as hr FROM signal_performance WHERE hit_5d IS NOT NULL")
    n_samples = int(perf['n'].iloc[0]) if not perf.empty else 0
    hr = perf['hr'].iloc[0] if not perf.empty and pd.notna(perf['hr'].iloc[0]) else 0

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(
            f'<div style="background:#1e293b;border:1px solid #334155;border-radius:8px;padding:1rem;">'
            f'<div style="color:#94a3b8;font-size:0.8rem;">Signal Track Record</div>'
            f'<div style="color:#e2e8f0;font-size:1.5rem;">{hr:.0%} hit rate</div>'
            f'<div style="color:#f87171;font-size:0.75rem;">⚠ Based on only {n_samples} samples — '
            f'not statistically significant (need 200+)</div></div>',
            unsafe_allow_html=True,
        )
    with col2:
        avg_lag = query_db("""
            SELECT avg(julianday(filing_date) - julianday(transaction_date)) as avg_lag
            FROM congress_trades WHERE filing_date IS NOT NULL AND transaction_date IS NOT NULL
        """)
        lag_val = avg_lag['avg_lag'].iloc[0] if not avg_lag.empty and pd.notna(avg_lag['avg_lag'].iloc[0]) else 0
        st.markdown(
            f'<div style="background:#1e293b;border:1px solid #334155;border-radius:8px;padding:1rem;">'
            f'<div style="color:#94a3b8;font-size:0.8rem;">Avg Filing Delay</div>'
            f'<div style="color:#fbbf24;font-size:1.5rem;">{lag_val:.0f} days</div>'
            f'<div style="color:#f87171;font-size:0.75rem;">⚠ Signals may be stale — '
            f'congress members have 30-45 days to disclose</div></div>',
            unsafe_allow_html=True,
        )

    # ── Full Disclaimer ──
    st.markdown("---")
    st.markdown(
        '<div style="background:#0f172a;border:1px solid #334155;border-radius:8px;padding:1rem;margin-top:1rem;">'
        '<p style="color:#f87171;font-weight:700;margin:0 0 0.5rem 0;">DISCLAIMER</p>'
        '<p style="color:#94a3b8;font-size:0.78rem;margin:0;line-height:1.5;">'
        'This dashboard is for <strong>educational and research purposes only</strong>. '
        'It does NOT constitute investment advice, financial advice, trading advice, or any other advice. '
        'Congressional trading data is sourced from public disclosures and may be delayed 30-45 days. '
        'Past performance does not guarantee future results. '
        'All signals are AI-generated and may contain errors. '
        'Always do your own research and consult a qualified financial advisor before making investment decisions. '
        'The creators of this tool accept no liability for any financial losses.</p>'
        '</div>',
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
