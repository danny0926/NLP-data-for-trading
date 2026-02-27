"""
SEC Form 4 Insider Trading 抓取入口點
抓取 SEC EDGAR Form 4 資料並存入 SQLite，
可與國會交易 (congress_trades) 交叉比對產生投資訊號。

使用方式:
    python run_sec_form4.py                  # 預設: 最近 7 天，最多 50 筆
    python run_sec_form4.py --days 14        # 回溯 14 天
    python run_sec_form4.py --max 100        # 最多 100 筆
    python run_sec_form4.py --cross-ref      # 執行國會交易交叉比對
    python run_sec_form4.py --days 7 --cross-ref  # 抓取 + 交叉比對
"""

import argparse
import hashlib
import logging
import os
import sqlite3
import sys
from datetime import datetime, timedelta

from dotenv import load_dotenv

load_dotenv()

# 確保從專案根目錄執行
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.config import DB_PATH
from src.database import init_db
from src.logging_config import setup_logging
from src.etl.sec_form4_fetcher import SECForm4Fetcher

logger = logging.getLogger("SECForm4")


def save_trades_to_db(trades: list, db_path: str = None) -> dict:
    """
    將 Form4Trade 列表寫入 sec_form4_trades 表。
    使用 accession_number 做去重。

    Returns:
        {"new": int, "skipped": int}
    """
    if db_path is None:
        db_path = DB_PATH

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    new_count = 0
    skipped_count = 0

    for trade in trades:
        # 去重 hash: accession + txn_date + txn_type + shares + ticker
        hash_str = "|".join(str(v) for v in [
            trade.accession_number, trade.transaction_date,
            trade.transaction_type, trade.shares, trade.ticker,
        ])
        data_hash = hashlib.sha256(hash_str.encode()).hexdigest()

        try:
            cursor.execute('''
                INSERT INTO sec_form4_trades (
                    accession_number, filer_name, filer_title, issuer_name,
                    ticker, transaction_type, transaction_date, shares,
                    price_per_share, total_value, ownership_type, source_url,
                    data_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                trade.accession_number,
                trade.filer_name,
                trade.filer_title,
                trade.issuer_name,
                trade.ticker,
                trade.transaction_type,
                trade.transaction_date,
                trade.shares,
                trade.price_per_share,
                trade.total_value,
                trade.ownership_type,
                trade.source_url,
                data_hash,
            ))
            new_count += 1
        except sqlite3.IntegrityError:
            # data_hash 重複
            skipped_count += 1

    conn.commit()
    conn.close()

    logger.info(f"DB 寫入完成: 新增 {new_count}, 跳過(重複) {skipped_count}")
    return {"new": new_count, "skipped": skipped_count}


def cross_reference_congress(days_window: int = 30, db_path: str = None) -> list:
    """
    交叉比對國會交易 (congress_trades) 與 SEC Form 4 (sec_form4_trades)。
    找出同一 ticker 在 30 天內同時有國會議員和公司內部人交易的重合紀錄。

    這是極強的投資訊號：
    - 國會議員 + 內部人同時買入 → 強烈看多
    - 國會議員 + 內部人同時賣出 → 強烈看空

    Args:
        days_window: 時間窗口（天），預設 30 天
        db_path: 資料庫路徑

    Returns:
        list[dict]: 交叉比對結果
    """
    if db_path is None:
        db_path = DB_PATH

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 查詢: 同一 ticker，congress_trades 和 sec_form4_trades 的交易日期在 N 天內
    query = '''
        SELECT
            ct.ticker,
            ct.politician_name AS congress_member,
            ct.transaction_type AS congress_action,
            ct.transaction_date AS congress_date,
            ct.amount_range AS congress_amount,
            ct.chamber,
            f4.filer_name AS insider_name,
            f4.filer_title AS insider_title,
            f4.issuer_name AS company,
            f4.transaction_type AS insider_action,
            f4.transaction_date AS insider_date,
            f4.shares AS insider_shares,
            f4.price_per_share AS insider_price,
            f4.total_value AS insider_value
        FROM congress_trades ct
        INNER JOIN sec_form4_trades f4
            ON ct.ticker = f4.ticker
            AND ct.ticker IS NOT NULL
            AND f4.ticker IS NOT NULL
        WHERE
            ABS(JULIANDAY(ct.transaction_date) - JULIANDAY(f4.transaction_date)) <= ?
        ORDER BY ct.transaction_date DESC
    '''

    cursor.execute(query, (days_window,))
    rows = cursor.fetchall()
    conn.close()

    results = []
    for row in rows:
        record = dict(row)

        # 判斷訊號方向
        congress_buy = record["congress_action"] in ("Buy", "Purchase")
        # Form 4: P=Purchase, S=Sale
        insider_buy = record["insider_action"] in ("P", "A", "P(D)")

        if congress_buy and insider_buy:
            signal = "STRONG_BUY"
            signal_desc = "國會議員 + 內部人同時買入"
        elif not congress_buy and not insider_buy:
            signal = "STRONG_SELL"
            signal_desc = "國會議員 + 內部人同時賣出"
        else:
            signal = "MIXED"
            signal_desc = "國會議員與內部人方向不一致"

        record["signal"] = signal
        record["signal_description"] = signal_desc
        results.append(record)

    return results


def print_cross_ref_results(results: list):
    """漂亮地印出交叉比對結果"""
    if not results:
        print("\n=== 交叉比對結果 ===")
        print("未發現國會交易與 SEC Form 4 的重合紀錄。")
        print("提示: 請先執行 ETL pipeline 抓取國會交易，再執行 Form 4 抓取。")
        return

    print(f"\n{'='*70}")
    print(f"  交叉比對結果: 國會交易 × SEC Form 4 Insider Trading")
    print(f"  共找到 {len(results)} 筆重合紀錄")
    print(f"{'='*70}\n")

    # 按訊號分組
    strong_buy = [r for r in results if r["signal"] == "STRONG_BUY"]
    strong_sell = [r for r in results if r["signal"] == "STRONG_SELL"]
    mixed = [r for r in results if r["signal"] == "MIXED"]

    if strong_buy:
        print(f"  [STRONG BUY] 國會議員 + 內部人同時買入 ({len(strong_buy)} 筆)")
        print(f"  {'-'*60}")
        for r in strong_buy:
            _print_record(r)

    if strong_sell:
        print(f"\n  [STRONG SELL] 國會議員 + 內部人同時賣出 ({len(strong_sell)} 筆)")
        print(f"  {'-'*60}")
        for r in strong_sell:
            _print_record(r)

    if mixed:
        print(f"\n  [MIXED] 方向不一致 ({len(mixed)} 筆)")
        print(f"  {'-'*60}")
        for r in mixed:
            _print_record(r)


def _print_record(r: dict):
    """印出單筆交叉比對紀錄"""
    insider_val = ""
    if r.get("insider_value"):
        insider_val = f"${r['insider_value']:,.0f}"
    elif r.get("insider_shares"):
        insider_val = f"{r['insider_shares']:,.0f} shares"

    print(f"    Ticker: {r['ticker']}")
    print(f"      國會: {r['congress_member']} ({r['chamber']}) "
          f"- {r['congress_action']} {r['congress_amount']} "
          f"on {r['congress_date']}")
    print(f"      內部: {r['insider_name']} ({r.get('insider_title', 'N/A')}) "
          f"- {r['insider_action']} {insider_val} "
          f"on {r['insider_date']}")
    print(f"      公司: {r.get('company', 'N/A')}")
    print()


def main():
    setup_logging()

    parser = argparse.ArgumentParser(description="SEC Form 4 Insider Trading Fetcher")
    parser.add_argument("--days", type=int, default=7,
                        help="回溯天數 (預設 7)")
    parser.add_argument("--max", type=int, default=50,
                        help="最大抓取 filing 數 (預設 50)")
    parser.add_argument("--cross-ref", action="store_true",
                        help="執行國會交易交叉比對")
    parser.add_argument("--cross-ref-only", action="store_true",
                        help="只執行交叉比對（不抓取新資料）")
    parser.add_argument("--window", type=int, default=30,
                        help="交叉比對時間窗口天數 (預設 30)")
    args = parser.parse_args()

    # 初始化資料庫（確保表存在）
    init_db()

    if not args.cross_ref_only:
        # 抓取 Form 4 資料
        print(f"\n開始抓取 SEC Form 4 insider trading 資料...")
        print(f"回溯 {args.days} 天，最多 {args.max} 筆 filing\n")

        fetcher = SECForm4Fetcher()
        trades = fetcher.fetch(days=args.days, max_filings=args.max)

        if trades:
            stats = save_trades_to_db(trades)
            print(f"\n抓取完成: 新增 {stats['new']} 筆，跳過(重複) {stats['skipped']} 筆")
        else:
            print("\n未抓取到任何交易資料。")
            print("可能原因: SEC EDGAR API 暫時不可用或日期範圍內無 filing")

    # 交叉比對
    if args.cross_ref or args.cross_ref_only:
        print(f"\n執行交叉比對 (時間窗口: {args.window} 天)...")
        results = cross_reference_congress(days_window=args.window)
        print_cross_ref_results(results)


if __name__ == "__main__":
    main()
