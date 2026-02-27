# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Congressional Trading Intelligence System ("Political Alpha Monitor") — an AI-powered pipeline that monitors US congressional trading disclosures and generates investment signals using Gemini 2.5 Flash zero-shot reasoning. The project is written in **Python 3.9+** and uses **SQLite** for persistence.

Primary language in code comments and UI output is **Traditional Chinese (繁體中文)**.

## Setup & Running

```bash
# ── Windows (開發/偵錯) ──
.\venv\Scripts\Activate.ps1
pip install -r requirements_v3.txt
# 額外依賴: pip install google-genai beautifulsoup4 PyMuPDF playwright
# Playwright 瀏覽器: python -m playwright install chromium

# ── WSL2 (推薦，自動化排程) ──
bash setup_wsl.sh          # 一鍵安裝 WSL 環境 (Xvfb + venv + Playwright)
bash run_etl_wsl.sh --days 7  # 執行 ETL pipeline (免佔桌面)

# ── 主要入口 ──
python run_etl_pipeline.py --senate-only --days 7     # ETL: Senate 交易
python run_etl_pipeline.py --house-only --max-house 5  # ETL: House 交易
python run_etl_pipeline.py --days 14                   # ETL: 兩院都跑
python run_congress_discovery.py                        # AI Discovery: 投資訊號

# ── 報告生成（需要 Gemini CLI: npm install -g @anthropic-ai/gemini-cli）──
python generate_report.py                    # 今日報告
python generate_report.py --days 7           # 過去 7 天總結
python generate_report.py --date 2026-02-13  # 指定日期
python generate_report.py --days 90          # 長期總結

# ── 初始化資料庫 ──
python -c "from src.database import init_db; init_db()"
```

There is no test suite, no linter configuration, and no build step.

## Architecture

系統由三個子系統組成：**ETL Pipeline**（資料抓取）、**AI Discovery**（訊號生成）、**Report Generator**（報告生成）。

### ETL Pipeline (src/etl/) — LLM-Driven 融合架構

```
run_etl_pipeline.py                    ← CLI 入口 (argparse)
        │
        ▼
src/etl/pipeline.py                    ← 調度器 (CongressETLPipeline)
    │
    ├── Senate 路徑:
    │   SenateFetcher (Playwright + Akamai bypass)
    │       │ (失敗時自動 fallback)
    │       └── CapitolTradesFetcher (curl_cffi)
    │   → LLMTransformer (Gemini Flash, classified prompt)
    │   → Loader (Pydantic 驗證 + SHA256 去重 + SQLite)
    │
    └── House 路徑:
        HouseFetcher (requests POST + PDF 下載)
        → LLMTransformer (Gemini Vision, PDF→PNG→multimodal)
        → Loader (同上)

src/etl/schemas.py                     ← Pydantic 資料合約 (CongressTrade, ExtractionResult)
src/etl/base_fetcher.py                ← 抽象基底 (BaseFetcher, FetchResult, SourceType)
src/etl/senate_fetcher.py              ← Playwright 繞 Akamai WAF (headless=False + Xvfb)
src/etl/house_fetcher.py               ← House PDF 下載 (POST ViewMemberSearchResult)
src/etl/capitoltrades_fetcher.py       ← Capitol Trades fallback (1-based 分頁)
src/etl/llm_transformer.py             ← LLM Transform 核心 (3 種 prompt + retry ×3)
src/etl/loader.py                      ← Load 層 (confidence 門檻 + 去重 + DB 寫入)
```

### AI Discovery (原有系統)

```
run_congress_discovery.py              ← Entry point: iterates Tier 1/2 targets
        │
        ▼
src/discovery_engine_v4.py             ← Core AI agent (Gemini 2.5 Flash + google-search tool)
    │   Sends zero-shot prompts per target_type (CONGRESS / 13F / SOCIAL)
    │   Extracts JSON from LLM output, normalizes fields, saves signals
    │   Execution logic: impact_score >= 8 → OPEN, < 8 → CLOSE
    │
    ▼
src/database.py                        ← SQLite schema (data/data.db)
```

### Legacy Fetchers (獨立運行，未整合進 ETL)

```
src/senate_fetcher_v1.py               ← 舊版 Senate scraper (curl_cffi, 目前被 Akamai 擋)
src/house_fetcher_v3_ajax.py           ← 舊版 House scraper (DataTable protocol, 端點已變)
src/congress_trading_fetcher.py        ← 舊版統一介面
src/main.py                            ← 舊版 orchestrator (需從 src/ 目錄內執行)

Analysis Tools:
  src/congress_alpha_final.py          ← Historical alpha analysis from GitHub raw data
  src/sector_radar.py                  ← Sector enrichment via yfinance
  src/final_discovery_tool.py          ← Alternative discovery agent (reference)
```

## Database Schema

```sql
-- ETL Pipeline 輸出 (新)
congress_trades (id, chamber, politician_name, transaction_date, filing_date,
                 ticker, asset_name, asset_type, transaction_type, amount_range,
                 owner, comment, source_url, source_format, extraction_confidence,
                 data_hash UNIQUE, created_at)

extraction_log  (id, source_type, source_url, confidence, raw_record_count,
                 extracted_count, status, error_message, created_at)

-- AI Discovery 輸出 (原有)
ai_intelligence_signals, senate_trades, house_trades,
institutional_holdings, ocr_queue
```

## Key Configuration

- **`.env`** — must contain `GOOGLE_API_KEY` for Gemini API access
- **Database path** — `data/data.db` (hardcoded in `database.py`, `discovery_engine_v4.py`, `loader.py`)
- **Model** — `gemini-2.5-flash` (configurable via `--model` flag or constructor)

## Important Patterns

### ETL Pipeline

- **Senate Akamai bypass**: `senate_fetcher.py` 使用 **Playwright headless=False** 繞過 Akamai Bot Manager。headless=True 會被偵測。生產環境用 **WSL2 + Xvfb** 虛擬螢幕免佔桌面。流程：首頁 → 點擊 `#agree_statement` checkbox（自動導航到 /search/）→ 填表 → 攔截 DataTable AJAX 回應。
- **Capitol Trades fallback**: Senate EFD 失敗時自動切換。注意使用 **1-based 分頁**（`page=1` 起算，`page=0` 回傳空結果）。HTML 表格經 `_trim_capitoltrades_html()` 轉為純文字（243KB→1.7KB）再送 LLM。
- **House 端點**: `POST /FinancialDisclosure/ViewMemberSearchResult` 回傳 HTML（非 JSON）。PDF 連結在 `cols[0]`（Name 欄），不是 `cols[3]`。姓名格式 "LastName, Hon.. FirstName" 需解析。
- **Classified Prompts**: 三種專用 prompt — `SENATE_HTML_PROMPT`、`HOUSE_PDF_PROMPT`、`CAPITOLTRADES_HTML_PROMPT`，根據 `source_type` + `metadata.source_site` 路由。
- **LLM Transform retry**: Pydantic 驗證失敗時，將錯誤訊息附加到 prompt 尾部重試（最多 3 次）。
- **Deduplication**: SHA256 hash of (politician_name, transaction_date, ticker, amount_range, transaction_type)。
- **Confidence threshold**: `< 0.7` → `manual_review` 狀態，`≥ 0.7` → 自動寫入。
- **Python 3.9 相容**: 不使用 `dict | None` 語法（需 `Optional[dict]`），WSL Ubuntu 預設 Python 3.9/3.10。

### AI Discovery (原有)

- **JSON extraction from LLM**: `_extract_json()` strips markdown fences, finds JSON via regex, handles trailing commas.
- **Signal normalization**: Handles field name variants (`ticker`/`symbol`/`stock_code`, `score`/`impact_score`/`magnitude`).
- **Execution timing**: impact_score >= 8 → MOO (Market On Open); < 8 → MOC (Market On Close).
- **`src/main.py` imports**: Uses bare imports (no `src.` prefix), must run from inside `src/`.

## Data Sources

| Source | Endpoint | Fetcher | Status |
|--------|----------|---------|--------|
| Senate disclosures | efdsearch.senate.gov | `src/etl/senate_fetcher.py` (Playwright) | ✅ Akamai bypassed |
| Capitol Trades (fallback) | capitoltrades.com | `src/etl/capitoltrades_fetcher.py` | ✅ Working |
| House disclosures | disclosures-clerk.house.gov | `src/etl/house_fetcher.py` (PDF+Vision) | ✅ Working |
| Historical trades | GitHub raw CSV | `src/congress_alpha_final.py` | ✅ Working |
| Stock sector data | yfinance API | `src/sector_radar.py` | ✅ Working |
| AI analysis | Google Gemini API | `src/discovery_engine_v4.py` | ✅ Working |

## WSL2 Environment

Senate fetcher 需要 Playwright headless=False（Akamai 偵測 headless）。WSL2 + Xvfb 提供虛擬螢幕：

```bash
# 一次性設置
cd "/mnt/d/VScode_project/NLP data for trading"
bash setup_wsl.sh

# 執行 (免佔 Windows 桌面)
bash run_etl_wsl.sh --senate-only --days 7

# Windows Task Scheduler 排程
wsl -d Ubuntu -- bash -c "cd '/mnt/d/VScode_project/NLP data for trading' && bash run_etl_wsl.sh --days 7"
```

- venv 路徑: `.venv_wsl/`
- Xvfb 虛擬螢幕: 1920x1080x24
- 專案透過 `/mnt/d/` 直接存取 Windows 檔案

## bk/ Directory

Contains backups, older fetcher versions (v1/v2), and documentation files (`PROJECT_SPEC.md`, `CONGRESS_FETCHER_README.md`, `簡易使用說明.md`). These are reference/archive only.
