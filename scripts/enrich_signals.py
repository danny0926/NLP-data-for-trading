"""批量回補 AI 信號缺失的 ticker（Reverse Enrichment）。

從 congress_trades 回補 ai_intelligence_signals 中缺失 ticker 的記錄。
使用 name_mapping 模組進行跨表議員名匹配。

使用方式：
    python scripts/enrich_signals.py              # 預設模式（回補並寫入 DB）
    python scripts/enrich_signals.py --dry-run     # 僅預覽，不寫入
"""
import argparse
import sqlite3
import sys
import os
from datetime import datetime
from typing import Optional, List, Tuple, Dict

# 加入專案根目錄到 path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from src.name_mapping import normalize_name, find_politician_in_trades

DB_PATH = os.path.join(PROJECT_ROOT, "data", "data.db")


def get_signals_missing_ticker(conn: sqlite3.Connection) -> List[Tuple]:
    """取得所有缺少 ticker 的 AI 信號。"""
    cur = conn.cursor()
    cur.execute("""
        SELECT id, source_name, impact_score, sentiment, timestamp
        FROM ai_intelligence_signals
        WHERE ticker IS NULL OR ticker = ''
        ORDER BY source_name, timestamp DESC
    """)
    return cur.fetchall()


def get_recent_trades_for_politician(
    conn: sqlite3.Connection,
    politician_name: str,
    limit: int = 5,
) -> List[Tuple[str, str, str, str]]:
    """取得指定議員最近的交易 ticker。

    Returns:
        List of (ticker, asset_name, transaction_type, transaction_date)
    """
    cur = conn.cursor()
    cur.execute("""
        SELECT DISTINCT ticker, asset_name, transaction_type, transaction_date
        FROM congress_trades
        WHERE politician_name = ?
          AND ticker IS NOT NULL
          AND ticker != ''
        ORDER BY transaction_date DESC
        LIMIT ?
    """, (politician_name, limit))
    return cur.fetchall()


def enrich_signal(
    conn: sqlite3.Connection,
    signal_id: str,
    ticker: str,
    dry_run: bool = False,
) -> bool:
    """回補單筆信號的 ticker。"""
    if dry_run:
        return True
    cur = conn.cursor()
    cur.execute(
        "UPDATE ai_intelligence_signals SET ticker = ? WHERE id = ?",
        (ticker, signal_id),
    )
    return cur.rowcount > 0


def run_enrichment(dry_run: bool = False) -> Dict[str, int]:
    """執行批量回補。

    Returns:
        統計結果 dict: {enriched, skipped_no_match, skipped_no_trades, total}
    """
    conn = sqlite3.connect(DB_PATH)
    signals = get_signals_missing_ticker(conn)

    stats = {
        "enriched": 0,
        "skipped_no_match": 0,
        "skipped_no_trades": 0,
        "total": len(signals),
    }

    # 按 source_name 分組處理，避免重複查詢
    processed_names = {}  # type: Dict[str, Optional[str]]  # source_name → matched ETL name
    trade_cache = {}  # type: Dict[str, List[Tuple]]  # etl_name → trades

    print(f"{'[DRY RUN] ' if dry_run else ''}開始回補 AI 信號 ticker...")
    print(f"共 {len(signals)} 筆缺少 ticker 的信號\n")

    for signal_id, source_name, impact_score, sentiment, timestamp in signals:
        # 查找 ETL 對應的議員名
        if source_name not in processed_names:
            etl_name = find_politician_in_trades(source_name, DB_PATH)
            processed_names[source_name] = etl_name
            if etl_name:
                print(f"  [匹配] {source_name} → {etl_name}")
            else:
                print(f"  [跳過] {source_name} — 在 congress_trades 中無匹配")

        etl_name = processed_names[source_name]
        if not etl_name:
            stats["skipped_no_match"] += 1
            continue

        # 取得最近的交易 ticker
        if etl_name not in trade_cache:
            trades = get_recent_trades_for_politician(conn, etl_name)
            trade_cache[etl_name] = trades

        trades = trade_cache[etl_name]
        if not trades:
            stats["skipped_no_trades"] += 1
            continue

        # 取最近一筆交易的 ticker 回補
        ticker = trades[0][0]
        asset_name = trades[0][1]

        if enrich_signal(conn, signal_id, ticker, dry_run=dry_run):
            stats["enriched"] += 1
            print(
                f"    {'[預覽]' if dry_run else '[回補]'} "
                f"signal={signal_id[:8]}... "
                f"← ticker={ticker} ({asset_name})"
            )

    if not dry_run:
        conn.commit()
        print(f"\n已提交 {stats['enriched']} 筆更新到資料庫")

    conn.close()
    return stats


def main():
    parser = argparse.ArgumentParser(description="回補 AI 信號缺失的 ticker")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="僅預覽，不寫入資料庫",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("  Reverse Enrichment: AI 信號 Ticker 回補")
    print(f"  時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  資料庫: {DB_PATH}")
    print("=" * 60)
    print()

    stats = run_enrichment(dry_run=args.dry_run)

    print()
    print("=" * 60)
    print("  回補統計")
    print("=" * 60)
    print(f"  總計缺少 ticker 的信號:    {stats['total']}")
    print(f"  成功回補:                  {stats['enriched']}")
    print(f"  跳過（議員無匹配）:        {stats['skipped_no_match']}")
    print(f"  跳過（無交易記錄）:        {stats['skipped_no_trades']}")
    print("=" * 60)


if __name__ == "__main__":
    main()
