# Political Alpha Monitor — 每日營運報告
**報告日期**: 2026-02-27
**生成時間**: 2026-02-27 18:28:36
**資料來源**: `data.db`
**可用區段**: 5 / 5

---

## 1. ETL Pipeline 狀態

### 1.1 今日 ETL 執行紀錄

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
| house_pdf | 0.95 | 4 | 4 | success | 2026-02-27 08:09:38 |
| house_pdf | 0.98 | 3 | 3 | success | 2026-02-27 08:09:26 |
| house_pdf | 0.98 | 1 | 1 | success | 2026-02-27 08:09:14 |
| house_pdf | 0.95 | 4 | 4 | success | 2026-02-27 08:09:03 |
| house_pdf | 0.95 | 2 | 2 | success | 2026-02-27 08:08:44 |
| senate_html | 0.95 | 13 | 13 | success | 2026-02-27 08:08:20 |
| senate_html | 0.95 | 1 | 1 | success | 2026-02-27 08:08:04 |
| senate_html | 0.95 | 1 | 1 | success | 2026-02-27 08:07:58 |
| senate_html | 0.95 | 14 | 14 | success | 2026-02-27 08:07:44 |
| senate_html | 0.95 | 23 | 23 | success | 2026-02-27 08:07:27 |

- 今日執行次數: **25**
- 成功次數: **24** / 25
- 平均信心度: **0.97**

### 1.2 今日新增交易紀錄

- 今日新增: **385 筆**
  - House: 338 筆
  - Senate: 47 筆
- 交易類型分布:
  - Buy: 209 筆
  - Sale: 175 筆
  - Exchange: 1 筆

**今日新增交易明細（前 10 筆）:**

| 議員 | 院別 | Ticker | 交易類型 | 金額區間 | 交易日 | 信心度 |
|------|------|--------|----------|----------|--------|--------|
| Debbie Dingell | House | VSNNT | Exchange | $1,001 - $15,000 | 2026-01-05 | 0.98 |
| Suzan K. DelBene | House | N/A | Sale | $15,001 - $50,000 | 2026-01-13 | 0.95 |
| Suzan K. DelBene | House | N/A | Sale | $250,001 - $500,000 | 2026-01-06 | 0.95 |
| Suzan K. DelBene | House | N/A | Buy | $250,001 - $500,000 | 2026-01-06 | 0.95 |
| Suzan K. DelBene | House | N/A | Sale | $50,001 - $100,000 | 2026-01-13 | 0.95 |
| Suzan K. DelBene | House | N/A | Buy | $1,001 - $15,000 | 2025-12-17 | 0.98 |
| April McClain Delaney | House | TECH | Sale | $1,001 - $15,000 | 2026-01-28 | 0.99 |
| April McClain Delaney | House | BJ | Sale | $1,001 - $15,000 | 2026-01-28 | 0.99 |
| April McClain Delaney | House | IDXX | Sale | $1,001 - $15,000 | 2026-01-13 | 0.99 |
| April McClain Delaney | House | LH | Buy | $1,001 - $15,000 | 2026-01-28 | 0.99 |

*...共 385 筆，僅顯示前 10 筆。*

### 1.3 資料庫全域統計

| 指標 | 數值 |
|------|------|
| 總交易筆數 | 404 |
| House 交易 | 347 (85.9%) |
| Senate 交易 | 57 (14.1%) |
| 不重複議員 | 17 |
| 不重複 Ticker | 262 |
| 最新交易日期 | 2026-02-17 |
| 最新資料建立 | 2026-02-27 08:19:52 |

---

## 2. AI 信號摘要

### 2.1 今日新增信號

今日新增 **64 個**信號。

- 高影響力 (score >= 8): **15** 個
- 中等影響 (score 6-7): **33** 個
- 低影響 (score < 6): **16** 個

### 2.2 全域信號統計

| 指標 | 數值 |
|------|------|
| 信號總數 | 102 |
| 高影響力 (>= 8) | 17 (16.7%) |
| 中等影響 (6-7) | 45 (44.1%) |
| 低影響 (< 6) | 17 (16.7%) |
| 無評分 (NULL) | 23 (22.5%) |
| 有 Ticker 的信號 | 40 (39.2%) |

### 2.3 Top 信號（今日）

| 來源 | 議員/機構 | Ticker | 影響分數 | 情緒 | 建議 |
|------|-----------|--------|----------|------|------|
| CONGRESS | Nancy Pelosi | AB | 9 | Positive | OPEN |
| CONGRESS | Richard Blumenthal | BINANCE | 9 | Negative | OPEN |
| CONGRESS | Julie Johnson | N/A | 9 | Positive | OPEN |
| CONGRESS | Nancy Pelosi | GOOGL | 8 | Positive | OPEN |
| CONGRESS | Nancy Pelosi | AMZN | 8 | Positive | OPEN |
| CONGRESS | Josh Gottheimer | N/A | 8 | Positive | OPEN |
| CONGRESS | Marjorie Taylor Greene | N/A | 8 | Neutral | OPEN |
| CONGRESS | Richard Blumenthal | N/A | 8 | Neutral | OPEN |
| CONGRESS | Markwayne Mullin | CVX | 8 | Positive | OPEN |
| CONGRESS | Markwayne Mullin | RTX | 8 | Positive | OPEN |

---

## 3. 信號品質指標 (SQS)

- 總評分筆數: **404**
- 平均 SQS: **48.1**

### 等級分布

| 等級 | 筆數 | 佔比 |
|------|------|------|
| Platinum | 0 | 0.0% |
| Gold | 13 | 3.2% |
| Silver | 341 | 84.4% |
| Bronze | 40 | 9.9% |
| Discard | 10 | 2.5% |

### Top 5 最高分信號

| SQS | 等級 | 議員 | Ticker | 建議行動 |
|-----|------|------|--------|----------|
| 65.5 | Gold | David H McCormick | GS | 信號，MOC |
| 64.2 | Gold | Gilbert Cisneros | CSGP | 信號，MOC |
| 64.2 | Gold | Gilbert Cisneros | DASH | 信號，MOC |
| 64.2 | Gold | Gilbert Cisneros | ISRG | 信號，MOC |
| 64.2 | Gold | Gilbert Cisneros | WDAY | 信號，MOC |

---

## 4. 匯聚訊號 (Convergence Signals)

- 匯聚事件總數: **6**
- 買入匯聚: **3** | 賣出匯聚: **3**

### 活躍匯聚事件

| 排名 | Ticker | 方向 | 議員數 | 院別 | 評分 | 時間跨度 | 涉及議員 |
|------|--------|------|--------|------|------|----------|----------|
| 1 | AAPL | 買入 | 2 | House/Senate | 1.501 | 0天 | Nancy Pelosi(House), John Boozman(Sen... |
| 2 | ETN | 買入 | 2 | House/Senate | 1.484 | 1天 | John Boozman(Senate), Gilbert Cisnero... |
| 3 | DIS | 買入 | 2 | House/Senate | 1.484 | 1天 | John Boozman(Senate), Gilbert Cisnero... |
| 4 | GS | 賣出 | 3 | House | 1.419 | 5天 | Steve Cohen(House), Donald Sternoff J... |
| 5 | NFLX | 賣出 | 2 | House | 0.967 | 2天 | Gilbert Cisneros(House), Richard W. A... |
| 6 | PWR | 賣出 | 2 | House | 0.634 | 22天 | April McClain Delaney(House), Gilbert... |

---

## 5. 議員排名 (Politician Intelligence Score)

共 **5** 位議員已排名。

### Top 5 議員

| 排名 | 議員姓名 | 院別 | PIS 總分 | 交易數 | 標的數 | 活躍度 | 信念度 | 分散度 | 時效性 |
|------|----------|------|----------|--------|--------|--------|--------|--------|--------|
| 1 | John Boozman | Senate | 75.0 (A) | 37 | 34 | 25.0 | 0.0 | 25.0 | 25.0 |
| 2 | David H McCormick | Senate | 55.1 (B) | 9 | 1 | 5.6 | 25.0 | 3.0 | 21.6 |
| 3 | William F Hagerty, IV | Senate | 37.7 (C) | 1 | 0 | 0.0 | 25.0 | 0.0 | 12.7 |
| 4 | Richard Blumenthal | Senate | 26.8 (C) | 9 | 0 | 5.6 | 1.3 | 0.0 | 19.9 |
| 5 | Susan M Collins | Senate | 4.9 (D) | 1 | 0 | 0.0 | 4.9 | 0.0 | 0.0 |

---

*本報告由 Political Alpha Monitor 自動生成。*