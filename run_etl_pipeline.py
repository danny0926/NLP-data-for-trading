"""
Congressional Trading ETL Pipeline 入口點
LLM-Driven fusion architecture: Extract (traditional) + Transform (LLM) + Load (rules)

使用方式:
    python run_etl_pipeline.py                    # 預設: Senate 7天 + House 今年
    python run_etl_pipeline.py --days 30          # Senate 回溯 30 天
    python run_etl_pipeline.py --senate-only      # 只跑 Senate
    python run_etl_pipeline.py --house-only       # 只跑 House
    python run_etl_pipeline.py --max-house 10     # House 最多 10 份 PDF
"""

import argparse
import os
import sys

from dotenv import load_dotenv

load_dotenv()

# 確保從專案根目錄執行
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.config import DB_PATH, GEMINI_MODEL
from src.database import init_db
from src.etl.pipeline import CongressETLPipeline


def main():
    parser = argparse.ArgumentParser(description="Congressional Trading ETL Pipeline")
    parser.add_argument("--days", type=int, default=7, help="Senate 回溯天數 (預設 7)")
    parser.add_argument("--year", type=int, default=None, help="House 報告年份 (預設今年)")
    parser.add_argument("--senate-only", action="store_true", help="只執行 Senate 路徑")
    parser.add_argument("--house-only", action="store_true", help="只執行 House 路徑")
    parser.add_argument("--max-house", type=int, default=20, help="House PDF 最大下載數 (預設 20)")
    parser.add_argument("--model", type=str, default=GEMINI_MODEL, help="Gemini model name")
    args = parser.parse_args()

    # 決定執行哪些路徑
    run_senate = not args.house_only
    run_house = not args.senate_only

    # 初始化資料庫
    init_db()

    # 執行 pipeline
    pipeline = CongressETLPipeline(db_path=DB_PATH, model_name=args.model)
    stats = pipeline.run(
        days=args.days,
        filing_year=args.year,
        run_senate=run_senate,
        run_house=run_house,
        max_house_reports=args.max_house,
    )

    # Exit code: 0 if any records processed, 1 if all failed
    if stats["new"] + stats["skipped"] == 0 and stats["failed"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
