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
# Dashboard 依賴: pip install -r requirements_dashboard.txt  (streamlit, plotly)
# Playwright 瀏覽器: python -m playwright install chromium

# ── WSL2 (推薦，自動化排程) ──
bash setup_wsl.sh          # 一鍵安裝 WSL 環境 (Xvfb + venv + Playwright)
bash run_etl_wsl.sh --days 7  # 執行 ETL pipeline (免佔桌面)
bash run_daily_wsl.sh         # 每日完整流程 (WSL2 wrapper)
bash cron_setup.sh            # 設定 WSL2 cron 排程

# ── 每日自動化（推薦）──
python run_daily.py                              # 完整每日流程 (Smoke→ETL→Discovery→Analysis→Dashboard)
python run_daily.py --skip-etl                   # 跳過 ETL
python run_daily.py --analysis-only              # 只跑分析 + Dashboard
python run_daily.py --days 7                     # ETL 回溯天數（預設 3）

# ── 統一 Pipeline ──
python run_full_pipeline.py                      # 完整 pipeline (ETL→Discovery→Analysis)
python run_full_pipeline.py --analysis-only      # 只跑分析 (SQS/收斂/排名/信號/投組)
python run_full_pipeline.py --skip-etl           # 跳過 ETL
python run_full_pipeline.py --days 14            # ETL 回溯 14 天

# ── 個別入口 ──
python run_etl_pipeline.py --senate-only --days 7     # ETL: Senate 交易
python run_etl_pipeline.py --house-only --max-house 5  # ETL: House 交易
python run_congress_discovery.py                        # AI Discovery: 投資訊號
python run_sec_form4.py --days 7 --cross-ref            # SEC Form 4 抓取 + 交叉比對
python run_fama_french_backtest.py                      # Fama-French 三因子回測

# ── 分析模組 ──
python -m src.signal_scorer                    # SQS 信號評分
python -m src.convergence_detector             # 多議員收斂偵測
python -m src.politician_ranking               # 議員 PIS 排名
python -m src.alpha_signal_generator           # Alpha 信號生成
python -m src.portfolio_optimizer              # 投組最佳化
python -m src.daily_report                     # 每日報告
python -m src.daily_report --days 7            # 過去 7 天總結
python -m src.smart_alerts --dry-run           # 智慧告警（預覽模式）
python -m src.signal_tracker                   # 信號績效追蹤

# ── Dashboard ──
streamlit run streamlit_app.py                 # 互動式 Streamlit 儀表板
python generate_dashboard.py                   # 生成靜態 HTML Dashboard

# ── 系統健康檢查 ──
python smoke_test.py                           # 全模組 smoke test

# ── 初始化資料庫 ──
python -c "from src.database import init_db; init_db()"
```

There is no test suite, no linter configuration, and no build step.

## Architecture

系統由七個子系統組成：**ETL Pipeline**（資料抓取）、**AI Discovery**（訊號生成）、**Signal Analysis**（信號分析與回測）、**Portfolio Optimization**（投組配置）、**Report & Alerts**（報告與告警）、**Dashboard**（互動式視覺化）、**Scheduling**（自動排程）。統一入口: `run_full_pipeline.py`、`run_daily.py`。

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
src/etl/sec_form4_fetcher.py           ← SEC EDGAR Form 4 insider trading (XML 解析)
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

### Signal Analysis & Backtesting (src/)

```
src/signal_scorer.py                   ← SQS 5 維度加權評分 (Actionability/Timeliness/Conviction/InfoEdge/MarketImpact)
src/convergence_detector.py            ← 多議員匯聚訊號偵測 (30 天窗口, 跨院加分)
src/politician_ranking.py              ← PIS 議員排名 (Activity/Conviction/Diversification/Timing)
src/alpha_signal_generator.py          ← Alpha 信號生成 (基於回測實證 + SQS + 收斂)
src/alpha_backtest.py                  ← Event Study 回測引擎 (CAR_5d/20d/60d vs SPY)
src/fama_french.py                     ← Fama-French 三因子模型 (FF3 factor-adjusted CAR)
src/signal_tracker.py                  ← 信號績效追蹤 (hit rate, actual alpha, MAE/MFE)
src/name_mapping.py                    ← 跨系統議員姓名標準化 (ETL ↔ Discovery 名稱映射)
src/ticker_enricher.py                 ← Ticker 補全 (靜態映射 → 模式偵測 → yfinance 搜尋)
```

### Portfolio & Reporting (src/)

```
src/portfolio_optimizer.py             ← MPT 投組最佳化 (max 10% 單一標的, min 2%)
src/daily_report.py                    ← 每日 Markdown 報告 (匯整全部資料來源)
src/smart_alerts.py                    ← 5 類智慧告警 (高 alpha/收斂/大額/$100K+/異常 filing lag)
```

### Dashboard & Automation

```
streamlit_app.py                       ← Streamlit 互動式儀表板 (Plotly 圖表)
generate_dashboard.py                  ← 靜態 HTML Dashboard 生成器
run_full_pipeline.py                   ← 統一 Pipeline 調度器 (ETL→Discovery→Analysis)
run_daily.py                           ← 每日自動排程器 (Smoke→ETL→Discovery→Analysis→Dashboard)
run_sec_form4.py                       ← SEC Form 4 入口 (抓取 + 國會交易交叉比對)
run_fama_french_backtest.py            ← FF3 回測入口 (Market-Adjusted vs FF3 比較)
smoke_test.py                          ← 系統健康檢查 (全模組 import + DB 驗證)

Scheduling:
  setup_scheduler.ps1                  ← Windows Task Scheduler 設定
  run_daily_wsl.sh                     ← WSL2 每日執行 wrapper
  cron_setup.sh                        ← WSL2 cron 排程設定
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
-- ETL Pipeline 輸出
congress_trades (id, chamber, politician_name, transaction_date, filing_date,
                 ticker, asset_name, asset_type, transaction_type, amount_range,
                 owner, comment, source_url, source_format, extraction_confidence,
                 data_hash UNIQUE, created_at)

extraction_log  (id, source_type, source_url, confidence, raw_record_count,
                 extracted_count, status, error_message, created_at)

sec_form4_trades (id, accession_number, filer_name, filer_title, issuer_name,
                  ticker, transaction_type, transaction_date, shares, price_per_share,
                  total_value, ownership_type, source_url, data_hash UNIQUE, created_at)

-- Signal Analysis 輸出
signal_quality_scores (id, trade_id UNIQUE, politician_name, ticker, sqs, grade, action,
                       actionability, timeliness, conviction, information_edge,
                       market_impact, scored_at)

convergence_signals (id, ticker, direction, politician_count, politicians, chambers,
                     window_start, window_end, span_days, score, score_base,
                     score_cross_chamber, score_time_density, score_amount_weight, detected_at)

politician_rankings (politician_name PK, chamber, total_trades, avg_trade_size,
                     trades_per_month, unique_tickers, buy_count, sale_count,
                     pis_activity, pis_conviction, pis_diversification, pis_timing,
                     pis_total, rank, updated_at)

alpha_signals (id, trade_id, ticker, asset_name, politician_name, chamber,
               transaction_type, direction, expected_alpha_5d, expected_alpha_20d,
               confidence, signal_strength, combined_multiplier, convergence_bonus,
               has_convergence, politician_grade, filing_lag_days, sqs_score, sqs_grade,
               reasoning, created_at)

-- Portfolio & Performance
portfolio_positions (id, ticker, sector, weight, conviction_score, expected_alpha,
                     volatility_30d, sharpe_estimate, reasoning, created_at)

signal_performance (id, signal_id UNIQUE, ticker, direction, signal_date,
                    expected_alpha_5d/20d, actual_return_5d/20d, actual_alpha_5d/20d,
                    spy_return_5d/20d, hit_5d, hit_20d, signal_strength, confidence,
                    max_favorable_excursion, max_adverse_excursion, evaluated_at)

fama_french_results (id, politician_name, ticker, transaction_type, direction,
                     transaction_date, filing_date, filing_lag, amount_range, chamber,
                     ff3_car_5d/20d/60d, mkt_car_5d/20d/60d, alpha_est,
                     beta_mkt, beta_smb, beta_hml, r_squared, n_est, created_at)

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

### Signal Analysis

- **SQS 評分**: 5 維度加權 — Actionability(0.30), Timeliness(0.20), Conviction(0.25), InfoEdge(0.15), MarketImpact(0.10)。品質等級: Platinum(80+)→自動信號, Gold(60-79)→MOC, Silver(40-59)→觀察, Bronze(20-39)→人工審閱, Discard(<20)→淘汰。
- **收斂偵測**: 30 天窗口內 2+ 議員同方向交易同一 ticker。評分考慮議員數量、跨院加分(+0.5)、時間密度、金額加權。
- **PIS 議員排名**: 四維度 — Activity(交易頻率)、Conviction(平均規模)、Diversification(標的多樣性)、Timing(申報時效)。
- **Alpha 信號**: 基於回測實證 (Buy +0.77% CAR_5d, Sale 反向 alpha)。乘數調整: chamber、amount($15K-$50K 最強)、filing_lag(<15d)、politician_grade。方向: Buy→LONG, Sale→LONG(反向 alpha)。
- **Name mapping**: `name_mapping.py` 解決 ETL 格式 ("David H McCormick") vs Discovery 格式 ("Dave McCormick") 的名稱不匹配。使用 canonical name + alias 映射。
- **Ticker enrichment**: `ticker_enricher.py` 四層策略 — 靜態映射 → 模式偵測 → yfinance 搜尋 → 不可解析標記。

### Backtesting

- **Event Study**: 事件日=Filing Date，窗口 [0,+5/+20/+60] 交易日，Benchmark=SPY。
- **Fama-French 3-Factor**: 估計窗口 [-250,-10]，OLS 回歸 R-Rf = a + b1(Mkt-RF) + b2(SMB) + b3(HML)。因子數據自動從 Kenneth French Data Library 下載並快取於 `data/ff_factors_daily.csv`。
- **Signal Tracker**: 追蹤已生成信號的實際表現，計算 hit rate、actual alpha、MAE/MFE，寫入 `signal_performance` 表。

### SEC Form 4

- **EDGAR API**: 使用 EFTS search-index 搜尋 Form 4 filings，解析 XML 取得交易詳情。必須含 User-Agent header（含信箱），速率限制 10 req/s。
- **Cross-reference**: `run_sec_form4.py --cross-ref` 比對 `sec_form4_trades` 與 `congress_trades` 同 ticker，找出國會議員與公司內部人同向交易的強力訊號。

### Portfolio & Alerts

- **MPT 投組**: 最大單一權重 10%，最小 2%。基於 conviction_score、expected_alpha、volatility 計算 Sharpe estimate。每次執行清空舊持倉重新計算。
- **Smart Alerts**: 5 類觸發 — 高強度 alpha(>0.7)、收斂信號、大額交易($100K+)、Top 議員新交易(PIS A/B)、異常 filing lag(<3天)。

### Streamlit Dashboard

- **互動式儀表板**: `streamlit_app.py` 使用 Plotly 圖表，直接讀取 `data/data.db`。安裝: `pip install -r requirements_dashboard.txt`。
- **靜態 Dashboard**: `generate_dashboard.py` 輸出獨立 HTML 檔，無需伺服器。

### Scheduling (自動排程)

- **Windows**: `setup_scheduler.ps1` 設定 Windows Task Scheduler。
- **WSL2**: `run_daily_wsl.sh` 封裝 + `cron_setup.sh` 設定 cron job。
- **統一入口**: `run_daily.py` — Smoke Test → ETL → Discovery → Analysis → Dashboard → 驗證，支援 `--skip-etl`、`--analysis-only`、`--days N`。

## Data Sources

| Source | Endpoint | Fetcher | Status |
|--------|----------|---------|--------|
| Senate disclosures | efdsearch.senate.gov | `src/etl/senate_fetcher.py` (Playwright) | ✅ Akamai bypassed |
| Capitol Trades (fallback) | capitoltrades.com | `src/etl/capitoltrades_fetcher.py` | ✅ Working |
| House disclosures | disclosures-clerk.house.gov | `src/etl/house_fetcher.py` (PDF+Vision) | ✅ Working |
| Historical trades | GitHub raw CSV | `src/congress_alpha_final.py` | ✅ Working |
| Stock sector data | yfinance API | `src/sector_radar.py` | ✅ Working |
| SEC Form 4 insider trading | SEC EDGAR EFTS API | `src/etl/sec_form4_fetcher.py` (XML) | ✅ Working |
| Fama-French factors | Kenneth French Data Library | `src/fama_french.py` (daily CSV) | ✅ Working |
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
