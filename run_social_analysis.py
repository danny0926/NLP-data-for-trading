"""
社群媒體分析 CLI 入口點 — 抓取 + NLP 分析 + 交叉比對 + 信號生成

完整流程: 抓取貼文 → NLP 分析 → 交叉比對國會交易 → 產生 alpha 信號

使用方式:
    python run_social_analysis.py                  # 預設: 抓取 + 分析, 過去 24 小時
    python run_social_analysis.py --hours 48       # 過去 48 小時
    python run_social_analysis.py --skip-fetch     # 跳過抓取，只分析 DB 中現有貼文
    python run_social_analysis.py --dry-run        # 只分析，不寫入 DB
"""

import argparse
import os
import sys

from dotenv import load_dotenv

load_dotenv()

# 確保從專案根目錄 import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.database import init_db
from src.logging_config import setup_logging


def main():
    setup_logging()

    parser = argparse.ArgumentParser(
        description="社群媒體分析 — Political Alpha Monitor"
    )
    parser.add_argument(
        "--hours", type=int, default=24,
        help="回溯時間窗口（小時，預設 24）"
    )
    parser.add_argument(
        "--skip-fetch", action="store_true",
        help="跳過抓取，只分析 DB 中現有貼文"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="只分析，不寫入資料庫"
    )
    args = parser.parse_args()

    # 初始化 DB
    init_db()

    # Step 1: 抓取（除非 --skip-fetch）
    if not args.skip_fetch:
        from src.etl.social_fetcher import SocialFetcher

        print(f"\n[Step 1/2] Fetching social media posts (past {args.hours}h)...")
        fetcher = SocialFetcher()
        posts = fetcher.fetch_all_targets(hours=args.hours, dry_run=args.dry_run)
        print(f"  Fetched: {len(posts)} posts")
    else:
        print("\n[Step 1/2] Skipping fetch (--skip-fetch)")

    # Step 2: 分析 + 交叉比對 + 信號生成
    from src.social_analyzer import SocialAnalyzer

    print(f"\n[Step 2/2] Analyzing posts + cross-referencing trades...")
    analyzer = SocialAnalyzer()
    stats = analyzer.analyze_batch(hours=args.hours, dry_run=args.dry_run)

    # 摘要
    print(f"\n{'='*60}")
    print("Social Media Analysis Pipeline Complete")
    print(f"{'='*60}")
    print(f"  Posts analyzed:      {stats['total']}")
    print(f"  Signals generated:   {stats['signals']}")
    print(f"  Alpha signals:       {stats.get('alpha_signals', 0)}")
    print(f"  CONSISTENT:          {stats['consistent']}")
    print(f"  CONTRADICTORY:       {stats['contradictory']}")
    print(f"  NO_TRADE:            {stats['no_trade']}")
    if args.dry_run:
        print("  (Dry Run — no DB writes)")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
