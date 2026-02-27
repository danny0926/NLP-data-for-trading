#!/bin/bash
# ============================================================
# WSL2 + Xvfb 環境設置腳本
# 在 WSL Ubuntu 終端中執行:
#   cd /mnt/d/VScode_project/NLP\ data\ for\ trading
#   bash setup_wsl.sh
# ============================================================

set -e  # 任何錯誤即停止

PROJECT_DIR="/mnt/d/VScode_project/NLP data for trading"
VENV_DIR="$PROJECT_DIR/.venv_wsl"

echo "============================================"
echo "  WSL2 + Xvfb 環境設置"
echo "============================================"

# ── Step 1: 系統依賴 ──
echo ""
echo "[1/5] 安裝系統依賴 (需要 sudo 密碼)..."
sudo apt-get update -qq 2>&1 | grep -v "nvidia" || true
sudo apt-get install -y xvfb python3-pip python3-venv \
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libdbus-1-3 libxkbcommon0 \
    libatspi2.0-0 libxcomposite1 libxdamage1 libxfixes3 \
    libxrandr2 libgbm1 libpango-1.0-0 libcairo2 libasound2 \
    libwayland-client0
echo "  ✓ 系統依賴安裝完成"

# ── Step 2: Python venv ──
echo ""
echo "[2/5] 建立 Python 虛擬環境..."
python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"
pip install --upgrade pip -q
echo "  ✓ venv 建立於 $VENV_DIR"

# ── Step 3: Python 依賴 ──
echo ""
echo "[3/5] 安裝 Python 依賴..."
cd "$PROJECT_DIR"

# 核心依賴
pip install -q \
    pydantic \
    python-dotenv \
    beautifulsoup4 \
    google-genai \
    PyMuPDF \
    curl_cffi \
    playwright

# 如果有 requirements 檔案，也安裝
if [ -f "requirements_v3.txt" ]; then
    pip install -q -r requirements_v3.txt 2>/dev/null || true
fi
echo "  ✓ Python 依賴安裝完成"

# ── Step 4: Playwright Chromium ──
echo ""
echo "[4/5] 安裝 Playwright Chromium (Linux 版)..."
python -m playwright install chromium
echo "  ✓ Playwright Chromium 安裝完成"

# ── Step 5: 驗證 ──
echo ""
echo "[5/5] 驗證安裝..."
python -c "
from playwright.sync_api import sync_playwright
print('  ✓ Playwright import OK')
"
which xvfb-run > /dev/null && echo "  ✓ xvfb-run 可用"
python -c "from google import genai; print('  ✓ google-genai OK')"
python -c "from pydantic import BaseModel; print('  ✓ pydantic OK')"
python -c "from bs4 import BeautifulSoup; print('  ✓ beautifulsoup4 OK')"

echo ""
echo "============================================"
echo "  設置完成！"
echo ""
echo "  執行方式:"
echo "    source $VENV_DIR/bin/activate"
echo "    cd \"$PROJECT_DIR\""
echo "    xvfb-run python run_etl_pipeline.py --senate-only --days 7"
echo ""
echo "  或使用 wrapper 腳本:"
echo "    bash run_etl_wsl.sh --senate-only --days 7"
echo "============================================"
