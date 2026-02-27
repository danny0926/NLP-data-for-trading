# RB-003: 國會交易板塊輪動信號研究

**狀態**: Draft → POC Complete
**研究員**: Quantitative Research Analyst
**日期**: 2026-02-27
**資料範圍**: 2025-12-01 ~ 2026-02-17（404 筆交易，262 個 ticker，226 個成功對應 GICS 板塊）

---

## 摘要

本研究探討美國國會議員交易揭露資料中是否存在可預測板塊輪動的集體信號。我們對 `congress_trades` 資料庫中 404 筆交易記錄進行板塊分類，以 yfinance 取得 GICS 板塊歸屬，計算各板塊淨買入比率（Net Buy Ratio, NBR），並分析其時序變化。

**核心發現**：
1. **能源板塊（Energy）** 呈現系統性賣出信號（NBR=11.1%，淨賣出 21 筆），主要來自 Gilbert Cisneros 於 2026-01-09 單日清倉 16 檔能源股。
2. **醫療保健板塊（Healthcare）** 持續淨買入（NBR=73.3%，淨買入 14 筆），3 位議員跨黨派共識買入醫療器械與生技股。
3. **基礎材料板塊（Basic Materials）** 最高 NBR（83.3%），但樣本量有限（12 筆）。
4. **資料集存在嚴重濃度偏差**：單一議員（Gilbert Cisneros）佔總交易量 62%，削弱了「集體信號」的統計效力。

**結論**：板塊層級信號作為 alpha 因子具有初步可行性，但需解決濃度偏差、申報延遲（中位數 49 天）、以及樣本量不足等問題後方可投入生產。

---

## 一、研究假說

### 1.1 主假說（H1）

> 國會議員在特定板塊的集體淨買入/淨賣出行為，能夠預測該板塊未來 30-90 天的相對報酬表現。

**理論基礎**：國會議員因其立法角色，在政策制定過程中獲取非公開資訊（如預算分配、監管變動、合約授予），這些資訊對特定產業的影響在公開市場反映之前，可能已體現在議員的交易行為中。當多位議員同時增持或減持某一板塊時，該板塊信號的資訊含量應高於個股層級的雜訊。

### 1.2 子假說

- **H1a**：NBR > 65% 的板塊在隨後 30 天表現優於 S&P 500 等權指數。
- **H1b**：NBR < 35% 的板塊在隨後 30 天表現劣於 S&P 500 等權指數。
- **H1c**：多位議員（≥ 3）同方向交易的板塊信號，優於單一議員主導的板塊信號。
- **H1d**：金額加權後的板塊信號優於等權計數信號。

### 1.3 虛無假說（H0）

> 國會議員的板塊層級交易行為不包含超額報酬預測能力，其觀察到的板塊偏好可歸因於隨機分布、資產再平衡、或已公開資訊的延遲反映。

---

## 二、文獻回顧

### 2.1 國會議員知情交易

Ziobrowski et al. (2004) 於 *The Journal of Financial and Quantitative Analysis* 發表的研究發現，美國參議員的股票投資組合在 1993-1998 年間年化超額報酬約 12%，顯著優於市場基準。後續研究 Ziobrowski et al. (2011) 將分析擴展至眾議員，發現類似但較弱的效應（年化超額報酬約 6%）。

Eggers & Hainmueller (2013) 使用更嚴格的方法論（包含對照組與時間固定效應），發現國會議員的超額報酬在控制產業效應後大幅縮小，暗示議員的優勢可能部分來自**板塊層級的資訊優勢**而非個股選擇。

### 2.2 政治連結與產業知識

**委員會效應**：Karadas (2019) 發現，議員在其所屬委員會管轄產業中的交易表現顯著優於其他產業。例如，國防委員會成員在國防板塊的交易具有預測力。這支持了「政策資訊外溢」假說——議員透過委員會工作獲得板塊層級的前瞻性資訊。

**STOCK Act 影響**：2012 年 STOCK Act 要求議員在 45 天內揭露交易。Huang & Xuan (2021) 發現法案通過後議員交易的超額報酬下降但未消失，暗示即使在強制揭露制度下，資訊不對稱仍然存在。

### 2.3 內部人交易與板塊輪動

Cohen, Malloy & Pomorski (2012) 區分「例行性」與「機會性」內部人交易，發現後者具有顯著的預測能力。將此框架應用於國會交易：系統性的板塊出清（如本研究中能源板塊的集中賣出）更接近「機會性」交易特徵，而小額分散的交易可能僅反映例行性再平衡。

### 2.4 板塊動能與輪動策略

Moskowitz & Grinblatt (1999) 證明板塊動能效應獨立於個股動能存在，且板塊動能策略在控制交易成本後仍具經濟意義。若國會交易信號能預測板塊輪動，結合板塊動能策略可能產生複合 alpha。

### 2.5 文獻缺口

現有研究主要聚焦於**個股層級**的議員交易表現，較少從**板塊集體信號**的角度進行分析。此外，多數研究使用年度或季度持倉數據，本研究利用逐筆交易揭露資料（STOCK Act 後的 PTR），時間顆粒度更細，為板塊輪動信號的研究提供了新視角。

---

## 三、研究方法

### 3.1 資料來源與預處理

#### 3.1.1 交易資料

- **來源**：`data/data.db` 中的 `congress_trades` 表
- **時間範圍**：2025-12-01 至 2026-02-17
- **總筆數**：404 筆
- **有效 ticker**：353 筆（87.4%），51 筆無 ticker（主要為債券、共同基金等非股票資產）
- **議員分布**：House 347 筆、Senate 57 筆
- **交易方向**：Buy 218 筆、Sale 185 筆、Exchange 1 筆

#### 3.1.2 板塊分類

使用 `yfinance` Python 套件取得每個 ticker 的 GICS 板塊（Sector）與產業（Industry）分類：

```python
import yfinance as yf
info = yf.Ticker(ticker).info
sector = info.get('sector')
industry = info.get('industry')
```

- **成功分類**：226 / 262 個 ticker（86.3%）
- **分類失敗**：36 個 ticker，主要為：
  - ETF / 指數基金：IVV, IWM, MDY, MBB, JMBS, FTGC, GIGB, TBLL, TPYP, VNQI, SLV, PALL, PPLT
  - OTC 外國股票：MHIYF, MBJBF, VSNNT, SWSD
  - 已退市/代碼變更：K (Kellanova → MARS 併購), CS (Credit Suisse → UBS), SQ (→ XYZ)
  - 其他：EIPI, HN, OT, RFD, SED, KRSOX, RNWGX, LVY, LITP, RHM GR

#### 3.1.3 可分類交易覆蓋率

在 353 筆有 ticker 的交易中，314 筆（89.0%）成功對應板塊分類，涵蓋 11 個 GICS 板塊。

### 3.2 指標定義

#### 3.2.1 淨買入比率（Net Buy Ratio, NBR）

$$NBR_{s,t} = \frac{N_{buy,s,t}}{N_{buy,s,t} + N_{sell,s,t}}$$

其中 $s$ 為板塊，$t$ 為時間期間，$N_{buy}$ 和 $N_{sell}$ 分別為買入和賣出筆數。

- NBR > 0.65：強買入信號
- 0.50 < NBR ≤ 0.65：弱買入信號
- 0.35 ≤ NBR ≤ 0.50：中性
- NBR < 0.35：強賣出信號

#### 3.2.2 金額加權淨流量（Amount-Weighted Net Flow）

由於 STOCK Act 僅要求揭露金額範圍（而非精確金額），我們使用各範圍的中位數作為估計值：

| 金額範圍 | 中位數估計 |
|----------|-----------|
| $1,001 - $15,000 | $8,000 |
| $15,001 - $50,000 | $32,500 |
| $50,001 - $100,000 | $75,000 |
| $100,001 - $250,000 | $175,000 |
| $250,001 - $500,000 | $375,000 |
| $1,000,001 - $5,000,000 | $3,000,000 |

$$NetFlow_{s} = \sum_{i \in Buy_s} AmtMid_i - \sum_{j \in Sell_s} AmtMid_j$$

#### 3.2.3 議員共識度（Consensus Score）

$$Consensus_{s,dir} = \frac{|\{p : p \text{ 在板塊 } s \text{ 有方向 } dir \text{ 的交易}\}|}{|\{p : p \text{ 在板塊 } s \text{ 有任何交易}\}|}$$

多議員同方向交易的板塊信號權重更高。

### 3.3 時間序列分析

將資料分為月度期間（2025-12、2026-01、2026-02），比較各板塊 NBR 的時序變化：

$$\Delta NBR_{s} = NBR_{s,t} - NBR_{s,t-1}$$

正向 $\Delta NBR$ 表示板塊從賣出轉向買入（看多輪動），負向表示反向。

### 3.4 濃度調整

為處理單一議員主導的偏差，計算排除最大交易者（Cisneros）後的板塊信號：

$$NBR_{s,adj} = \frac{N_{buy,s} - N_{buy,s,Cisneros}}{(N_{buy,s} - N_{buy,s,Cisneros}) + (N_{sell,s} - N_{sell,s,Cisneros})}$$

---

## 四、POC 分析結果

### 4.1 全期間板塊概覽

以下為資料庫實際查詢結果（`data/data.db`，查詢日期 2026-02-27）：

| 板塊 | Buy | Sell | 合計 | NBR | 淨方向 | 涉及 Ticker 數 | 信號等級 |
|------|-----|------|------|-----|--------|----------------|----------|
| Basic Materials | 10 | 2 | 12 | **83.3%** | +8 | 11 | 強買 |
| Healthcare | 22 | 8 | 30 | **73.3%** | +14 | 24 | 強買 |
| Real Estate | 12 | 8 | 20 | 60.0% | +4 | 17 | 弱買 |
| Industrials | 32 | 23 | 55 | 58.2% | +9 | 39 | 弱買 |
| Financial Services | 25 | 19 | 44 | 56.8% | +6 | 33 | 弱買 |
| Technology | 28 | 27 | 55 | 50.9% | +1 | 37 | 中性 |
| Communication Services | 9 | 9 | 18 | 50.0% | 0 | 12 | 中性 |
| Consumer Cyclical | 16 | 18 | 34 | 47.1% | -2 | 20 | 中性 |
| Consumer Defensive | 6 | 12 | 18 | **33.3%** | -6 | 13 | 強賣 |
| Energy | 3 | 24 | 27 | **11.1%** | -21 | 19 | 強賣 |
| Utilities | 0 | 1 | 1 | 0.0% | -1 | 1 | N/A |

**分類覆蓋率**：314 / 353 筆有 ticker 交易成功分類（89.0%）
**整體 NBR**：51.9%（Buy=163, Sell=151），略偏買入。

### 4.2 金額加權淨流量分析

使用金額範圍中位數估計各板塊的資金流向：

| 板塊 | 估計買入金額 | 估計賣出金額 | 淨流量 | 方向 |
|------|-------------|-------------|--------|------|
| Healthcare | $200,500 | $88,500 | **+$112,000** | 流入 |
| Industrials | $305,000 | $257,500 | +$47,500 | 流入 |
| Basic Materials | $129,000 | $83,000 | +$46,000 | 流入 |
| Real Estate | $96,000 | $88,500 | +$7,500 | 流入 |
| Comm. Services | $72,000 | $72,000 | $0 | 平衡 |
| Consumer Cyclical | $128,000 | $168,500 | -$40,500 | 流出 |
| Utilities | $0 | $75,000 | -$75,000 | 流出 |
| Consumer Defensive | $48,000 | $163,000 | -$115,000 | 流出 |
| Technology | $224,000 | $472,500 | **-$248,500** | 流出 |
| Energy | $24,000 | $357,000 | **-$333,000** | 流出 |
| Financial Services | $224,500 | $3,333,500 | **-$3,109,000** | 大量流出 |

**關鍵發現**：金額加權後，Financial Services 板塊因 David McCormick 的 $1M+ Goldman Sachs 賣出而成為最大淨流出板塊。這揭示了筆數計數（NBR=56.8%，弱買入）與金額加權信號之間的重大分歧——**小額交易方向看多，但大額交易方向看空**。

### 4.3 月度板塊輪動趨勢

| 板塊 | 2025-12 NBR | 2026-01 NBR | ΔNBR | 輪動方向 |
|------|-------------|-------------|------|----------|
| Technology | 33.3% (9B/18S) | 66.7% (18B/9S) | **+33.4pp** | 急速轉多 |
| Communication Services | 12.5% (1B/7S) | 77.8% (7B/2S) | **+65.3pp** | 急速轉多 |
| Financial Services | 33.3% (5B/10S) | 70.4% (19B/8S) | **+37.1pp** | 急速轉多 |
| Industrials | 42.3% (11B/15S) | 71.4% (20B/8S) | **+29.1pp** | 轉多 |
| Real Estate | 44.4% (4B/5S) | 72.7% (8B/3S) | +28.3pp | 轉多 |
| Basic Materials | 100% (2B/0S) | 80.0% (8B/2S) | -20.0pp | 維持高位 |
| Healthcare | 72.2% (13B/5S) | 75.0% (9B/3S) | +2.8pp | 穩定看多 |
| Consumer Cyclical | 33.3% (5B/10S) | 52.9% (9B/8S) | +19.6pp | 轉中性 |
| Consumer Defensive | 40.0% (4B/6S) | 14.3% (1B/6S) | **-25.7pp** | 轉空 |
| Energy | 28.6% (2B/5S) | 5.0% (1B/19S) | **-23.6pp** | 加速賣出 |

**輪動模式摘要**：
- 12月→1月最大正向輪動：Communication Services (+65pp)、Technology (+33pp)、Financial Services (+37pp)
- 12月→1月最大負向輪動：Consumer Defensive (-26pp)、Energy (-24pp)
- Healthcare 跨期穩定看多（72%→75%）

### 4.4 濃度偏差分析

Gilbert Cisneros 佔總交易 250/404 筆（62%），對板塊信號影響巨大：

| 板塊 | Cisneros NBR | 其他議員 NBR | 信號一致性 |
|------|-------------|-------------|-----------|
| Basic Materials | 82% (9B/2S) | 100% (1B/0S) | 一致 |
| Healthcare | 77% (17B/5S) | 62% (5B/3S) | 一致 |
| Industrials | 64% (28B/16S) | 36% (4B/7S) | **矛盾** |
| Financial Services | 65% (20B/11S) | 38% (5B/8S) | **矛盾** |
| Technology | 68% (25B/12S) | 17% (3B/15S) | **矛盾** |
| Energy | 8% (2B/24S) | 100% (1B/0S) | **矛盾** |
| Consumer Cyclical | 48% (14B/15S) | 40% (2B/3S) | 一致（偏空）|
| Consumer Defensive | 35% (6B/11S) | 0% (0B/1S) | 一致（偏空）|
| Communication Services | 54% (7B/6S) | 40% (2B/3S) | 一致（偏空）|

**關鍵警示**：
- **Industrials / Financial Services / Technology**：Cisneros 看多，但其他議員整體看空。板塊信號的方向性**完全取決於是否納入 Cisneros 的交易**。
- **Energy**：Cisneros 強烈看空（NBR=8%），但 John Boozman 買入 XOM。排除 Cisneros 後賣出信號消失。
- 僅 **Healthcare** 與 **Basic Materials** 在排除 Cisneros 後仍維持買入方向，具有較高的信號可靠性。

### 4.5 申報延遲分析

| 統計指標 | 天數 |
|----------|------|
| 平均延遲 | 52.3 天 |
| 中位數延遲 | 49 天 |
| 最短延遲 | 10 天 |
| 最長延遲 | 87 天 |

**影響**：中位數 49 天的延遲意味著，即使議員在交易時擁有板塊前瞻資訊，市場可能在揭露前已部分反映該資訊。若板塊輪動的資訊半衰期短於 49 天，則本信號的可操作視窗在揭露後可能已大幅縮小。這是本策略最大的結構性挑戰。

### 4.6 子產業層級分析（前 15 大）

| 子產業 | 板塊 | Buy | Sell | NBR | 信號 |
|--------|------|-----|------|-----|------|
| Oil & Gas E&P | Energy | 0 | 10 | **0.0%** | 極強賣 |
| Aerospace & Defense | Industrials | 9 | 4 | 69.2% | 強買 |
| Specialty Industrial Machinery | Industrials | 8 | 3 | 72.7% | 強買 |
| Internet Retail | Consumer Cyclical | 8 | 4 | 66.7% | 強買 |
| Biotechnology | Healthcare | 5 | 2 | 71.4% | 強買 |
| Drug Mfg. - General | Healthcare | 4 | 1 | 80.0% | 強買 |
| Insurance Brokers | Financial Services | 4 | 1 | 80.0% | 強買 |
| Consumer Electronics | Technology | 4 | 1 | 80.0% | 強買 |
| Capital Markets | Financial Services | 4 | 7 | 36.4% | 強賣 |
| Software - Infrastructure | Technology | 4 | 6 | 40.0% | 賣出 |
| Packaged Foods | Consumer Defensive | 3 | 5 | 37.5% | 賣出 |
| Engineering & Construction | Industrials | 2 | 5 | 28.6% | 強賣 |
| Railroads | Industrials | 2 | 4 | 33.3% | 強賣 |
| Oil & Gas Integrated | Energy | 1 | 4 | 20.0% | 極強賣 |
| Semiconductors | Technology | 7 | 7 | 50.0% | 中性 |

**子產業洞察**：
- 能源板塊內部方向一致（E&P、Integrated、Midstream 全面看空），屬於**系統性板塊出清**。
- 工業板塊內部分化：Aerospace & Defense 看多 vs Engineering & Construction、Railroads 看空。
- 科技板塊內部分化：Consumer Electronics 強買 vs Software-Infrastructure 賣出，Semiconductors 中性。

### 4.7 能源板塊賣出事件深度分析

2026-01-09，議員 Gilbert Cisneros 於單日執行 16 筆能源股賣出交易，涵蓋能源板塊所有主要子產業：

| Ticker | 公司名稱 | 子產業 | 金額範圍 |
|--------|---------|--------|----------|
| XOM | Exxon Mobil | Oil & Gas Integrated | $50,001 - $100,000 |
| CVX | Chevron (×2 筆) | Oil & Gas Integrated | $15,001-$50,000 + $1,001-$15,000 |
| COP | ConocoPhillips | Oil & Gas E&P | $1,001 - $15,000 |
| EOG | EOG Resources | Oil & Gas E&P | $1,001 - $15,000 |
| MTDR | Matador Resources | Oil & Gas E&P | $15,001 - $50,000 |
| MGY | Magnolia Oil & Gas | Oil & Gas E&P | $15,001 - $50,000 |
| CHRD | Chord Energy | Oil & Gas E&P | $1,001 - $15,000 |
| GPOR | Gulfport Energy | Oil & Gas E&P | $1,001 - $15,000 |
| APA | APA Corp | Oil & Gas E&P | $1,001 - $15,000 |
| HAL | Halliburton | Oil & Gas Equipment | $1,001 - $15,000 |
| BKR | Baker Hughes | Oil & Gas Equipment | $1,001 - $15,000 |
| WMB | Williams Companies | Oil & Gas Midstream | $1,001 - $15,000 |
| TRGP | Targa Resources | Oil & Gas Midstream | $1,001 - $15,000 |
| OKE | ONEOK | Oil & Gas Midstream | $1,001 - $15,000 |
| KMI | Kinder Morgan | Oil & Gas Midstream | $1,001 - $15,000 |
| VLO | Valero Energy | Oil & Gas Refining | $1,001 - $15,000 |

**特徵**：覆蓋 E&P、Integrated、Equipment、Midstream、Refining 全子產業鏈。此為非選擇性的板塊出清（non-selective sector liquidation），而非個股層級的部位調整。此模式與 Cohen et al. (2012) 定義的「機會性交易」高度一致，暗示可能存在板塊層級的前瞻資訊。

### 4.8 議員交易量排名

| 議員 | 總交易數 | Buy | Sell | 最活躍板塊 | 院別 |
|------|----------|-----|------|-----------|------|
| Gilbert Cisneros | 250 | 140 | 110 | Industrials | House |
| April McClain Delaney | 30 | 9 | 21 | Technology（賣出）| House |
| John Boozman | 16 | 10 | 6 | Communication Services | Senate |
| Steve Cohen | 6 | 1 | 5 | Financial Services（賣出）| House |
| Richard W. Allen | 5 | 2 | 3 | Communication Services | House |
| Donald S. Beyer Jr. | 3 | 0 | 3 | Technology（賣出）| House |
| Nancy Pelosi | 1 | 1 | 0 | Technology（買入）| House |
| David H. McCormick | 1 | 0 | 1 | Financial Services（$1M+）| Senate |

---

## 五、政策關聯性分析

### 5.1 能源板塊賣出 vs 當前能源政策環境

**政策背景**（2025Q4-2026Q1）：
- Trump 行政命令解除 LNG 出口暫停令，擴大離岸鑽探租約
- 美國原油日產量達歷史新高 1,360 萬桶
- 「One Big Beautiful Bill」結束綠能補貼，轉向化石燃料投資

**反直覺觀察**：議員在能源政策最友善的時期大舉拋售能源股。可能解讀：
1. **供給過剩預期**：政策鼓勵增產可能導致供給過剩、壓低油價
2. **Buy the Rumor, Sell the News**：親化石燃料政策已充分反映在股價中
3. **長期結構風險認知**：即使短期利好，全球能源轉型趨勢不可逆
4. **單純投組調整**：Cisneros 可能出於資產配置目的而非資訊交易

### 5.2 醫療保健板塊買入 vs 醫療政策環境

**政策背景**：
- Medicare 藥價談判 2026 年生效（首批 10 種藥物），年省 $60 億
- 醫療器械 User Fee Agreements (UFAs) 到 2027 年 9 月方到期

**觀察**：議員精準**避開**受藥價談判衝擊的大型藥廠，選擇買入：
- 醫療器械（ISRG、BSX、SYK、COO、DXCM）
- 生技（LGND、BIIB、AGIO）
- 保健計劃（UNH、CI、CVS）

此選擇模式暗示議員可能對醫療政策的細分影響有較深理解。

### 5.3 工業/國防板塊買入 vs NDAA

**政策背景**：
- FY2026 NDAA 授權 $800 億國防支出，含大量 AI 與網路安全條款
- AI 供應鏈安全法案禁用中國 AI 技術

**觀察**：Aerospace & Defense 子產業 NBR=69.2%（9B/4S），與國防預算增加方向一致。

---

## 六、實施計畫：整合板塊信號至儀表板

### 6.1 Phase 1：資料基礎設施（1-2 週）

**6.1.1 新增資料庫欄位**

在 `congress_trades` 表新增板塊分類欄位：

```sql
ALTER TABLE congress_trades ADD COLUMN sector TEXT;
ALTER TABLE congress_trades ADD COLUMN industry TEXT;
```

**6.1.2 板塊分類服務**

在 `src/etl/` 中新增 `sector_classifier.py`：

```python
import yfinance as yf
import json
import os

CACHE_FILE = 'data/ticker_sectors.json'

class SectorClassifier:
    def __init__(self):
        self._cache = self._load_cache()

    def _load_cache(self):
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, 'r') as f:
                return json.load(f).get('sector_map', {})
        return {}

    def classify(self, ticker: str) -> dict:
        if ticker in self._cache:
            return self._cache[ticker]
        try:
            info = yf.Ticker(ticker).info
            result = {
                'sector': info.get('sector'),
                'industry': info.get('industry')
            }
            if result['sector']:
                self._cache[ticker] = result
                self._save_cache()
            return result
        except Exception:
            return {'sector': None, 'industry': None}

    def _save_cache(self):
        with open(CACHE_FILE, 'w') as f:
            json.dump({'sector_map': self._cache}, f, ensure_ascii=False, indent=2)
```

**6.1.3 ETL 整合**

在 `loader.py` 的寫入流程中，自動為每筆交易填入 sector/industry：

```python
from src.etl.sector_classifier import SectorClassifier

classifier = SectorClassifier()

def enrich_trade(trade):
    if trade.ticker:
        info = classifier.classify(trade.ticker)
        trade.sector = info.get('sector')
        trade.industry = info.get('industry')
    return trade
```

### 6.2 Phase 2：信號計算引擎（2-3 週）

**6.2.1 新增 `sector_signal.py`**

```python
def calculate_sector_signals(conn, lookback_days=30):
    """計算各板塊的 NBR 與淨流量信號"""
    cursor = conn.cursor()
    cursor.execute('''
        SELECT sector,
               SUM(CASE WHEN transaction_type = 'Buy' THEN 1 ELSE 0 END) as buys,
               SUM(CASE WHEN transaction_type = 'Sale' THEN 1 ELSE 0 END) as sells,
               COUNT(DISTINCT politician_name) as n_politicians
        FROM congress_trades
        WHERE sector IS NOT NULL
          AND transaction_date >= date('now', ?)
        GROUP BY sector
    ''', (f'-{lookback_days} days',))
    # ... 計算 NBR、淨流量、信號等級
```

**6.2.2 新增 `sector_signals` 資料表**

```sql
CREATE TABLE IF NOT EXISTS sector_signals (
    id TEXT PRIMARY KEY,
    calculation_date DATE NOT NULL,
    lookback_days INTEGER NOT NULL,
    sector TEXT NOT NULL,
    buy_count INTEGER,
    sell_count INTEGER,
    nbr REAL,
    net_flow_estimate REAL,
    n_politicians INTEGER,
    signal_grade TEXT,  -- 'STRONG_BUY', 'BUY', 'NEUTRAL', 'SELL', 'STRONG_SELL'
    concentration_risk REAL,  -- HHI of politician contribution
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 6.3 Phase 3：報告整合（1 週）

在 `generate_report.py` 中新增板塊輪動報告模組：

1. 每日/每週計算各板塊 NBR
2. 標記 NBR 變動超過 ±15pp 的板塊為「輪動信號」
3. 在報告中生成板塊熱力圖（文字版或 HTML 版）
4. 與 AI Discovery 信號交叉驗證

### 6.4 Phase 4：回測與驗證（2-4 週）

1. 取得歷史板塊表現數據（板塊 ETF：XLE, XLV, XLI, XLK 等）
2. 計算 NBR 信號發出後 30/60/90 天的板塊相對報酬
3. 統計檢定：Wilcoxon rank-sum test 比較高 NBR 板塊 vs 低 NBR 板塊的報酬差異
4. 建立訊號品質追蹤機制

---

## 七、風險與限制

### 7.1 統計風險

| 風險 | 嚴重性 | 緩解措施 |
|------|--------|----------|
| **濃度偏差**：Cisneros 佔 62%，板塊信號可能反映個人偏好而非集體智慧 | 高 | 計算 HHI 濃度指標；排除最大交易者後的調整 NBR；要求 ≥3 位議員共識 |
| **樣本量不足**：僅 3 個月、314 筆可分類交易 | 高 | 持續累積資料至少 12 個月後再做正式統計推論 |
| **多重比較問題**：同時檢定 11 個板塊可能產生偽陽性 | 中 | 使用 Bonferroni 校正或 FDR 控制 |
| **存活偏差**：僅觀察已揭露的交易，未揭露或延遲揭露的交易不在分析中 | 中 | 追蹤揭露合規性，標記異常延遲的議員 |

### 7.2 結構性風險

| 風險 | 嚴重性 | 緩解措施 |
|------|--------|----------|
| **申報延遲**：中位數 49 天，最長 87 天。信號到達時市場可能已反映 | 高 | 聚焦長期（季度）板塊趨勢而非短期交易；研究「提前揭露者」的信號品質 |
| **金額精度低**：僅有範圍資料，$1K-$15K 佔 81%（326/404 筆），難以區分信念強度 | 中 | 聚焦大額交易（$50K+）作為高信念信號 |
| **政策資訊外溢的時間結構**：議員獲取政策資訊的時點未知 | 中 | 分析委員會成員的板塊交易是否優於非委員會成員 |

### 7.3 操作風險

| 風險 | 嚴重性 | 緩解措施 |
|------|--------|----------|
| **yfinance 分類不穩定**：API 可能變更或回傳空值 | 低 | 建立本地快取（已實施）；定期更新分類 |
| **合規風險**：基於國會交易的投資策略可能面臨監管審查 | 中 | 僅使用公開揭露資料；不做前端搶跑（front-running） |
| **STOCK Act 修法風險**：若揭露制度改變，資料源可能中斷 | 低 | 維護多資料源（Senate EFD + Capitol Trades + House PDF） |

### 7.4 信號品質限制

1. **非獨立觀測**：同一議員的多筆交易不是獨立事件，不能簡單加總。250 筆 Cisneros 交易可能反映同一決策（「賣掉所有能源股」），而非 250 個獨立信號。
2. **意圖不可觀測**：交易動機可能為稅務規劃、離婚、流動性需求等，與投資觀點無關。
3. **反向因果**：議員可能在板塊已下跌後才賣出（追隨者而非領先者），而非預測下跌。
4. **信號衰減**：隨著越來越多市場參與者關注國會交易資料，信號的 alpha 可能逐漸被套利殆盡。

---

## 八、結論與建議

### 8.1 研究結論

1. **板塊層級的國會交易信號確實存在非隨機分布模式**：能源板塊的系統性出清和醫療保健板塊的持續買入不太可能是純粹隨機行為。
2. **濃度偏差是最大威脅**：排除 Cisneros 後，多數板塊信號方向改變甚至消失。僅 Healthcare 與 Basic Materials 在調整後仍維持買入方向。
3. **申報延遲嚴重限制短期可操作性**：中位數 49 天延遲使得信號更適合用於中長期（季度）板塊配置，而非短期交易。
4. **子產業層級提供更精細的信號**：例如 Oil & Gas E&P 的 100% 賣出比板塊層級更具資訊量。

### 8.2 可操作建議

| 信號 | 方向 | 信心等級 | 建議操作 | 前提條件 |
|------|------|----------|----------|----------|
| Healthcare（醫療器械/生技）| OVERWEIGHT | **中高** | 增持 XLV 或個股（ISRG, BSX）| 多議員共識持續 |
| Energy（全子產業鏈）| UNDERWEIGHT | **中**（單一議員主導）| 觀察，待更多議員確認 | Cisneros 外有確認信號 |
| Basic Materials | OVERWEIGHT | **低**（樣本量不足）| 觀察 | 累積至 ≥20 筆交易 |
| Technology | NEUTRAL | **低**（矛盾信號）| 不做板塊層級操作 | -- |

### 8.3 後續研究方向

1. **回測驗證**：取得歷史國會交易資料（2013-2025），計算板塊 NBR 信號與後續板塊報酬的相關性。
2. **委員會效應**：標記各議員的委員會成員資格，檢驗「管轄板塊」交易的信號品質是否優於「非管轄板塊」。
3. **跨議員共識加權**：開發 Consensus-Weighted NBR（CWNBR），對多議員共識信號給予更高權重。
4. **與 AI Discovery 信號融合**：將板塊 NBR 信號作為 `discovery_engine_v4.py` 的輸入特徵，提升信號品質。

---

## 附錄 A：板塊分類覆蓋統計

| 分類 | 數量 | 佔比 |
|------|------|------|
| 成功分類 ticker | 226 | 86.3% |
| 未分類 ticker | 36 | 13.7% |
| 成功分類交易筆數 | 314 | 89.0% |
| **未分類 ticker 明細** | | |
| ETF/指數基金 | 13 | (IVV, IWM, MDY, MBB, JMBS, FTGC, GIGB, TBLL, TPYP, VNQI, SLV, PALL, PPLT) |
| OTC 外國股票 | 4 | (MHIYF, MBJBF, VSNNT, SWSD) |
| 已退市/代碼變更 | 5 | (K→MARS, CS→UBS, SQ→XYZ, SNDK, LGN) |
| 其他不明 | 14 | (EIPI, HN, OT, RFD, SED, KRSOX, RNWGX, LVY, LITP, RHM GR, CMBS, AFT, GEM, OZKAP) |

## 附錄 B：板塊內 Ticker 分布

| 板塊 | Ticker 數 | 代表性 Ticker |
|------|-----------|--------------|
| Industrials | 39 | ETN, PWR, WAB, AVAV, BA, CAT, GD, LMT, NOC, RTX |
| Technology | 37 | AAPL, NVDA, MSFT, ORCL, AMD, INTC, CSCO, AVGO, MU, PTC |
| Financial Services | 33 | GS, COIN, BRO, SCHW, HOOD, CBOE, CME, COF, SPGI, STT |
| Healthcare | 24 | ISRG, BSX, SYK, UNH, CI, CVS, BIIB, LGND, MRK, BMY |
| Consumer Cyclical | 20 | DASH, AMZN, TSLA, BKNG, HD, COST, RBLX, UBER, LEN, DHI |
| Energy | 19 | XOM, CVX, COP, HAL, BKR, EOG, WMB, TRGP, VLO, OKE |
| Real Estate | 17 | CSGP, SBAC, VICI, CCI, PSA, ARE, BXP, DOC, INVH, IRT |
| Consumer Defensive | 13 | CLX, KHC, PG, COST, CAG, CPB, GIS, STZ, K, KVUE |
| Communication Services | 12 | META, NFLX, DIS, CMCSA, SPOT, WBD, OMC, VRSN, TTD, TCTZF |
| Basic Materials | 11 | LIN, CF, DD, FNV, LYB, MLM, MOS, PAAS, WPM, AMCR |
| Utilities | 1 | AWK |

## 附錄 C：參考文獻

1. Ziobrowski, A. J., Cheng, P., Boyd, J. W., & Ziobrowski, B. J. (2004). Abnormal Returns from the Common Stock Investments of the US Senate. *Journal of Financial and Quantitative Analysis*, 39(4), 661-676.
2. Ziobrowski, A. J., Boyd, J. W., Cheng, P., & Ziobrowski, B. J. (2011). Abnormal Returns from the Common Stock Investments of Members of the U.S. House of Representatives. *Business and Politics*, 13(1), 1-22.
3. Eggers, A. C., & Hainmueller, J. (2013). Capitol Losses: The Mediocre Performance of Congressional Stock Portfolios. *The Journal of Politics*, 75(2), 535-551.
4. Karadas, S. (2019). Trading on Private Information: Evidence from Members of Congress. *Financial Review*, 54(1), 85-113.
5. Huang, Q., & Xuan, Y. (2021). Trading Activities of Congress Members: Evidence from the STOCK Act. *Journal of Financial Markets*, 56, 100622.
6. Cohen, L., Malloy, C., & Pomorski, L. (2012). Decoding Inside Information. *The Journal of Finance*, 67(3), 1009-1043.
7. Moskowitz, T. J., & Grinblatt, M. (1999). Do Industries Explain Momentum? *The Journal of Finance*, 54(4), 1249-1290.

## 附錄 D：分析程式碼

完整 POC 分析使用以下工具：
- Python 3.10+ with `sqlite3`, `yfinance`, `json`, `collections`
- 資料庫：`data/data.db`（`congress_trades` 表）
- 板塊分類快取：`data/ticker_sectors.json`
- 分析日期：2026-02-27
