# CEO 營運審閱報告
日期: 2026-02-27

---

## 一、本輪營運結果評估

### 1.1 資料擷取成果

| 指標 | 數值 | 評價 |
|------|------|------|
| 交易紀錄總數 | 404 筆 | 合格 — 首輪完整運作的基線數據 |
| House 交易 | 347 筆 (85.9%) | 良好 — PDF 解析管線穩定 |
| Senate 交易 | 57 筆 (14.1%) | 偏低 — Akamai 繞過成功但產出較少 |
| 涵蓋議員 | 17 位 | 不足 — 目標清單 30 位，覆蓋率僅 57% |
| 不同 Ticker | 262 個 | 良好 — 資產多樣性充足 |
| 日期範圍 | 2025-12-01 ~ 2026-12-26 | 警告 — 未來日期(2026-12-26)為資料異常 |
| 提取信心度 >= 0.9 | 403/404 (99.8%) | 優秀 — LLM 解析品質極高 |

**ETL 管線評分: B+** — 基礎設施穩定運作，但覆蓋率和資料品質仍有提升空間。

### 1.2 AI Discovery 信號成果

| 指標 | 數值 | 評價 |
|------|------|------|
| 信號總數 | 102 個 | 合格 |
| 高影響力 (score >= 8) | 17 個 (16.7%) | 合理比例 |
| 中等影響 (score 6-7) | 45 個 (44.1%) | 正常 |
| 低影響 (score < 6) | 17 個 (16.7%) | 正常 |
| NULL score | 23 個 (22.5%) | **嚴重問題** — 近 1/4 信號無評分 |
| 有 Ticker 的信號 | 37/102 (36%) | **核心問題** — 64% 信號無法直接操作 |

**AI Discovery 評分: C+** — 產出量可接受，但信號品質嚴重制約可操作性。

### 1.3 關鍵高影響力信號摘要

| 議員 | Ticker | Score | 方向 | 可操作性 |
|------|--------|-------|------|---------|
| Nancy Pelosi | AB | 9 | Positive | 可操作 |
| Nancy Pelosi | GOOGL | 8 | Positive | 可操作 |
| Nancy Pelosi | AMZN | 8 | Positive | 可操作 |
| Richard Blumenthal | BINANCE | 9 | Negative | 不可操作 (非上市股票) |
| Julie Johnson | (無) | 9 | Positive | 不可操作 |
| Markwayne Mullin | CVX | 8 | Positive | 可操作 |
| Markwayne Mullin | RTX | 8 | Positive | 可操作 |
| Debbie Wasserman Schultz | ICHR | 8 | Positive | 可操作 |
| Josh Gottheimer | (無) | 8 | Positive | 不可操作 |
| Jefferson Shreve | (無) | 8 | Positive | 不可操作 |
| Ted Cruz | (無) | 8 | Negative | 不可操作 |
| Ron Wyden | (無) | 8 | Negative | 不可操作 |
| Marjorie Taylor Greene | (無) | 8 | Neutral | 不可操作 |
| Lisa McClain | (無) | 8 | Neutral/Negative | 不可操作 |

**可操作信號: 17 個高影響力中僅 6 個 (35%) 有有效 Ticker** — 這是當前系統最大的效率瓶頸。

---

## 二、關鍵發現與問題

### 2.1 嚴重問題 (需立即處理)

**P0: 信號可操作性不足**
- 102 個 AI 信號中，僅 37 個 (36%) 有 Ticker
- 17 個高影響力信號中，僅 6 個 (35%) 可直接交易
- 根本原因: Discovery Engine 的 zero-shot prompt 對議員交易新聞的解析，經常無法提取出具體股票代號。議員交易本身就有 ticker（在 `congress_trades` 表中），但 AI Discovery 走的是獨立的 Google Search 路徑，未能有效關聯 ETL 已擷取的結構化交易數據

**P1: 資料日期異常**
- 交易日期最大值為 2026-12-26，明顯是未來日期（今天是 2026-02-27）
- 可能原因: LLM 解析日期時產生幻覺，或原始資料的年份格式解析錯誤
- 需排查具體紀錄並修正 LLM prompt 的日期驗證邏輯

**P2: 23 個信號 impact_score 為 NULL**
- 佔總信號的 22.5%，代表 LLM 回傳格式不符預期
- `_extract_json()` 的解析或 signal normalization 未能正確處理這些案例

### 2.2 中等問題

**M1: 議員覆蓋率不足**
- 目標清單 30 位，實際覆蓋 17 位 (57%)
- 13 位議員可能無近期交易揭露，也可能是 fetcher 未能觸及
- 建議: 區分「無交易紀錄」vs「擷取失敗」，加入覆蓋率追蹤指標

**M2: Gilbert Cisneros 交易量異常集中**
- 單一議員佔 272/404 = 67% 的交易紀錄
- 151 筆買入 + 121 筆賣出，可能是大規模投資組合調整
- 這會嚴重偏斜統計指標，應考慮加權或分類處理

**M3: BINANCE 作為 Ticker 的誤判**
- Richard Blumenthal 的高分信號 ticker 為 "BINANCE"，但 Binance 並非上市公司
- AI Discovery 將新聞關鍵字誤判為可交易 ticker
- 需加入 ticker 驗證層（對照 NYSE/NASDAQ 上市公司清單）

### 2.3 正面發現

- **ETL 提取品質極高**: 99.8% 的紀錄信心度 >= 0.9，LLM Transform 管線非常穩定
- **House PDF 解析成功率佳**: 24 個 PDF 中 23 個成功 (96%)
- **Senate fallback 機制運作正常**: Capitol Trades 作為備援成功提供數據
- **Pelosi 信號具參考價值**: AB (AllianceBernstein), GOOGL, AMZN 三個高分信號均為可操作的大型股
- **能源/國防板塊信號清晰**: Mullin 的 CVX (Chevron) + RTX (Raytheon) 反映能源/國防政策預期

---

## 三、研究方向指示

### 優先研究課題: 信號品質提升與 Alpha 驗證

經評估五個候選方向，我的決定如下:

- **(c) 信號品質提升** 和 **(b) Alpha 驗證** 合併為一個優先研究課題
- 理由: 64% 的信號無 ticker 是當前系統最大的「價值漏斗瓶頸」。在信號不可操作的情況下，增加數據源 (a) 或建立推送系統 (d) 都是在「放大一個有缺陷的產品」。同時，若不驗證議員交易是否真有 alpha，整個系統的投資價值假設就是未經驗證的

### 優先課題: 信號品質提升 + Alpha 回測驗證

- **研究目標**:
  1. 將信號可操作率從 36% 提升至 80%+（通過 ETL 數據與 AI Discovery 的交叉關聯）
  2. 回測驗證議員交易的超額報酬是否統計顯著
  3. 建立信號品質評分框架，淘汰低品質信號

- **預期成果**:
  1. 改進後的 Discovery Engine，能自動從 `congress_trades` 表關聯 ticker 到信號
  2. 議員交易 Alpha 回測報告（至少 12 個月歷史數據，含 Sharpe ratio、hit rate）
  3. 信號品質儀表板指標（可操作率、ticker 覆蓋率、score 分布）

- **交付物**:
  1. `src/signal_enrichment.py` — 信號 ticker 自動補全模組
  2. `src/alpha_backtest.py` — Alpha 回測引擎
  3. `docs/reports/Alpha_Validation_Report.md` — 回測結果報告
  4. Dashboard 新增信號品質 tab

- **期限建議**: 2 週（第 1 週: 信號品質提升 + 回測框架 / 第 2 週: 驗證 + 報告）

### 次要研究課題（排隊）

| 優先序 | 課題 | 理由 | 預估時程 |
|--------|------|------|---------|
| 2 | (d) 即時通知系統 | 信號品質提升後，高分信號的即時推送才有價值。Telegram bot 基礎已建好 | 3 天 |
| 3 | (a) SEC Form 4 整合 | 增加機構交易維度，但需先確認議員交易本身有 alpha 再擴展 | 1 週 |
| 4 | (e) PostgreSQL 遷移 | 404 筆數據量下 SQLite 完全足夠，待數據量破萬再考慮 | 1 週 |

---

## 四、對各部門的指示

### CTO (技術長):
1. **立即修復**: 資料日期異常（2026-12-26 未來日期）— 排查 `llm_transformer.py` 的日期解析邏輯，加入日期範圍驗證（transaction_date 不可超過 filing_date + 30 天）
2. **立即修復**: 23 個 NULL impact_score 信號 — 排查 `discovery_engine_v4.py` 的 `_extract_json()` 和 signal normalization，確保 LLM 回傳格式異常時有 fallback
3. **架構改進**: 設計 `congress_trades` → `ai_intelligence_signals` 的 ticker 關聯機制，讓 Discovery Engine 在生成信號時能查詢已有的結構化交易數據
4. **技術債務**: BINANCE 等非上市公司 ticker 的過濾 — 加入 ticker 驗證層

### CDO (首席資料官):
1. **資料品質**: 建立每日資料品質儀表板指標 — 覆蓋率（議員數/目標數）、可操作率（有 ticker 信號/總信號）、信心度分布
2. **異常偵測**: Gilbert Cisneros 272 筆交易需人工審核 — 確認是否為正常的大規模投資組合調整，還是 ETL 重複擷取
3. **歷史數據**: 準備至少 12 個月的議員交易歷史數據（可利用 `congress_alpha_final.py` 的 GitHub CSV 源），用於 Alpha 回測

### CPO (首席產品官):
1. **Dashboard 優化**: 在 Streamlit Dashboard 增加「信號品質」tab — 顯示可操作率趨勢、ticker 覆蓋率、score 分布
2. **使用者反饋**: 設計信號反饋機制 — 讓使用者標記信號是否有用，建立品質改善回饋迴路
3. **產品路線圖**: 信號品質達標(可操作率 > 80%)後，優先推出 Telegram 即時推送功能

---

## 五、CEO 總結

本輪營運證明了 Political Alpha Monitor 的 **基礎設施已穩定運作** — ETL 管線的 99.8% 高信心度提取是一個出色的技術成就。然而，系統的 **價值鏈存在明顯瓶頸**: 從「資料擷取」到「可操作信號」的轉換率僅 36%，意味著我們擷取了大量高品質的原始數據，卻未能有效轉化為投資決策。

**核心策略方向**: 在擴展數據源或功能之前，先聚焦提升現有信號的品質和可操作性，並通過 Alpha 回測驗證我們的核心價值假設 — 國會議員交易確實能產生超額報酬。只有在這個假設得到數據支撐後，後續的擴展（更多數據源、即時推送、機構交易整合）才有意義。

**下一個里程碑**: 信號可操作率達到 80%，並完成首份 Alpha 回測報告。

---

*報告生成時間: 2026-02-27*
*資料快照: data/data.db (404 trades, 102 signals)*
*系統版本: Political Alpha Monitor v1.0 (Phase 1 Complete)*
