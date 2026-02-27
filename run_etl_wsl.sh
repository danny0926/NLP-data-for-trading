#!/bin/bash
# ============================================================
# WSL2 ETL Pipeline 執行腳本
# 用法:
#   bash run_etl_wsl.sh [參數]
#   bash run_etl_wsl.sh --senate-only --days 7
#   bash run_etl_wsl.sh --house-only --max-house 5
#
# 從 Windows Task Scheduler 呼叫:
#   wsl -d Ubuntu -- bash -c "cd '/mnt/d/VScode_project/NLP data for trading' && bash run_etl_wsl.sh --senate-only --days 7"
# ============================================================

PROJECT_DIR="/mnt/d/VScode_project/NLP data for trading"
VENV_DIR="$PROJECT_DIR/.venv_wsl"

# 啟動虛擬環境
source "$VENV_DIR/bin/activate"
cd "$PROJECT_DIR"

# 載入 .env
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# 用 xvfb-run 啟動虛擬螢幕並執行 pipeline
echo "[WSL] 啟動 xvfb-run + ETL pipeline..."
echo "[WSL] 參數: $@"
xvfb-run --auto-servernum --server-args="-screen 0 1920x1080x24" \
    python run_etl_pipeline.py "$@"

ETL_EXIT=$?
echo "[WSL] ETL Pipeline 完成 (exit=$ETL_EXIT)。"

# ETL 成功後生成報告
if [ $ETL_EXIT -eq 0 ]; then
    echo "[WSL] 生成交易分析報告..."
    python generate_report.py --days 1
    echo "[WSL] 報告生成完成。"
else
    echo "[WSL] ETL 失敗，跳過報告生成。"
fi
