# Political Alpha Monitor -- Report (2026-02-21 ~ 2026-02-27)


> 報告生成時間: 2026-02-27 18:31:48  
> 資料來源: congress_trades, ai_intelligence_signals, signal_quality_scores, convergence_signals, politician_rankings, extraction_log

## 1. 執行摘要 (Executive Summary)

本期間無新交易紀錄。

> 資料庫總計 404 筆交易，最新交易日期 2026-02-17。

## 2. 新交易明細 (New Trades)

2026-02-21 ~ 2026-02-27 期間無新交易。

## 3. 最佳可操作訊號 (Top Actionable Signals)

> SQS 品質等級: Platinum (80+) > Gold (60-79) > Silver (40-59) > Bronze (20-39) > Discard (<20)

### 等級分布

| 等級 | 筆數 | 平均 SQS | 最低 | 最高 |
|------|------|----------|------|------|
| [***] Platinum | 0 | - | - | - |
| [**] Gold | 13 | 62.3 | 60.5 | 65.5 |
| [*] Silver | 341 | 50.7 | 40.8 | 59.2 |
| [.] Bronze | 40 | 29.9 | 21.8 | 39.5 |
| [-] Discard | 10 | 17.0 | 14.2 | 19.2 |

### Gold+ 訊號明細（共 13 筆）

| # | 等級 | SQS | 議員 | Ticker | 資產 | 買/賣 | 金額 | 交易日 | A | T | C | I | M |
|---|------|-----|------|--------|------|-------|------|--------|---|---|---|---|---|
| 1 | [**] Gold | **65.5** | David H McCormick | `GS` | Goldman Sachs Group | Sale | $1,000,001 - $5,000,000 | 2026-01-23 | 100 | 50 | 70 | 20 | 50 |
| 2 | [**] Gold | **64.2** | Gilbert Cisneros | `CSGP` | CoStar Group, Inc. - Comm | Buy | $1,001 - $15,000 | 2026-01-28 | 100 | 50 | 65 | 20 | 50 |
| 3 | [**] Gold | **64.2** | Gilbert Cisneros | `DASH` | DoorDash, Inc. - Common S | Buy | $1,001 - $15,000 | 2026-01-28 | 100 | 50 | 65 | 20 | 50 |
| 4 | [**] Gold | **64.2** | Gilbert Cisneros | `ISRG` | Intuitive Surgical, Inc.  | Buy | $1,001 - $15,000 | 2026-01-30 | 100 | 50 | 65 | 20 | 50 |
| 5 | [**] Gold | **64.2** | Gilbert Cisneros | `WDAY` | Workday, Inc. - Class A C | Buy | $1,001 - $15,000 | 2026-01-28 | 100 | 50 | 65 | 20 | 50 |
| 6 | [**] Gold | **61.8** | John Boozman | `OMC` | Omnicom Group Inc | Sale | $1,001 - $15,000 | 2026-01-29 | 100 | 50 | 55 | 20 | 50 |
| 7 | [**] Gold | **61.8** | John Boozman | `MU` | Micron Technology | Sale | $1,001 - $15,000 | 2026-01-26 | 100 | 50 | 55 | 20 | 50 |
| 8 | [**] Gold | **61.8** | Jake Auchincloss | `STT` | State Street Corporation  | Sale | $15,001 - $50,000 | 2026-02-17 | 100 | 75 | 35 | 20 | 50 |
| 9 | [**] Gold | **60.5** | Sheri Biggs | `HN` | COATUE INNOVATION FUND | Buy | $250,001 - $500,000 | 2025-12-26 | 100 | 0 | 90 | 20 | 50 |
| 10 | [**] Gold | **60.5** | April McClain Delaney | `PTC` | PTC Inc. - Common Stock | Sale | $1,001 - $15,000 | 2026-01-30 | 100 | 50 | 50 | 20 | 50 |
| 11 | [**] Gold | **60.5** | April McClain Delaney | `TRMB` | Trimble Inc. - Common Sto | Sale | $1,001 - $15,000 | 2026-01-29 | 100 | 50 | 50 | 20 | 50 |
| 12 | [**] Gold | **60.5** | April McClain Delaney | `TRMB` | Trimble Inc. - Common Sto | Sale | $1,001 - $15,000 | 2026-01-28 | 100 | 50 | 50 | 20 | 50 |
| 13 | [**] Gold | **60.5** | April McClain Delaney | `WAB` | Westinghouse Air Brake Te | Sale | $1,001 - $15,000 | 2026-01-30 | 100 | 50 | 50 | 20 | 50 |

> **維度說明**: A=可操作性(30%) T=時效性(20%) C=確信度(25%) I=資訊優勢(15%) M=市場影響(10%)

## 4. Convergence 警報 (多議員同向操作)

> 當多位議員在短時間窗口內對同一標的進行同方向操作時觸發。 跨院 (Cross-Chamber) 訊號更具參考價值。

- 匯聚事件總數: **6** (買入 3 / 賣出 3)

### 4.1 `AAPL` -- 買入 (Cross-Chamber)

- **Convergence Score**: 1.501
- **議員數**: 2 人
- **參與議員**: Nancy Pelosi(House), John Boozman(Senate)
- **院別**: House/Senate
- **時間窗口**: 2026-01-15 ~ 2026-01-15 (0 天)
- **分數明細**: base=0.500 + cross_chamber=0.500 + time_density=1.000 + amount_weight=0.002

### 4.2 `ETN` -- 買入 (Cross-Chamber)

- **Convergence Score**: 1.484
- **議員數**: 2 人
- **參與議員**: John Boozman(Senate), Gilbert Cisneros(House)
- **院別**: House/Senate
- **時間窗口**: 2026-01-29 ~ 2026-01-30 (1 天)
- **分數明細**: base=0.500 + cross_chamber=0.500 + time_density=0.967 + amount_weight=0.002

### 4.3 `DIS` -- 買入 (Cross-Chamber)

- **Convergence Score**: 1.484
- **議員數**: 2 人
- **參與議員**: John Boozman(Senate), Gilbert Cisneros(House)
- **院別**: House/Senate
- **時間窗口**: 2026-01-08 ~ 2026-01-09 (1 天)
- **分數明細**: base=0.500 + cross_chamber=0.500 + time_density=0.967 + amount_weight=0.002

### 4.4 `GS` -- 賣出 (Single-Chamber)

- **Convergence Score**: 1.419
- **議員數**: 3 人
- **參與議員**: Steve Cohen(House), Donald Sternoff Jr. Beyer(House), Sheri Biggs(House)
- **院別**: House
- **時間窗口**: 2025-12-17 ~ 2025-12-22 (5 天)
- **分數明細**: base=1.000 + cross_chamber=0.000 + time_density=0.833 + amount_weight=0.005

### 4.5 `NFLX` -- 賣出 (Single-Chamber)

- **Convergence Score**: 0.967
- **議員數**: 2 人
- **參與議員**: Gilbert Cisneros(House), Richard W. Allen(House)
- **院別**: House
- **時間窗口**: 2025-12-10 ~ 2025-12-12 (2 天)
- **分數明細**: base=0.500 + cross_chamber=0.000 + time_density=0.933 + amount_weight=0.002

### 4.6 `PWR` -- 賣出 (Single-Chamber)

- **Convergence Score**: 0.634
- **議員數**: 2 人
- **參與議員**: April McClain Delaney(House), Gilbert Cisneros(House)
- **院別**: House
- **時間窗口**: 2025-12-02 ~ 2025-12-24 (22 天)
- **分數明細**: base=0.500 + cross_chamber=0.000 + time_density=0.267 + amount_weight=0.002


## 5. 議員觀察清單 (Politician Watch List)

> PIS (Politician Influence Score) 綜合評分，基於活躍度、確信度、分散度、時效性。

| Rank | 議員 | 院別 | 交易數 | PIS 總分 | 等級 | 活躍度 | 確信度 | 分散度 | 時效性 | 買/賣 | 平均延遲 |
|------|------|------|--------|----------|------|--------|--------|--------|--------|-------|----------|
| 1 | **Jake Auchincloss** | House | 1 | **51.4** | B | 0.0 | 1.4 | 25.0 | 25.0 | 0/1 | 10.0天 |
| 2 | **Gilbert Cisneros** | House | 272 | **50.5** | B | 25.0 | 0.8 | 18.4 | 6.3 | 151/121 | 54.4天 |
| 3 | **John Boozman** | Senate | 37 | **48.0** | C | 6.0 | 0.0 | 23.0 | 19.0 | 23/14 | 24.2天 |
| 4 | **David H McCormick** | Senate | 9 | **47.3** | C | 1.3 | 25.0 | 2.8 | 18.2 | 8/1 | 26.1天 |
| 5 | **Nancy Pelosi** | House | 1 | **47.1** | C | 0.0 | 0.0 | 25.0 | 22.1 | 1/0 | 17.0天 |
| 6 | **William F Hagerty, IV** | Senate | 1 | **41.2** | C | 0.0 | 25.0 | 0.0 | 16.2 | 1/0 | 31.0天 |
| 7 | **Richard W. Allen** | House | 6 | **32.4** | C | 0.5 | 3.2 | 20.8 | 7.8 | 3/3 | 50.8天 |
| 8 | **Debbie Dingell** | House | 1 | **31.9** | C | 0.0 | 0.0 | 25.0 | 6.9 | 0/0 | 53.0天 |
| 9 | **Steve Cohen** | House | 7 | **28.4** | C | 1.0 | 1.5 | 25.0 | 0.9 | 1/6 | 67.3天 |
| 10 | **Rob Bresnahan** | House | 2 | **21.7** | D | 0.2 | 2.5 | 0.0 | 19.1 | 2/0 | 24.0天 |
| 11 | **April McClain Delaney** | House | 31 | **20.5** | D | 2.5 | 0.0 | 14.5 | 3.5 | 10/21 | 61.1天 |
| 12 | **Richard Blumenthal** | Senate | 9 | **20.5** | D | 1.3 | 1.3 | 0.0 | 17.9 | 3/6 | 27.0天 |
| 13 | **Sheri Biggs** | House | 9 | **19.1** | D | 1.1 | 4.0 | 13.9 | 0.0 | 7/2 | 69.4天 |
| 14 | **Suzan K. DelBene** | House | 5 | **18.8** | D | 0.7 | 11.3 | 0.0 | 6.8 | 2/3 | 53.2天 |
| 15 | **Susan M Collins** | Senate | 1 | **18.1** | D | 0.0 | 4.9 | 0.0 | 13.2 | 1/0 | 38.0天 |
| 16 | **Donald Sternoff Jr. Beyer** | House | 10 | **17.0** | D | 0.8 | 3.5 | 5.0 | 7.7 | 4/6 | 51.2天 |
| 17 | **Michael A. Jr. Collins** | House | 2 | **6.5** | D | 0.2 | 0.0 | 0.0 | 6.3 | 1/1 | 54.5天 |

## 6. AI Intelligence 訊號

**全域統計**: 102 筆訊號 | 40 筆含 ticker | 79 筆含 impact score

**本期 (2026-02-21 ~ 2026-02-27)**: 64 筆訊號（38 筆可操作）

| # | 來源 | 對象 | Ticker | Impact | Sentiment | 建議 | 時間 |
|---|------|------|--------|--------|-----------|------|------|
| 1 | CONGRESS | Richard Blumenthal | `BINANCE` | **9**/10 | Negative | OPEN | 2026-02-27 08:23 |
| 2 | CONGRESS | Nancy Pelosi | `AB` | **9**/10 | Positive | OPEN | 2026-02-27 08:20 |
| 3 | CONGRESS | Debbie Wasserman Schultz | `ICHR` | **8**/10 | Positive | OPEN | 2026-02-27 08:27 |
| 4 | CONGRESS | Markwayne Mullin | `CVX` | **8**/10 | Positive | OPEN | 2026-02-27 08:23 |
| 5 | CONGRESS | Markwayne Mullin | `RTX` | **8**/10 | Positive | OPEN | 2026-02-27 08:23 |
| 6 | CONGRESS | Nancy Pelosi | `GOOGL` | **8**/10 | Positive | OPEN | 2026-02-27 08:20 |
| 7 | CONGRESS | Nancy Pelosi | `AMZN` | **8**/10 | Positive | OPEN | 2026-02-27 08:20 |
| 8 | CONGRESS | Dave McCormick | `GS` | **7**/10 | Neutral | CLOSE | 2026-02-27 08:27 |
| 9 | CONGRESS | Dave McCormick | `GS` | **7**/10 | Positive | CLOSE | 2026-02-27 08:27 |
| 10 | CONGRESS | Scott Franklin | `HSY` | **7**/10 | Negative | CLOSE | 2026-02-27 08:26 |
| 11 | CONGRESS | Markwayne Mullin | `CVX` | **7**/10 | Positive | CLOSE | 2026-02-27 08:23 |
| 12 | CONGRESS | Richard Blumenthal | `CRYPTOCURRENCY` | **7**/10 | Negative | CLOSE | 2026-02-27 08:23 |
| 13 | CONGRESS | Richard Blumenthal | `RTX` | **7**/10 | Positive | CLOSE | 2026-02-27 08:23 |
| 14 | CONGRESS | Dan Crenshaw | `UNH, CI` | **7**/10 | Negative | CLOSE | 2026-02-27 08:22 |
| 15 | CONGRESS | Ro Khanna | `TECH_SECTOR` | **7**/10 | Negative | CLOSE | 2026-02-27 08:21 |
| 16 | CONGRESS | Susan Collins | `56042RG22` | **6**/10 | Neutral | CLOSE | 2026-02-27 08:28 |
| 17 | CONGRESS | Dave McCormick | `PENNSYLVANIA ST GO` | **6**/10 | Positive | CLOSE | 2026-02-27 08:27 |
| 18 | CONGRESS | Dave McCormick | `DURA-BOND PIPE` | **6**/10 | Positive | CLOSE | 2026-02-27 08:27 |
| 19 | CONGRESS | Dave McCormick | `GS` | **6**/10 | Positive | CLOSE | 2026-02-27 08:27 |
| 20 | CONGRESS | Dave McCormick | `GS` | **6**/10 | Positive | CLOSE | 2026-02-27 08:27 |

> **高影響力 (score >= 8)**: 7 筆 -- `BINANCE`(Richard Blumenthal), `AB`(Nancy Pelosi), `ICHR`(Debbie Wasserman Schultz), `CVX`(Markwayne Mullin), `RTX`(Markwayne Mullin)

## 7. 系統健康 (System Health)

### ETL Pipeline 狀態

- 執行次數: **25** (成功 24 / 失敗 1)
- 總萃取筆數: **445**
  - `house_pdf`: 20 次 (成功 19, 萃取 393 筆)
  - `senate_html`: 5 次 (成功 5, 萃取 52 筆)
- 平均信心度: **0.97**
- 最近執行: 2026-02-27 08:19:52 (`house_pdf`, success)

| 來源類型 | 信心度 | 原始筆數 | 萃取筆數 | 狀態 | 時間 |
|----------|--------|----------|----------|------|------|
| house_pdf | 0.98 | 1 | 1 | success | 2026-02-27 08:19:52 |
| house_pdf | 0.95 | 15 | 15 | success | 2026-02-27 08:19:42 |
| house_pdf | 0.98 | 1 | 1 | success | 2026-02-27 08:19:15 |
| house_pdf | 0.99 | 15 | 15 | success | 2026-02-27 08:19:06 |
| house_pdf | 0.98 | 16 | 16 | success | 2026-02-27 08:18:38 |
| house_pdf | 0.98 | 2 | 2 | success | 2026-02-27 08:18:14 |
| house_pdf | 0.95 | 1 | 1 | partial | 2026-02-27 08:17:56 |
| house_pdf | 0.98 | 2 | 2 | success | 2026-02-27 08:17:48 |
| house_pdf | 0.98 | 5 | 5 | success | 2026-02-27 08:17:38 |
| house_pdf | 0.98 | 87 | 151 | success | 2026-02-27 08:17:26 |
| house_pdf | 0.98 | 72 | 122 | success | 2026-02-27 08:14:42 |
| house_pdf | 0.98 | 2 | 2 | success | 2026-02-27 08:11:37 |
| house_pdf | 0.98 | 1 | 1 | success | 2026-02-27 08:11:22 |
| house_pdf | 0.98 | 26 | 26 | success | 2026-02-27 08:11:11 |
| house_pdf | 0.95 | 19 | 19 | success | 2026-02-27 08:10:29 |

*（共 25 筆，僅顯示前 15 筆）*

### 資料新鮮度

| 指標 | 數值 |
|------|------|
| 資料庫交易總筆數 | 404 |
| House 交易 | 347 (85.9%) |
| Senate 交易 | 57 (14.1%) |
| 不重複議員 | 17 |
| 不重複 Ticker | 262 |
| 最新交易日期 | 2026-02-17 |
| 最新資料建立 | 2026-02-27 08:19:52 |

## 8. Alpha 洞察 (Historical Insights)

> 基於歷史國會交易回測數據的固定洞察（來自 `alpha_backtest.py` 分析結果）。

### 關鍵發現

1. **國會買入訊號具有正 alpha**
   - 5 日平均超額報酬: **+0.77%** (相對 SPY 基準)
   - 10 日平均超額報酬: **+1.02%**
   - 統計顯著性: 在大額交易 (>$250K) 子群中更為顯著

2. **賣出訊號為反向指標**
   - 國會議員賣出後，標的股票短期內常有**正報酬**
   - 建議: 不宜跟隨賣出操作做空，反而可觀察是否為買入機會

3. **最佳進場策略**
   - **Gold+ 等級 + 跨院 Convergence**: 最高勝率組合
   - 建議執行方式: MOC (Market On Close) 或次日 MOO (Market On Open)
   - 持有期: 5-10 個交易日

4. **關鍵風險**
   - 申報延遲: 部分交易延遲 30-45+ 天才申報，資訊時效性降低
   - 小額交易 (<$15K): 訊號雜訊比高，不建議單獨操作
   - 非股票資產 (基金/LLC): 無法直接複製

### 操作建議

| 訊號類型 | 建議動作 | 持有期 | 信心 |
|----------|----------|--------|------|
| Gold+ Buy + Convergence | 跟隨買入 | 5-10 日 | 高 |
| Gold+ Buy (單一議員) | 觀察，MOC 小倉位 | 5 日 | 中 |
| 大額 Sale (>$250K) | 反向觀察（可能買入機會）| 3-5 日 | 中低 |
| Silver 以下 | 僅觀察，不操作 | N/A | 低 |

---

*本報告由 Political Alpha Monitor 自動生成。*