#!/bin/bash
# ============================================================
# Political Alpha Monitor — WSL2 每日自動執行腳本
# 支援 Playwright headless=False (via Xvfb 虛擬螢幕)
#
# 用法:
#   bash run_daily_wsl.sh                      # 完整每日流程
#   bash run_daily_wsl.sh --skip-etl           # 跳過 ETL
#   bash run_daily_wsl.sh --analysis-only      # 只跑分析
#   bash run_daily_wsl.sh --days 14            # 擴大回溯
#
# 從 Windows Task Scheduler 呼叫:
#   wsl -d Ubuntu -- bash -c "cd '/mnt/d/VScode_project/NLP data for trading' && bash run_daily_wsl.sh"
# ============================================================

set -euo pipefail

PROJECT_DIR="/mnt/d/VScode_project/NLP data for trading"
VENV_DIR="$PROJECT_DIR/.venv_wsl"
LOG_DIR="$PROJECT_DIR/logs"
TODAY=$(date +%Y-%m-%d)
LOG_FILE="$LOG_DIR/daily_wsl_${TODAY}.log"

# ── 初始化 ──
mkdir -p "$LOG_DIR"
cd "$PROJECT_DIR"

log() {
    echo "[$(date '+%H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "============================================"
log "  Political Alpha Monitor — WSL2 每日執行"
log "  日期: $TODAY"
log "  參數: $*"
log "============================================"

# ── 載入環境變數 ──
if [ -f .env ]; then
    set -a
    source .env
    set +a
    log "已載入 .env"
fi

# ── 啟動虛擬環境 ──
if [ ! -d "$VENV_DIR" ]; then
    log "[ERROR] 找不到 WSL venv: $VENV_DIR"
    log "請先執行: bash setup_wsl.sh"
    exit 1
fi

source "$VENV_DIR/bin/activate"
log "已啟動虛擬環境: $VENV_DIR"

# ── 檢查 Xvfb ──
if ! command -v xvfb-run &> /dev/null; then
    log "[WARN] xvfb-run 未安裝，Senate fetcher 可能無法運行"
    log "  安裝方式: sudo apt-get install xvfb"
fi

# ── 執行 Pipeline (透過 Xvfb 虛擬螢幕) ──
log "啟動 xvfb-run + run_daily.py..."

XVFB_ARGS="--auto-servernum --server-args=-screen 0 1920x1080x24"

xvfb-run $XVFB_ARGS python run_daily.py "$@" 2>&1 | tee -a "$LOG_FILE"
PIPELINE_EXIT=${PIPESTATUS[0]}

log "Pipeline 執行完成 (exit=$PIPELINE_EXIT)"

# ── 清理 ──
# 清理可能殘留的 Xvfb lock 檔
rm -f /tmp/.X*-lock 2>/dev/null || true

if [ $PIPELINE_EXIT -eq 0 ]; then
    log "[OK] 每日流程全部成功"
else
    log "[WARN] 每日流程有部分失敗 (exit=$PIPELINE_EXIT)"
fi

exit $PIPELINE_EXIT
