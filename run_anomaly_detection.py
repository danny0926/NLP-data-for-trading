#!/usr/bin/env python3
"""
國會交易異常偵測 — Entry Point

用法:
    python run_anomaly_detection.py                    # 執行全部偵測
    python run_anomaly_detection.py --report-only      # 只生成報告（不儲存到 DB）
    python run_anomaly_detection.py --save              # 偵測並儲存到 DB
"""

import argparse
import logging
import os
import sys
from datetime import date

# 確保 project root 在 sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.anomaly_detector import AnomalyDetector, Severity


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def main():
    parser = argparse.ArgumentParser(description="國會交易異常偵測系統")
    parser.add_argument("--report-only", action="store_true", help="僅生成報告，不儲存到 DB")
    parser.add_argument("--save", action="store_true", help="將偵測結果儲存到 anomaly_detections 表")
    parser.add_argument("--output", type=str, default=None, help="報告輸出路徑（預設: docs/reports/）")
    args = parser.parse_args()

    setup_logging()
    logger = logging.getLogger("AnomalyDetection")

    logger.info("=" * 60)
    logger.info("國會交易異常偵測系統啟動")
    logger.info("=" * 60)

    detector = AnomalyDetector()

    # 執行各項偵測
    logger.info("── 開始偵測 ──")
    anomalies = detector.run_all_detections()

    if not anomalies:
        logger.info("未偵測到任何異常")
        return

    # 複合分數
    composite = detector.compute_composite_scores(anomalies)

    # 印出摘要
    print("\n" + "=" * 60)
    print("偵測結果摘要")
    print("=" * 60)
    print(f"  總異常數: {len(anomalies)}")
    print(f"  CRITICAL: {sum(1 for a in anomalies if a.severity == Severity.CRITICAL)}")
    print(f"  HIGH:     {sum(1 for a in anomalies if a.severity == Severity.HIGH)}")
    print(f"  MEDIUM:   {sum(1 for a in anomalies if a.severity == Severity.MEDIUM)}")
    print(f"  LOW:      {sum(1 for a in anomalies if a.severity == Severity.LOW)}")

    print("\n議員複合異常分數排名:")
    for rank, (politician, score) in enumerate(composite.items(), 1):
        print(f"  {rank}. {politician}: {score:.2f}")

    print("\n最嚴重異常 (Top 10):")
    for a in anomalies[:10]:
        print(f"  [{a.severity.value:8s}] {a.anomaly_type:8s} | {a.politician[:25]:25s} | "
              f"{a.ticker or 'N/A':6s} | score={a.score:.1f}")

    # 儲存到 DB
    if args.save and not args.report_only:
        saved = detector.save_to_db(anomalies)
        logger.info(f"已儲存 {saved} 筆偵測結果到資料庫")

    # 生成報告
    report = detector.generate_report(anomalies, composite)

    if args.output:
        report_path = args.output
    else:
        report_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs", "reports")
        os.makedirs(report_dir, exist_ok=True)
        report_path = os.path.join(report_dir, f"Anomaly_Detection_{date.today().isoformat()}.md")

    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)

    logger.info(f"報告已生成: {report_path}")
    print(f"\n報告已儲存至: {report_path}")


if __name__ == "__main__":
    main()
