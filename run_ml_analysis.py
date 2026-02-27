#!/usr/bin/env python3
"""
ML Feature Importance Analysis — 入口腳本
國會交易訊號特徵重要性分析

Usage:
    python run_ml_analysis.py
    python run_ml_analysis.py --db data/data.db
"""

import argparse
import sys
from pathlib import Path

# 確保專案根目錄在 sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.ml_signal_model import run_full_analysis


def main():
    parser = argparse.ArgumentParser(
        description="ML Feature Importance Analysis — 國會交易訊號特徵重要性分析"
    )
    parser.add_argument(
        "--db", type=str, default=None,
        help="SQLite 資料庫路徑 (預設: data/data.db)"
    )
    args = parser.parse_args()

    results = run_full_analysis(db_path=args.db)

    # 摘要輸出
    print("\n" + "=" * 60)
    print("  Results Summary")
    print("=" * 60)
    print(f"  Regression CV R²:      {results['reg_results']['cv_r2_mean']:.4f}")
    print(f"  Classification CV Acc:  {results['clf_results']['cv_accuracy_mean']:.4f}")
    print(f"  Classification CV F1:   {results['clf_results']['cv_f1_mean']:.4f}")
    print(f"  Predictions saved:      {results['n_predictions_saved']}")
    print(f"  Report:                 {results['report_path']}")
    print(f"  Plots:                  {', '.join(results['plot_paths'].values())}")

    # Top 5 features
    print("\n  Top 5 Most Important Features:")
    for _, row in results["fi_df"].head(5).iterrows():
        print(f"    #{int(row['rank'])} {row.name:<25s} score={row['combined_score']:.3f}")

    print()


if __name__ == "__main__":
    main()
