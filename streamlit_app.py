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
        'PAM v2.1 | Research Use Only<br>Not Investment Advice</div>',
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

    k1, k2, k3, k4, k5, k6 = st.columns(6)
    k1.metric("Trades Tracked", f"{total_trades:,}")
    k2.metric("Alpha Signals", f"{active_signals:,}")
    k3.metric("Enhanced (PACS)", f"{enhanced:,}")
    k4.metric("Portfolio", f"{portfolio_pos} holdings")
    k5.metric("5d Hit Rate", f"{hr5*100:.0f}%" if hr5 else "N/A")
    k6.metric("Social Intel", f"{social_posts} posts")

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
        avg_alpha_5d = perf_df.loc[has_5d, "actual_alpha_5d"].mean() * 100
        col1.metric("5 日勝率", f"{hr_5d:.1f}%", help=f"基於 {n_5d} 個樣本")
        col2.metric("5 日平均 Alpha", f"{avg_alpha_5d:+.2f}%", help=f"n={n_5d}")
    else:
        col1.metric("5 日勝率", "N/A")
        col2.metric("5 日平均 Alpha", "N/A")

    if n_20d > 0:
        hr_20d = perf_df.loc[has_20d, "hit_20d"].mean() * 100
        avg_alpha_20d = perf_df.loc[has_20d, "actual_alpha_20d"].mean() * 100
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
    if n_5d < min_samples:
        st.warning(
            f"⚠ **Statistical Warning**: 5-day hit rate is based on only **{n_5d} samples** "
            f"(minimum {min_samples} needed for significance). "
            f"Results should be interpreted with extreme caution. "
            f"A {hr_5d:.0f}% hit rate with n={n_5d} has a 95% CI of approximately "
            f"±{1.96 * (50 / (n_5d ** 0.5)):.0f}% — indistinguishable from random."
            if n_5d > 0 else
            f"⚠ **Statistical Warning**: No samples with actual returns yet. "
            f"Minimum {min_samples} samples needed for statistically meaningful results."
        )

    # Cumulative Alpha Chart
    cum_df = perf_df[perf_df["actual_alpha_5d"].notna()].sort_values("signal_date").copy()
    if not cum_df.empty and "signal_date" in cum_df.columns:
        st.subheader("累積 Alpha 曲線 (5 日)")
        cum_df["cum_alpha"] = (cum_df["actual_alpha_5d"] * 100).cumsum()
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

    # Scatter: expected vs actual alpha
    scatter_df = perf_df[perf_df["actual_alpha_5d"].notna()].copy()
    if not scatter_df.empty:
        st.subheader("預期 vs 實際 Alpha (5 日)")
        scatter_df["actual_alpha_5d_pct"] = scatter_df["actual_alpha_5d"] * 100
        scatter_df["expected_alpha_5d_pct"] = scatter_df["expected_alpha_5d"] * 100
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
        mae_mfe_df["MFE"] = mae_mfe_df["max_favorable_excursion"] * 100
        mae_mfe_df["MAE"] = mae_mfe_df["max_adverse_excursion"] * 100
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

    # Performance table
    st.subheader("績效明細")
    display_cols = ["ticker", "direction", "signal_strength", "confidence",
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

    # Trade count (7d)
    recent_trades = query_db("SELECT COUNT(*) as n FROM congress_trades WHERE created_at >= date('now', '-7 days')")
    ctx3.metric("New Trades (7d)", int(recent_trades['n'].iloc[0]) if not recent_trades.empty else 0)

    # Unique politicians
    pol_count = query_db("SELECT COUNT(DISTINCT politician_name) as n FROM congress_trades")
    ctx4.metric("Politicians Tracked", int(pol_count['n'].iloc[0]) if not pol_count.empty else 0)

    st.markdown('<hr class="section-divider">', unsafe_allow_html=True)

    # ── Section 1: Top BUY Signals (max 5) ──
    st.markdown("### 🟢 Top Buy Signals")
    top_buys = query_db("""
        SELECT a.ticker, a.asset_name, a.politician_name, a.chamber,
               a.signal_strength, a.confidence, a.expected_alpha_20d,
               a.reasoning,
               CASE
                   WHEN a.signal_strength >= 1.0 THEN '🔥 Strong'
                   WHEN a.signal_strength >= 0.5 THEN '⭐ Moderate'
                   ELSE '📊 Weak'
               END as strength_label,
               CASE
                   WHEN a.confidence >= 0.7 THEN '🟢 High'
                   WHEN a.confidence >= 0.5 THEN '🟡 Medium'
                   ELSE '🔴 Low'
               END as confidence_label
        FROM alpha_signals a
        WHERE a.direction = 'LONG'
          AND a.created_at >= date('now', '-7 days')
        ORDER BY a.signal_strength DESC
        LIMIT 5
    """)

    if not top_buys.empty:
        for _, row in top_buys.iterrows():
            asset = row['asset_name'] if pd.notna(row['asset_name']) else row['ticker']
            alpha_str = f"+{row['expected_alpha_20d']:.1f}%" if pd.notna(row['expected_alpha_20d']) else "N/A"
            st.markdown(
                f'<div style="background:#1e293b;border-left:4px solid #4ade80;border-radius:8px;'
                f'padding:1rem;margin-bottom:0.8rem;">'
                f'<div style="display:flex;justify-content:space-between;align-items:center;">'
                f'<div>'
                f'<span style="color:#4ade80;font-size:1.3rem;font-weight:700;">{row["ticker"]}</span>'
                f'<span style="color:#94a3b8;margin-left:0.5rem;">{asset}</span>'
                f'</div>'
                f'<div style="text-align:right;">'
                f'<span style="color:#e2e8f0;">{row["strength_label"]}</span>'
                f' · <span>{row["confidence_label"]}</span>'
                f'</div></div>'
                f'<div style="color:#94a3b8;font-size:0.85rem;margin-top:0.5rem;">'
                f'👤 {row["politician_name"]} ({row["chamber"]}) · '
                f'Expected 20d Alpha: <strong style="color:#4ade80;">{alpha_str}</strong>'
                f'</div></div>',
                unsafe_allow_html=True,
            )
    else:
        st.info("No strong buy signals in the last 7 days.")

    # ── Section 2: Convergence Alerts ──
    st.markdown("### 🔔 Convergence Alerts")
    st.caption("Multiple politicians buying the same stock — strongest signal type.")
    convergence = query_db("""
        SELECT ticker, direction, politician_count, politicians, chambers, score,
               CASE
                   WHEN score >= 2.0 THEN '🔥 Very Strong'
                   WHEN score >= 1.5 THEN '⭐ Strong'
                   ELSE '📊 Moderate'
               END as score_label
        FROM convergence_signals
        ORDER BY score DESC
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
