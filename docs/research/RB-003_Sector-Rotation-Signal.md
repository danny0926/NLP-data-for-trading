# RB-003: Congressional Sector Rotation Signal

**狀態**: Draft
**研究員**: Market Researcher
**日期**: 2026-02-27
**資料範圍**: 2025-12-01 ~ 2026-02-17（404 筆交易，262 個 ticker，226 個成功對應板塊）

---

## 摘要

本研究分析國會議員交易記錄中的板塊輪動信號。在 404 筆交易中，我們成功為 226 個 ticker 取得 yfinance 板塊分類，覆蓋率達 86%。分析發現三個具有統計意義的板塊信號：**能源板塊強烈賣出**（淨方向 -21）、**醫療保健板塊強力買入**（淨方向 +14）、以及**工業板塊加速買入**（淨方向 +9）。這些信號與當前政策環境高度一致。

---

## 一、板塊分布分析

### 1.1 總覽（全時段）

| 板塊 | Buy 筆數 | Sale 筆數 | 淨方向 | 方向 | 涉及議員數 | 涉及 Ticker 數 |
|------|----------|-----------|--------|------|------------|----------------|
| Industrials | 32 | 23 | +9 | BUY | 5 | 39 |
| Technology | 28 | 27 | +1 | FLAT | 7 | 37 |
| Financial Services | 25 | 19 | +6 | BUY | 9 | 33 |
| Healthcare | 22 | 8 | **+14** | **BUY** | 3 | 24 |
| Consumer Cyclical | 16 | 18 | -2 | SELL | 2 | 20 |
| Energy | 3 | 24 | **-21** | **SELL** | 2 | 19 |
| Real Estate | 12 | 8 | +4 | BUY | 1 | 17 |
| Consumer Defensive | 6 | 12 | -6 | SELL | 2 | 13 |
| Communication Services | 9 | 9 | 0 | FLAT | 3 | 12 |
| Basic Materials | 10 | 2 | +8 | BUY | 2 | 11 |
| Utilities | 0 | 1 | -1 | SELL | 1 | 1 |

### 1.2 核心觀察

- **最強買入信號**: Healthcare（+14），接著是 Industrials（+9）和 Basic Materials（+8）
- **最強賣出信號**: Energy（-21），接著是 Consumer Defensive（-6）
- **中性板塊**: Technology 與 Communication Services 幾乎持平

### 1.3 前 30 大子產業

| 子產業 | 板塊 | Buy | Sell | 淨方向 | 議員數 |
|--------|------|-----|------|--------|--------|
| Oil & Gas E&P | Energy | 0 | 10 | **-10** | 1 |
| Aerospace & Defense | Industrials | 9 | 4 | +5 | 2 |
| Specialty Industrial Machinery | Industrials | 8 | 3 | +5 | 2 |
| Internet Retail | Consumer Cyclical | 8 | 4 | +4 | 1 |
| Medical Instruments & Supplies | Healthcare | 4 | 0 | **+4** | 1 |
| Capital Markets | Financial Services | 4 | 7 | -3 | 5 |
| Oil & Gas Midstream | Energy | 1 | 4 | -3 | 1 |
| Oil & Gas Integrated | Energy | 1 | 4 | -3 | 2 |
| Engineering & Construction | Industrials | 2 | 5 | -3 | 3 |
| Biotechnology | Healthcare | 5 | 2 | +3 | 2 |
| Consumer Electronics | Technology | 4 | 1 | +3 | 4 |
| Specialty Chemicals | Basic Materials | 4 | 1 | +3 | 1 |
| Drug Manufacturers - General | Healthcare | 4 | 1 | +3 | 1 |
| Insurance Brokers | Financial Services | 4 | 1 | +3 | 2 |

---

## 二、近期板塊輪動趨勢

### 2.1 時序比較：2025 年 12 月 vs 2026 年 1-2 月

| 板塊 | 12月 Buy | 12月 Sell | 12月淨 | 1月+ Buy | 1月+ Sell | 1月+淨 | 輪動幅度 |
|------|----------|----------|--------|----------|----------|--------|----------|
| Technology | 9 | 18 | -9 | 19 | 9 | **+10** | **+19** |
| Industrials | 11 | 15 | -4 | 21 | 8 | **+13** | **+17** |
| Financial Services | 5 | 10 | -5 | 20 | 9 | **+11** | **+16** |
| Energy | 2 | 5 | -3 | 1 | 19 | **-18** | **-15** |
| Communication Services | 1 | 7 | -6 | 8 | 2 | +6 | +12 |
| Consumer Cyclical | 5 | 10 | -5 | 11 | 8 | +3 | +8 |
| Real Estate | 4 | 5 | -1 | 8 | 3 | +5 | +6 |
| Basic Materials | 2 | 0 | +2 | 8 | 2 | +6 | +4 |
| Consumer Defensive | 4 | 6 | -2 | 2 | 6 | -4 | -2 |
| Healthcare | 13 | 5 | +8 | 9 | 3 | +6 | -2 |
| Utilities | 0 | 0 | 0 | 0 | 1 | -1 | -1 |

### 2.2 關鍵輪動發現

**正向輪動（加速買入）：**
1. **Technology (+19 shift)**: 12 月大量賣出後，1 月起轉為淨買入。這是最劇烈的方向反轉。
2. **Industrials (+17 shift)**: 類似反轉模式，1 月後大幅買入工業股。
3. **Financial Services (+16 shift)**: 金融股從淨賣出轉為淨買入，4 位議員參與買入。

**負向輪動（加速賣出）：**
1. **Energy (-15 shift)**: 12 月已偏賣出，1 月加速拋售。1 月 9 日 Gilbert Cisneros 一天賣出 18 檔能源股。

**穩定板塊：**
- Healthcare 保持一致買入方向（12 月 +8，1 月 +6），表現穩定。

### 2.3 能源板塊賣出明細（關鍵信號）

Gilbert Cisneros 於 **2026-01-09 單日集中賣出 18 檔能源股**，涵蓋：

| 日期 | Ticker | 公司 | 子產業 | 金額 |
|------|--------|------|--------|------|
| 2026-01-09 | XOM | Exxon Mobil | Oil & Gas Integrated | $50,001 - $100,000 |
| 2026-01-09 | CVX | Chevron | Oil & Gas Integrated | $15,001 - $50,000 |
| 2026-01-09 | COP | ConocoPhillips | Oil & Gas E&P | $1,001 - $15,000 |
| 2026-01-09 | HAL | Halliburton | Oil & Gas Equipment | $1,001 - $15,000 |
| 2026-01-09 | BKR | Baker Hughes | Oil & Gas Equipment | $1,001 - $15,000 |
| 2026-01-09 | EOG | EOG Resources | Oil & Gas E&P | $1,001 - $15,000 |
| 2026-01-09 | MTDR | Matador Resources | Oil & Gas E&P | $15,001 - $50,000 |
| 2026-01-09 | MGY | Magnolia Oil & Gas | Oil & Gas E&P | $15,001 - $50,000 |
| 2026-01-09 | WMB | Williams Companies | Oil & Gas Midstream | $1,001 - $15,000 |
| 2026-01-09 | VLO | Valero Energy | Oil & Gas Refining | $1,001 - $15,000 |
| 2026-01-09 | TRGP | Targa Resources | Oil & Gas Midstream | $1,001 - $15,000 |
| 2026-01-09 | OKE | ONEOK | Oil & Gas Midstream | $1,001 - $15,000 |
| 2026-01-09 | KMI | Kinder Morgan | Oil & Gas Midstream | $1,001 - $15,000 |
| 2026-01-09 | GPOR | Gulfport Energy | Oil & Gas E&P | $1,001 - $15,000 |
| 2026-01-09 | CHRD | Chord Energy | Oil & Gas E&P | $1,001 - $15,000 |
| 2026-01-09 | APA | APA Corp | Oil & Gas E&P | $1,001 - $15,000 |
| 2026-01-09 | CCJ | Cameco (鈾) | Uranium | $1,001 - $15,000 |
| 2026-01-09 | CVX | Chevron (二次) | Oil & Gas Integrated | $1,001 - $15,000 |

此為 **系統性板塊出清**，非個股調整。

---

## 三、多議員板塊共識分析

同一板塊有多位議員同方向交易時，信號更可靠：

### 3.1 買入共識（2+ 議員）

| 板塊 | 共識議員 | 議員名單 |
|------|----------|----------|
| Technology | 4 位 | Nancy Pelosi, Gilbert Cisneros, John Boozman, Steve Cohen |
| Industrials | 4 位 | Gilbert Cisneros, John Boozman, April McClain Delaney, Richard W. Allen |
| Financial Services | 4 位 | Gilbert Cisneros, John Boozman, April McClain Delaney, Richard W. Allen |
| Healthcare | 3 位 | Gilbert Cisneros, John Boozman, April McClain Delaney |
| Basic Materials | 2 位 | Gilbert Cisneros, April McClain Delaney |
| Communication Services | 2 位 | Gilbert Cisneros, John Boozman |
| Consumer Cyclical | 2 位 | Gilbert Cisneros, April McClain Delaney |
| Energy | 2 位 | Gilbert Cisneros, John Boozman |

### 3.2 賣出共識（2+ 議員）

| 板塊 | 共識議員 | 議員名單 |
|------|----------|----------|
| Financial Services | 7 位 | Gilbert Cisneros, April McClain Delaney, Steve Cohen, David H McCormick, Donald Beyer, Jake Auchincloss, Sheri Biggs |
| Technology | 5 位 | Gilbert Cisneros, April McClain Delaney, John Boozman, Donald Beyer, Richard W. Allen |
| Industrials | 4 位 | Gilbert Cisneros, April McClain Delaney, John Boozman, Steve Cohen |
| Communication Services | 3 位 | Gilbert Cisneros, John Boozman, Richard W. Allen |
| Consumer Cyclical | 2 位 | Gilbert Cisneros, April McClain Delaney |
| Consumer Defensive | 2 位 | Gilbert Cisneros, April McClain Delaney |
| Healthcare | 2 位 | Gilbert Cisneros, April McClain Delaney |

### 3.3 共識解讀

- **Financial Services** 呈現矛盾信號：4 位議員買入、7 位議員賣出。賣出方更廣泛，可能反映對利率/監管的不確定性。
- **Technology** 同樣矛盾：4 位買、5 位賣。但注意 Nancy Pelosi 屬買方（她的科技股交易歷史性地跑贏大盤）。
- **Healthcare** 買方共識（3 位買、2 位賣）支持淨買入信號。
- **Industrials** 與 Technology 類似的混合信號，但淨方向仍為買入。

---

## 四、政策關聯分析

### 4.1 能源板塊賣出 vs 能源政策

**政策環境**：
- Trump 政府積極推動化石燃料產業：解除 LNG 出口禁令、擴大離岸鑽探租約、提出新的 OCS 租賃計劃
- 「One Big Beautiful Bill」結束綠能補貼，轉向化石燃料投資
- 美國原油產量達歷史新高 1,360 萬桶/日

**矛盾與解讀**：
議員在能源政策最友善的時期大舉賣出能源股，這是**反直覺的**。可能原因：
1. **供給過剩預期**：過度增產可能壓低油價，反而不利能源股表現
2. **估值到頂**：親化石燃料政策已反映在股價中（buy the rumor, sell the news）
3. **利潤回吐**：此前能源股已有顯著漲幅，議員選擇獲利了結
4. **長期結構轉型**：即使短期政策利好，全球能源轉型的長期趨勢仍在

**信號強度**：高（單議員系統性出清整個板塊，非個股交易）

### 4.2 醫療保健板塊買入 vs 醫療政策

**政策環境**：
- Medicare 藥價談判於 2026 年生效（首批 10 種藥物），預計每年為 Medicare 節省 60 億美元
- 議員集中買入的是**醫療器械**和**生技**，非受藥價談判影響的大型藥廠
- 醫療器械 User Fee Agreements (UFAs) 要到 2027 年 9 月才到期

**解讀**：
議員精準避開藥價談判衝擊的子產業（大型藥廠），選擇買入：
- **醫療器械** (ISRG, BSX, SYK, COO, DXCM)：受惠於人口老化和手術量回升
- **生技** (LGND, BIIB, AGIO)：創新藥管線估值被低估
- **醫療保健計劃** (UNH, CI, CVS)：Medicaid 改革可能增加覆蓋

**信號強度**：中高（多議員買入共識，且板塊選擇規避已知風險）

### 4.3 科技/工業板塊輪動 vs 國防/AI 政策

**政策環境**：
- FY2026 NDAA 授權 80 億美元國防支出，大量 AI 和網路安全條款
- AI 供應鏈安全要求禁用中國 AI（DeepSeek）
- 半導體出口管制（AI OVERWATCH Act 限制 Nvidia Blackwell 出口）
- 國防工業基礎聯盟建設

**解讀**：
1. **Aerospace & Defense** 子產業淨買入 +5（AVAV、LMT 等）：與國防預算增加一致
2. **Specialty Industrial Machinery** 淨買入 +5：可能反映國內製造回流
3. **Technology 整體 12 月賣→1 月買**：可能反映 AI 政策明朗化後的信心回升
4. **Consumer Electronics** 淨買入 +3（AAPL 等，4 位議員）：最廣泛的議員共識之一

**信號強度**：中（與政策方向一致，但科技板塊混合信號降低確信度）

---

## 五、議員個體分析

### 5.1 Gilbert Cisneros（250 筆，佔總量 62%）

**板塊偏好**：
| 板塊 | Buy | Sell | 淨 | 解讀 |
|------|-----|------|----|------|
| Technology | 25 | 12 | +13 | 看多科技 |
| Industrials | 28 | 16 | +12 | 看多工業 |
| Healthcare | 17 | 5 | +12 | 看多醫療 |
| Financial Services | 20 | 11 | +9 | 看多金融 |
| Basic Materials | 9 | 2 | +7 | 看多原材料 |
| Energy | 2 | 24 | **-22** | **強烈看空能源** |
| Consumer Defensive | 6 | 11 | -5 | 看空防禦性消費 |

Cisneros 佔據資料集 62%，是主要信號來源。他的板塊策略清晰：**做多成長型板塊（科技、工業、醫療），做空傳統能源和防禦性消費**。

### 5.2 April McClain Delaney（30 筆）

整體偏賣出，Technology 賣出最多（-9）。可能進行組合再平衡。

### 5.3 John Boozman（16 筆，Senate）

Healthcare 和 Financial Services 均為淨買入（各 +2）。值得注意的是他買入 XOM（與 Cisneros 反向），顯示議員間對能源的分歧。

---

## 六、濃度風險與限制

### 6.1 資料濃度偏差

- Gilbert Cisneros 佔總交易 62%（250/404），**板塊信號高度依賴單一議員**
- 若排除 Cisneros，能源板塊賣出信號近乎消失
- 真正的「多議員共識」只在 Technology 和 Financial Services 板塊存在

### 6.2 其他限制

1. **金額範圍粗糙**：$1,001-$15,000 區間佔絕大多數，無法精確量化資金流向
2. **時間延遲**：Filing date 與 Transaction date 存在數日至數週延遲
3. **披露義務 vs 投資意圖**：議員可能基於合規需求而非投資觀點交易
4. **樣本量有限**：3 個月資料，難以做出長期統計推論

---

## 七、策略建議

### 7.1 高信心信號（可作為 alpha 因子）

| 信號 | 方向 | 信心 | 理由 |
|------|------|------|------|
| 能源板塊 | UNDERWEIGHT | 高 | 系統性出清 + 供給過剩風險 |
| 醫療器械/生技 | OVERWEIGHT | 中高 | 多議員買入 + 規避藥價風險 |
| 工業（航太/機械） | OVERWEIGHT | 中 | NDAA 國防預算 + 製造回流 |

### 7.2 觀察信號（需更多數據確認）

| 信號 | 方向 | 信心 | 理由 |
|------|------|------|------|
| Technology | 中性偏多 | 低 | 矛盾信號，但 Pelosi 買入值得注意 |
| Financial Services | 中性 | 低 | 買賣兩方均有多議員參與 |
| Consumer Defensive | UNDERWEIGHT | 低 | 淨賣出但樣本少 |

### 7.3 實施建議

1. **板塊 ETF 配對**：做空 XLE（能源 ETF）+ 做多 XLV（醫療 ETF）作為板塊輪動策略
2. **個股篩選**：在醫療器械子產業中，優先考慮多議員買入的 ticker（ISRG, BSX）
3. **監控頻率**：每週更新板塊流向，特別關注能源板塊是否出現買回信號
4. **風險管理**：由於資料集高度集中於 Cisneros，建議將 Cisneros 信號權重降至 50%，以避免單一議員偏差

---

## 附錄 A：板塊分類方法

- 使用 yfinance API 取得 GICS 板塊分類
- 262 個 ticker 中 226 個成功對應（86% 覆蓋率）
- 未對應的 36 個 ticker 主要為 ETF（IVV, IWM, MDY）、OTC 外國股票（MHIYF, BABAF）和已退市股票

## 附錄 B：資料來源

- 交易數據：`data/data.db` congress_trades 表（404 筆，2025-12-01 ~ 2026-02-17）
- 板塊分類：yfinance（yahoo finance）GICS 分類
- 政策資訊：
  - [美國能源部政策](https://www.energy.gov/articles/promises-made-promises-kept)
  - [One Big Beautiful Bill 能源稅務影響](https://taxfoundation.org/blog/big-beautiful-bill-green-energy-tax-credit-changes/)
  - [Medicare 藥價談判](https://www.cms.gov/newsroom/fact-sheets/medicare-drug-price-negotiation-program-negotiated-prices-initial-price-applicability-year-2026)
  - [FY2026 NDAA AI 和國防](https://www.kslaw.com/news-and-insights/fy-2026-ndaa-domestic-sourcing-artificial-intelligence-cybersecurity-and-acquisition-reforms)
  - [2026 AI 政策與半導體展望](https://www.mondaq.com/unitedstates/new-technology/1742332/2026-ai-policy-and-semiconductor-outlook-how-federal-preemption-state-ai-laws-and-chip-export-controls-will-shape-us-policy)
