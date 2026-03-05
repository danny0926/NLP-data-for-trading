"""
Political Alpha Monitor — Interactive Dashboard (Streamlit)
國會交易智慧分析系統 — 互動式儀表板

使用方式:
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

# ── 色彩主題 ──
COLORS = {
    "primary": "#38bdf8",
    "green": "#4ade80",
    "red": "#f87171",
    "yellow": "#fbbf24",
    "purple": "#a78bfa",
    "orange": "#fb923c",
    "teal": "#2dd4bf",
    "pink": "#f472b6",
}
PLOTLY_COLORS = [
    "#38bdf8", "#4ade80", "#fbbf24", "#a78bfa", "#f87171",
    "#fb923c", "#2dd4bf", "#e879f9", "#818cf8", "#34d399",
]


# ── 資料庫工具 ──
@st.cache_data(ttl=300)
def query_db(sql: str, params: tuple = ()) -> pd.DataFrame:
    """查詢 SQLite，回傳 DataFrame。"""
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(sql, conn, params=params)
    conn.close()
    return df


def get_table_count(table: str) -> int:
    """取得表格列數。"""
    try:
        df = query_db(f"SELECT COUNT(*) as cnt FROM {table}")
        return int(df.iloc[0]["cnt"])
    except Exception:
        return 0


def get_db_size_mb() -> float:
    """取得 DB 檔案大小 (MB)。"""
    try:
        return os.path.getsize(DB_PATH) / (1024 * 1024)
    except Exception:
        return 0.0


def get_last_etl_time() -> str:
    """取得最後一次 ETL 執行時間。"""
    try:
        df = query_db("SELECT MAX(created_at) as last_run FROM extraction_log")
        val = df.iloc[0]["last_run"]
        return str(val) if val else "尚無記錄"
    except Exception:
        return "尚無記錄"


# ── 頁面配置 ──
st.set_page_config(
    page_title="Political Alpha Monitor",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ── 側邊欄 ──
def render_sidebar():
    """渲染側邊欄：導覽、全域篩選、系統狀態。"""
    st.sidebar.title("Political Alpha Monitor")
    st.sidebar.caption("國會交易智慧分析系統")

    page = st.sidebar.radio(
        "導覽",
        [
            "總覽儀表板",
            "Alpha 訊號",
            "投資組合",
            "政治人物排名",
            "匯聚訊號",
            "交易瀏覽器",
            "訊號品質分析",
            "訊號績效追蹤",
            "板塊輪動",
        ],
    )

    st.sidebar.markdown("---")
    st.sidebar.subheader("全域篩選")

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
        "日期範圍",
        value=(min_date.date(), max_date.date()),
        min_value=min_date.date(),
        max_value=max_date.date(),
    )

    chamber_filter = st.sidebar.multiselect(
        "院別", ["House", "Senate"], default=["House", "Senate"]
    )

    st.sidebar.markdown("---")
    st.sidebar.subheader("系統狀態")

    col1, col2 = st.sidebar.columns(2)
    col1.metric("交易數", get_table_count("congress_trades"))
    col2.metric("訊號數", get_table_count("alpha_signals"))

    col3, col4 = st.sidebar.columns(2)
    col3.metric("持倉數", get_table_count("portfolio_positions"))
    col4.metric("DB 大小", f"{get_db_size_mb():.1f} MB")

    st.sidebar.caption(f"最後 ETL: {get_last_etl_time()}")

    if st.sidebar.button("重新整理資料"):
        st.cache_data.clear()
        st.rerun()

    # Ensure date_range is a tuple of two
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = date_range
    else:
        start_date = min_date.date()
        end_date = max_date.date()

    return page, str(start_date), str(end_date), chamber_filter


# ══════════════════════════════════════════════
# Page 1: 總覽儀表板
# ══════════════════════════════════════════════
def page_overview(start_date: str, end_date: str, chambers: List[str]):
    st.header("總覽儀表板")

    # KPI cards
    total_trades = get_table_count("congress_trades")
    active_signals = get_table_count("alpha_signals")
    portfolio_pos = get_table_count("portfolio_positions")

    sqs_df = query_db("SELECT AVG(sqs) as avg_sqs FROM signal_quality_scores")
    avg_sqs = sqs_df.iloc[0]["avg_sqs"] or 0

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("總交易數", f"{total_trades:,}")
    k2.metric("活躍訊號", f"{active_signals:,}")
    k3.metric("投資組合持倉", f"{portfolio_pos}")
    k4.metric("平均 SQS 分數", f"{avg_sqs:.1f}")

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
            st.plotly_chart(fig, use_container_width=True)
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
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("尚無訊號資料")

    # Recent activity timeline
    st.subheader("近期活動 (最新 10 筆交易)")
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
                "politician_name": "政治人物",
                "ticker": "代碼",
                "transaction_type": "類型",
                "amount_range": "金額範圍",
                "transaction_date": "交易日",
                "filing_date": "申報日",
                "chamber": "院別",
            }),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("目前日期範圍內無交易資料")


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

    # Color-coded table
    def color_strength(val):
        if pd.isna(val):
            return ""
        if val >= 0.8:
            return "background-color: rgba(74, 222, 128, 0.2)"
        elif val >= 0.5:
            return "background-color: rgba(251, 191, 36, 0.2)"
        else:
            return "background-color: rgba(248, 113, 113, 0.2)"

    display_df = signals_df.rename(columns={
        "ticker": "代碼", "asset_name": "資產名稱", "politician_name": "政治人物",
        "chamber": "院別", "direction": "方向", "signal_strength": "訊號強度",
        "expected_alpha_5d": "Alpha 5d%", "expected_alpha_20d": "Alpha 20d%",
        "confidence": "信心度", "sqs_score": "SQS", "sqs_grade": "等級",
        "filing_lag_days": "申報延遲(天)", "created_at": "建立時間",
    })
    st.dataframe(
        display_df.style.applymap(color_strength, subset=["訊號強度"]),
        use_container_width=True,
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
    st.plotly_chart(fig, use_container_width=True)


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
        st.plotly_chart(fig, use_container_width=True)

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
        st.plotly_chart(fig, use_container_width=True)

    # Positions table
    st.subheader("所有持倉")
    display_pos = pos_df[["ticker", "sector", "weight", "conviction_score",
                           "expected_alpha", "volatility_30d", "sharpe_estimate"]].copy()
    display_pos["weight"] = display_pos["weight"].apply(lambda x: f"{x:.2%}" if pd.notna(x) else "-")
    display_pos["expected_alpha"] = display_pos["expected_alpha"].apply(lambda x: f"{x:.4f}" if pd.notna(x) else "-")
    display_pos["volatility_30d"] = display_pos["volatility_30d"].apply(lambda x: f"{x:.2%}" if pd.notna(x) else "-")
    display_pos.rename(columns={
        "ticker": "代碼", "sector": "板塊", "weight": "權重",
        "conviction_score": "信念分數", "expected_alpha": "預期 Alpha",
        "volatility_30d": "30日波動率", "sharpe_estimate": "Sharpe",
    }, inplace=True)
    st.dataframe(display_pos, use_container_width=True, hide_index=True)


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
        st.plotly_chart(fig, use_container_width=True)

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
        st.plotly_chart(fig, use_container_width=True)

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
    st.dataframe(display_rank, use_container_width=True, hide_index=True)

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
            st.dataframe(trades_df, use_container_width=True, hide_index=True)
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

    # Highlight strongest
    top = conv_df.iloc[0]
    st.success(
        f"最強匯聚: **{top['ticker']}** — {top['direction']} | "
        f"分數: {top['score']:.3f} | "
        f"涉及 {top['politician_count']} 位政治人物 ({top['politicians']})"
    )

    # Table
    display_conv = conv_df[["ticker", "direction", "politician_count", "politicians",
                             "chambers", "window_start", "window_end", "span_days",
                             "score", "detected_at"]].copy()
    display_conv.rename(columns={
        "ticker": "代碼", "direction": "方向", "politician_count": "政治人物數",
        "politicians": "涉及政治人物", "chambers": "院別", "window_start": "窗口起始",
        "window_end": "窗口結束", "span_days": "天數跨度",
        "score": "匯聚分數", "detected_at": "偵測時間",
    }, inplace=True)
    st.dataframe(display_conv, use_container_width=True, hide_index=True)

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
    st.dataframe(score_df, use_container_width=True, hide_index=True)

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
        st.plotly_chart(fig, use_container_width=True)


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
        st.dataframe(display_trades, use_container_width=True, hide_index=True, height=500)

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
            st.plotly_chart(fig, use_container_width=True)
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
        st.plotly_chart(fig, use_container_width=True)

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
        st.plotly_chart(fig, use_container_width=True)

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
        st.plotly_chart(fig, use_container_width=True)

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
    st.dataframe(top_sqs, use_container_width=True, hide_index=True)


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

    if has_5d.sum() > 0:
        hr_5d = perf_df.loc[has_5d, "hit_5d"].mean() * 100
        avg_alpha_5d = perf_df.loc[has_5d, "actual_alpha_5d"].mean() * 100
        col1.metric("5 日勝率", f"{hr_5d:.1f}%")
        col2.metric("5 日平均 Alpha", f"{avg_alpha_5d:+.2f}%")
    else:
        col1.metric("5 日勝率", "N/A")
        col2.metric("5 日平均 Alpha", "N/A")

    if has_20d.sum() > 0:
        hr_20d = perf_df.loc[has_20d, "hit_20d"].mean() * 100
        avg_alpha_20d = perf_df.loc[has_20d, "actual_alpha_20d"].mean() * 100
        col3.metric("20 日勝率", f"{hr_20d:.1f}%")
        col4.metric("20 日平均 Alpha", f"{avg_alpha_20d:+.2f}%")
    else:
        col3.metric("20 日勝率", "N/A")
        col4.metric("20 日平均 Alpha", "N/A")

    col5, col6 = st.columns(2)
    col5.metric("已評估訊號", f"{len(perf_df)}")
    with_returns = (perf_df["actual_alpha_5d"].notna() | perf_df["actual_alpha_20d"].notna()).sum()
    col6.metric("有實際報酬", f"{with_returns}")

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
        st.plotly_chart(fig, use_container_width=True)

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
        st.plotly_chart(fig2, use_container_width=True)

    # Performance table
    st.subheader("績效明細")
    display_cols = ["ticker", "direction", "signal_strength", "confidence",
                    "actual_alpha_5d", "actual_alpha_20d", "hit_5d", "hit_20d",
                    "max_favorable_excursion", "max_adverse_excursion", "evaluated_at"]
    avail_cols = [c for c in display_cols if c in perf_df.columns]
    st.dataframe(perf_df[avail_cols].head(50), use_container_width=True, hide_index=True)


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
    st.plotly_chart(fig, use_container_width=True)

    # Sector details table
    st.subheader("板塊詳細資料")
    display_cols = ["sector", "etf", "direction", "signal_strength", "expected_alpha_20d",
                    "momentum_score", "net_ratio", "trades", "buy_count", "sale_count",
                    "politician_count", "cross_chamber", "rotation_type"]
    avail = [c for c in display_cols if c in sector_df.columns]
    st.dataframe(sector_df[avail], use_container_width=True, hide_index=True)

    # Rotation types
    if "rotation_type" in sector_df.columns:
        st.subheader("輪動類型分布")
        rot_counts = sector_df["rotation_type"].value_counts()
        fig2 = px.pie(values=rot_counts.values, names=rot_counts.index,
                      color_discrete_sequence=PLOTLY_COLORS)
        fig2.update_layout(height=350, margin=dict(t=30))
        st.plotly_chart(fig2, use_container_width=True)


# ══════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════
def main():
    page, start_date, end_date, chambers = render_sidebar()

    if page == "總覽儀表板":
        page_overview(start_date, end_date, chambers)
    elif page == "Alpha 訊號":
        page_alpha_signals(start_date, end_date, chambers)
    elif page == "投資組合":
        page_portfolio()
    elif page == "政治人物排名":
        page_politicians(start_date, end_date, chambers)
    elif page == "匯聚訊號":
        page_convergence()
    elif page == "交易瀏覽器":
        page_trade_explorer(start_date, end_date, chambers)
    elif page == "訊號品質分析":
        page_signal_quality()
    elif page == "訊號績效追蹤":
        page_signal_performance()
    elif page == "板塊輪動":
        page_sector_rotation()


if __name__ == "__main__":
    main()
