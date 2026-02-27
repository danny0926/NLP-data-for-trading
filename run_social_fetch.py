"""
社群媒體抓取 CLI 入口點
抓取 Twitter/X、Truth Social、Reddit 上追蹤目標的貼文。

使用方式:
    python run_social_fetch.py                     # 預設: 全平台, 過去 24 小時
    python run_social_fetch.py --hours 48          # 過去 48 小時
    python run_social_fetch.py --twitter-only      # 只抓 Twitter/X
    python run_social_fetch.py --reddit-only       # 只抓 Reddit
    python run_social_fetch.py --truth-only        # 只抓 Truth Social
    python run_social_fetch.py --dry-run           # 抓取但不寫入 DB
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
from src.etl.social_fetcher import SocialFetcher


def main():
    setup_logging()

    parser = argparse.ArgumentParser(
        description="社群媒體抓取 — Political Alpha Monitor"
    )
    parser.add_argument(
        "--hours", type=int, default=24,
        help="回溯時間窗口（小時，預設 24）"
    )
    parser.add_argument(
        "--twitter-only", action="store_true",
        help="只抓取 Twitter/X"
    )
    parser.add_argument(
        "--reddit-only", action="store_true",
        help="只抓取 Reddit"
    )
    parser.add_argument(
        "--truth-only", action="store_true",
        help="只抓取 Truth Social"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="只抓取，不寫入資料庫"
    )
    args = parser.parse_args()

    # 初始化 DB（確保表存在）
    init_db()

    fetcher = SocialFetcher()

    # 判斷單平台或全平台
    if args.twitter_only:
        posts = fetcher.fetch_twitter_only(hours=args.hours, dry_run=args.dry_run)
    elif args.reddit_only:
        posts = fetcher.fetch_reddit_only(hours=args.hours, dry_run=args.dry_run)
    elif args.truth_only:
        posts = fetcher.fetch_truth_only(hours=args.hours, dry_run=args.dry_run)
    else:
        posts = fetcher.fetch_all_targets(hours=args.hours, dry_run=args.dry_run)

    # 摘要輸出
    print(f"\n{'='*60}")
    print(f"社群媒體抓取完成")
    print(f"{'='*60}")
    print(f"  總貼文數: {len(posts)}")

    # 按平台統計
    by_platform = {}
    for p in posts:
        platform = p.get("platform", "unknown")
        by_platform[platform] = by_platform.get(platform, 0) + 1
    for platform, count in sorted(by_platform.items()):
        print(f"  {platform}: {count} 則")

    # 按作者類型統計
    by_type = {}
    for p in posts:
        atype = p.get("author_type", "unknown")
        by_type[atype] = by_type.get(atype, 0) + 1
    for atype, count in sorted(by_type.items()):
        print(f"  [{atype}]: {count} 則")

    if args.dry_run:
        print("  (Dry Run — 未寫入資料庫)")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
