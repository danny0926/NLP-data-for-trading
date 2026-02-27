# Political Alpha Monitor

美國國會議員交易情報系統 — 透過 AI 驅動的 ETL pipeline 監控國會議員財務揭露，自動生成投資訊號與分析報告。

## 功能概覽

- **ETL Pipeline** — 自動抓取 Senate / House 財務揭露資料，經 LLM 結構化後寫入資料庫
- **AI Discovery** — 針對高績效議員進行 zero-shot 分析，產生帶有 impact score 的投資訊號
- **Report Generator** — 從資料庫查詢交易紀錄，透過 Gemini 生成每日 / 週期分析報告

## 系統架構

```
┌────────────────────────────────────────────────────────┐
│  ETL Pipeline (run_etl_pipeline.py)                    │
│                                                        │
│  Senate ─→ Playwright (Akamai bypass)                  │
│            ↘ fallback: Capitol Trades (curl_cffi)      │
│               ─→ LLM Transform (Gemini Flash)          │
│                    ─→ Pydantic 驗證 + SHA256 去重       │
│                         ─→ SQLite (congress_trades)    │
│                                                        │
│  House  ─→ PDF 下載 (requests POST)                    │
│               ─→ LLM Vision (PDF→PNG→multimodal)       │
│                    ─→ 同上                              │
├────────────────────────────────────────────────────────┤
│  AI Discovery (run_congress_discovery.py)               │
│  Gemini 2.5 Flash + google-search ─→ ai_intelligence_ │
│  signals (impact_score ≥ 8 → MOO, < 8 → MOC)          │
├────────────────────────────────────────────────────────┤
│  Report Generator (generate_report.py)                  │
│  SQLite query ─→ 統計摘要 ─→ Gemini CLI ─→ Markdown    │
└────────────────────────────────────────────────────────┘
```

## 資料來源

| 來源 | 網站 | 方法 |
|------|------|------|
| Senate 財務揭露 | efdsearch.senate.gov | Playwright headless=False |
| Capitol Trades (fallback) | capitoltrades.com | curl_cffi |
| House 財務揭露 | disclosures-clerk.house.gov | PDF 下載 + Gemini Vision |
| 股票產業分類 | Yahoo Finance | yfinance API |

## 安裝

### 前置需求

- Python 3.9+
- [Google Gemini API Key](https://ai.google.dev/) (存放於 `.env`)
- (選用) Gemini CLI — 報告生成功能需要

### Windows 開發環境

```bash
# 建立虛擬環境
python -m venv venv
.\venv\Scripts\Activate.ps1

# 安裝依賴
pip install -r requirements_v3.txt
pip install google-genai beautifulsoup4 PyMuPDF playwright

# 安裝 Playwright 瀏覽器
python -m playwright install chromium

# 設定 API Key
echo GOOGLE_API_KEY=your_key_here > .env

# 初始化資料庫
python -c "from src.database import init_db; init_db()"
```

### WSL2 自動化環境 (推薦)

Senate fetcher 需要 Playwright headless=False，WSL2 + Xvfb 提供虛擬螢幕，免佔 Windows 桌面。

```bash
cd "/mnt/d/VScode_project/NLP data for trading"
bash setup_wsl.sh          # 一鍵安裝
```

## 使用方式

### ETL Pipeline — 抓取交易資料

```bash
# 預設：Senate 7 天 + House 今年
python run_etl_pipeline.py

# 只跑 Senate，回溯 14 天
python run_etl_pipeline.py --senate-only --days 14

# 只跑 House，最多 5 份 PDF
python run_etl_pipeline.py --house-only --max-house 5

# 兩院都跑，回溯 30 天
python run_etl_pipeline.py --days 30
```

### AI Discovery — 投資訊號

```bash
python run_congress_discovery.py
```

對 Tier 1/2 目標議員進行 Gemini zero-shot 分析，產生帶有 impact score 的交易訊號寫入 `ai_intelligence_signals` 表。

### 報告生成

```bash
python generate_report.py                    # 今日報告
python generate_report.py --days 7           # 過去 7 天總結
python generate_report.py --date 2026-02-13  # 指定日期
```

報告自動儲存至 `reports/` 目錄。

### WSL2 自動化排程

```bash
# 手動執行
bash run_etl_wsl.sh --senate-only --days 7

# Windows Task Scheduler 排程
wsl -d Ubuntu -- bash -c "cd '/mnt/d/VScode_project/NLP data for trading' && bash run_etl_wsl.sh --days 7"
```

## 資料庫結構

資料存放在 `data/data.db` (SQLite)。

| 表名 | 用途 |
|------|------|
| `congress_trades` | ETL Pipeline 統一交易紀錄 |
| `extraction_log` | ETL 萃取紀錄 / 錯誤追蹤 |
| `ai_intelligence_signals` | AI Discovery 投資訊號 |
| `senate_trades` | 舊版 Senate 交易 (legacy) |
| `house_trades` | 舊版 House 交易 (legacy) |

## 專案結構

```
├── run_etl_pipeline.py            # ETL 入口
├── run_congress_discovery.py      # AI Discovery 入口
├── generate_report.py             # 報告生成入口
├── setup_wsl.sh                   # WSL 一鍵安裝
├── run_etl_wsl.sh                 # WSL ETL 執行腳本
├── requirements_v3.txt            # Python 依賴
├── .env                           # API Key (不進版控)
├── data/
│   └── data.db                    # SQLite 資料庫
├── reports/                       # 生成的報告
├── src/
│   ├── database.py                # DB schema + init
│   ├── discovery_engine_v4.py     # AI Discovery 核心
│   ├── sector_radar.py            # 產業分類 (yfinance)
│   ├── congress_alpha_final.py    # 歷史績效分析
│   └── etl/
│       ├── pipeline.py            # ETL 調度器
│       ├── schemas.py             # Pydantic 資料合約
│       ├── base_fetcher.py        # Fetcher 抽象基底
│       ├── senate_fetcher.py      # Senate 抓取 (Playwright)
│       ├── house_fetcher.py       # House PDF 下載
│       ├── capitoltrades_fetcher.py  # Capitol Trades fallback
│       ├── llm_transformer.py     # LLM 結構化核心
│       └── loader.py              # 驗證 + 去重 + 寫入
└── bk/                            # 備份 / 舊版程式 (參考用)
```

## 技術重點

- **Akamai WAF bypass**: Playwright `headless=False` 搭配 WSL2 Xvfb 虛擬螢幕，突破 Senate EFD 的 Bot Manager
- **LLM-Driven Transform**: 使用 Gemini 2.5 Flash 搭配三種分類 prompt (Senate HTML / House PDF / Capitol Trades)，將非結構化資料轉為 Pydantic model
- **自動 retry**: Pydantic 驗證失敗時，將錯誤訊息附加至 prompt 重試 (最多 3 次)
- **SHA256 去重**: 以 (politician_name, transaction_date, ticker, amount_range, transaction_type) 組合雜湊，避免重複寫入
- **信心度門檻**: `extraction_confidence < 0.7` 標記為 `manual_review`，`≥ 0.7` 自動寫入

## License

Private repository. All rights reserved.
