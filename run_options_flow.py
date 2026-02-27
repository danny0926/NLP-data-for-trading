"""Options Flow Runner — 選擇權異常活動分析入口

分析 alpha 訊號前 20 檔標的的選擇權市場活動，
交叉比對國會交易方向，產生確認/警告訊號。

用法:
    python run_options_flow.py                # 分析前 20 檔
    python run_options_flow.py --top 10       # 分析前 10 檔
    python run_options_flow.py --no-save      # 不寫入資料庫
    python run_options_flow.py --no-integrate # 不整合回 alpha_signals
"""

import argparse
import logging
import os
from datetime import date

from src.options_flow import OptionsFlowAnalyzer


def main():
    parser = argparse.ArgumentParser(
        description="Options Flow Analyzer — 選擇權異常活動分析"
    )
    parser.add_argument(
        "--top", type=int, default=20,
        help="分析前 N 檔標的（預設: 20）"
    )
    parser.add_argument(
        "--db", type=str, default=None,
        help="資料庫路徑（預設: data/data.db）"
    )
    parser.add_argument(
        "--no-save", action="store_true",
        help="不寫入 options_flow_signals 資料表"
    )
    parser.add_argument(
        "--no-integrate", action="store_true",
        help="不將情緒分數整合回 alpha_signals"
    )
    parser.add_argument(
        "--no-report", action="store_true",
        help="不生成 Markdown 報告"
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    print("=" * 80)
    print("  Options Flow Analyzer — 選擇權異常活動分析")
    print("=" * 80)
    print(f"  分析標的數: {args.top}")
    print()

    analyzer = OptionsFlowAnalyzer(db_path=args.db)

    # 分析
    results = analyzer.analyze_top_signals(top_n=args.top)

    if not results:
        print("\n  無法取得任何選擇權資料。可能原因：")
        print("  - alpha_signals 表中無資料")
        print("  - 標的無選擇權（如外國股票 / OTC）")
        print("  - yfinance API 限流")
        return

    # 終端摘要
    _print_summary(results)

    # 寫入 DB
    if not args.no_save:
        db_result = analyzer.save_results(results)
        print(f"\n  DB 寫入: 新增 {db_result['inserted']}, 跳過 {db_result['skipped']}")

    # 整合回 alpha_signals
    if not args.no_integrate:
        updated = analyzer.apply_to_alpha_signals(results)
        print(f"  Alpha 訊號整合: 更新 {updated} 筆")

    # 報告
    if not args.no_report:
        today_str = date.today().strftime("%Y-%m-%d")
        report_path = os.path.join(
            "docs", "reports", f"Options_Flow_{today_str}.md"
        )
        analyzer.generate_report(results, report_path)
        print(f"\n  報告已生成: {report_path}")

    print()


def _print_summary(results):
    """終端摘要輸出。"""
    from collections import Counter

    print(f"\n  分析結果: {len(results)} 檔有選擇權資料")
    print()

    # 訊號類型統計
    type_counts = Counter(r["signal_type"] for r in results)
    print("  訊號類型分布:")
    for st, cnt in type_counts.most_common():
        print(f"    {st:<25} {cnt}")
    print()

    # 情緒分布
    bullish = [r for r in results if r["sentiment"] > 0]
    bearish = [r for r in results if r["sentiment"] < 0]
    neutral = [r for r in results if r["sentiment"] == 0]
    avg_sent = sum(r["sentiment"] for r in results) / len(results)

    print(f"  情緒分布: 偏多={len(bullish)}, 偏空={len(bearish)}, 中性={len(neutral)}")
    print(f"  平均情緒分數: {avg_sent:+.3f}")
    print()

    # Top 表格
    header = (
        f"  {'#':>3}  "
        f"{'Ticker':<8}  "
        f"{'P/C':>6}  "
        f"{'Sentiment':>9}  "
        f"{'Signal Type':<25}  "
        f"{'Call Vol':>10}  "
        f"{'Put Vol':>10}  "
        f"{'Unusual':>7}  "
        f"{'Congress':>8}"
    )
    print(header)
    print(f"  {'-' * 100}")

    for i, r in enumerate(results, start=1):
        print(
            f"  {i:>3}  "
            f"{r['ticker']:<8}  "
            f"{r['put_call_ratio']:>6.2f}  "
            f"{r['sentiment']:>+8.3f}  "
            f"{r['signal_type']:<25}  "
            f"{r['call_volume']:>10,}  "
            f"{r['put_volume']:>10,}  "
            f"{r['unusual_volume_total']:>7}  "
            f"{r['congress_direction']:>8}"
        )

    print()


if __name__ == "__main__":
    main()
