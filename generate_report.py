"""
Daily Report Generator — 每日國會交易報告
從 congress_trades 查詢資料，透過 Gemini CLI 單次對話生成分析報告。
"""

import argparse
import os
import shutil
import sqlite3
import subprocess
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

from src.config import DB_PATH, GEMINI_MODEL


def query_trades(db_path: str, start_date: str, end_date: str) -> tuple:
    """查詢指定日期範圍的交易紀錄。"""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("""
        SELECT politician_name, chamber, ticker, asset_name,
               transaction_type, amount_range, transaction_date, filing_date,
               source_format, owner
        FROM congress_trades
        WHERE transaction_date BETWEEN ? AND ?
        ORDER BY transaction_date DESC
    """, (start_date, end_date))
    rows = cur.fetchall()
    conn.close()
    return rows


def calculate_stats(rows: list) -> dict:
    """計算統計摘要。"""
    if not rows:
        return {}

    total = len(rows)
    buys = sum(1 for r in rows if r[4] == "Buy")
    sells = sum(1 for r in rows if r[4] == "Sale")

    politician_counts = Counter(r[0] for r in rows)
    most_active = politician_counts.most_common(3)

    tickers = [r[2] for r in rows if r[2]]
    ticker_counts = Counter(tickers)

    large_keywords = ["250K", "500K", "1M", "5M"]
    large_trades = [r for r in rows if any(k in (r[5] or "") for k in large_keywords)]

    return {
        "total": total,
        "buys": buys,
        "sells": sells,
        "exchanges": total - buys - sells,
        "most_active": most_active,
        "unique_politicians": len(politician_counts),
        "unique_tickers": len(ticker_counts),
        "top_tickers": ticker_counts.most_common(5),
        "large_trades": len(large_trades),
    }


def format_data_table(rows: list) -> str:
    """將交易資料格式化為文字表格。"""
    lines = [
        "議員 | 院別 | Ticker | 資產名稱 | 買/賣 | 金額區間 | 交易日 | 申報日",
        "-" * 100,
    ]
    for r in rows:
        ticker = r[2] or "N/A"
        asset = (r[3] or "N/A")[:40]
        lines.append(
            f"{r[0]} | {r[1]} | {ticker} | {asset} | {r[4]} | {r[5]} | {r[6]} | {r[7]}"
        )
    return "\n".join(lines)


def build_context(data_table: str, stats: dict, start_date: str, end_date: str) -> str:
    """組裝 stdin 傳入的上下文資料（交易資料 + 統計 + 輸出格式要求）。"""
    stats_lines = [
        f"- 總筆數: {stats['total']}",
        f"- 買入: {stats['buys']}, 賣出: {stats['sells']}, 交換: {stats['exchanges']}",
        f"- 不重複議員: {stats['unique_politicians']}",
        f"- 不重複 ticker: {stats['unique_tickers']}",
        f"- 最活躍議員: {', '.join(f'{name}({count}筆)' for name, count in stats['most_active'])}",
        f"- 大額交易 (≥$250K): {stats['large_trades']} 筆",
    ]
    if stats["top_tickers"]:
        stats_lines.append(
            f"- 熱門 ticker: {', '.join(f'{t}({c}筆)' for t, c in stats['top_tickers'])}"
        )

    return f"""你是專業的國會交易分析師。以下是美國國會議員的交易揭露資料。

報告日期範圍: {start_date} ~ {end_date}

=== 交易紀錄 ===
{data_table}

=== 統計摘要 ===
{chr(10).join(stats_lines)}

=== 輸出要求 ===
請用繁體中文生成 Markdown 格式的每日分析報告，包含以下段落：

## 1. 今日概覽
簡潔的數字摘要（總筆數、買賣比、最活躍議員等）

## 2. 重要交易
列出值得關注的交易，附簡短分析（為什麼重要、可能的意圖）

## 3. 異常警報
偵測以下異常（如有）：
- 單一議員短期密集交易
- 大額交易（≥$250K）
- 多位議員同方向操作同一標的
- 交易日與申報日間隔異常（>45天可能涉及延遲申報）
- 反向操作（同一議員對同一資產先買後賣或反之）
如無明顯異常，簡述「本期無明顯異常」

## 4. 趨勢觀察
整體買賣傾向、值得後續追蹤的模式

注意：
- 只分析實際存在的資料，絕不捏造
- ticker 為 N/A 表示無公開股票代碼（可能是基金、LLC 等私人資產）
- 金額只有區間，無精確數字
- 保持專業客觀的分析語氣
"""


def call_gemini_cli(context: str, model: str = "gemini-2.5-flash") -> str:
    """透過 Gemini CLI 單次對話生成報告。context 透過 stdin 傳入。"""
    gemini_path = shutil.which("gemini")
    if not gemini_path:
        raise RuntimeError(
            "Gemini CLI 未找到。請確認已安裝: npm install -g @anthropic-ai/gemini-cli"
        )

    instruction = "請根據上方提供的國會交易資料和統計摘要，生成繁體中文 Markdown 格式的每日分析報告。"

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"

    result = subprocess.run(
        [gemini_path, "-m", model, "-o", "text", "-p", instruction],
        input=context.encode("utf-8"),
        capture_output=True,
        timeout=180,
        env=env,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"Gemini CLI 錯誤 (code={result.returncode}): {result.stderr.decode('utf-8', errors='replace')}"
        )

    return result.stdout.decode("utf-8", errors="replace").strip()


def main():
    parser = argparse.ArgumentParser(description="國會交易每日報告生成器")
    parser.add_argument("--date", help="報告結束日期 (YYYY-MM-DD)，預設今天")
    parser.add_argument("--days", type=int, default=1, help="回溯天數 (預設 1)")
    parser.add_argument("--db", default=DB_PATH, help="資料庫路徑")
    parser.add_argument("--model", default=GEMINI_MODEL, help="Gemini 模型")
    args = parser.parse_args()

    # 日期範圍
    if args.date:
        end_dt = datetime.strptime(args.date, "%Y-%m-%d")
    else:
        end_dt = datetime.now()
    end_date = end_dt.strftime("%Y-%m-%d")
    start_dt = end_dt - timedelta(days=args.days - 1)
    start_date = start_dt.strftime("%Y-%m-%d")

    print(f"[Report] 生成國會交易報告: {start_date} ~ {end_date}")

    # 查詢資料
    rows = query_trades(args.db, start_date, end_date)
    if not rows:
        print("[!] 該日期範圍無交易資料")
        return

    print(f"   找到 {len(rows)} 筆交易")

    # 統計
    stats = calculate_stats(rows)

    # 組裝上下文
    data_table = format_data_table(rows)
    context = build_context(data_table, stats, start_date, end_date)
    print(f"   Prompt 大小: {len(context)} chars")

    # 呼叫 Gemini CLI
    print("   呼叫 Gemini CLI 生成報告...")
    report = call_gemini_cli(context, model=args.model)

    # 儲存
    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)

    if args.days == 1:
        filename = f"{end_date}-daily.md"
    else:
        filename = f"{end_date}-{args.days}d-summary.md"

    filepath = reports_dir / filename
    filepath.write_text(report, encoding="utf-8")

    print(f"   報告已儲存: {filepath}")
    print("\n" + "=" * 60)
    # Windows cp950 無法顯示部分 Unicode，用 sys.stdout.buffer 強制 UTF-8
    import sys
    sys.stdout.buffer.write(report.encode("utf-8"))
    sys.stdout.buffer.write(b"\n")
    sys.stdout.buffer.flush()
    print("=" * 60)


if __name__ == "__main__":
    main()
