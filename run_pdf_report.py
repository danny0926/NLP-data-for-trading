"""
PDF 報告入口 — Political Alpha Monitor
產生含圖表的專業 PDF 投資報告。

使用方式:
    python run_pdf_report.py                    # 今日報告
    python run_pdf_report.py --date 2026-02-27  # 指定日期
    python run_pdf_report.py --days 7           # 過去 7 天
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from src.pdf_report import main

if __name__ == "__main__":
    main()
