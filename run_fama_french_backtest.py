"""Fama-French 三因子 Alpha 回測入口。

同時執行 Market-Adjusted 和 Fama-French 3-Factor 兩種模型，
輸出比較報告並保存結果到 SQLite。

用法:
    python run_fama_french_backtest.py
    python run_fama_french_backtest.py --windows 5 20 60
    python run_fama_french_backtest.py --force-download   # 強制重新下載因子數據
"""

import argparse
import sys
from datetime import datetime

from src.fama_french import FamaFrenchModel


def main():
    parser = argparse.ArgumentParser(description="Fama-French 三因子 Alpha 回測")
    parser.add_argument(
        "--windows", nargs="+", type=int, default=[5, 20, 60],
        help="事件窗口天數（預設: 5 20 60）"
    )
    parser.add_argument(
        "--force-download", action="store_true",
        help="強制重新下載 Fama-French 因子數據"
    )
    parser.add_argument(
        "--output", type=str, default=None,
        help="報告輸出路徑（預設: docs/reports/FF3_Backtest_{date}.md）"
    )
    args = parser.parse_args()

    print("=" * 70)
    print("  Fama-French 三因子 Alpha 回測")
    print("=" * 70)
    print(f"  事件窗口: {args.windows}")
    print(f"  模型: Market-Adjusted (CAR) vs Fama-French 3-Factor (FF3-CAR)")
    print("")

    # ── 初始化 ──
    model = FamaFrenchModel()

    # ── 載入因子數據 ──
    if args.force_download:
        model.load_ff_factors(force_download=True)

    # ── 執行回測 ──
    results = model.run_backtest(windows=args.windows)

    if results.empty:
        print("[錯誤] 回測結果為空，請確認 congress_trades 表有數據")
        sys.exit(1)

    # ── 保存到 DB ──
    model.save_results(results)

    # ── 生成比較報告 ──
    date_str = datetime.now().strftime("%Y-%m-%d")
    output_path = args.output or f"docs/reports/FF3_Backtest_{date_str}.md"
    model.generate_comparison_report(results, output_path)

    # ── 印出摘要 ──
    print("\n" + "=" * 70)
    print("  回測摘要")
    print("=" * 70)

    comparison = model.comparison_analysis(results, args.windows)
    for key, stats in comparison.items():
        if stats.get("insufficient_data"):
            print(f"\n--- {key} --- (樣本不足)")
            continue

        n = stats["n"]
        ff3 = stats["ff3"]
        mkt = stats["market"]
        diff = stats["diff"]

        def sig(p):
            if p < 0.01:
                return "***"
            if p < 0.05:
                return "**"
            if p < 0.10:
                return "*"
            return ""

        print(f"\n--- {key} (n={n}) ---")
        print(
            f"  MKT-Adj:  mean={mkt['mean']:+.4f}, "
            f"p={mkt['p_value']:.4f}{sig(mkt['p_value'])}, "
            f"hit={mkt['hit_rate']:.1%}"
        )
        print(
            f"  FF3-Adj:  mean={ff3['mean']:+.4f}, "
            f"p={ff3['p_value']:.4f}{sig(ff3['p_value'])}, "
            f"hit={ff3['hit_rate']:.1%}"
        )
        print(
            f"  Diff:     mean={diff['mean']:+.4f}, "
            f"p={diff['p_value']:.4f}{sig(diff['p_value'])}"
        )

    # ── CSV 匯出 ──
    csv_path = f"data/ff3_results_{date_str}.csv"
    results.to_csv(csv_path, index=False, encoding="utf-8-sig")
    print(f"\n[匯出] CSV: {csv_path}")
    print(f"[報告] Markdown: {output_path}")
    print(f"\n完成！")


if __name__ == "__main__":
    main()
