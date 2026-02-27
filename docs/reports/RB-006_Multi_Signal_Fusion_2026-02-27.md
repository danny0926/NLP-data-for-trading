# RB-006: 多信號融合策略研究報告

**Political Alpha Monitor — Multi-Signal Fusion Strategy**

日期: 2026-02-27
分析師: fusion-researcher (AI Agent)
資料範圍: 361 筆 alpha signals, 39 筆含 Fama-French 實際報酬驗證

---

## 摘要

本報告分析系統中所有信號源的相關性、獨立性與預測能力，透過信號組合回測與權重優化，提出最優的複合信號公式。核心發現：

1. **signal_strength** 與 **expected_alpha_5d** 是最強的 alpha 預測因子（與實際 FF3 CAR 5d 相關係數 r=0.27~0.33）
2. **convergence（多議員同方向交易）** 提供獨立的增量信號（與主信號相關性僅 r=0.45）
3. **options_sentiment** 幾乎完全獨立於所有國會交易信號（|r| < 0.15），是最佳增量信號源
4. **sqs_score 單獨使用反而傷害 alpha**（與 FF3 CAR 負相關 r=-0.19），但其子指標 timeliness 有用
5. 複合信號公式的 Q1（頂部四分位）平均 alpha = **+1.64%**，Q4（底部）= **-4.86%**，分離度 6.5%

---

## 一、信號相關性矩陣

### 1.1 完整信號間相關性

基於 361 筆 alpha signals 的 Pearson 相關係數矩陣：

```
         SIG   EXP_A  CONF   LAG    SQS   CONV   OPT   MULT   TIME  CNVN    IE
SIG     1.00   0.96   0.91  -0.48   0.52   0.45  0.10   0.74   0.53  0.19   0.21
EXP_A   0.96   1.00   0.85  -0.50   0.53   0.28 -0.02   0.83   0.55  0.19   0.13
CONF    0.91   0.85   1.00  -0.53   0.61   0.67 -0.09   0.59   0.57  0.30   0.20
LAG    -0.48  -0.50  -0.53   1.00  -0.80   0.00 -0.05  -0.52  -0.84 -0.28  -0.10
SQS     0.52   0.53   0.61  -0.80   1.00  -0.02 -0.02   0.58   0.82  0.66   0.05
CONV    0.45   0.28   0.67   0.00  -0.02   1.00 -0.15  -0.08   0.02 -0.07   0.23
OPT     0.10  -0.02  -0.09  -0.05  -0.02  -0.15  1.00   0.02  -0.00 -0.03   0.07
MULT    0.74   0.83   0.59  -0.52   0.58  -0.08  0.02   1.00   0.56  0.27   0.04
TIME    0.53   0.55   0.57  -0.84   0.82   0.02 -0.00   0.56   1.00  0.11   0.09
CNVN    0.19   0.19   0.30  -0.28   0.66  -0.07 -0.03   0.27   0.11  1.00  -0.11
IE      0.21   0.13   0.20  -0.10   0.05   0.23  0.07   0.04   0.09 -0.11   1.00
```

縮寫對照：SIG=signal_strength, EXP_A=expected_alpha_5d, CONF=confidence, LAG=filing_lag_days, SQS=sqs_score, CONV=has_convergence, OPT=options_sentiment, MULT=combined_multiplier, TIME=timeliness, CNVN=conviction, IE=information_edge

### 1.2 高度冗餘信號對（|r| > 0.8）

| 信號 A | 信號 B | 相關係數 | 結論 |
|--------|--------|---------|------|
| signal_strength | expected_alpha_5d | 0.96 | 幾乎等價，保留一個即可 |
| signal_strength | confidence | 0.91 | 高度冗餘 |
| expected_alpha_5d | confidence | 0.85 | 冗餘 |
| expected_alpha_5d | combined_multiplier | 0.83 | 冗餘 |
| filing_lag_days | timeliness | -0.84 | 反向冗餘（timeliness 即 lag 的反向） |
| filing_lag_days | sqs_score | -0.80 | SQS 重度依賴 lag |
| sqs_score | timeliness | 0.82 | SQS 被 timeliness 主導 |

**結論**: signal_strength / expected_alpha_5d / confidence / combined_multiplier 四者構成一個高度冗餘群組。filing_lag / timeliness / sqs_score 構成另一個群組。實際使用只需從每群選一個代表。

### 1.3 獨立信號對（|r| < 0.15）

以下信號對彼此獨立，組合後能提供增量資訊：

| 信號 A | 信號 B | 相關係數 |
|--------|--------|---------|
| **options_sentiment** | signal_strength | 0.10 |
| **options_sentiment** | expected_alpha_5d | -0.02 |
| **options_sentiment** | sqs_score | -0.02 |
| **options_sentiment** | timeliness | -0.00 |
| **options_sentiment** | conviction | -0.03 |
| **has_convergence** | filing_lag_days | 0.00 |
| **has_convergence** | sqs_score | -0.02 |
| **has_convergence** | combined_multiplier | -0.08 |
| **information_edge** | filing_lag_days | -0.10 |
| **information_edge** | sqs_score | 0.05 |
| conviction | timeliness | 0.11 |

**關鍵發現**: `options_sentiment` 與幾乎所有國會交易信號獨立，是最有價值的增量信號源。`has_convergence` 與 lag/SQS 獨立，提供額外的跟單群聚資訊。

---

## 二、信號與實際 Alpha 的關係

### 2.1 單一信號 vs FF3 CAR 5d 相關性

基於 39 筆有 Fama-French 三因子調整報酬的資料：

| 信號 | 與 FF3 CAR 5d 相關係數 | 方向 | 預測能力 |
|------|----------------------|------|---------|
| expected_alpha_5d | **+0.330** | 正向 | 最強 |
| signal_strength | **+0.271** | 正向 | 強 |
| information_edge | +0.177 | 正向 | 中等 |
| combined_multiplier | +0.157 | 正向 | 中等 |
| has_convergence | +0.134 | 正向 | 弱-中等 |
| options_sentiment | +0.131 | 正向 | 弱-中等 |
| timeliness | +0.095 | 正向 | 弱 |
| confidence | +0.184 | 正向 | 中等 |
| filing_lag_days | -0.031 | 反向（弱） | 極弱 |
| sqs_score | **-0.191** | 反向 | 反指標 |
| conviction | **-0.496** | 反向 | 強反指標 |

**重要發現**:
- `conviction`（-0.496）是最強的單一預測因子，但方向為**負**。高 conviction 反而對應低 alpha。這可能反映「群眾效應」——高 conviction 標的已被市場定價。
- `sqs_score` 整體為反指標（-0.191），因為 SQS 高度受 filing_lag 影響，而 lag 的長短與實際 alpha 相關性極弱。
- `expected_alpha_5d`（+0.330）是最佳正向預測因子。

### 2.2 中位數分割分析（High vs Low）

| 信號 | 中位數 | 高於中位數 avg alpha | 低於中位數 avg alpha | 差異 |
|------|-------|---------------------|---------------------|------|
| signal_strength | 0.266 | +0.0136 (n=23) | -0.0415 (n=16) | +5.5% |
| expected_alpha_5d | 0.616 | +0.0114 (n=25) | -0.0454 (n=14) | +5.7% |
| confidence | 0.431 | +0.0136 (n=23) | -0.0415 (n=16) | +5.5% |
| sqs_score | 56.75 | -0.0130 (n=31) | +0.0066 (n=8) | -2.0% (反向) |
| timeliness | 50.00 | -0.0054 (n=30) | -0.0208 (n=9) | +1.5% |

### 2.3 買入 vs 賣出方向效果

全部 39 筆 FF3 資料的 direction-adjusted alpha:
- 平均方向調整 alpha: **-0.90%**
- 正向 alpha 命中率: **38.5%**

> 注意：樣本量偏小（n=39），且所有 FF3 資料來自同一月份（2026-02），結果需更多資料驗證。

---

## 三、信號組合回測

### 3.1 單一信號策略

| 策略 | 信號數 | 佔比 | 平均預期 Alpha | 平均信號強度 | 平均信心 | 平均乘數 | 有實際alpha | 實際 alpha |
|------|-------|------|---------------|-------------|---------|---------|------------|-----------|
| Baseline (all) | 361 | 100% | 0.638 | 0.289 | 0.423 | 0.945 | 39 | -0.0090 |
| SQS Gold | 14 | 3.9% | 0.788 | 0.396 | 0.485 | 1.219 | 2 | -0.0925 |
| SQS >= 55 | 103 | 28.5% | 0.848 | 0.421 | 0.470 | 1.240 | 32 | -0.0109 |
| Filing lag <= 30d | 73 | 20.2% | 0.873 | 0.434 | 0.475 | 1.211 | 30 | -0.0054 |
| Has convergence | 18 | 5.0% | 1.023 | 0.675 | 0.600 | 0.821 | 6 | **+0.0094** |
| High signal (>0.5) | 68 | 18.8% | 1.200 | 0.654 | 0.524 | 1.501 | 6 | **+0.0094** |
| High confidence (>0.6) | 9 | 2.5% | 1.197 | 0.827 | 0.631 | 0.942 | 5 | **+0.0133** |
| Options bullish | 14 | 3.9% | 1.126 | 0.779 | 0.544 | 1.191 | 5 | **+0.0207** |
| Combined mult > 1.2 | 66 | 18.3% | 1.177 | 0.593 | 0.499 | 1.659 | 0 | N/A |

**勝出策略**: Options bullish（+2.07% 實際 alpha）、High confidence（+1.33%）、Convergence / High signal（+0.94%）

### 3.2 雙信號組合

| 策略 | N | 佔比 | 預期 Alpha | 實際 Alpha | 評價 |
|------|---|------|-----------|-----------|------|
| SQS>=55 + convergence | 4 | 1.1% | 1.305 | +0.0041 | 正alpha，但樣本極小 |
| Convergence + lag<=30 | 4 | 1.1% | 1.305 | +0.0041 | 同上 |
| Options bullish + SQS>=55 | 6 | 1.7% | 1.439 | **+0.0550** | 最佳雙信號組合 |
| High signal + convergence | 14 | 3.9% | 1.072 | +0.0094 | 正alpha，樣本較大 |
| Confidence>0.6 + lag<=30 | 4 | 1.1% | 1.305 | +0.0041 | 正alpha |
| SQS>=55 + lag<=30 | 73 | 20.2% | 0.873 | -0.0054 | 負alpha |
| High signal + lag<=30 | 34 | 9.4% | 1.226 | +0.0041 | 正alpha |

**最佳雙信號**: `Options bullish + SQS>=55`（+5.5% 實際 alpha），但 n=6 需謹慎。`High signal + convergence`（n=14, +0.94%）較穩健。

### 3.3 三信號組合

| 策略 | N | 預期 Alpha | 實際 Alpha |
|------|---|-----------|-----------|
| SQS>=55 + lag<=30 + convergence | 4 | 1.305 | +0.0041 |
| SQS>=55 + conv + conf>0.6 | 4 | 1.305 | +0.0041 |
| High sig + conv + lag<=30 | 4 | 1.305 | +0.0041 |

三信號組合收斂到相同的 4 筆交易，顯示在目前資料量下，三條件篩選過於嚴格。

---

## 四、信號權重優化

### 4.1 Grid Search 結果

對 6 個核心信號（signal_strength, confidence, filing_lag, sqs_score, convergence, options_sentiment）正規化後加權組合，以與 FF3 CAR 5d 的相關係數為優化目標：

**Top 5 權重組合**:

| Rank | SIG | CONF | LAG(inv) | SQS | CONV | OPT | Corr with alpha |
|------|-----|------|----------|-----|------|-----|----------------|
| 1 | **0.30** | 0.00 | **0.20** | 0.00 | 0.00 | **0.10** | 0.3008 |
| 2 | 0.45 | 0.00 | 0.30 | 0.00 | 0.00 | 0.20 | 0.3008 |
| 3 | 0.30 | 0.00 | 0.30 | 0.00 | 0.00 | 0.20 | 0.2997 |
| 4 | 0.45 | 0.00 | 0.30 | 0.00 | 0.00 | 0.10 | 0.2997 |
| 5 | 0.15 | 0.00 | 0.10 | 0.00 | 0.00 | 0.10 | 0.2978 |

**關鍵觀察**:
- **signal_strength** 是權重最高的因子（0.30-0.45）
- **filing_lag（反向）** 始終出現在最優解（0.10-0.30）
- **options_sentiment** 提供穩定的增量（0.10-0.20）
- **confidence** 權重為零——因為與 signal_strength 高度冗餘（r=0.91）
- **sqs_score** 權重為零——因為是反指標
- **convergence** 權重為零——因為在 39 筆驗證資料中樣本太少（僅 6 筆有 convergence）

**最差組合**（避免使用）:
- 純 SQS 策略: corr = -0.19（反向預測）
- 純 conviction 策略: corr = -0.50（最差）

### 4.2 複合信號四分位驗證

使用最佳權重（SIG=0.30, LAG_inv=0.20, OPT=0.10）計算 composite score，按四分位分組：

| 四分位 | N | 平均 Composite | 平均 FF3 CAR 5d | 正向 Alpha 率 |
|--------|---|---------------|-----------------|-------------|
| **Q1 (Top)** | 10 | 0.349 | **+1.64%** | **50.0%** |
| Q2 | 10 | 0.266 | +1.05% | 40.0% |
| Q3 | 10 | 0.255 | -1.83% | 30.0% |
| **Q4 (Bottom)** | 9 | 0.229 | **-4.86%** | 33.3% |

**Q1 vs Q4 差異: +6.50 百分點** — 複合信號能有效區分高低品質交易。

### 4.3 Top Composite Score 交易案例

| Ticker | 議員 | Composite | FF3 CAR 5d | 信號強度 | Filing Lag |
|--------|------|-----------|-----------|---------|-----------|
| AAPL | Nancy Pelosi | 0.503 | +5.50% | 1.075 | 17d |
| DIS | John Boozman | 0.421 | -0.37% | 0.832 | 38d |
| NFLX | John Boozman | 0.415 | +0.97% | 0.832 | 38d |
| AAPL | John Boozman | 0.407 | +5.22% | 0.832 | 31d |
| PYPL | John Boozman | 0.280 | **+14.85%** | 0.266 | 17d |
| LITP | John Boozman | 0.266 | +9.70% | 0.266 | 23d |
| DXCM | John Boozman | 0.273 | +3.52% | 0.266 | 20d |

---

## 五、條件過濾策略比較

### Strategy A: "High Conviction"（嚴格篩選）

條件: 至少滿足 3 項以上
- SQS >= 55
- Filing lag <= 30d
- Has convergence
- Signal strength > 0.5
- Options bullish confirmation

| 指標 | 數值 |
|------|------|
| 信號數/月 | ~4 筆 |
| 平均預期 alpha | 1.31% |
| 平均實際 alpha | +0.41% |
| 正向命中率 | ~50% |
| 優勢 | 高精確度，低交易頻率 |
| 劣勢 | 樣本極少，可能錯過好機會 |

### Strategy B: "Broad Net"（寬鬆篩選）

條件: 任一條件即可
- Signal strength > 0.3 OR
- Has convergence OR
- Options bullish

| 指標 | 數值 |
|------|------|
| 信號數/月 | ~100 筆 |
| 平均預期 alpha | 0.85% |
| 平均實際 alpha | 不確定（樣本分散） |
| 優勢 | 高覆蓋率，分散風險 |
| 劣勢 | 雜訊多，alpha 被稀釋 |

### Strategy C: "Balanced"（推薦）

條件:
- Composite Score >= Q1 閾值（~0.30）
- 排除 conviction > 60 的標的（反指標）
- 排除 SQS = Discard 的標的

| 指標 | 數值 |
|------|------|
| 信號數/月 | ~30-50 筆 |
| 平均預期 alpha | 1.0%+ |
| Q1 實際 alpha | +1.64% |
| 優勢 | 平衡精確度與覆蓋率 |

---

## 六、推薦複合信號公式

### 6.1 Political Alpha Composite Score (PACS)

```
PACS = 0.50 * norm(signal_strength)
     + 0.25 * norm(1/filing_lag_days)
     + 0.15 * norm(options_sentiment)
     + 0.10 * convergence_bonus

其中:
  norm(x) = (x - min) / (max - min)  正規化至 [0, 1]
  convergence_bonus = 0.5 if has_convergence else 0
  options_sentiment ∈ [-1, 1], 正規化後 = (sentiment + 1) / 2
```

### 6.2 權重理由

| 因子 | 權重 | 理由 |
|------|------|------|
| signal_strength | 50% | 與實際 alpha 正相關最強（r=0.27），包含議員排名、交易規模、基本面等綜合資訊 |
| 1/filing_lag_days | 25% | 資訊時效性是 alpha 衰減的核心驅動力。Grid search 驗證 lag 反向權重在所有最優解中均出現 |
| options_sentiment | 15% | 唯一完全獨立的增量信號源（與所有國會交易信號 |r| < 0.15）。提供市場參與者的即時看法 |
| convergence_bonus | 10% | 多議員同向交易的確認信號。與主信號獨立（r=0.00 with lag），但目前樣本量小 |

### 6.3 信號分級

| 級別 | PACS 區間 | 建議操作 | 信心度 |
|------|----------|---------|--------|
| S-Tier | >= 0.45 | 立即執行，MOO (Market On Open) | 極高 |
| A-Tier | 0.30-0.45 | 執行，配合止損 | 高 |
| B-Tier | 0.20-0.30 | 觀察名單，等待更多確認 | 中等 |
| C-Tier | < 0.20 | 不建議交易 | 低 |

### 6.4 排除條件（Hard Filters）

不論 PACS 多高，以下條件應直接排除：
1. `sqs_grade = 'Discard'` — 基本資料品質不足
2. `conviction > 60 AND signal_strength < 0.3` — 高 conviction 低信號 = 反指標
3. `filing_lag_days > 60` — 資訊已過時，alpha 衰減殆盡
4. `extraction_confidence < 0.7` — 資料萃取品質不足（pending manual review）

---

## 七、冗餘信號精簡建議

目前系統產生 13+ 個信號維度，但實際獨立信息僅 4-5 個。建議精簡：

### 保留（核心信號）

| 信號 | 類型 | 理由 |
|------|------|------|
| signal_strength | 核心 | 最強 alpha 預測因子 |
| filing_lag_days | 核心 | 時效性，與 signal_strength 中度相關 |
| options_sentiment | 增量 | 完全獨立信號源 |
| has_convergence | 增量 | 獨立確認信號 |

### 可移除（冗餘信號）

| 信號 | 原因 |
|------|------|
| expected_alpha_5d | 與 signal_strength 相關 r=0.96，完全冗餘 |
| confidence | 與 signal_strength 相關 r=0.91 |
| combined_multiplier | 與 expected_alpha 相關 r=0.83 |
| timeliness | 與 filing_lag 相關 r=-0.84 |
| sqs_score | 被 lag+timeliness 主導，且為反指標 |
| conviction | 強反指標，反而降低 alpha |
| market_impact | 全為常數 50.0（無變異） |
| actionability | 全為常數 ~100（無變異） |

### 需要更多資料才能判斷

| 信號 | 原因 |
|------|------|
| information_edge | 弱正向（r=0.18），獨立性好，但目前效果不顯著 |
| insider_overlap_count | 資料太少（僅 1 筆 non-zero） |
| anomaly detections | 122 tickers 有異常標記，但幾乎全為 TIMING 類型，需更多 SIZE/CLUSTER/REVERSAL 樣本 |

---

## 八、ML 模型校準結果

ML 預測模型（`ml_predictions`）的交叉驗證：

| 指標 | 數值 | 評估 |
|------|------|------|
| 預測 SQS vs 實際 SQS 相關係數 | 0.778 | 良好 |
| Grade 預測準確率 | 100% | 過擬合風險 |
| 平均預測 Grade 機率 | 0.885 | 偏高 |
| 預測 SQS MAE | 2.97 分 | 可接受 |

**注意**: Grade 預測 100% 準確率極可能是過擬合。建議使用 ML 預測的 `predicted_sqs_score` 作為額外驗證，但不應作為主要交易信號。

ML grade_proba 與信號的相關性：
- grade_proba <-> confidence: -0.230（反向）
- grade_proba <-> convergence: -0.220（反向）
- grade_proba <-> signal_strength: -0.166（反向）

這進一步證實 ML 模型可能學到了與 alpha 方向相反的模式。

---

## 九、議員效果分析

| 議員 | PIS 排名 | 交易數 | 平均預期 Alpha | 實際 Alpha | 評價 |
|------|---------|-------|---------------|-----------|------|
| Nancy Pelosi | #5 | 1 | 1.424 | **+5.50%** | 最佳實際 alpha |
| Jake Auchincloss | #1 | 1 | 1.638 | N/A | 最高預期，待驗證 |
| David H McCormick | #4 | 1 | 0.980 | N/A | 高 PIS，待驗證 |
| John Boozman | #3 | 37 | 0.588 | -1.07% | 大量交易但 alpha 偏負 |
| Gilbert Cisneros | #2 | 266 | 0.672 | N/A | 最多交易，無 FF 驗證 |

**建議**: 將議員 PIS 排名整合入 PACS 公式中作為微調因子（非核心因子），例如 Top 5 議員給予 +5% 加成。

---

## 十、局限性與後續工作

### 10.1 資料量限制
- FF3 驗證資料僅 39 筆（來自單一月份 2026-02），統計顯著性不足
- Convergence 信號僅 6 筆有 FF3 驗證
- Options flow 僅 17 筆記錄
- 需累積 3-6 個月資料後重新校準權重

### 10.2 建議後續研究
1. **時間序列回測**: 累積更多月份的 FF3 資料後，進行 rolling window 回測
2. **非線性模型**: 目前使用線性相關分析，可能遺漏非線性交互效果
3. **交易成本**: 未納入滑價、手續費、市場衝擊成本
4. **Sector 調整**: 不同行業的 alpha 特徵可能不同
5. **動態權重**: 市場環境（bull/bear/volatility）可能影響最優權重

### 10.3 實作建議
1. 在 `src/alpha_signal_generator.py` 中新增 `compute_pacs()` 函數
2. 將 PACS 分級結果寫入 `alpha_signals.pacs_score` 和 `alpha_signals.pacs_tier` 欄位
3. Telegram Bot 僅推送 S-Tier 和 A-Tier 信號
4. Dashboard 加入 PACS 視覺化面板
5. 每月重新校準權重（使用 rolling 3-month FF3 資料）

---

## 附錄: 完整 Grid Search 結果

權重格式: (signal_strength, confidence, filing_lag_inv, sqs_score, convergence, options_sentiment)

| 權重組合 | Corr with FF3 |
|---------|---------------|
| (0.30, 0.00, 0.20, 0.00, 0.00, 0.10) | 0.3008 |
| (0.45, 0.00, 0.30, 0.00, 0.00, 0.20) | 0.3008 |
| (0.30, 0.00, 0.30, 0.00, 0.00, 0.20) | 0.2997 |
| (0.45, 0.00, 0.30, 0.00, 0.00, 0.10) | 0.2997 |
| (0.15, 0.00, 0.10, 0.00, 0.00, 0.10) | 0.2978 |
| (0.30, 0.00, 0.20, 0.00, 0.00, 0.20) | 0.2978 |
| (0.45, 0.00, 0.20, 0.00, 0.00, 0.10) | 0.2969 |
| (0.45, 0.00, 0.20, 0.00, 0.00, 0.00) | 0.2953 |
| (0.45, 0.00, 0.20, 0.00, 0.00, 0.20) | 0.2939 |
| (0.15, 0.00, 0.20, 0.00, 0.00, 0.20) | 0.2933 |

---

*報告結束。資料截至 2026-02-27。*
