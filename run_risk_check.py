"""風險檢查入口 — 載入持倉、執行風險規則、輸出評估

用法:
    python run_risk_check.py               # 預設風險檢查
    python run_risk_check.py --db data/data.db  # 指定資料庫
"""

import logging
import sys
import os

# 確保專案根目錄在 sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.risk_manager import run_risk_assessment


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Risk Check -- Political Alpha Monitor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
範例:
  python run_risk_check.py                    # 執行風險檢查
  python run_risk_check.py --db data/data.db  # 指定資料庫路徑
        """
    )
    parser.add_argument("--db", type=str, default=None,
                        help="資料庫路徑 (預設: data/data.db)")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    result = run_risk_assessment(db_path=args.db)

    # 根據風險狀況回傳 exit code
    summary = result.get("summary", {})
    if summary.get("risk_off_mode"):
        sys.exit(2)  # 風險控制模式
    elif summary.get("critical_count", 0) > 0:
        sys.exit(1)  # 有 CRITICAL 部位
    else:
        sys.exit(0)  # 正常


if __name__ == "__main__":
    main()
