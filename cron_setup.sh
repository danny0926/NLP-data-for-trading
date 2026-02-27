#!/bin/bash
# ============================================================
# Political Alpha Monitor — WSL2 Cron 排程設定
# 在 WSL Ubuntu 終端中執行:
#   cd /mnt/d/VScode_project/NLP\ data\ for\ trading
#   bash cron_setup.sh
#
# 建立的 cron 排程:
#   1. 每天 06:00 — 完整每日流程 (--days 3)
#   2. 每週日 05:00 — 擴大回溯 (--days 14)
# ============================================================

set -euo pipefail

PROJECT_DIR="/mnt/d/VScode_project/NLP data for trading"
SCRIPT="$PROJECT_DIR/run_daily_wsl.sh"
CRON_TAG="# PoliticalAlphaMonitor"

echo "============================================"
echo "  Political Alpha Monitor — Cron 排程設定"
echo "============================================"
echo ""

# ── 驗證 ──
if [ ! -f "$SCRIPT" ]; then
    echo "[ERROR] 找不到 $SCRIPT"
    exit 1
fi

# 確保腳本可執行
chmod +x "$SCRIPT"

# ── 確保 cron 服務啟動 ──
echo "[1/3] 啟動 cron 服務..."
if command -v systemctl &> /dev/null && systemctl is-active --quiet cron 2>/dev/null; then
    echo "  cron 已在運行中"
else
    sudo service cron start 2>/dev/null || true
    echo "  cron 服務已啟動"
fi

# ── 移除舊的排程 ──
echo ""
echo "[2/3] 清除舊的排程..."
# 備份現有 crontab
crontab -l 2>/dev/null > /tmp/crontab_backup.txt || true
# 移除舊的 PoliticalAlphaMonitor 排程
grep -v "$CRON_TAG" /tmp/crontab_backup.txt > /tmp/crontab_clean.txt 2>/dev/null || true
echo "  已清除舊排程"

# ── 新增排程 ──
echo ""
echo "[3/3] 新增排程..."

cat >> /tmp/crontab_clean.txt << CRON_EOF
# === Political Alpha Monitor 自動排程 === $CRON_TAG
# 每天 06:00 (台灣時間) — 完整每日流程
0 6 * * * cd "$PROJECT_DIR" && bash run_daily_wsl.sh --days 3 >> "$PROJECT_DIR/logs/cron_daily.log" 2>&1 $CRON_TAG
# 每週日 05:00 — 擴大回溯 14 天
0 5 * * 0 cd "$PROJECT_DIR" && bash run_daily_wsl.sh --days 14 >> "$PROJECT_DIR/logs/cron_weekly.log" 2>&1 $CRON_TAG
CRON_EOF

# 安裝新的 crontab
crontab /tmp/crontab_clean.txt
echo "  排程已安裝"

# ── 驗證 ──
echo ""
echo "============================================"
echo "  Cron 排程設定完成！"
echo "============================================"
echo ""
echo "  目前的 cron 排程:"
echo "  ---"
crontab -l | grep -A1 "$CRON_TAG" || echo "  (無排程)"
echo "  ---"
echo ""
echo "  手動測試:"
echo "    bash run_daily_wsl.sh --analysis-only"
echo ""
echo "  查看 cron 日誌:"
echo "    tail -f $PROJECT_DIR/logs/cron_daily.log"
echo ""
echo "  移除所有排程:"
echo "    crontab -l | grep -v '$CRON_TAG' | crontab -"
echo ""

# 清理暫存檔
rm -f /tmp/crontab_backup.txt /tmp/crontab_clean.txt
