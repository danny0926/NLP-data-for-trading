# RB-001: Signal Quality Enhancement & Alpha Validation

**狀態**: Draft
**研究主管**: Research Lead
**日期**: 2026-02-27
**委託方**: CEO

---

## 一、問題定義

### 1.1 核心瓶頸：信號可操作率過低

本系統（Political Alpha Monitor）目前產生的 AI Discovery 信號存在嚴重的可操作性問題：

| 指標 | 數值 | 說明 |
|------|------|------|
| AI 信號總數 | 102 | `ai_intelligence_signals` 表 |
| 有 Ticker 信號 | 37 (36.3%) | 僅三分之一可直接用於交易 |
| 高影響力信號 (score>=8) | 17 | 應優先執行的信號 |
| 高影響力+有 Ticker | 7 (41.2%) | **近六成高影響力信號無法執行** |
| 無 score 信號 | 23 (22.5%) | LLM 回傳格式不一致 |

相對地，ETL Pipeline 已收錄的結構化數據資產：

| 指標 | 數值 |
|------|------|
| 交易總筆數 | 404 筆 |
| 有 Ticker 交易 | 353 (87.4%) |
| 不同 Ticker | 262 個 |
| 不同議員 | 17 人 |
| House 交易 | 347 筆 |
| Senate 交易 | 57 筆 |

### 1.2 問題根因分析

**AI Discovery 與 ETL Pipeline 之間存在數據斷層。** 具體原因如下：

1. **Google Search 依賴性**：`discovery_engine_v4.py` 的 CONGRESS prompt 透過 Gemini 的 `google_search` tool 即時搜尋網路，取得的資訊品質不穩定。搜尋結果可能不含 ticker，或 LLM 未能從新聞中提取 ticker。

2. **ETL 橋接已啟動但覆蓋率不足**：`_get_local_trades()` 方法已實作（line 114-156），但僅在 `congress_trades` 中找到 2 位議員的交易記錄與 `ai_intelligence_signals` 的 `source_name` 匹配（Nancy Pelosi、Richard Blumenthal）。原因是 ETL 收錄了 17 位議員，而 AI Discovery 涵蓋 25 位來源，兩者的姓名匹配率低。

3. **信號存儲無 Ticker 時的寬鬆策略**：`_save_signal()` 在第 266 行允許 `score > 5` 且無 ticker 的信號入庫，導致大量無法直接交易的信號累積。

4. **LLM 輸出格式不一致**：23 個信號連 `impact_score` 都是 NULL，表示 JSON 解析或欄位映射存在漏洞。

### 1.3 量化影響

若以每日交易為目標，信號池中實際可用的信號為 37 個（含 ticker），其中 score >= 7 的約 15 個。以 30 位追蹤議員、每人每月 1-2 次掃描計算，**每月可操作信號不到 20 個，遠低於可交易覆蓋的需求**。

---

## 二、文獻調查

### 2.1 學術研究：國會議員交易 Alpha

#### Ziobrowski 系列研究（開創性研究）

| 研究 | 年份 | 發現 |
|------|------|------|
| Ziobrowski et al. — Senate | 2004 | 參議員投資組合每年超額報酬約 **12%**，遠超市場（1993-1998 數據） |
| Ziobrowski et al. — House | 2011 | 眾議員投資組合每年超額報酬約 **6%**（1985-2001，16,000+ 筆交易） |

這些研究確立了「國會議員利用資訊優勢交易」的學術基礎，但數據年代久遠（pre-STOCK Act）。

#### STOCK Act 後的研究

| 研究 | 年份 | 發現 |
|------|------|------|
| Huang & Xuan — STOCK Act 影響 | 2022 | STOCK Act 前 Carhart alpha **9.5%/年**（統計顯著）；Act 後降至 **0.9%/年**（不顯著） |
| Choi et al. — ScienceDirect | 2022 | 六個月期限內，眾議員買入組合平均跑輸市場 26 bps，賣出組合跑輸 11 bps；**與隨機選股無統計差異** |
| NBER Working Paper #26975 | 2020 | 參議員選股能力與普通散戶無異（"Feckless as the Rest of Us"） |

**關鍵結論**：學術研究對 STOCK Act 後是否仍存在 alpha 有分歧。早期研究（2004-2011）顯示顯著 alpha，但近期研究多認為 alpha 已顯著減少或消失。

#### 但值得注意的反面證據

- **Unusual Whales 2025 報告**：140 位國會議員在 2025 年進行 14,451 筆交易，總額 $7.2 億。32.2% 的議員跑贏大盤，雖然整體多數未能超越市場，但頂尖交易者仍展現出超額報酬。
- **NANC ETF**（追蹤民主黨議員）2023-2025 年化報酬 **27%**，跑贏 S&P 500 約 12 個百分點；**KRUZ ETF**（追蹤共和黨議員）年化 13%，跑輸大盤。
- **ScienceDirect 2025 研究**（NANC vs KRUZ）：確認黨派差異存在，但風險調整後（Sharpe ratio）兩者均未顯著超越市場。
- **CEPR 2024 分析**：政治權力（如委員會主席）與交易獲利存在正相關，暗示部分議員仍可能利用資訊優勢。

**本專案的啟示**：alpha 可能仍存在於特定條件下（高影響力議員、大額交易、與立法行動相關的交易），但不是所有議員交易都有 alpha。因此，**信號品質比信號數量更重要**。

### 2.2 信號品質框架

#### 量化交易信號品質指標

根據 Macrosynergy Research 及 ExtractAlpha 的方法論：

| 指標 | 定義 | 適用場景 |
|------|------|----------|
| **Information Coefficient (IC)** | 信號預測值與實際報酬的 rank correlation | 評估信號預測能力 |
| **Precision** | 預測正報酬中實際為正的比例 | 避免假信號（false positive） |
| **Recall / Sensitivity** | 實際正報酬中被成功預測的比例 | 避免遺漏好機會 |
| **AUC-PR** | Precision-Recall 曲線下面積 | 綜合評估 |
| **Alpha Decay** | 信號效力隨時間衰減的速率 | 決定執行時機 |
| **Hit Rate** | 信號指引的交易中獲利交易的比例 | 最直觀的表現指標 |
| **Profit Factor** | 總獲利 / 總虧損 | 風險回報比 |

#### 本專案適用的品質維度

1. **Actionability（可操作性）**：是否有明確 ticker + 方向（Buy/Sell）
2. **Timeliness（時效性）**：從交易日到信號產生的延遲天數
3. **Conviction（確信度）**：交易金額、是否為議員本人操作、歷史表現
4. **Information Edge（資訊優勢）**：議員是否具備相關委員會席位或立法影響力
5. **Market Impact（市場影響）**：交易的資產流動性、市值、是否已被市場定價

### 2.3 競品分析

| 平台 | 定位 | 數據範圍 | 定價 | 主要功能 | 我們的差異化 |
|------|------|----------|------|----------|-------------|
| **Unusual Whales** | 全方位交易數據平台 | 國會+Options Flow | $45-100/月 | 議員投資組合追蹤、回測、ETF (NANC/KRUZ)、Prediction Markets | 他們提供原始數據+簡單分析；我們提供 **AI 驅動的信號** |
| **Capitol Trades** | 免費國會交易追蹤 | 國會交易 | 免費 | 即時交易列表、議員搜尋、視覺化 | 他們是資料展示；我們提供 **可操作信號** |
| **Quiver Quantitative** | 進階量化分析 | 國會+機構+社群 | 免費+Pro | QuantConnect 整合、歷史回測、政策影響分析 | 他們偏分析工具；我們做 **端到端的信號生成** |
| **2iQ Research** | 機構級政治交易數據 | SEC + 國會 | 企業定價 | Form 4、STOCK Act 合規分析 | 他們服務機構；我們面向 **獨立交易者** |

**競品共同弱點**：所有競品都是「數據展示」或「工具平台」，沒有一個提供 AI 驅動的交易信號生成。這是我們的核心差異化。

**但競品的數據品質標準值得借鏡**：Unusual Whales 的議員投資組合追蹤功能確保每筆交易都有 ticker；Quiver Quantitative 的 QuantConnect 整合要求標準化的 ticker + 日期格式。我們的 36.3% ticker 覆蓋率在行業中不合格。

---

## 三、解決方案設計

### 3.1 ETL → Discovery 的 Ticker 橋接方案

#### 方案 A：ETL-First Signal Enrichment（推薦）

**核心思路**：先查詢 `congress_trades` 取得結構化交易記錄，再用 AI 分析其投資意涵，而非讓 AI 透過 Google Search 自行搜尋。

```
目前流程：
  CONGRESS target → Google Search → LLM → JSON (常缺 ticker)

改進流程：
  CONGRESS target → 查詢 congress_trades → 組合 prompt context
                  → Google Search (補充新聞/政策) → LLM → JSON (ticker 已知)
```

**實施細節**：

1. **強化 `_get_local_trades()` 名稱匹配**：
   - 目前使用 `LIKE %name%` 模糊匹配，覆蓋率僅 2/25
   - 改用 normalized name mapping（如 `targets.py` 中的 30 位議員對應 ETL 中的 politician_name）
   - 建立姓名別名表（如 "Debbie Wasserman Schultz" vs "Wasserman Schultz, Debbie"）

2. **重構 CONGRESS prompt 為 Two-Phase 策略**：
   - **Phase 1（ETL-based）**：若 `congress_trades` 有該議員記錄，直接以交易記錄為主體生成信號，prompt 中提供完整的 ticker/date/amount 資訊，LLM 僅負責分析意涵和評分
   - **Phase 2（Search-based）**：在 Phase 1 基礎上，透過 Google Search 補充最新新聞/政策，增強分析深度

3. **Ticker 強制要求**：
   - 修改 `_save_signal()` 邏輯：若 `source_type == "CONGRESS"` 且 ticker 為空，降級為 `low_actionability` 標記而非直接入庫
   - 增加 `actionability_score` 欄位（0-100）

#### 方案 B：Reverse Enrichment（補充方案）

對已存在但缺 ticker 的 65 個信號，批量用 `source_name` 反查 `congress_trades`，嘗試回補 ticker：

```sql
-- 範例查詢
UPDATE ai_intelligence_signals s
SET ticker = (
  SELECT t.ticker FROM congress_trades t
  WHERE t.politician_name LIKE '%' || s.source_name || '%'
    AND t.ticker IS NOT NULL
  ORDER BY t.transaction_date DESC LIMIT 1
)
WHERE s.ticker IS NULL OR s.ticker = '';
```

此方案可立即提升現有信號的可操作率，但需人工驗證匹配品質。

### 3.2 Alpha 回測方法論

#### 回測設計

| 參數 | 設定 | 理由 |
|------|------|------|
| **方法** | Event Study（事件研究法） | 學術標準，可與 Ziobrowski 系列直接比較 |
| **事件日** | Filing Date（申報日） | 實際可用日；交易日不一定即時公開 |
| **事件窗口** | [0, +5], [0, +20], [0, +60] 交易日 | 短中長期 alpha 衰減分析 |
| **估計窗口** | [-250, -20] 交易日 | 標準 Market Model 參數估計期 |
| **異常報酬** | AR = R_actual - (alpha + beta * R_market) | Market Model |
| **累積異常報酬** | CAR = sum(AR over event window) | 累積效果 |
| **Benchmark** | SPY (S&P 500 ETF) | 最廣泛使用的大盤基準 |
| **統計檢定** | Patell t-test + BMP test | 標準事件研究檢定 |

#### 回測分層

為了測試「alpha 是否集中在特定條件」，設計以下分層：

1. **按議員 Tier 分層**：Tier 1 vs Tier 2 vs Tier 3
2. **按交易金額分層**：>$50K vs <$50K
3. **按交易類型分層**：Buy vs Sale
4. **按議員委員會分層**：有相關委員會席位 vs 無
5. **按 ETL confidence 分層**：>0.9 vs 0.7-0.9
6. **按時效性分層**：Filing lag < 15 天 vs > 15 天

#### 數據來源

- **ETL 數據**：`congress_trades` 404 筆（2025-2026），用於近期驗證
- **歷史數據**：`CongressAlphaTool` 的 GitHub CSV（House + Senate 歷史），用於大樣本回測
- **股價數據**：透過 `yfinance` API 取得事件窗口期間的調整收盤價
- **最低樣本量**：每個分層至少 30 筆交易，以確保統計有效性

### 3.3 信號品質評分框架

#### 五維度評分模型

```
Signal Quality Score (SQS) = w1*A + w2*T + w3*C + w4*I + w5*M

其中：
A = Actionability Score (0-100)    權重 w1 = 0.30
T = Timeliness Score (0-100)       權重 w2 = 0.20
C = Conviction Score (0-100)       權重 w3 = 0.25
I = Information Edge Score (0-100) 權重 w4 = 0.15
M = Market Impact Score (0-100)    權重 w5 = 0.10
```

#### 各維度計算方式

**A - Actionability（可操作性）30%**

| 條件 | 分數 |
|------|------|
| 有明確 Ticker + Buy/Sale 方向 | 100 |
| 有 Ticker 但方向模糊 | 70 |
| 有 Sector 但無 Ticker | 30 |
| 僅有文字描述 | 0 |

**T - Timeliness（時效性）20%**

| 條件 | 分數 |
|------|------|
| Filing lag <= 7 天 | 100 |
| Filing lag 8-15 天 | 75 |
| Filing lag 16-30 天 | 50 |
| Filing lag 31-45 天 | 25 |
| Filing lag > 45 天 | 0 |

**C - Conviction（確信度）25%**

| 條件 | 分數增量 |
|------|---------|
| 金額 > $250K | +40 |
| 金額 $50K-$250K | +25 |
| 金額 $15K-$50K | +15 |
| 金額 < $15K | +5 |
| Owner = Self | +20 |
| Owner = Joint/Spouse | +10 |
| Owner = Child/Other | +5 |
| 多筆同方向交易 (集中買入/賣出) | +20 |
| ETL extraction_confidence >= 0.9 | +20 |

**I - Information Edge（資訊優勢）15%**

| 條件 | 分數 |
|------|------|
| 議員為相關委員會主席/ranking member | 100 |
| 議員為相關委員會成員 | 70 |
| 議員有相關產業背景 | 50 |
| 無明顯資訊優勢 | 20 |

**M - Market Impact（市場影響潛力）10%**

| 條件 | 分數 |
|------|------|
| 小型股 (市值 < $2B) + 大額交易 | 100 |
| 中型股 ($2B-$10B) | 70 |
| 大型股 ($10B-$200B) | 40 |
| 超大型股 (> $200B) | 20 |

#### 品質等級分類

| 等級 | SQS 範圍 | 行動 |
|------|---------|------|
| **Platinum** | 80-100 | 自動產生交易信號，MOO 執行 |
| **Gold** | 60-79 | 產生交易信號，MOC 執行 |
| **Silver** | 40-59 | 列入觀察清單，不自動執行 |
| **Bronze** | 20-39 | 僅記錄，人工審閱 |
| **Discard** | 0-19 | 淘汰，不入庫 |

#### 淘汰規則

以下信號直接歸類為 Discard：
- 無 Ticker 且無具體 Sector（Actionability = 0）
- Filing lag > 45 天且金額 < $15K
- ETL extraction_confidence < 0.5
- impact_score 為 NULL（LLM 解析失敗）

---

## 四、行動計畫

### Phase 1：資料橋接與信號品質框架（第 1-2 週）

| 步驟 | 工作內容 | 交付物 | 負責 |
|------|---------|--------|------|
| 1.1 | 建立議員姓名 normalization mapping（targets.py ↔ congress_trades） | `src/name_mapping.py` | Engineering |
| 1.2 | 強化 `_get_local_trades()` 匹配邏輯 | 更新 `discovery_engine_v4.py` | Engineering |
| 1.3 | 重構 CONGRESS prompt 為 Two-Phase 策略 | 更新 `discovery_engine_v4.py` | Engineering |
| 1.4 | 實作 Signal Quality Score 計算模組 | `src/signal_scorer.py` | Engineering |
| 1.5 | 新增 `actionability_score` 欄位至 `ai_intelligence_signals` 表 | DB migration | Engineering |
| 1.6 | 批量回補現有 65 個無 ticker 信號（方案 B） | SQL script + 驗證報告 | Data |

**Phase 1 目標**：信號可操作率（有 ticker）從 36% 提升至 **80%+**

### Phase 2：Alpha 回測驗證（第 3-4 週）

| 步驟 | 工作內容 | 交付物 | 負責 |
|------|---------|--------|------|
| 2.1 | 取得歷史股價數據（yfinance，覆蓋 congress_trades 中的 262 個 ticker） | `data/price_cache/` | Data |
| 2.2 | 實作 Event Study 回測框架 | `src/alpha_backtest.py` | Research |
| 2.3 | 執行分層回測（Tier/金額/類型/委員會/時效性） | 回測報告 | Research |
| 2.4 | 以歷史 GitHub CSV 數據擴大回測樣本 | 擴展回測報告 | Research |
| 2.5 | 統計顯著性檢定與結論 | 研究報告 `RB-002_Alpha-Backtest-Results.md` | Research |

**Phase 2 目標**：確認或否定以下假設——
- H1: Tier 1 議員交易存在統計顯著的正 alpha
- H2: 大額交易 (>$50K) 的 alpha 顯著高於小額
- H3: Filing lag < 15 天的交易 alpha 顯著高於晚申報的交易

### Phase 3：系統整合與上線（第 5-6 週）

| 步驟 | 工作內容 | 交付物 | 負責 |
|------|---------|--------|------|
| 3.1 | 根據回測結果調整 SQS 權重 | 更新 `signal_scorer.py` | Research |
| 3.2 | 整合 SQS 至 `run_congress_discovery.py` 輸出 | 系統更新 | Engineering |
| 3.3 | Dashboard 顯示信號品質等級 | 報告模板更新 | Engineering |
| 3.4 | 建立信號品質監控指標 | 監控腳本 | Engineering |
| 3.5 | End-to-end 測試（ETL → Discovery → SQS → 報告） | 測試報告 | QA |

**Phase 3 目標**：完整的信號品質管線上線，每日產出 Platinum/Gold 等級信號

---

## 五、風險與假設

### 已知風險

| 風險 | 嚴重度 | 緩解措施 |
|------|--------|---------|
| **Alpha 不存在**：回測可能證明 STOCK Act 後議員交易無顯著 alpha | 高 | 即使整體無 alpha，仍可聚焦特定條件（高金額+委員會主席）；退而求其次可做「議員情緒指標」 |
| **Filing lag 過長**：交易日到申報日的平均延遲 20-30 天，alpha 可能已衰減 | 高 | 分析 alpha 半衰期；若 alpha 在 filing date 後仍存在，則策略可行 |
| **樣本量不足**：ETL 僅 404 筆，部分分層可能不到 30 筆 | 中 | 用 GitHub CSV 歷史數據擴充；對低樣本量分層使用 bootstrap 方法 |
| **LLM 成本增加**：Two-Phase prompt 策略增加 API 調用量 | 低 | Phase 1 為 ETL 查詢（零成本），僅 Phase 2 調用 Gemini API |
| **姓名匹配錯誤**：fuzzy matching 可能產生 false positive | 中 | 建立確定性映射表（非模糊匹配），人工驗證 30 位議員的映射 |

### 未驗證假設

1. **假設 A**：議員的委員會席位與其交易的 alpha 之間存在正相關——需回測驗證
2. **假設 B**：大額交易（>$50K）的 alpha 高於小額交易——直覺合理但需數據支持
3. **假設 C**：Filing lag 較短的交易仍保有可交易的 alpha——這是整個策略的前提假設
4. **假設 D**：ETL 數據的 ticker 準確率足以支撐回測——需驗證 ETL extraction_confidence 與實際 ticker 正確率的相關性
5. **假設 E**：以 SPY 為 benchmark 是合適的——部分議員交易集中在小型股或特定 sector，可能需要 sector-specific benchmark

---

## 六、建議下一步

### 立即行動（本週內）

1. **批量回補 ticker（方案 B）**：用 SQL 腳本對現有 65 個無 ticker 信號進行 reverse enrichment，預估可回補 10-15 個信號，將可操作率從 36% 提升至約 50%。

2. **建立姓名映射表**：手動建立 `targets.py` 30 位議員與 `congress_trades` 中 `politician_name` 的精確映射。這是後續所有橋接工作的基礎。

3. **啟動 Phase 2.1**：開始用 yfinance 下載 262 個 ticker 的歷史股價，這是回測的前置作業。

### 待 CEO 核准的決策

1. 是否核准 Phase 1 的 prompt 重構？這會改變 Discovery Engine 的核心行為。
2. 是否核准 Phase 2 的回測工作？預計需要 2 週全職研究時間。
3. 若回測結果顯示 alpha 不顯著，是否接受將產品定位從「alpha 信號」轉向「議員交易情報監控」？

---

## 參考文獻

1. Ziobrowski, A. J., Cheng, P., Boyd, J. W., & Ziobrowski, B. J. (2004). "Abnormal Returns from the Common Stock Investments of the U.S. Senate." *Journal of Financial and Quantitative Analysis*, 39(4), 661-676.
2. Ziobrowski, A. J., Boyd, J. W., Cheng, P., & Ziobrowski, B. J. (2011). "Abnormal Returns From the Common Stock Investments of Members of the U.S. House of Representatives." *Business and Politics*, 13(1).
3. Huang, S. & Xuan, Y. (2022). "Trading Political Favors: Evidence from the Impact of the STOCK Act." George Washington University Working Paper.
4. Choi, J. et al. (2022). "Do senators and house members beat the stock market? Evidence from the STOCK Act." *Journal of Public Economics*, 206.
5. Eggers, A. C. & Hainmueller, J. (2020). "Senators As Feckless As the Rest of Us at Stock Picking." NBER Working Paper #26975.
6. Unusual Whales (2025). "Congress Trading Report 2025."
7. Macrosynergy (2024). "How to measure the quality of a trading signal."
8. NANC/KRUZ ETF Performance — Morningstar, etf.com, ScienceDirect (2025).
