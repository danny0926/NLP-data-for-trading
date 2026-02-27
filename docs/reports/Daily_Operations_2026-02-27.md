# 每日營運摘要 — 2026-02-27

## Executive Summary

今日完成 **Political Alpha Monitor** 系統的重大突破，從數據品質修復到 Alpha 驗證到生產級模組建設，實現了從研究到可運營的跨越。

### 核心成就
- **5,345 筆歷史交易回測完成** — 確認國會交易存在統計顯著 alpha
- **12 個新模組** 從零開始建設完成
- **4 份研究報告** 產出 (RB-001/002/003 + Extended Backtest)
- **6 個新 DB table** 上線 (signal_quality_scores, convergence_signals, politician_rankings, alpha_signals, portfolio_positions, + daily report)

---

## Alpha 研究成果 — 核心發現

### 買入信號 (Buy)
| 資料集 | 樣本數 | CAR_5d | p-value | 結論 |
|--------|--------|--------|---------|------|
| Capitol Trades (近12月) | 1,509 | **+0.77%** | <0.001*** | 統計顯著 alpha |
| Senate Watcher (2019-20) | 964 | +0.44% | 0.013** | 確認存在 |

### 賣出信號 (Sale) — 反向指標
| 資料集 | 樣本數 | CAR_5d | CAR_60d | 結論 |
|--------|--------|--------|---------|------|
| Capitol Trades | 1,441 | -0.50% | **-5.49%*** | 反向交易：議員賣出 → 買入 |
| Senate Watcher | 1,079 | +1.05% | -0.66% | 短期正、長期弱反轉 |

### 最佳信號條件
- **House > Senate** (House CAR_5d = +0.19% vs Senate -0.28%)
- **金額 $15K-$50K** (CAR_20d = +1.45%, 最佳 risk-adjusted)
- **Filing lag < 15天** (CAR_5d = +1.13%, p=0.003)
- **多議員收斂** (同一標的多人同向交易 → 額外 +0.5% bonus)

---

## 今日建設的模組

### 核心分析模組
| 模組 | 路徑 | 功能 | 狀態 |
|------|------|------|------|
| Signal Quality Scorer | `src/signal_scorer.py` | 5維 SQS 評分 (Actionability/Timeliness/Conviction/InfoEdge/MarketImpact) | ✅ 已運行 |
| Alpha Backtest Engine | `src/alpha_backtest.py` | Event Study + Market-Adjusted CAR | ✅ 已運行 |
| Name Mapper | `src/name_mapping.py` | 跨系統政治人物姓名正規化 | ✅ 已運行 |
| Convergence Detector | `src/convergence_detector.py` | 多議員收斂信號偵測 | ✅ 6 事件 |
| Politician Ranker | `src/politician_ranking.py` | PIS 議員排名 | ✅ Top 5 |
| Historical Backtest | `run_historical_backtest.py` | Capitol Trades + Senate Watcher 歷史回測 | ✅ 5345 trades |

### 下午完成
| 模組 | 路徑 | 功能 | 狀態 |
|------|------|------|------|
| Daily Report Generator | `src/daily_report.py` | 每日彙總報告 (5 sections) | DONE |
| Alpha Signal Generator | `src/alpha_signal_generator.py` | 即時交易信號 (352 signals) | DONE |
| Portfolio Optimizer | `src/portfolio_optimizer.py` | MPT 投組配置 (35 positions) | DONE |
| Full Pipeline Orchestrator | `run_full_pipeline.py` | 一鍵統一 pipeline | DONE |

---

## 研究報告產出

| 編號 | 主題 | 核心發現 | 可操作性 |
|------|------|----------|----------|
| RB-001 | Signal Quality + Alpha | 建立 SQS 框架，確認 alpha 存在 | ⭐⭐⭐⭐⭐ |
| RB-002 | Multi-Politician Convergence | 6 收斂事件，GS 三人賣出最強 | ⭐⭐⭐⭐ |
| RB-003 | Sector Rotation | Energy sell(-21), Healthcare buy(+14) | ⭐⭐⭐ |
| Extended Backtest | Alpha 歷史驗證 | 5345 trades, Buy +0.77%, Sale contrarian | ⭐⭐⭐⭐⭐ |

---

## 資料庫現況

| Table | 行數 | 用途 |
|-------|------|------|
| congress_trades | 404 | ETL 抓取的交易 |
| ai_intelligence_signals | 102 | AI Discovery 信號 |
| signal_quality_scores | 404 | SQS 評分 |
| alpha_signals | 352 | Alpha 交易信號 |
| convergence_signals | 6 | 收斂信號 |
| politician_rankings | 17 | 議員排名 |
| portfolio_positions | 35 | 投組配置 |
| extraction_log | 37 | ETL 日誌 |

### 外部資料
- `data/ticker_sectors.json` — 226 個 ticker 的 GICS 分類

---

## 系統架構演進

```
今日前:
  ETL → DB → AI Discovery → Signals → [人工判讀]

今日後 (run_full_pipeline.py --analysis-only):
  ETL → DB → AI Discovery → Signals
              |                |
         Name Mapping    SQS Scoring (404)
              |                |
         Convergence     Alpha Backtest (5345 trades)
         Detector (6)         |
              |           Alpha Signal Generator (352)
         Politician           |
         Ranking (17)    Portfolio Optimizer (35 positions)
              |                |
         Daily Report    [可操作信號 + 投組配置]
```

---

## Git 活動

今日 commit 數: **22+**（含 agent 提交）
分支: `main`，全部已 push 至 `origin/main`

---

## 次日待辦

### P0（必須）
1. ☐ 執行 ETL pipeline 抓取最新交易 (`--days 7`)
2. ☐ 執行 AI Discovery 生成新信號

### P1（重要）
3. ☐ 修正 Capitol Trades ticker 提取率（目前~65%，目標>90%）
4. ☐ 整合 Alpha Signal Generator 到主 pipeline
5. ☐ 設定 Windows Task Scheduler 自動排程

### P2（優化）
6. ☐ Fama-French 三因子模型取代 Market-Adjusted Model
7. ☐ SEC Form 4 資料整合（增加資料來源）
8. ☐ PostgreSQL 遷移（scalability）
9. ☐ 前端 Dashboard（Streamlit 或 Gradio）

---

*報告自動生成 — Political Alpha Monitor Operations Team*
*2026-02-27 18:35 CST (最終更新)*
