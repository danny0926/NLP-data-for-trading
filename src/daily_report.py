"""
Daily Report Generator — 每日國會交易綜合報告
匯整所有資料來源（congress_trades、ai_intelligence_signals、signal_quality_scores、
convergence_signals、politician_rankings、extraction_log）生成單一可操作的 Markdown 報告。

使用方式:
    python -m src.daily_report              # 今日
    python -m src.daily_report --days 7     # 過去 7 天
    python -m src.daily_report --date 2026-02-27
"""

import argparse
import logging
import os
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.config import DB_PATH
from src.logging_config import setup_logging

logger = logging.getLogger("DailyReport")

# ============================================================================
# 工具函式
# ============================================================================


def _pct(part: int, total: int) -> str:
    """計算百分比並格式化為字串。"""
    if total == 0:
        return "0.0%"
    return f"{part / total * 100:.1f}%"


def _amount_to_sortkey(amount_range: Optional[str]) -> int:
    """將金額區間轉為排序用數值（愈大愈高）。"""
    if not amount_range:
        return 0
    mapping = [
        ("$50,000,001", 9), ("$25,000,001", 8), ("$5,000,001", 7),
        ("$1,000,001", 6), ("$500,001", 5), ("$250,001", 4),
        ("$100,001", 3), ("$50,001", 3), ("$15,001", 2), ("$1,001", 1),
    ]
    for prefix, score in mapping:
        if prefix in amount_range:
            return score
    return 0


def _grade_indicator(grade: str) -> str:
    """品質等級指示符號（純文字）。"""
    mapping = {
        "Platinum": "[***]",
        "Gold": "[**]",
        "Silver": "[*]",
        "Bronze": "[.]",
        "Discard": "[-]",
    }
    return mapping.get(grade, "[ ]")


def _safe_query(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> Optional[List[dict]]:
    """安全查詢——表不存在時回傳 None。"""
    try:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]
    except Exception as e:
        logger.warning(f"查詢失敗（表可能不存在）: {e}")
        return None


# ============================================================================
# 資料庫查詢函式（每個表獨立 try/except）
# ============================================================================


def query_trades(conn: sqlite3.Connection, start: str, end: str) -> Optional[List[dict]]:
    """查詢指定日期範圍內的 congress_trades（依交易日期）。"""
    return _safe_query(conn, """
        SELECT id, chamber, politician_name, transaction_date,
               filing_date, ticker, asset_name, asset_type,
               transaction_type, amount_range, owner, comment,
               extraction_confidence, created_at
        FROM congress_trades
        WHERE transaction_date BETWEEN ? AND ?
        ORDER BY transaction_date DESC, politician_name
    """, (start, end))


def query_sqs_for_trades(conn: sqlite3.Connection, trade_ids: List[str]) -> Optional[List[dict]]:
    """查詢這些交易對應的 Signal Quality Scores。"""
    if not trade_ids:
        return []
    placeholders = ",".join("?" for _ in trade_ids)
    return _safe_query(conn, f"""
        SELECT s.trade_id, s.politician_name, s.ticker, s.sqs, s.grade,
               s.action, s.actionability, s.timeliness, s.conviction,
               s.information_edge, s.market_impact, s.scored_at
        FROM signal_quality_scores s
        WHERE s.trade_id IN ({placeholders})
        ORDER BY s.sqs DESC
    """, tuple(trade_ids))


def query_top_sqs(conn: sqlite3.Connection, limit: int = 20) -> Optional[List[dict]]:
    """查詢全域 SQS 排名最高的 Gold+ 訊號。"""
    return _safe_query(conn, """
        SELECT s.trade_id, s.politician_name, s.ticker, s.sqs, s.grade,
               s.action, s.actionability, s.timeliness, s.conviction,
               s.information_edge, s.market_impact,
               ct.transaction_type, ct.amount_range, ct.transaction_date,
               ct.filing_date, ct.chamber, ct.asset_name
        FROM signal_quality_scores s
        JOIN congress_trades ct ON s.trade_id = ct.id
        WHERE s.grade IN ('Platinum', 'Gold')
        ORDER BY s.sqs DESC
        LIMIT ?
    """, (limit,))


def query_sqs_distribution(conn: sqlite3.Connection) -> Optional[List[dict]]:
    """查詢 SQS 等級分布。"""
    return _safe_query(conn, """
        SELECT grade, COUNT(*) as cnt,
               AVG(sqs) as avg_sqs, MIN(sqs) as min_sqs, MAX(sqs) as max_sqs
        FROM signal_quality_scores
        GROUP BY grade
        ORDER BY avg_sqs DESC
    """)


def query_convergence(conn: sqlite3.Connection) -> Optional[List[dict]]:
    """查詢所有 convergence_signals。"""
    return _safe_query(conn, """
        SELECT id, ticker, direction, politician_count, politicians,
               chambers, window_start, window_end, span_days, score,
               score_base, score_cross_chamber, score_time_density,
               score_amount_weight, detected_at
        FROM convergence_signals
        ORDER BY score DESC
    """)


def query_rankings(conn: sqlite3.Connection) -> Optional[List[dict]]:
    """查詢 politician_rankings，依排名排序。"""
    return _safe_query(conn, """
        SELECT politician_name, chamber, total_trades, avg_trade_size,
               trades_per_month, unique_tickers, buy_count, sale_count,
               buy_sale_ratio, avg_filing_lag_days, diversification_ratio,
               pis_activity, pis_conviction, pis_diversification, pis_timing,
               pis_total, rank, updated_at
        FROM politician_rankings
        ORDER BY rank ASC
    """)


def query_ai_signals(conn: sqlite3.Connection, start: str, end: str) -> Optional[List[dict]]:
    """查詢指定日期範圍的 AI intelligence signals。"""
    return _safe_query(conn, """
        SELECT id, source_type, source_name, ticker, impact_score,
               sentiment, logic_reasoning, recommended_execution, timestamp
        FROM ai_intelligence_signals
        WHERE DATE(timestamp) BETWEEN ? AND ?
        ORDER BY impact_score DESC NULLS LAST, timestamp DESC
    """, (start, end))


def query_ai_signals_all(conn: sqlite3.Connection) -> Optional[List[dict]]:
    """查詢所有 AI intelligence signals（用於全域統計）。"""
    return _safe_query(conn, """
        SELECT id, source_type, source_name, ticker, impact_score,
               sentiment, recommended_execution, timestamp
        FROM ai_intelligence_signals
        ORDER BY impact_score DESC NULLS LAST
    """)


def query_extraction_log(conn: sqlite3.Connection, start: str, end: str) -> Optional[List[dict]]:
    """查詢指定日期範圍的 extraction_log。"""
    return _safe_query(conn, """
        SELECT id, source_type, source_url, confidence,
               raw_record_count, extracted_count, status,
               error_message, created_at
        FROM extraction_log
        WHERE DATE(created_at) BETWEEN ? AND ?
        ORDER BY created_at DESC
    """, (start, end))


def query_trades_summary(conn: sqlite3.Connection) -> Optional[dict]:
    """查詢 congress_trades 全域統計。"""
    try:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        cur.execute("SELECT COUNT(*) as total FROM congress_trades")
        total = cur.fetchone()["total"]

        cur.execute("SELECT chamber, COUNT(*) as cnt FROM congress_trades GROUP BY chamber")
        chamber_counts = {r["chamber"]: r["cnt"] for r in cur.fetchall()}

        cur.execute("SELECT MAX(transaction_date) as v FROM congress_trades")
        latest_tx = cur.fetchone()["v"]

        cur.execute("SELECT MAX(created_at) as v FROM congress_trades")
        latest_created = cur.fetchone()["v"]

        cur.execute("SELECT COUNT(DISTINCT politician_name) as v FROM congress_trades")
        unique_pol = cur.fetchone()["v"]

        cur.execute("SELECT COUNT(DISTINCT ticker) as v FROM congress_trades WHERE ticker IS NOT NULL AND ticker != ''")
        unique_tick = cur.fetchone()["v"]

        return {
            "total": total,
            "chamber_counts": chamber_counts,
            "latest_transaction_date": latest_tx,
            "latest_created_at": latest_created,
            "unique_politicians": unique_pol,
            "unique_tickers": unique_tick,
        }
    except Exception as e:
        logger.warning(f"查詢 congress_trades 全域統計失敗: {e}")
        return None


# ============================================================================
# 統計與分析
# ============================================================================


def compute_trade_stats(trades: List[dict]) -> Dict[str, Any]:
    """計算期間內交易統計摘要。"""
    if not trades:
        return {"total": 0, "buys": 0, "sales": 0, "exchanges": 0,
                "senate_count": 0, "house_count": 0, "unique_politicians": 0,
                "unique_tickers": 0, "most_active": [], "top_tickers": [],
                "large_trades": [], "avg_filing_lag": 0, "late_filings_count": 0}

    total = len(trades)
    buys = sum(1 for t in trades if t["transaction_type"] == "Buy")
    sales = sum(1 for t in trades if t["transaction_type"] and "Sale" in t["transaction_type"])
    exchanges = total - buys - sales

    politician_counts = Counter(t["politician_name"] for t in trades)
    most_active = politician_counts.most_common(5)

    tickers = [t["ticker"] for t in trades if t["ticker"]]
    ticker_counts = Counter(tickers)
    top_tickers = ticker_counts.most_common(10)

    senate_count = sum(1 for t in trades if t["chamber"] == "Senate")
    house_count = sum(1 for t in trades if t["chamber"] == "House")

    # 大額交易（>= $250,001）
    large_keywords = ["$250,001", "$500,001", "$1,000,001", "$5,000,001", "$25,000,001",
                      "$50,000,001"]
    large_trades = [t for t in trades if any(k in (t["amount_range"] or "") for k in large_keywords)]

    # 申報延遲分析
    filing_lags = []  # type: List[int]
    for t in trades:
        if t["transaction_date"] and t["filing_date"]:
            try:
                td = datetime.strptime(t["transaction_date"], "%Y-%m-%d")
                fd = datetime.strptime(t["filing_date"], "%Y-%m-%d")
                lag = (fd - td).days
                if lag >= 0:
                    filing_lags.append(lag)
            except (ValueError, TypeError):
                pass
    avg_lag = sum(filing_lags) / len(filing_lags) if filing_lags else 0
    late_filings = [l for l in filing_lags if l > 45]

    return {
        "total": total,
        "buys": buys,
        "sales": sales,
        "exchanges": exchanges,
        "senate_count": senate_count,
        "house_count": house_count,
        "unique_politicians": len(politician_counts),
        "unique_tickers": len(ticker_counts),
        "most_active": most_active,
        "top_tickers": top_tickers,
        "large_trades": large_trades,
        "avg_filing_lag": avg_lag,
        "late_filings_count": len(late_filings),
    }


# ============================================================================
# Markdown 報告區段生成
# ============================================================================


def _section_executive_summary(
    stats: Dict[str, Any],
    top_sqs: Optional[List[dict]],
    convergence: Optional[List[dict]],
    ai_signals: Optional[List[dict]],
    db_summary: Optional[dict],
) -> str:
    """## 1. 執行摘要 (Executive Summary)"""
    lines = ["## 1. 執行摘要 (Executive Summary)"]

    if stats["total"] == 0:
        lines.append("\n本期間無新交易紀錄。")
        if db_summary:
            lines.append(f"\n> 資料庫總計 {db_summary['total']} 筆交易，"
                         f"最新交易日期 {db_summary['latest_transaction_date']}。")
        return "\n".join(lines)

    # 核心數字表格
    lines.append("")
    lines.append("| 指標 | 數值 |")
    lines.append("|------|------|")
    lines.append(f"| 交易總筆數 | **{stats['total']}** |")
    lines.append(f"| 買入 / 賣出 / 其他 | {stats['buys']} / {stats['sales']} / {stats['exchanges']} |")
    lines.append(f"| Senate / House | {stats['senate_count']} / {stats['house_count']} |")
    lines.append(f"| 不重複議員 | {stats['unique_politicians']} |")
    lines.append(f"| 不重複 Ticker | {stats['unique_tickers']} |")
    lines.append(f"| 大額交易 (>=$250K) | {len(stats['large_trades'])} 筆 |")
    lines.append(f"| 平均申報延遲 | {stats['avg_filing_lag']:.1f} 天 |")
    lines.append(f"| 延遲申報 (>45天) | {stats['late_filings_count']} 筆 |")

    # Gold+ 訊號數量
    gold_plus_count = len(top_sqs) if top_sqs else 0
    lines.append(f"| Gold+ 等級訊號 | {gold_plus_count} 筆 |")

    # Convergence 數量
    conv_count = len(convergence) if convergence else 0
    lines.append(f"| Convergence 警報 | {conv_count} 筆 |")

    # AI 訊號
    ai_count = len(ai_signals) if ai_signals else 0
    lines.append(f"| AI Intelligence 訊號 | {ai_count} 筆 |")

    # 買賣比
    if stats["sales"] > 0:
        ratio = stats["buys"] / stats["sales"]
        if ratio > 1.5:
            sentiment = "偏多 (買入主導)"
        elif ratio < 0.67:
            sentiment = "偏空 (賣出主導)"
        else:
            sentiment = "中性"
        lines.append(f"| 買賣比 (B/S Ratio) | {ratio:.2f} -- {sentiment} |")
    else:
        if stats["buys"] > 0:
            lines.append("| 買賣比 (B/S Ratio) | N/A (無賣出) |")

    # 最活躍議員
    if stats["most_active"]:
        active_str = ", ".join(f"{name} ({cnt}筆)" for name, cnt in stats["most_active"][:3])
        lines.append("")
        lines.append(f"**最活躍議員**: {active_str}")

    # 熱門 Ticker
    if stats["top_tickers"]:
        ticker_str = ", ".join(f"`{t}` ({c}筆)" for t, c in stats["top_tickers"][:5])
        lines.append(f"\n**熱門標的**: {ticker_str}")

    # 資料庫全域快照
    if db_summary:
        lines.append("")
        lines.append(f"> 資料庫快照: 共 {db_summary['total']} 筆交易 | "
                     f"{db_summary['unique_politicians']} 位議員 | "
                     f"{db_summary['unique_tickers']} 檔標的 | "
                     f"最新交易日 {db_summary['latest_transaction_date']}")

    return "\n".join(lines)


def _section_new_trades(
    trades: List[dict],
    sqs_map: Dict[str, dict],
    stats: Dict[str, Any],
    start_date: str,
    end_date: str,
) -> str:
    """## 2. 新交易明細 (New Trades)"""
    lines = ["## 2. 新交易明細 (New Trades)"]

    if not trades:
        lines.append(f"\n{start_date} ~ {end_date} 期間無新交易。")
        return "\n".join(lines)

    lines.append(f"\n共 **{len(trades)}** 筆交易（{start_date} ~ {end_date}）。以下依金額排序，列出前 30 筆：\n")

    # 依金額排序
    sorted_trades = sorted(trades, key=lambda t: _amount_to_sortkey(t["amount_range"]), reverse=True)

    lines.append("| # | 議員 | 院別 | Ticker | 買/賣 | 金額區間 | 交易日 | SQS | 等級 |")
    lines.append("|---|------|------|--------|-------|----------|--------|-----|------|")

    for i, t in enumerate(sorted_trades[:30], 1):
        ticker = t["ticker"] or "N/A"
        txn = t["transaction_type"] or "N/A"
        amount = t["amount_range"] or "N/A"
        tx_date = t["transaction_date"] or "N/A"

        sqs_info = sqs_map.get(t["id"])
        if sqs_info:
            sqs_val = f"{sqs_info['sqs']:.1f}"
            grade = sqs_info["grade"]
        else:
            sqs_val = "-"
            grade = "-"

        lines.append(
            f"| {i} | {t['politician_name']} | {t['chamber']} | "
            f"`{ticker}` | {txn} | {amount} | {tx_date} | {sqs_val} | {grade} |"
        )

    if len(trades) > 30:
        lines.append(f"\n*（僅顯示前 30 筆，共 {len(trades)} 筆）*")

    # 大額交易警示
    if stats["large_trades"]:
        lines.append(f"\n### 大額交易警示 (>= $250K)\n")
        for t in stats["large_trades"]:
            ticker = t["ticker"] or "N/A"
            lines.append(
                f"- **{t['politician_name']}** ({t['chamber']}) -- "
                f"`{ticker}` {t['transaction_type']} **{t['amount_range']}** "
                f"({t['transaction_date']})"
            )

    return "\n".join(lines)


def _section_top_signals(top_sqs: Optional[List[dict]], sqs_dist: Optional[List[dict]]) -> str:
    """## 3. 最佳可操作訊號 (Top Actionable Signals)"""
    lines = ["## 3. 最佳可操作訊號 (Top Actionable Signals)"]
    lines.append("\n> SQS 品質等級: Platinum (80+) > Gold (60-79) > Silver (40-59) > Bronze (20-39) > Discard (<20)")

    # SQS 分布統計
    if sqs_dist:
        lines.append("\n### 等級分布\n")
        lines.append("| 等級 | 筆數 | 平均 SQS | 最低 | 最高 |")
        lines.append("|------|------|----------|------|------|")
        grade_order = ["Platinum", "Gold", "Silver", "Bronze", "Discard"]
        dist_map = {d["grade"]: d for d in sqs_dist}
        for g in grade_order:
            d = dist_map.get(g)
            if d:
                lines.append(
                    f"| {_grade_indicator(g)} {g} | {d['cnt']} | "
                    f"{d['avg_sqs']:.1f} | {d['min_sqs']:.1f} | {d['max_sqs']:.1f} |"
                )
            else:
                lines.append(f"| {_grade_indicator(g)} {g} | 0 | - | - | - |")

    # Gold+ 明細
    if not top_sqs:
        lines.append("\n目前無 Gold 以上等級的訊號。")
        return "\n".join(lines)

    lines.append(f"\n### Gold+ 訊號明細（共 {len(top_sqs)} 筆）\n")
    lines.append("| # | 等級 | SQS | 議員 | Ticker | 資產 | 買/賣 | 金額 | 交易日 | A | T | C | I | M |")
    lines.append("|---|------|-----|------|--------|------|-------|------|--------|---|---|---|---|---|")

    for i, s in enumerate(top_sqs, 1):
        ticker = s["ticker"] or "N/A"
        txn = s.get("transaction_type") or "N/A"
        amount = s.get("amount_range") or "N/A"
        tx_date = s.get("transaction_date") or "N/A"
        asset = (s.get("asset_name") or "N/A")[:25]
        indicator = _grade_indicator(s["grade"])

        lines.append(
            f"| {i} | {indicator} {s['grade']} | **{s['sqs']:.1f}** | "
            f"{s['politician_name']} | `{ticker}` | {asset} | {txn} | {amount} | {tx_date} | "
            f"{s['actionability']:.0f} | {s['timeliness']:.0f} | {s['conviction']:.0f} | "
            f"{s['information_edge']:.0f} | {s['market_impact']:.0f} |"
        )

    lines.append("")
    lines.append("> **維度說明**: A=可操作性(30%) T=時效性(20%) C=確信度(25%) I=資訊優勢(15%) M=市場影響(10%)")

    return "\n".join(lines)


def _section_convergence(convergence: Optional[List[dict]]) -> str:
    """## 4. Convergence 警報（多議員同向操作）"""
    lines = ["## 4. Convergence 警報 (多議員同向操作)"]

    if convergence is None:
        lines.append("\n> convergence_signals 資料表不存在或查詢失敗。")
        lines.append("> 執行 `python -m src.convergence_detector` 可建立此資料表。")
        return "\n".join(lines)

    if not convergence:
        lines.append("\n目前無 convergence 訊號。")
        return "\n".join(lines)

    buy_events = [c for c in convergence if c["direction"] == "Buy"]
    sale_events = [c for c in convergence if c["direction"] != "Buy"]

    lines.append(
        f"\n> 當多位議員在短時間窗口內對同一標的進行同方向操作時觸發。"
        f" 跨院 (Cross-Chamber) 訊號更具參考價值。"
    )
    lines.append(f"\n- 匯聚事件總數: **{len(convergence)}** (買入 {len(buy_events)} / 賣出 {len(sale_events)})\n")

    for i, c in enumerate(convergence, 1):
        cross = "Cross-Chamber" if "/" in (c.get("chambers") or "") else "Single-Chamber"
        direction_label = "買入" if c["direction"] == "Buy" else "賣出"
        lines.append(f"### 4.{i} `{c['ticker']}` -- {direction_label} ({cross})")
        lines.append("")
        lines.append(f"- **Convergence Score**: {c['score']:.3f}")
        lines.append(f"- **議員數**: {c['politician_count']} 人")
        lines.append(f"- **參與議員**: {c['politicians']}")
        lines.append(f"- **院別**: {c['chambers']}")
        lines.append(f"- **時間窗口**: {c['window_start']} ~ {c['window_end']} ({c['span_days']} 天)")

        # 分數明細
        base = c.get("score_base") or 0
        cross_s = c.get("score_cross_chamber") or 0
        density = c.get("score_time_density") or 0
        amount_w = c.get("score_amount_weight") or 0
        lines.append(
            f"- **分數明細**: base={base:.3f} + cross_chamber={cross_s:.3f} + "
            f"time_density={density:.3f} + amount_weight={amount_w:.3f}"
        )
        lines.append("")

    return "\n".join(lines)


def _section_politician_watchlist(rankings: Optional[List[dict]]) -> str:
    """## 5. 議員觀察清單 (Politician Watch List)"""
    lines = ["## 5. 議員觀察清單 (Politician Watch List)"]
    lines.append("\n> PIS (Politician Influence Score) 綜合評分，基於活躍度、確信度、分散度、時效性。\n")

    if rankings is None:
        lines.append("> politician_rankings 資料表不存在或查詢失敗。")
        lines.append("> 執行 `python -m src.politician_ranking` 可建立此資料表。")
        return "\n".join(lines)

    if not rankings:
        lines.append("目前無議員排名資料。")
        return "\n".join(lines)

    lines.append("| Rank | 議員 | 院別 | 交易數 | PIS 總分 | 等級 | 活躍度 | 確信度 | 分散度 | 時效性 | 買/賣 | 平均延遲 |")
    lines.append("|------|------|------|--------|----------|------|--------|--------|--------|--------|-------|----------|")

    for r in rankings:
        pis = r["pis_total"]
        if pis >= 75:
            grade_tag = "A"
        elif pis >= 50:
            grade_tag = "B"
        elif pis >= 25:
            grade_tag = "C"
        else:
            grade_tag = "D"

        buy_sale = f"{r['buy_count']}/{r['sale_count']}"
        lines.append(
            f"| {r['rank']} | **{r['politician_name']}** | {r['chamber']} | "
            f"{r['total_trades']} | **{pis:.1f}** | {grade_tag} | "
            f"{r['pis_activity']:.1f} | {r['pis_conviction']:.1f} | "
            f"{r['pis_diversification']:.1f} | {r['pis_timing']:.1f} | "
            f"{buy_sale} | {r['avg_filing_lag_days']:.1f}天 |"
        )

    return "\n".join(lines)


def _section_ai_signals(
    signals_period: Optional[List[dict]],
    signals_all: Optional[List[dict]],
    start_date: str,
    end_date: str,
) -> str:
    """## 6. AI Intelligence Signals"""
    lines = ["## 6. AI Intelligence 訊號"]

    if signals_period is None and signals_all is None:
        lines.append("\n> ai_intelligence_signals 資料表不存在或查詢失敗。")
        return "\n".join(lines)

    # 期間訊號
    period_list = signals_period or []
    all_list = signals_all or []

    # 全域統計
    if all_list:
        total_all = len(all_list)
        has_ticker = sum(1 for s in all_list if s.get("ticker"))
        has_score = sum(1 for s in all_list if s.get("impact_score") is not None)
        lines.append(f"\n**全域統計**: {total_all} 筆訊號 | "
                     f"{has_ticker} 筆含 ticker | {has_score} 筆含 impact score")

    # 期間訊號
    if period_list:
        actionable = [s for s in period_list if s.get("impact_score") and s.get("ticker")]
        lines.append(f"\n**本期 ({start_date} ~ {end_date})**: "
                     f"{len(period_list)} 筆訊號（{len(actionable)} 筆可操作）\n")

        if actionable:
            # 按 impact_score 排序
            actionable.sort(key=lambda x: x.get("impact_score") or 0, reverse=True)
            lines.append("| # | 來源 | 對象 | Ticker | Impact | Sentiment | 建議 | 時間 |")
            lines.append("|---|------|------|--------|--------|-----------|------|------|")
            for i, s in enumerate(actionable[:20], 1):
                lines.append(
                    f"| {i} | {s['source_type']} | {s['source_name']} | "
                    f"`{s['ticker']}` | **{s['impact_score']}**/10 | {s.get('sentiment') or 'N/A'} | "
                    f"{s.get('recommended_execution') or 'N/A'} | {str(s.get('timestamp', ''))[:16]} |"
                )

            # 高影響力訊號摘要
            high_impact = [s for s in actionable if (s.get("impact_score") or 0) >= 8]
            if high_impact:
                lines.append(f"\n> **高影響力 (score >= 8)**: {len(high_impact)} 筆 -- "
                             + ", ".join(f"`{s['ticker']}`({s['source_name']})" for s in high_impact[:5]))
        else:
            lines.append("*本期所有 AI 訊號均缺少 ticker 或 impact score。*")
    else:
        lines.append(f"\n{start_date} ~ {end_date} 期間無 AI 訊號。")

        # 顯示全域 top 訊號
        if all_list:
            scored = [s for s in all_list if s.get("impact_score") and s.get("ticker")]
            scored.sort(key=lambda x: x.get("impact_score") or 0, reverse=True)
            top5 = scored[:5]
            if top5:
                lines.append("\n**全域 Top 5 訊號（歷史）:**\n")
                lines.append("| 來源 | 對象 | Ticker | Impact | Sentiment | 建議 |")
                lines.append("|------|------|--------|--------|-----------|------|")
                for s in top5:
                    lines.append(
                        f"| {s['source_type']} | {s['source_name']} | "
                        f"`{s['ticker']}` | {s['impact_score']}/10 | "
                        f"{s.get('sentiment') or 'N/A'} | {s.get('recommended_execution') or 'N/A'} |"
                    )

    return "\n".join(lines)


def _section_system_health(
    extraction_logs: Optional[List[dict]],
    stats: Dict[str, Any],
    db_summary: Optional[dict],
    start_date: str,
    end_date: str,
) -> str:
    """## 7. 系統健康 (System Health)"""
    lines = ["## 7. 系統健康 (System Health)"]

    # ETL Pipeline 狀態
    lines.append("\n### ETL Pipeline 狀態\n")

    if extraction_logs is None:
        lines.append("> extraction_log 資料表不存在或查詢失敗。")
    elif not extraction_logs:
        lines.append(f"{start_date} ~ {end_date} 期間無 ETL 執行紀錄。")
    else:
        success = sum(1 for l in extraction_logs if l["status"] == "success")
        failed = sum(1 for l in extraction_logs if l["status"] != "success")
        total_extracted = sum(l["extracted_count"] or 0 for l in extraction_logs)

        lines.append(f"- 執行次數: **{len(extraction_logs)}** (成功 {success} / 失敗 {failed})")
        lines.append(f"- 總萃取筆數: **{total_extracted}**")

        # 依來源分組
        source_stats = Counter(l["source_type"] for l in extraction_logs)
        for source, count in source_stats.most_common():
            source_logs = [l for l in extraction_logs if l["source_type"] == source]
            source_success = sum(1 for l in source_logs if l["status"] == "success")
            source_extracted = sum(l["extracted_count"] or 0 for l in source_logs)
            lines.append(f"  - `{source}`: {count} 次 (成功 {source_success}, 萃取 {source_extracted} 筆)")

        # 平均信心度
        conf_values = [l["confidence"] for l in extraction_logs if l["confidence"] is not None]
        if conf_values:
            avg_conf = sum(conf_values) / len(conf_values)
            lines.append(f"- 平均信心度: **{avg_conf:.2f}**")

        # 最近一次執行
        latest = extraction_logs[0]
        lines.append(f"- 最近執行: {latest['created_at']} (`{latest['source_type']}`, {latest['status']})")

        # ETL 明細表格
        lines.append("\n| 來源類型 | 信心度 | 原始筆數 | 萃取筆數 | 狀態 | 時間 |")
        lines.append("|----------|--------|----------|----------|------|------|")
        for log in extraction_logs[:15]:
            confidence = f"{log['confidence']:.2f}" if log['confidence'] is not None else "N/A"
            raw_count = log['raw_record_count'] if log['raw_record_count'] is not None else "N/A"
            ext_count = log['extracted_count'] if log['extracted_count'] is not None else "N/A"
            status = log['status'] or "N/A"
            created = (log['created_at'] or "N/A")[:19]
            lines.append(
                f"| {log['source_type']} | {confidence} | {raw_count} | "
                f"{ext_count} | {status} | {created} |"
            )
        if len(extraction_logs) > 15:
            lines.append(f"\n*（共 {len(extraction_logs)} 筆，僅顯示前 15 筆）*")

        # 錯誤紀錄
        errors = [l for l in extraction_logs if l.get("error_message")]
        if errors:
            lines.append("\n### 錯誤紀錄\n")
            for e in errors[:5]:
                msg = (e["error_message"] or "")[:200]
                lines.append(f"- [{str(e['created_at'])[:16]}] `{e['source_type']}`: {msg}")

    # 資料新鮮度
    lines.append("\n### 資料新鮮度\n")
    if db_summary:
        lines.append(f"| 指標 | 數值 |")
        lines.append(f"|------|------|")
        lines.append(f"| 資料庫交易總筆數 | {db_summary['total']} |")
        for chamber, cnt in sorted(db_summary["chamber_counts"].items()):
            pct_val = _pct(cnt, db_summary["total"])
            lines.append(f"| {chamber} 交易 | {cnt} ({pct_val}) |")
        lines.append(f"| 不重複議員 | {db_summary['unique_politicians']} |")
        lines.append(f"| 不重複 Ticker | {db_summary['unique_tickers']} |")
        lines.append(f"| 最新交易日期 | {db_summary['latest_transaction_date']} |")
        lines.append(f"| 最新資料建立 | {db_summary['latest_created_at']} |")
    else:
        lines.append("無法取得資料庫統計。")

    return "\n".join(lines)


def _section_alpha_insights() -> str:
    """## 8. Alpha 洞察 (Historical Insights)"""
    lines = ["## 8. Alpha 洞察 (Historical Insights)"]
    lines.append("""
> 基於歷史國會交易回測數據的固定洞察（來自 `alpha_backtest.py` 分析結果）。

### 關鍵發現

1. **國會買入訊號具有正 alpha**
   - 5 日平均超額報酬: **+0.77%** (相對 SPY 基準)
   - 10 日平均超額報酬: **+1.02%**
   - 統計顯著性: 在大額交易 (>$250K) 子群中更為顯著

2. **賣出訊號為反向指標**
   - 國會議員賣出後，標的股票短期內常有**正報酬**
   - 建議: 不宜跟隨賣出操作做空，反而可觀察是否為買入機會

3. **最佳進場策略**
   - **Gold+ 等級 + 跨院 Convergence**: 最高勝率組合
   - 建議執行方式: MOC (Market On Close) 或次日 MOO (Market On Open)
   - 持有期: 5-10 個交易日

4. **關鍵風險**
   - 申報延遲: 部分交易延遲 30-45+ 天才申報，資訊時效性降低
   - 小額交易 (<$15K): 訊號雜訊比高，不建議單獨操作
   - 非股票資產 (基金/LLC): 無法直接複製

### 操作建議

| 訊號類型 | 建議動作 | 持有期 | 信心 |
|----------|----------|--------|------|
| Gold+ Buy + Convergence | 跟隨買入 | 5-10 日 | 高 |
| Gold+ Buy (單一議員) | 觀察，MOC 小倉位 | 5 日 | 中 |
| 大額 Sale (>$250K) | 反向觀察（可能買入機會）| 3-5 日 | 中低 |
| Silver 以下 | 僅觀察，不操作 | N/A | 低 |""")

    return "\n".join(lines)


# ============================================================================
# 報告組裝
# ============================================================================


def build_report(db_path: str, start_date: str, end_date: str) -> str:
    """建構完整報告並回傳 Markdown 字串。"""
    conn = sqlite3.connect(db_path)

    try:
        logger.info(f"查詢期間: {start_date} ~ {end_date}")

        # ── 查詢所有資料 ──
        trades = query_trades(conn, start_date, end_date)
        trades_list = trades if trades else []
        logger.info(f"  congress_trades: {len(trades_list)} 筆")

        trade_ids = [t["id"] for t in trades_list]
        sqs_for_trades = query_sqs_for_trades(conn, trade_ids)
        sqs_list = sqs_for_trades if sqs_for_trades else []
        logger.info(f"  signal_quality_scores (本期交易): {len(sqs_list)} 筆")

        # 建立 trade_id -> sqs 的對應
        sqs_map = {}  # type: Dict[str, dict]
        for s in sqs_list:
            sqs_map[s["trade_id"]] = s

        top_sqs = query_top_sqs(conn, limit=20)
        logger.info(f"  top SQS (Gold+): {len(top_sqs) if top_sqs else 0} 筆")

        sqs_dist = query_sqs_distribution(conn)
        logger.info(f"  SQS distribution: {len(sqs_dist) if sqs_dist else 0} grades")

        convergence = query_convergence(conn)
        logger.info(f"  convergence_signals: {len(convergence) if convergence else 0} 筆")

        rankings = query_rankings(conn)
        logger.info(f"  politician_rankings: {len(rankings) if rankings else 0} 筆")

        ai_signals_period = query_ai_signals(conn, start_date, end_date)
        logger.info(f"  ai_intelligence_signals (本期): {len(ai_signals_period) if ai_signals_period else 0} 筆")

        ai_signals_all = query_ai_signals_all(conn)
        logger.info(f"  ai_intelligence_signals (全域): {len(ai_signals_all) if ai_signals_all else 0} 筆")

        extraction_logs = query_extraction_log(conn, start_date, end_date)
        logger.info(f"  extraction_log: {len(extraction_logs) if extraction_logs else 0} 筆")

        db_summary = query_trades_summary(conn)

        # ── 統計 ──
        stats = compute_trade_stats(trades_list)

        # ── 組裝報告 ──
        sections = []  # type: List[str]

        # 標題區
        if start_date == end_date:
            title = f"# Political Alpha Monitor -- Daily Report ({end_date})"
        else:
            title = f"# Political Alpha Monitor -- Report ({start_date} ~ {end_date})"
        sections.append(title)
        sections.append(
            f"\n> 報告生成時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  \n"
            f"> 資料來源: congress_trades, ai_intelligence_signals, signal_quality_scores, "
            f"convergence_signals, politician_rankings, extraction_log"
        )

        # 各區段
        sections.append(_section_executive_summary(stats, top_sqs, convergence, ai_signals_period, db_summary))
        sections.append(_section_new_trades(trades_list, sqs_map, stats, start_date, end_date))
        sections.append(_section_top_signals(top_sqs, sqs_dist))
        sections.append(_section_convergence(convergence))
        sections.append(_section_politician_watchlist(rankings))
        sections.append(_section_ai_signals(ai_signals_period, ai_signals_all, start_date, end_date))
        sections.append(_section_system_health(extraction_logs, stats, db_summary, start_date, end_date))
        sections.append(_section_alpha_insights())

        # 尾部
        sections.append("---\n\n*本報告由 Political Alpha Monitor 自動生成。*")

        return "\n\n".join(sections)

    finally:
        conn.close()


# ============================================================================
# CLI 入口
# ============================================================================


def main():
    """CLI 入口：解析參數、生成報告、儲存檔案。"""
    setup_logging()

    parser = argparse.ArgumentParser(
        description="Political Alpha Monitor -- 每日綜合報告生成器"
    )
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="報告結束日期 (YYYY-MM-DD)，預設為今日",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=1,
        help="回溯天數 (預設 1)",
    )
    parser.add_argument(
        "--db",
        type=str,
        default=DB_PATH,
        help=f"資料庫路徑（預設: {DB_PATH}）",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="報告輸出目錄（預設: docs/reports/）",
    )
    args = parser.parse_args()

    # 決定日期範圍
    if args.date:
        try:
            end_dt = datetime.strptime(args.date, "%Y-%m-%d")
        except ValueError:
            print(f"[!] 日期格式錯誤: {args.date}，請使用 YYYY-MM-DD 格式")
            return
    else:
        end_dt = datetime.now()
    end_date = end_dt.strftime("%Y-%m-%d")
    start_dt = end_dt - timedelta(days=args.days - 1)
    start_date = start_dt.strftime("%Y-%m-%d")

    # 確認資料庫存在
    if not os.path.exists(args.db):
        print(f"[!] 資料庫不存在: {args.db}")
        print("    請先執行 ETL pipeline 或 python -c \"from src.database import init_db; init_db()\"")
        return

    print(f"[DailyReport] 生成綜合報告: {start_date} ~ {end_date}")
    print(f"   資料庫: {args.db}")

    # 建構報告
    report = build_report(args.db, start_date, end_date)

    # 決定輸出目錄
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        output_dir = Path(__file__).parent.parent / "docs" / "reports"

    output_dir.mkdir(parents=True, exist_ok=True)

    # 檔名
    if args.days == 1:
        filename = f"Daily_Report_{end_date}.md"
    else:
        filename = f"Daily_Report_{end_date}_{args.days}d.md"

    filepath = output_dir / filename
    filepath.write_text(report, encoding="utf-8")

    print(f"[DailyReport] 報告已儲存: {filepath}")
    print(f"[DailyReport] 報告大小: {len(report)} 字元")

    # 輸出到終端（UTF-8 安全輸出）
    print("\n" + "=" * 70)
    try:
        sys.stdout.buffer.write(report.encode("utf-8"))
        sys.stdout.buffer.write(b"\n")
        sys.stdout.buffer.flush()
    except Exception:
        for line in report.split("\n"):
            try:
                print(line)
            except UnicodeEncodeError:
                print(line.encode("ascii", errors="replace").decode("ascii"))
    print("=" * 70)


if __name__ == "__main__":
    main()
