"""
每日營運狀態報告生成器 — Political Alpha Monitor

自動查詢所有資料來源，生成綜合性的每日營運報告（Markdown 格式）。
查詢的資料表包含：extraction_log、congress_trades、ai_intelligence_signals、
signal_quality_scores、convergence_signals、politician_rankings。

部分資料表可能尚未建立，使用 try/except 確保報告仍能正常產出。

用法:
    python -m src.daily_report                     # 今日報告
    python -m src.daily_report --date 2026-02-27   # 指定日期報告
"""

import argparse
import logging
import os
import sqlite3
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from src.config import DB_PATH
from src.logging_config import setup_logging

logger = logging.getLogger("DailyReport")

# ============================================================================
# 資料查詢函式（每個表獨立 try/except）
# ============================================================================


def _query_extraction_log(conn: sqlite3.Connection, report_date: str) -> Optional[List[dict]]:
    """查詢 extraction_log — 當日 ETL 執行紀錄。"""
    try:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT source_type, confidence, raw_record_count,
                   extracted_count, status, created_at
            FROM extraction_log
            WHERE DATE(created_at) = ?
            ORDER BY created_at DESC
        """, (report_date,))
        rows = [dict(r) for r in cursor.fetchall()]
        return rows
    except Exception as e:
        logger.warning(f"查詢 extraction_log 失敗（表可能不存在）: {e}")
        return None


def _query_congress_trades_today(conn: sqlite3.Connection, report_date: str) -> Optional[List[dict]]:
    """查詢 congress_trades — 當日新增的交易紀錄。"""
    try:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT chamber, politician_name, transaction_date, filing_date,
                   ticker, asset_name, transaction_type, amount_range,
                   extraction_confidence, created_at
            FROM congress_trades
            WHERE DATE(created_at) = ?
            ORDER BY created_at DESC
        """, (report_date,))
        rows = [dict(r) for r in cursor.fetchall()]
        return rows
    except Exception as e:
        logger.warning(f"查詢 congress_trades (今日) 失敗: {e}")
        return None


def _query_congress_trades_summary(conn: sqlite3.Connection) -> Optional[dict]:
    """查詢 congress_trades — 全域統計摘要。"""
    try:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # 總記錄數
        cursor.execute("SELECT COUNT(*) as total FROM congress_trades")
        total = cursor.fetchone()["total"]

        # 院別分布
        cursor.execute("""
            SELECT chamber, COUNT(*) as cnt
            FROM congress_trades
            GROUP BY chamber
        """)
        chamber_counts = {r["chamber"]: r["cnt"] for r in cursor.fetchall()}

        # 最新交易日期
        cursor.execute("SELECT MAX(transaction_date) as latest_tx FROM congress_trades")
        latest_tx = cursor.fetchone()["latest_tx"]

        # 最新建立日期
        cursor.execute("SELECT MAX(created_at) as latest_created FROM congress_trades")
        latest_created = cursor.fetchone()["latest_created"]

        # 不重複議員數
        cursor.execute("SELECT COUNT(DISTINCT politician_name) as unique_politicians FROM congress_trades")
        unique_politicians = cursor.fetchone()["unique_politicians"]

        # 不重複 ticker 數
        cursor.execute("""
            SELECT COUNT(DISTINCT ticker) as unique_tickers
            FROM congress_trades
            WHERE ticker IS NOT NULL AND ticker != ''
        """)
        unique_tickers = cursor.fetchone()["unique_tickers"]

        return {
            "total": total,
            "chamber_counts": chamber_counts,
            "latest_transaction_date": latest_tx,
            "latest_created_at": latest_created,
            "unique_politicians": unique_politicians,
            "unique_tickers": unique_tickers,
        }
    except Exception as e:
        logger.warning(f"查詢 congress_trades (摘要) 失敗: {e}")
        return None


def _query_ai_signals(conn: sqlite3.Connection, report_date: str) -> Optional[List[dict]]:
    """查詢 ai_intelligence_signals — 當日 AI 信號。"""
    try:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT source_type, source_name, ticker, impact_score,
                   sentiment, recommended_execution, timestamp
            FROM ai_intelligence_signals
            WHERE DATE(timestamp) = ?
            ORDER BY impact_score DESC
        """, (report_date,))
        rows = [dict(r) for r in cursor.fetchall()]
        return rows
    except Exception as e:
        logger.warning(f"查詢 ai_intelligence_signals 失敗（表可能不存在）: {e}")
        return None


def _query_ai_signals_all(conn: sqlite3.Connection) -> Optional[List[dict]]:
    """查詢 ai_intelligence_signals — 全部信號（用於統計）。"""
    try:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT source_type, source_name, ticker, impact_score,
                   sentiment, recommended_execution, timestamp
            FROM ai_intelligence_signals
            ORDER BY impact_score DESC
        """)
        rows = [dict(r) for r in cursor.fetchall()]
        return rows
    except Exception as e:
        logger.warning(f"查詢 ai_intelligence_signals (全部) 失敗: {e}")
        return None


def _query_signal_quality(conn: sqlite3.Connection) -> Optional[List[dict]]:
    """查詢 signal_quality_scores — SQS 品質分布。"""
    try:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT politician_name, ticker, sqs, grade, action, scored_at
            FROM signal_quality_scores
            ORDER BY sqs DESC
        """)
        rows = [dict(r) for r in cursor.fetchall()]
        return rows
    except Exception as e:
        logger.warning(f"查詢 signal_quality_scores 失敗（表可能不存在）: {e}")
        return None


def _query_convergence_signals(conn: sqlite3.Connection) -> Optional[List[dict]]:
    """查詢 convergence_signals — 匯聚訊號。"""
    try:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT ticker, direction, politician_count, politicians,
                   chambers, score, window_start, window_end,
                   span_days, detected_at
            FROM convergence_signals
            ORDER BY score DESC
        """)
        rows = [dict(r) for r in cursor.fetchall()]
        return rows
    except Exception as e:
        logger.warning(f"查詢 convergence_signals 失敗（表可能不存在）: {e}")
        return None


def _query_politician_rankings(conn: sqlite3.Connection) -> Optional[List[dict]]:
    """查詢 politician_rankings — 議員排名。"""
    try:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT politician_name, chamber, pis_total, rank,
                   total_trades, avg_trade_size, unique_tickers,
                   pis_activity, pis_conviction, pis_diversification, pis_timing
            FROM politician_rankings
            ORDER BY rank ASC
        """)
        rows = [dict(r) for r in cursor.fetchall()]
        return rows
    except Exception as e:
        logger.warning(f"查詢 politician_rankings 失敗（表可能不存在）: {e}")
        return None


# ============================================================================
# 報告區段生成
# ============================================================================


def _section_etl_status(
    extraction_logs: Optional[List[dict]],
    trades_today: Optional[List[dict]],
    trades_summary: Optional[dict],
) -> str:
    """生成「ETL Pipeline 狀態」區段。"""
    lines = []
    lines.append("## 1. ETL Pipeline 狀態\n")

    # ── 1a. 今日 ETL 執行紀錄 ──
    lines.append("### 1.1 今日 ETL 執行紀錄\n")

    if extraction_logs is None:
        lines.append("> extraction_log 資料表不存在或查詢失敗，跳過此區段。\n")
    elif len(extraction_logs) == 0:
        lines.append("今日無 ETL 執行紀錄。\n")
    else:
        lines.append("| 來源類型 | 信心度 | 原始筆數 | 萃取筆數 | 狀態 | 時間 |")
        lines.append("|----------|--------|----------|----------|------|------|")
        for log in extraction_logs:
            confidence = f"{log['confidence']:.2f}" if log['confidence'] is not None else "N/A"
            raw_count = log['raw_record_count'] if log['raw_record_count'] is not None else "N/A"
            ext_count = log['extracted_count'] if log['extracted_count'] is not None else "N/A"
            status = log['status'] or "N/A"
            created = log['created_at'] or "N/A"
            lines.append(
                f"| {log['source_type']} | {confidence} | {raw_count} | "
                f"{ext_count} | {status} | {created} |"
            )

        # 統計
        total_runs = len(extraction_logs)
        success_runs = sum(1 for l in extraction_logs if l['status'] == 'success')
        avg_confidence = 0.0
        conf_values = [l['confidence'] for l in extraction_logs if l['confidence'] is not None]
        if conf_values:
            avg_confidence = sum(conf_values) / len(conf_values)

        lines.append("")
        lines.append(f"- 今日執行次數: **{total_runs}**")
        lines.append(f"- 成功次數: **{success_runs}** / {total_runs}")
        lines.append(f"- 平均信心度: **{avg_confidence:.2f}**")
        lines.append("")

    # ── 1b. 今日新增交易 ──
    lines.append("### 1.2 今日新增交易紀錄\n")

    if trades_today is None:
        lines.append("> congress_trades 資料表查詢失敗，跳過此區段。\n")
    elif len(trades_today) == 0:
        lines.append("今日無新增交易紀錄。\n")
    else:
        # 院別統計
        chamber_counts = Counter(t['chamber'] for t in trades_today)
        # 交易類型統計
        tx_type_counts = Counter(t['transaction_type'] for t in trades_today if t['transaction_type'])

        lines.append(f"- 今日新增: **{len(trades_today)} 筆**")
        for chamber, cnt in sorted(chamber_counts.items()):
            lines.append(f"  - {chamber}: {cnt} 筆")
        lines.append(f"- 交易類型分布:")
        for tx_type, cnt in tx_type_counts.most_common():
            lines.append(f"  - {tx_type}: {cnt} 筆")

        # 列出前 10 筆
        lines.append("")
        lines.append("**今日新增交易明細（前 10 筆）:**\n")
        lines.append("| 議員 | 院別 | Ticker | 交易類型 | 金額區間 | 交易日 | 信心度 |")
        lines.append("|------|------|--------|----------|----------|--------|--------|")
        for trade in trades_today[:10]:
            ticker = trade['ticker'] or "N/A"
            tx_type = trade['transaction_type'] or "N/A"
            amount = trade['amount_range'] or "N/A"
            tx_date = trade['transaction_date'] or "N/A"
            conf = f"{trade['extraction_confidence']:.2f}" if trade['extraction_confidence'] else "N/A"
            lines.append(
                f"| {trade['politician_name']} | {trade['chamber']} | {ticker} | "
                f"{tx_type} | {amount} | {tx_date} | {conf} |"
            )
        if len(trades_today) > 10:
            lines.append(f"\n*...共 {len(trades_today)} 筆，僅顯示前 10 筆。*")
        lines.append("")

    # ── 1c. 全域統計 ──
    lines.append("### 1.3 資料庫全域統計\n")

    if trades_summary is None:
        lines.append("> congress_trades 資料表查詢失敗，跳過此區段。\n")
    elif trades_summary['total'] == 0:
        lines.append("資料庫中尚無交易紀錄。\n")
    else:
        s = trades_summary
        lines.append(f"| 指標 | 數值 |")
        lines.append(f"|------|------|")
        lines.append(f"| 總交易筆數 | {s['total']} |")
        for chamber, cnt in sorted(s['chamber_counts'].items()):
            pct = cnt / s['total'] * 100 if s['total'] > 0 else 0
            lines.append(f"| {chamber} 交易 | {cnt} ({pct:.1f}%) |")
        lines.append(f"| 不重複議員 | {s['unique_politicians']} |")
        lines.append(f"| 不重複 Ticker | {s['unique_tickers']} |")
        lines.append(f"| 最新交易日期 | {s['latest_transaction_date']} |")
        lines.append(f"| 最新資料建立 | {s['latest_created_at']} |")
        lines.append("")

    return "\n".join(lines)


def _section_ai_signals(
    signals_today: Optional[List[dict]],
    signals_all: Optional[List[dict]],
) -> str:
    """生成「AI 信號摘要」區段。"""
    lines = []
    lines.append("## 2. AI 信號摘要\n")

    if signals_today is None and signals_all is None:
        lines.append("> ai_intelligence_signals 資料表不存在或查詢失敗，跳過此區段。\n")
        return "\n".join(lines)

    # ── 2a. 今日信號 ──
    lines.append("### 2.1 今日新增信號\n")

    if signals_today is None:
        lines.append("> 查詢失敗，跳過。\n")
    elif len(signals_today) == 0:
        lines.append("今日無新增 AI 信號。\n")
    else:
        lines.append(f"今日新增 **{len(signals_today)} 個**信號。\n")

        # 分層統計
        high = [s for s in signals_today if s['impact_score'] is not None and s['impact_score'] >= 8]
        medium = [s for s in signals_today if s['impact_score'] is not None and 6 <= s['impact_score'] < 8]
        low = [s for s in signals_today if s['impact_score'] is not None and s['impact_score'] < 6]
        null_score = [s for s in signals_today if s['impact_score'] is None]

        lines.append(f"- 高影響力 (score >= 8): **{len(high)}** 個")
        lines.append(f"- 中等影響 (score 6-7): **{len(medium)}** 個")
        lines.append(f"- 低影響 (score < 6): **{len(low)}** 個")
        if null_score:
            lines.append(f"- 無評分 (NULL): **{len(null_score)}** 個")
        lines.append("")

    # ── 2b. 全部信號統計 ──
    lines.append("### 2.2 全域信號統計\n")

    if signals_all is None:
        lines.append("> 查詢失敗，跳過。\n")
    elif len(signals_all) == 0:
        lines.append("資料庫中尚無 AI 信號。\n")
    else:
        total = len(signals_all)
        high = [s for s in signals_all if s['impact_score'] is not None and s['impact_score'] >= 8]
        medium = [s for s in signals_all if s['impact_score'] is not None and 6 <= s['impact_score'] < 8]
        low = [s for s in signals_all if s['impact_score'] is not None and s['impact_score'] < 6]
        null_score = [s for s in signals_all if s['impact_score'] is None]
        has_ticker = [s for s in signals_all if s['ticker'] is not None and s['ticker'].strip()]

        lines.append(f"| 指標 | 數值 |")
        lines.append(f"|------|------|")
        lines.append(f"| 信號總數 | {total} |")
        lines.append(f"| 高影響力 (>= 8) | {len(high)} ({_pct(len(high), total)}) |")
        lines.append(f"| 中等影響 (6-7) | {len(medium)} ({_pct(len(medium), total)}) |")
        lines.append(f"| 低影響 (< 6) | {len(low)} ({_pct(len(low), total)}) |")
        if null_score:
            lines.append(f"| 無評分 (NULL) | {len(null_score)} ({_pct(len(null_score), total)}) |")
        lines.append(f"| 有 Ticker 的信號 | {len(has_ticker)} ({_pct(len(has_ticker), total)}) |")
        lines.append("")

    # ── 2c. Top 信號 ──
    source_signals = signals_today if (signals_today and len(signals_today) > 0) else signals_all
    if source_signals and len(source_signals) > 0:
        # 過濾有 impact_score 的
        scored = [s for s in source_signals if s['impact_score'] is not None]
        scored.sort(key=lambda x: x['impact_score'], reverse=True)
        top_signals = scored[:10]

        if top_signals:
            label = "今日" if (signals_today and len(signals_today) > 0) else "全域"
            lines.append(f"### 2.3 Top 信號（{label}）\n")
            lines.append("| 來源 | 議員/機構 | Ticker | 影響分數 | 情緒 | 建議 |")
            lines.append("|------|-----------|--------|----------|------|------|")
            for s in top_signals:
                ticker = s['ticker'] or "N/A"
                sentiment = s['sentiment'] or "N/A"
                execution = s['recommended_execution'] or "N/A"
                lines.append(
                    f"| {s['source_type']} | {s['source_name']} | {ticker} | "
                    f"{s['impact_score']} | {sentiment} | {execution} |"
                )
            lines.append("")

    return "\n".join(lines)


def _section_signal_quality(quality_scores: Optional[List[dict]]) -> str:
    """生成「信號品質指標」區段。"""
    lines = []
    lines.append("## 3. 信號品質指標 (SQS)\n")

    if quality_scores is None:
        lines.append("> signal_quality_scores 資料表不存在或查詢失敗，跳過此區段。\n")
        lines.append("> 執行 `python -m src.signal_scorer` 可建立此資料表。\n")
        return "\n".join(lines)

    if len(quality_scores) == 0:
        lines.append("尚無 SQS 評分資料。請先執行 `python -m src.signal_scorer` 進行評分。\n")
        return "\n".join(lines)

    total = len(quality_scores)
    avg_sqs = sum(s['sqs'] for s in quality_scores) / total

    # 等級分布
    grade_counts = Counter(s['grade'] for s in quality_scores)
    grade_order = ["Platinum", "Gold", "Silver", "Bronze", "Discard"]

    lines.append(f"- 總評分筆數: **{total}**")
    lines.append(f"- 平均 SQS: **{avg_sqs:.1f}**\n")

    lines.append("### 等級分布\n")
    lines.append("| 等級 | 筆數 | 佔比 |")
    lines.append("|------|------|------|")
    for grade in grade_order:
        cnt = grade_counts.get(grade, 0)
        pct = _pct(cnt, total)
        lines.append(f"| {grade} | {cnt} | {pct} |")
    lines.append("")

    # Top 5 最高分
    top5 = quality_scores[:5]
    if top5:
        lines.append("### Top 5 最高分信號\n")
        lines.append("| SQS | 等級 | 議員 | Ticker | 建議行動 |")
        lines.append("|-----|------|------|--------|----------|")
        for s in top5:
            ticker = s['ticker'] or "N/A"
            lines.append(
                f"| {s['sqs']:.1f} | {s['grade']} | {s['politician_name']} | "
                f"{ticker} | {s['action']} |"
            )
        lines.append("")

    return "\n".join(lines)


def _section_convergence(convergence_signals: Optional[List[dict]]) -> str:
    """生成「匯聚訊號」區段。"""
    lines = []
    lines.append("## 4. 匯聚訊號 (Convergence Signals)\n")

    if convergence_signals is None:
        lines.append("> convergence_signals 資料表不存在或查詢失敗，跳過此區段。\n")
        lines.append("> 執行 `python -m src.convergence_detector` 可建立此資料表。\n")
        return "\n".join(lines)

    if len(convergence_signals) == 0:
        lines.append("目前無匯聚事件。\n")
        return "\n".join(lines)

    total = len(convergence_signals)
    buy_events = [e for e in convergence_signals if e['direction'] == 'Buy']
    sale_events = [e for e in convergence_signals if e['direction'] == 'Sale']

    lines.append(f"- 匯聚事件總數: **{total}**")
    lines.append(f"- 買入匯聚: **{len(buy_events)}** | 賣出匯聚: **{len(sale_events)}**\n")

    # 列出全部事件（最多 15 個）
    lines.append("### 活躍匯聚事件\n")
    lines.append("| 排名 | Ticker | 方向 | 議員數 | 院別 | 評分 | 時間跨度 | 涉及議員 |")
    lines.append("|------|--------|------|--------|------|------|----------|----------|")

    for i, event in enumerate(convergence_signals[:15], start=1):
        direction_label = "買入" if event['direction'] == 'Buy' else "賣出"
        politicians_str = event['politicians'] or "N/A"
        # 截斷過長的議員名單
        if len(politicians_str) > 40:
            politicians_str = politicians_str[:37] + "..."
        span = f"{event['span_days']}天"
        lines.append(
            f"| {i} | {event['ticker']} | {direction_label} | "
            f"{event['politician_count']} | {event['chambers']} | "
            f"{event['score']:.3f} | {span} | {politicians_str} |"
        )

    if total > 15:
        lines.append(f"\n*...共 {total} 個匯聚事件，僅顯示前 15 個。*")
    lines.append("")

    return "\n".join(lines)


def _section_politician_rankings(rankings: Optional[List[dict]]) -> str:
    """生成「議員排名」區段。"""
    lines = []
    lines.append("## 5. 議員排名 (Politician Intelligence Score)\n")

    if rankings is None:
        lines.append("> politician_rankings 資料表不存在或查詢失敗，跳過此區段。\n")
        lines.append("> 執行 `python -m src.politician_ranking` 可建立此資料表。\n")
        return "\n".join(lines)

    if len(rankings) == 0:
        lines.append("尚無議員排名資料。請先執行 `python -m src.politician_ranking` 計算排名。\n")
        return "\n".join(lines)

    total = len(rankings)
    lines.append(f"共 **{total}** 位議員已排名。\n")

    # Top 5 議員
    top5 = rankings[:5]
    lines.append("### Top 5 議員\n")
    lines.append("| 排名 | 議員姓名 | 院別 | PIS 總分 | 交易數 | 標的數 | 活躍度 | 信念度 | 分散度 | 時效性 |")
    lines.append("|------|----------|------|----------|--------|--------|--------|--------|--------|--------|")

    for r in top5:
        # PIS 分級
        pis = r['pis_total']
        if pis >= 75:
            grade_tag = "A"
        elif pis >= 50:
            grade_tag = "B"
        elif pis >= 25:
            grade_tag = "C"
        else:
            grade_tag = "D"

        lines.append(
            f"| {r['rank']} | {r['politician_name']} | {r['chamber']} | "
            f"{pis:.1f} ({grade_tag}) | {r['total_trades']} | {r['unique_tickers']} | "
            f"{r['pis_activity']:.1f} | {r['pis_conviction']:.1f} | "
            f"{r['pis_diversification']:.1f} | {r['pis_timing']:.1f} |"
        )
    lines.append("")

    # 完整排名表（如果超過 5 位則折疊顯示）
    if total > 5:
        lines.append("<details>")
        lines.append(f"<summary>完整排名（共 {total} 位）</summary>\n")
        lines.append("| 排名 | 議員姓名 | 院別 | PIS 總分 | 交易數 |")
        lines.append("|------|----------|------|----------|--------|")
        for r in rankings:
            lines.append(
                f"| {r['rank']} | {r['politician_name']} | {r['chamber']} | "
                f"{r['pis_total']:.1f} | {r['total_trades']} |"
            )
        lines.append("\n</details>\n")

    return "\n".join(lines)


# ============================================================================
# 工具函式
# ============================================================================


def _pct(part: int, total: int) -> str:
    """計算百分比並格式化為字串。"""
    if total == 0:
        return "0.0%"
    return f"{part / total * 100:.1f}%"


# ============================================================================
# 報告組裝
# ============================================================================


def generate_report(db_path: str, report_date: str) -> str:
    """
    查詢所有資料表，組裝完整的每日營運報告（Markdown 格式）。

    Args:
        db_path: SQLite 資料庫路徑
        report_date: 報告日期，格式 YYYY-MM-DD

    Returns:
        Markdown 格式的報告文字
    """
    conn = sqlite3.connect(db_path)

    logger.info(f"開始生成每日報告: {report_date}")
    logger.info(f"資料庫路徑: {db_path}")

    # ── 查詢各資料表 ──
    extraction_logs = _query_extraction_log(conn, report_date)
    trades_today = _query_congress_trades_today(conn, report_date)
    trades_summary = _query_congress_trades_summary(conn)
    signals_today = _query_ai_signals(conn, report_date)
    signals_all = _query_ai_signals_all(conn)
    quality_scores = _query_signal_quality(conn)
    convergence = _query_convergence_signals(conn)
    rankings = _query_politician_rankings(conn)

    conn.close()

    # ── 統計可用區段 ──
    available_sections = 0
    total_sections = 5

    if extraction_logs is not None or trades_today is not None or trades_summary is not None:
        available_sections += 1
    if signals_today is not None or signals_all is not None:
        available_sections += 1
    if quality_scores is not None:
        available_sections += 1
    if convergence is not None:
        available_sections += 1
    if rankings is not None:
        available_sections += 1

    # ── 組裝報告 ──
    report_parts = []

    # 標題
    report_parts.append(f"# Political Alpha Monitor — 每日營運報告")
    report_parts.append(f"**報告日期**: {report_date}")
    report_parts.append(f"**生成時間**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_parts.append(f"**資料來源**: `{os.path.basename(db_path)}`")
    report_parts.append(f"**可用區段**: {available_sections} / {total_sections}")
    report_parts.append("")
    report_parts.append("---\n")

    # 各區段
    report_parts.append(_section_etl_status(extraction_logs, trades_today, trades_summary))
    report_parts.append("---\n")
    report_parts.append(_section_ai_signals(signals_today, signals_all))
    report_parts.append("---\n")
    report_parts.append(_section_signal_quality(quality_scores))
    report_parts.append("---\n")
    report_parts.append(_section_convergence(convergence))
    report_parts.append("---\n")
    report_parts.append(_section_politician_rankings(rankings))
    report_parts.append("---\n")

    # 尾部
    report_parts.append("*本報告由 Political Alpha Monitor 自動生成。*")

    report = "\n".join(report_parts)
    logger.info(f"報告生成完成，共 {len(report)} 字元")

    return report


# ============================================================================
# CLI 入口
# ============================================================================


def main():
    """CLI 入口：解析參數、生成報告、儲存檔案。"""
    setup_logging()

    parser = argparse.ArgumentParser(
        description="Political Alpha Monitor — 每日營運狀態報告生成器"
    )
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="報告日期 (YYYY-MM-DD)，預設為今日",
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

    # 決定報告日期
    if args.date:
        report_date = args.date
        # 驗證日期格式
        try:
            datetime.strptime(report_date, "%Y-%m-%d")
        except ValueError:
            print(f"[!] 日期格式錯誤: {report_date}，請使用 YYYY-MM-DD 格式")
            return
    else:
        report_date = datetime.now().strftime("%Y-%m-%d")

    # 確認資料庫存在
    if not os.path.exists(args.db):
        print(f"[!] 資料庫不存在: {args.db}")
        print("    請先執行 ETL pipeline 或 python -c \"from src.database import init_db; init_db()\"")
        return

    print(f"[DailyReport] 生成每日營運報告: {report_date}")
    print(f"   資料庫: {args.db}")

    # 生成報告
    report = generate_report(args.db, report_date)

    # 決定輸出目錄
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        output_dir = Path(__file__).parent.parent / "docs" / "reports"

    output_dir.mkdir(parents=True, exist_ok=True)

    # 儲存檔案
    filename = f"Daily_Report_{report_date}.md"
    filepath = output_dir / filename
    filepath.write_text(report, encoding="utf-8")

    print(f"   報告已儲存: {filepath}")
    print(f"   報告大小: {len(report)} 字元")

    # 輸出到終端（UTF-8 安全輸出）
    import sys
    print("\n" + "=" * 70)
    try:
        sys.stdout.buffer.write(report.encode("utf-8"))
        sys.stdout.buffer.write(b"\n")
        sys.stdout.buffer.flush()
    except Exception:
        # Fallback: 逐行輸出，忽略編碼錯誤
        for line in report.split("\n"):
            try:
                print(line)
            except UnicodeEncodeError:
                print(line.encode("ascii", errors="replace").decode("ascii"))
    print("=" * 70)


if __name__ == "__main__":
    main()
