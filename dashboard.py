"""Political Alpha Monitor — Web Dashboard v1

國會交易情報系統 Streamlit 儀表板
啟動方式: streamlit run dashboard.py
"""
import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import Optional, List, Tuple

# ── 配置 ──────────────────────────────────────────────
DB_PATH = str(Path(__file__).parent / "data" / "data.db")

st.set_page_config(
    page_title="Political Alpha Monitor",
    page_icon="🏛️",
    layout="wide",
)

# ── 資料庫工具 ────────────────────────────────────────


def get_connection() -> sqlite3.Connection:
    """取得 SQLite 連線（唯讀模式）"""
    return sqlite3.connect(DB_PATH)


def run_query(sql: str, params: Optional[List] = None) -> pd.DataFrame:
    """執行 SQL 查詢並回傳 DataFrame"""
    try:
        conn = get_connection()
        df = pd.read_sql_query(sql, conn, params=params or [])
        conn.close()
        return df
    except Exception as e:
        st.error(f"資料庫查詢錯誤: {e}")
        return pd.DataFrame()


def table_exists(table_name: str) -> bool:
    """檢查資料表是否存在"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        )
        result = cursor.fetchone()
        conn.close()
        return result is not None
    except Exception:
        return False


# ── 首頁 ─────────────────────────────────────────────

def show_home():
    st.title("🏛️ Political Alpha Monitor")
    st.caption("國會交易情報系統 — 今日概覽")

    if not table_exists("congress_trades"):
        st.warning("尚未建立 congress_trades 資料表，請先執行 ETL Pipeline。")
        return

    today = date.today().isoformat()
    week_ago = (date.today() - timedelta(days=7)).isoformat()

    # ── 指標卡 ──
    col1, col2, col3 = st.columns(3)

    # 今日新增
    df_today = run_query(
        "SELECT COUNT(*) AS cnt FROM congress_trades WHERE DATE(created_at) = ?",
        [today],
    )
    today_count = int(df_today["cnt"].iloc[0]) if not df_today.empty else 0

    # 本週新增
    df_week = run_query(
        "SELECT COUNT(*) AS cnt FROM congress_trades WHERE DATE(created_at) >= ?",
        [week_ago],
    )
    week_count = int(df_week["cnt"].iloc[0]) if not df_week.empty else 0

    # 北極星指標：本週可交易信號（有 ticker + confidence >= 0.7）
    df_signals = run_query(
        """SELECT COUNT(*) AS cnt FROM congress_trades
           WHERE DATE(created_at) >= ?
             AND ticker IS NOT NULL
             AND ticker != ''
             AND extraction_confidence >= 0.7""",
        [week_ago],
    )
    signal_count = int(df_signals["cnt"].iloc[0]) if not df_signals.empty else 0

    with col1:
        st.metric(label="📅 今日新增交易", value=today_count)
    with col2:
        st.metric(label="📆 本週新增交易", value=week_count)
    with col3:
        st.metric(label="⭐ 本週可交易信號", value=signal_count)

    st.markdown("---")

    # ── 最新 5 筆交易 ──
    st.subheader("📋 最新 5 筆交易")
    df_recent = run_query(
        """SELECT politician_name, chamber, ticker, asset_name,
                  transaction_type, amount_range, transaction_date,
                  extraction_confidence
           FROM congress_trades
           ORDER BY created_at DESC
           LIMIT 5"""
    )
    if df_recent.empty:
        st.info("目前沒有交易紀錄。請執行 ETL Pipeline 抓取資料。")
    else:
        df_recent.columns = [
            "議員", "院別", "Ticker", "資產名稱",
            "交易類型", "金額區間", "交易日期", "信心分數",
        ]
        st.dataframe(df_recent, use_container_width=True)


# ── 交易瀏覽頁 ───────────────────────────────────────

def show_trades():
    st.title("📊 交易瀏覽")

    if not table_exists("congress_trades"):
        st.warning("尚未建立 congress_trades 資料表，請先執行 ETL Pipeline。")
        return

    # ── 側邊欄篩選器 ──
    st.sidebar.markdown("### 🔍 篩選條件")

    default_start = date.today() - timedelta(days=90)
    default_end = date.today()

    date_start = st.sidebar.date_input("開始日期", value=default_start)
    date_end = st.sidebar.date_input("結束日期", value=default_end)

    politician_filter = st.sidebar.text_input("議員姓名（模糊搜尋）", value="")
    ticker_filter = st.sidebar.text_input("Ticker", value="")

    tx_type = st.sidebar.selectbox(
        "交易類型", ["All", "Buy", "Sale", "Exchange"]
    )
    chamber_type = st.sidebar.selectbox(
        "院別", ["All", "Senate", "House"]
    )

    # ── 組裝查詢 ──
    conditions = ["1=1"]
    params = []  # type: List

    if date_start and date_end:
        conditions.append("transaction_date BETWEEN ? AND ?")
        params.extend([date_start.isoformat(), date_end.isoformat()])

    if politician_filter.strip():
        conditions.append("politician_name LIKE ?")
        params.append(f"%{politician_filter.strip()}%")

    if ticker_filter.strip():
        conditions.append("ticker = ?")
        params.append(ticker_filter.strip().upper())

    if tx_type != "All":
        conditions.append("transaction_type = ?")
        params.append(tx_type)

    if chamber_type != "All":
        conditions.append("chamber = ?")
        params.append(chamber_type)

    where_clause = " AND ".join(conditions)

    df_trades = run_query(
        f"""SELECT politician_name, chamber, ticker, asset_name,
                   transaction_type, amount_range, transaction_date,
                   filing_date, owner, extraction_confidence, source_url
            FROM congress_trades
            WHERE {where_clause}
            ORDER BY transaction_date DESC
            LIMIT 500""",
        params,
    )

    # ── 結果 ──
    st.caption(f"共 {len(df_trades)} 筆紀錄（上限 500 筆）")

    if df_trades.empty:
        st.info("沒有符合條件的交易紀錄。")
    else:
        df_display = df_trades.copy()
        df_display.columns = [
            "議員", "院別", "Ticker", "資產名稱",
            "交易類型", "金額區間", "交易日期",
            "申報日期", "持有人", "信心分數", "來源連結",
        ]
        st.dataframe(df_display, use_container_width=True)

        # ── 議員交易次數統計 bar chart ──
        st.markdown("---")
        st.subheader("📊 議員交易次數統計 (Top 20)")

        df_by_politician = (
            df_trades.groupby("politician_name")
            .size()
            .reset_index(name="交易次數")
            .sort_values("交易次數", ascending=False)
            .head(20)
        )
        df_by_politician = df_by_politician.rename(
            columns={"politician_name": "議員"}
        )
        df_by_politician = df_by_politician.set_index("議員")
        st.bar_chart(df_by_politician)


# ── AI 信號頁 ─────────────────────────────────────────

def show_signals():
    st.title("🤖 AI 信號")

    if not table_exists("ai_intelligence_signals"):
        st.warning("尚未建立 ai_intelligence_signals 資料表，請先執行 AI Discovery。")
        return

    df_signals = run_query(
        """SELECT source_type, source_name, ticker, impact_score,
                  sentiment, logic_reasoning, recommended_execution,
                  timestamp
           FROM ai_intelligence_signals
           ORDER BY impact_score DESC
           LIMIT 100"""
    )

    if df_signals.empty:
        st.info("目前沒有 AI 分析信號。請執行 run_congress_discovery.py 生成信號。")
        return

    # ── 摘要指標 ──
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("信號總數", len(df_signals))
    with col2:
        avg_score = df_signals["impact_score"].mean()
        st.metric("平均影響力分數", f"{avg_score:.1f}")
    with col3:
        open_count = len(df_signals[df_signals["recommended_execution"] == "OPEN"])
        st.metric("OPEN 信號數", open_count)

    st.markdown("---")

    # ── 信號列表 ──
    for _, row in df_signals.iterrows():
        score = row["impact_score"]
        ticker = row["ticker"] or "N/A"
        source_name = row["source_name"]
        sentiment = row["sentiment"] or "N/A"
        execution = row["recommended_execution"] or "N/A"
        timestamp = row["timestamp"] or ""

        # 根據分數設定顏色標籤
        if score is not None and score >= 8:
            score_badge = f"🔴 {score}"
        elif score is not None and score >= 5:
            score_badge = f"🟡 {score}"
        else:
            score_badge = f"🟢 {score}"

        header = (
            f"**{ticker}** | {source_name} | "
            f"影響力: {score_badge} | "
            f"情緒: {sentiment} | "
            f"建議: {execution}"
        )

        with st.expander(header, expanded=False):
            st.markdown(f"**來源類型:** {row['source_type']}")
            st.markdown(f"**時間:** {timestamp}")
            st.markdown("**分析推理:**")
            reasoning = row["logic_reasoning"] or "（無推理內容）"
            st.markdown(reasoning)


# ── 數據品質頁 ────────────────────────────────────────

def show_quality():
    st.title("📈 數據品質")

    if not table_exists("congress_trades"):
        st.warning("尚未建立 congress_trades 資料表，請先執行 ETL Pipeline。")
        return

    # ── 整體指標 ──
    col1, col2, col3 = st.columns(3)

    # 總交易數
    df_total = run_query("SELECT COUNT(*) AS cnt FROM congress_trades")
    total_count = int(df_total["cnt"].iloc[0]) if not df_total.empty else 0

    # 有 Ticker 的交易數
    df_ticker = run_query(
        "SELECT COUNT(*) AS cnt FROM congress_trades WHERE ticker IS NOT NULL AND ticker != ''"
    )
    ticker_count = int(df_ticker["cnt"].iloc[0]) if not df_ticker.empty else 0

    # Ticker 覆蓋率
    coverage = (ticker_count / total_count * 100) if total_count > 0 else 0.0

    with col1:
        st.metric("總交易筆數", total_count)
    with col2:
        st.metric("有 Ticker 交易數", ticker_count)
    with col3:
        st.metric("Ticker 覆蓋率", f"{coverage:.1f}%")

    st.markdown("---")

    # ── extraction_confidence 分布直方圖 ──
    st.subheader("📊 信心分數分布")
    df_conf = run_query(
        "SELECT extraction_confidence FROM congress_trades WHERE extraction_confidence IS NOT NULL"
    )
    if not df_conf.empty:
        # 使用 Streamlit 原生 bar_chart 做直方圖近似
        import numpy as np

        hist_values, bin_edges = np.histogram(
            df_conf["extraction_confidence"].dropna(), bins=10, range=(0, 1)
        )
        bin_labels = [f"{bin_edges[i]:.1f}-{bin_edges[i+1]:.1f}" for i in range(len(hist_values))]
        df_hist = pd.DataFrame({"區間": bin_labels, "筆數": hist_values})
        df_hist = df_hist.set_index("區間")
        st.bar_chart(df_hist)

        # 基本統計
        avg_conf = df_conf["extraction_confidence"].mean()
        median_conf = df_conf["extraction_confidence"].median()
        st.caption(f"平均信心分數: {avg_conf:.3f} | 中位數: {median_conf:.3f}")
    else:
        st.info("沒有信心分數資料。")

    st.markdown("---")

    # ── ETL 萃取紀錄 ──
    st.subheader("🔄 ETL 萃取紀錄")

    if not table_exists("extraction_log"):
        st.info("尚未建立 extraction_log 資料表。")
        return

    df_log = run_query(
        "SELECT source_type, status, COUNT(*) AS cnt FROM extraction_log GROUP BY source_type, status"
    )

    if df_log.empty:
        st.info("沒有 ETL 萃取紀錄。")
        return

    # ETL Success Rate
    df_success_total = run_query("SELECT COUNT(*) AS cnt FROM extraction_log")
    df_success_ok = run_query("SELECT COUNT(*) AS cnt FROM extraction_log WHERE status = 'success'")
    log_total = int(df_success_total["cnt"].iloc[0]) if not df_success_total.empty else 0
    log_ok = int(df_success_ok["cnt"].iloc[0]) if not df_success_ok.empty else 0
    success_rate = (log_ok / log_total * 100) if log_total > 0 else 0.0

    st.metric("ETL Success Rate", f"{success_rate:.1f}%")

    # 按 status 統計（bar chart）
    st.subheader("萃取狀態統計")
    df_status = run_query(
        "SELECT status, COUNT(*) AS cnt FROM extraction_log GROUP BY status"
    )
    if not df_status.empty:
        df_status_chart = df_status.set_index("status")
        df_status_chart.columns = ["筆數"]
        st.bar_chart(df_status_chart)

    # 按 source_type 統計
    st.subheader("依來源類型統計")
    df_source = run_query(
        "SELECT source_type, COUNT(*) AS cnt FROM extraction_log GROUP BY source_type"
    )
    if not df_source.empty:
        df_source_chart = df_source.set_index("source_type")
        df_source_chart.columns = ["筆數"]
        st.bar_chart(df_source_chart)

    # 詳細紀錄表
    st.markdown("---")
    st.subheader("📋 最近 20 筆萃取紀錄")
    df_recent_log = run_query(
        """SELECT source_type, source_url, confidence,
                  raw_record_count, extracted_count, status,
                  error_message, created_at
           FROM extraction_log
           ORDER BY created_at DESC
           LIMIT 20"""
    )
    if not df_recent_log.empty:
        df_recent_log.columns = [
            "來源類型", "來源 URL", "信心分數",
            "原始筆數", "萃取筆數", "狀態",
            "錯誤訊息", "建立時間",
        ]
        st.dataframe(df_recent_log, use_container_width=True)


# ── 主路由 ────────────────────────────────────────────

def main():
    # 檢查 DB 是否存在
    if not Path(DB_PATH).exists():
        st.error(
            f"找不到資料庫: {DB_PATH}\n\n"
            "請先執行: `python -c \"from src.database import init_db; init_db()\"`"
        )
        return

    # 側邊欄導航
    page = st.sidebar.selectbox(
        "📌 導航",
        ["🏠 首頁", "📊 交易瀏覽", "🤖 AI 信號", "📈 數據品質"],
    )

    if page == "🏠 首頁":
        show_home()
    elif page == "📊 交易瀏覽":
        show_trades()
    elif page == "🤖 AI 信號":
        show_signals()
    elif page == "📈 數據品質":
        show_quality()

    # 頁尾
    st.sidebar.markdown("---")
    st.sidebar.caption(
        "Political Alpha Monitor v1\n\n"
        f"資料庫: `{DB_PATH}`\n\n"
        f"更新時間: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    )


if __name__ == "__main__":
    main()
