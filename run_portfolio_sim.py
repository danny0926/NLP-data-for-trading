"""投資組合回測模擬入口 — Portfolio Backtest Simulator

用法:
    python run_portfolio_sim.py                                 # 預設: $100K, equal weight
    python run_portfolio_sim.py --capital 200000                # 自訂資金
    python run_portfolio_sim.py --strategy conviction           # 信念加權策略
    python run_portfolio_sim.py --start-date 2025-12-01        # 指定起始日
    python run_portfolio_sim.py --end-date 2026-02-15          # 指定結束日
"""

import argparse
import logging
import sys

from src.portfolio_simulator import run_simulation


def main():
    parser = argparse.ArgumentParser(
        description="Portfolio Backtest Simulator — Political Alpha Monitor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
範例:
  python run_portfolio_sim.py                                 # 預設參數
  python run_portfolio_sim.py --capital 200000                # 起始資金 $200K
  python run_portfolio_sim.py --strategy conviction           # 信念加權
  python run_portfolio_sim.py --start-date 2025-12-01        # 指定起始日
  python run_portfolio_sim.py --capital 50000 --strategy conviction --start-date 2026-01-01
        """,
    )
    parser.add_argument(
        "--capital", type=float, default=100000.0,
        help="起始資金 (預設 $100,000)",
    )
    parser.add_argument(
        "--strategy", type=str, default="equal",
        choices=["equal", "conviction"],
        help="部位大小策略: equal (等權重 5%%) 或 conviction (信念加權 3-10%%)",
    )
    parser.add_argument(
        "--start-date", type=str, default=None,
        help="模擬起始日期 (YYYY-MM-DD)，預設使用全部資料",
    )
    parser.add_argument(
        "--end-date", type=str, default=None,
        help="模擬結束日期 (YYYY-MM-DD)，預設到今天",
    )
    parser.add_argument(
        "--db", type=str, default=None,
        help="資料庫路徑 (預設 data/data.db)",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    metrics = run_simulation(
        capital=args.capital,
        strategy=args.strategy,
        start_date=args.start_date,
        end_date=args.end_date,
        db_path=args.db,
    )

    if not metrics:
        print("[錯誤] 模擬失敗，請檢查資料是否足夠")
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
