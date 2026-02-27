# RB-005: 議員交易深度剖析 — 跟單優先級研究報告

**報告日期**: 2026-02-27
**分析師**: AI Research Agent (politician-researcher)
**資料來源**: congress_trades (404 筆), alpha_signals (352+ 筆), signal_quality_scores (404 筆), politician_rankings (17 筆), anomaly_detections
**分析期間**: 2025-12 ~ 2026-02

---

## 摘要

本報告針對資料庫中 17 位國會議員的交易紀錄進行深度分析，透過 alpha 表現、交易行為模式、K-Means 聚類、異常偵測等多維度指標，建立「跟單優先級」排名。分析發現 **House 議員在交易頻率和可操作性上優於 Senate**，但 Senate 議員具備更短的 filing lag 和更大的交易金額。綜合評估後，推薦 **Top 5 必追議員**及其最適跟單策略。

---

## 1. 個別議員 Alpha 表現分析

> 篩選條件：交易次數 >= 5 筆，具有 alpha 信號資料

### 1.1 Alpha 排行榜

| 排名 | 議員 | 院別 | 交易數 | 平均 Alpha 5d | 平均 Alpha 20d | 信號強度 | 勝率(>0.5%) |
|------|------|------|--------|---------------|----------------|----------|-------------|
| 1 | David H McCormick | Senate | 9 | **0.980%** | **1.921%** | 0.789 | 11.1% |
| 2 | Richard W. Allen | House | 6 | **0.912%** | **1.699%** | 0.446 | 83.3% |
| 3 | Gilbert Cisneros | House | 272 | 0.675% | 1.086% | 0.301 | 64.0% |
| 4 | John Boozman | Senate | 37 | 0.588% | 0.895% | 0.282 | 62.2% |
| 5 | Donald S. Beyer Jr. | House | 10 | 0.495% | 1.138% | 0.301 | 10.0% |
| 6 | Steve Cohen | House | 7 | 0.493% | 1.192% | 0.234 | 14.3% |
| 7 | Sheri Biggs | House | 9 | 0.463% | 0.639% | 0.223 | 11.1% |
| 8 | April McClain Delaney | House | 31 | 0.395% | 0.884% | 0.160 | 6.5% |

### 1.2 關鍵發現

- **David H McCormick** 擁有最高的單筆平均 alpha（0.98%），但其交易集中在單一標的（Municipal Bond 為主），且勝率僅 11.1%，可操作性極低（actionability 11.1%）。這反映其交易以高金額、低頻率、非股票為主的特徵。
- **Richard W. Allen** 是最均衡的高 alpha 交易者：alpha 0.91%、勝率 83.3%、可操作性 83.3%，且交易涵蓋多元化股票標的。
- **Gilbert Cisneros** 交易量最大（272 筆），提供最多可跟單機會，平均 alpha 0.68% 搭配 64% 勝率，具備統計顯著性。
- **John Boozman** 在 Senate 議員中表現突出：filing lag 僅 24.2 天（全體最低之一）、actionability 100%、勝率 62.2%。

---

## 2. 交易行為模式分析

### 2.1 交易金額分佈

| 議員 | 主要金額區間 | 平均交易規模 | 特徵 |
|------|-------------|-------------|------|
| David H McCormick | $100K-$500K, $1M-$5M | **$555,556** | 超大額集中交易 |
| Suzan K. DelBene | $250K-$500K | $113,201 | 大額非股票交易 |
| Sheri Biggs | $1K-$100K 分散 | $41,112 | 中等規模多元化 |
| Donald S. Beyer Jr. | $15K-$100K | $36,001 | 中等規模債券為主 |
| Richard W. Allen | $1K-$250K 分散 | $32,668 | 中等規模股票為主 |
| Steve Cohen | $1K-$50K | $16,001 | 中小額股票交易 |
| Gilbert Cisneros | **88.6% 在 $1K-$15K** | $9,233 | 小額高頻交易 |
| April McClain Delaney | **100% 在 $1K-$15K** | $1,001 | 全數小額交易 |
| John Boozman | **100% 在 $1K-$15K** | $1,001 | 全數小額交易 |

### 2.2 Filing Lag 模式（申報延遲）

| 議員 | 平均 Lag | 最短 | 最長 | 時效性評估 |
|------|---------|------|------|-----------|
| John Boozman | **24.2 天** | 17 天 | 38 天 | 極佳 |
| David H McCormick | **26.1 天** | 23 天 | 30 天 | 極佳且穩定 |
| Richard Blumenthal | 27.0 天 | 15 天 | 35 天 | 佳 |
| Richard W. Allen | 50.8 天 | 32 天 | 77 天 | 中等，變異大 |
| Donald S. Beyer Jr. | 51.2 天 | 16 天 | 79 天 | 中等，變異大 |
| Suzan K. DelBene | 53.2 天 | 45 天 | 72 天 | 偏慢 |
| Gilbert Cisneros | 54.4 天 | 24 天 | 79 天 | 偏慢 |
| April McClain Delaney | 61.1 天 | 28 天 | 87 天 | 慢 |
| Steve Cohen | **67.3 天** | 60 天 | 72 天 | 非常慢 |
| Sheri Biggs | **69.4 天** | 53 天 | 88 天 | 非常慢 |

### 2.3 資產類型偏好

| 議員 | 主要資產 | 股票比例 | 投資風格 |
|------|---------|---------|---------|
| April McClain Delaney | 100% 股票 | 100% | 純股票交易者 |
| John Boozman | 100% 股票 | 100% | 純股票交易者 |
| Gilbert Cisneros | 96.3% 股票 + 3.7% Muni Bond | 96% | 股票為主 |
| Steve Cohen | 85.7% 股票 + Preferred Stock | 86% | 股票為主 |
| Richard W. Allen | 83.3% 股票 + Treasury | 83% | 股票為主 |
| Sheri Biggs | 33% 股票 + 44% 基金 + 債券 | 33% | 多元化 |
| Donald S. Beyer Jr. | 70% 債券 + 30% Muni Bond | **0%** | 純固定收益 |
| David H McCormick | 89% Muni Bond + 11% 股票 | 11% | 以債券為主 |
| Richard Blumenthal | 100% Private Fund | **0%** | 私募基金 |
| Suzan K. DelBene | 80% 債券 + 20% Muni Bond | **0%** | 純固定收益 |

### 2.4 交易頻率

| 議員 | 月交易量 | 活躍月份 | 模式 |
|------|---------|---------|------|
| Gilbert Cisneros | **~136 筆/月** | 2025/12-2026/02 | 極高頻散彈式 |
| John Boozman | 37 筆/月 | 2026/01 單月 | 集中爆發 |
| April McClain Delaney | ~16 筆/月 | 2025/12-2026/01 | 穩定中高頻 |
| David H McCormick | 9 筆/月 | 2026/01 單月 | 集中買入 |
| Richard Blumenthal | 9 筆/月 | 2026/01 單月 | 集中交易 |
| Sheri Biggs | ~5 筆/月 | 2025/12-2026/01 | 偏低頻 |
| Steve Cohen | 7 筆/月 | 2025/12 單月 | 集中賣出 |
| Richard W. Allen | ~3 筆/月 | 2025/12-2026/01 | 低頻精選 |

---

## 3. K-Means 聚類分析

> 特徵向量: [交易數, 獨立標的數, 買入比例, 平均金額, Filing Lag, 股票比例, 平均 Alpha, 信號強度, SQS, Conviction]
> 聚類數: K=3 (StandardScaler 標準化)

### 聚類結果

| 聚類 | 成員 | 標籤 | 特徵描述 |
|------|------|------|---------|
| **Cluster 0** | Beyer, Blumenthal, DelBene | **被動非股票交易者** | 低頻(8筆)、非股票(0%股票比例)、中等金額($87K)、低 alpha(0.16%)、低 SQS(29.5) |
| **Cluster 1** | Delaney, Cisneros, Boozman, Allen, Biggs, Cohen | **活躍股票交易者** | 高頻(60筆)、多元標的(45個)、高股票比例(83%)、中等 alpha(0.59%)、高 SQS(49.3) |
| **Cluster 2** | McCormick | **高額集中交易者** | 極高金額($556K)、極高 conviction(61.7)、高 alpha(0.98%)、單一標的(GS/Muni Bond)、低 actionability(11%) |

### 聚類洞察

1. **Cluster 1（活躍股票交易者）**是最適合跟單的群組：
   - 交易標的以股票為主，流動性佳
   - 高 actionability（可實際執行交易）
   - 合理的 alpha 期望值搭配較高的統計樣本數

2. **Cluster 2（McCormick）**雖有最高 alpha，但：
   - 以市政債券為主，一般投資者難以複製
   - Actionability 極低
   - 單一標的風險集中

3. **Cluster 0（被動非股票交易者）**跟單價值最低：
   - 私募基金、債券等非公開市場標的
   - 信號品質差，Alpha 接近零

---

## 4. 異常交易偵測

### 4.1 異常摘要

| 議員 | 異常類型 | 嚴重度 | 次數 | 平均分數 | 含義 |
|------|---------|--------|------|---------|------|
| Gilbert Cisneros | SIZE (CRITICAL) | 極高 | 6 | 10.0 | 多筆 $250K-$500K 債券交易，遠超個人平均 |
| Gilbert Cisneros | TIMING | 高 | 114 | 6.1 | 大量交易時序異常 |
| Gilbert Cisneros | REVERSAL | 中 | 4 | 6.0 | 短期內反向操作（買後賣） |
| April McClain Delaney | TIMING | 高 | 16 | 7.5 | 交易時序可疑 |
| Sheri Biggs | TIMING | 高 | 6 | 6.6 | 交易時序可疑 |
| Steve Cohen | TIMING | 高 | 5 | 6.0 | 交易時序可疑 |
| **多人聚集交易** | CLUSTER | 高 | 1 | **9.5** | Beyer, Biggs, Cohen 同期交易 |

### 4.2 異常解讀

- **Gilbert Cisneros** 的 114 筆 TIMING 異常 + 6 筆 CRITICAL SIZE 異常值得高度關注。其大額市政債券購入（$250K-$500K）遠超個人平均交易規模（$9,233），z-score=6.24 屬於極端值。
- **CLUSTER 異常**顯示 Beyer、Biggs、Cohen 三人在同一時期進行交易，可能反映同一事件驅動的資訊外溢。
- **Delaney 的 TIMING 異常**（16 筆，平均分 7.5）是所有議員中時序異常分數最高的，暗示其交易時機可能與特定事件高度相關。

---

## 5. House vs Senate 統計比較

| 指標 | House | Senate | 差異 |
|------|-------|--------|------|
| 總交易數 | 347 | 57 | House 交易量 6x |
| 獨立議員數 | 12 | 5 | House 覆蓋更廣 |
| 獨立標的數 | 235 | 36 | House 多元化更高 |
| 買入比例 | 52.5% | **63.2%** | Senate 偏多頭 |
| **平均 Filing Lag** | 55.1 天 | **25.3 天** | Senate 快 2.2x |
| 平均交易金額 | $24,793 | **$105,395** | Senate 金額 4.3x |
| 平均 Alpha 5d | **0.647%** | 0.599% | House 略優 |
| 平均 Alpha 20d | **1.082%** | 0.922% | House 略優 |
| 平均信號強度 | 0.290 | 0.295 | 接近 |
| 平均 SQS | 48.39 | 48.32 | 接近 |
| **平均 Actionability** | **91.8%** | 68.8% | House 可操作性遠優 |

### 結論

- **House 更適合跟單**：可操作性高（91.8% vs 68.8%）、alpha 略優、交易量大提供更多機會
- **Senate 的優勢在於時效性**：filing lag 僅 25 天 vs House 的 55 天
- **Senate 金額更大**但以債券/非股票為主，對一般投資者價值有限

---

## 6. Top 5 必追議員推薦（跟單優先級）

> 綜合評分 = Alpha(30%) + 勝率(20%) + 信號強度(15%) + 可操作性(15%) + 時效性(10%) + Conviction(10%)

### 第 1 名: Richard W. Allen (House) — 綜合分 72.79

| 指標 | 數值 | 評級 |
|------|------|------|
| 平均 Alpha 5d | 0.912% | 極高 |
| 勝率 (>0.5%) | **83.3%** | 極高 |
| 可操作性 | 83.3% | 高 |
| 交易數 | 6 | 偏少 |
| 主要標的 | SPGI, NFLX, PAYX, FERG, AWK | 大型優質股 |
| Filing Lag | 50.8 天 | 中等 |
| 最佳交易 | SPGI Buy (alpha 1.39%) | |

**跟單策略**: 精選型跟單。Allen 交易不頻繁但命中率極高，每筆交易都值得認真評估。重點關注其買入信號，尤其是工業/科技類股票。

**風險提示**: 樣本數僅 6 筆，統計顯著性有待更多資料驗證。

---

### 第 2 名: Gilbert Cisneros (House) — 綜合分 60.83

| 指標 | 數值 | 評級 |
|------|------|------|
| 平均 Alpha 5d | 0.675% | 中高 |
| 勝率 (>0.5%) | **64.0%** | 高 |
| 可操作性 | **96.5%** | 極高 |
| 交易數 | **272** | 極多 |
| 獨立標的 | **200** | 極度多元化 |
| 最佳交易 | FNV/WPM Buy (alpha 1.80%) | 貴金屬股 |
| 異常 | 6 筆 CRITICAL SIZE + 114 TIMING | 需注意 |

**跟單策略**: 量化型跟單。Cisneros 的高頻交易提供大量信號，建議：
- 只跟單 Buy 信號（買入比例 55.5%，alpha 較高）
- 篩選 alpha > 0.8% 的信號（約 57 筆 very strong）
- 重點關注 $15K+ 交易（突破其常規的小額模式可能更有資訊含量）
- 留意 DASH、ETN、FNV、WPM 等重複買入標的

**風險提示**: 極大量 TIMING 異常需持續監控；大額債券交易可能與其委員會職責相關。

---

### 第 3 名: John Boozman (Senate) — 綜合分 60.60

| 指標 | 數值 | 評級 |
|------|------|------|
| 平均 Alpha 5d | 0.588% | 中等 |
| 勝率 (>0.5%) | **62.2%** | 高 |
| 可操作性 | **100%** | 滿分 |
| 交易數 | 37 | 適中 |
| Filing Lag | **24.2 天** | 極快 |
| Buy/Sell Ratio | 1.64 | 偏多頭 |
| 最佳交易 | AAPL/DIS/ETN/NFLX Buy (alpha 1.12%) | |

**跟單策略**: 時效優先型跟單。Boozman 是時效性最佳的議員之一（24 天 lag），搭配 100% actionability 和高勝率。建議：
- 優先跟單買入信號（Buy ratio 62%，偏多頭傾向）
- 利用其短 filing lag 的時效優勢
- 重點關注科技股買入（AAPL, DIS, NFLX 等 alpha > 1%）

**風險提示**: 全數為 $1K-$15K 小額交易，conviction 偏低。

---

### 第 4 名: David H McCormick (Senate) — 綜合分 58.69

| 指標 | 數值 | 評級 |
|------|------|------|
| 平均 Alpha 5d | **0.980%** | 最高 |
| 平均 Alpha 20d | **1.921%** | 最高 |
| 信號強度 | **0.789** | 最高 |
| Conviction | **61.7** | 最高 |
| 可操作性 | 11.1% | 極低 |
| Filing Lag | 26.1 天 | 極快 |
| 主要標的 | GS (股票) + Municipal Bonds | |
| Buy/Sell Ratio | **8.0** | 極度偏多頭 |

**跟單策略**: 高信念型跟單。McCormick 的交易特徵極為獨特：
- 極高金額（平均 $556K）、極高 conviction、極度偏多頭
- 唯一可跟單的是 **GS (Goldman Sachs)** 賣出信號（alpha 0.98%）
- 其市政債券交易不可複製，但反映其對固定收益市場的看法
- 建議關注其未來是否增加股票交易

**風險提示**: 9 筆交易中 8 筆為 Municipal Bond，實際可操作股票信號僅 1 筆。

---

### 第 5 名: Steve Cohen (House) — 綜合分 42.79

| 指標 | 數值 | 評級 |
|------|------|------|
| 平均 Alpha 5d | 0.493% | 中等 |
| 平均 Alpha 20d | **1.192%** | 高 |
| 可操作性 | **100%** | 滿分 |
| 交易數 | 7 | 偏少 |
| Buy/Sell Ratio | **0.17** | 極度偏空 |
| Filing Lag | 67.3 天 | 慢 |
| 最佳交易 | GS Sale (alpha 0.95%) | |

**跟單策略**: 逆向賣出信號型。Cohen 幾乎全為賣出操作（6/7 為 Sale），建議：
- 將其賣出信號視為「減持/避險」指標
- 當 Cohen 賣出某檔股票時，考慮減持或對沖
- GS 賣出信號 alpha 最高（0.95%），金融股是其主要操作領域

**風險提示**: Filing lag 67 天偏長，信號時效性較差。

---

## 7. 跟單優先級總覽

| 優先級 | 議員 | 綜合分 | 跟單類型 | 最適策略 |
|--------|------|--------|---------|---------|
| **S 級** | Richard W. Allen | 72.79 | 精選型 | 每筆交易全跟 |
| **A 級** | Gilbert Cisneros | 60.83 | 量化篩選型 | 篩選 alpha>0.8% 買入信號 |
| **A 級** | John Boozman | 60.60 | 時效優先型 | 快速跟單買入信號 |
| **B 級** | David H McCormick | 58.69 | 高信念型 | 僅跟股票交易 |
| **B 級** | Steve Cohen | 42.79 | 逆向賣出型 | 以賣出信號做減持參考 |
| C 級 | Sheri Biggs | 39.08 | 觀察 | 暫不跟單 |
| C 級 | April M. Delaney | 38.78 | 觀察 | 勝率太低暫不跟單 |
| D 級 | Donald S. Beyer Jr. | 36.23 | 不建議 | 債券為主，不可複製 |
| D 級 | Richard Blumenthal | N/A | 不建議 | 私募基金，完全不可複製 |
| D 級 | Suzan K. DelBene | N/A | 不建議 | 債券為主，無 alpha 信號 |

---

## 8. 附錄

### 8.1 聚類技術細節

- 演算法: K-Means (k=3, random_state=42, n_init=10)
- 標準化: StandardScaler (zero mean, unit variance)
- 特徵: 10 維 (total_trades, unique_tickers, buy_ratio, avg_amount, avg_lag, stock_ratio, avg_alpha, avg_signal, avg_sqs, avg_conviction)
- Silhouette 效果: 3 個清晰分群，分別對應「被動非股票」、「活躍股票」、「高額集中」交易風格

### 8.2 綜合評分公式

```
Composite = Alpha_Score * 0.30 + Win_Rate * 0.20 + Signal_Strength * 0.15
          + Actionability * 0.15 + Timing_Score * 0.10 + Conviction * 0.10

其中:
- Alpha_Score = min(avg_alpha_5d / 1.0 * 100, 100)
- Win_Rate = (trades with alpha > 0.5%) / total_trades * 100
- Signal_Strength = min(avg_signal / 1.0 * 100, 100)
- Actionability = avg actionability from SQS (0-100)
- Timing_Score = max(0, 100 - avg_filing_lag_days)
- Conviction = avg conviction from SQS (0-100)
```

### 8.3 資料限制

1. **時間範圍有限**: 僅 2025/12-2026/02 約 3 個月資料，長期趨勢需更多資料驗證
2. **Alpha 為模型預估**: expected_alpha 為系統推算值，非實際市場回報
3. **小樣本風險**: 多數議員交易數 < 40 筆，統計顯著性有限
4. **Cisneros 主導效應**: 272/404 筆交易（67%）來自單一議員，整體統計受其影響較大
5. **Non-stock trades**: 部分議員的主要交易為債券/基金，alpha 計算可能不適用

---

*報告生成時間: 2026-02-27 | Political Alpha Monitor v3.0*
