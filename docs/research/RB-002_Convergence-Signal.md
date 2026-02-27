# RB-002: Multi-Politician Convergence Signal

**狀態**: Draft
**研究員**: Quant Researcher
**日期**: 2026-02-27
**關聯**: RB-001 衍生研究

---

## 一、研究假設

### 1.1 核心假設

**當多位議員在 30 天內同方向交易同一 ticker 時，該 ticker 的後續表現會顯著優於（買入匯聚）或劣於（賣出匯聚）大盤。**

### 1.2 理論基礎

- **單一議員交易**：可能反映個人理財需求（繳稅、資產配置、生活開支），信噪比低
- **多議員同方向交易**：暗示共同的資訊來源（即將通過的法案、委員會聽證情報、政策走向），類似「聰明錢匯聚」(smart money convergence)
- **跨院匯聚**：Senate + House 同時交易同一股票，信號強度更高——兩院議員接觸不同資訊管道，同步行動暗示資訊高度可靠

### 1.3 學術類比

此假設與公司內部人交易文獻中的「cluster trading」高度類似。Alldredge & Cicero (2019) 發現公司內部人聚集交易後的月度超額報酬達 **2.1%**，比獨立交易高出 **0.9%**。本研究將此概念從公司內部人延伸至國會議員。

---

## 二、數據分析

### 2.1 數據集概覽

| 指標 | 數值 |
|------|------|
| 交易總筆數 | 353 筆（有 ticker） |
| 不同 Ticker | 262 個 |
| 不同議員 | 11 位 |
| 數據期間 | 2025-12-02 至 2026-02-17 |
| 交易類型 | Buy: 218 / Sale: 185 / Exchange: 1 |
| 院別分布 | House: 347 / Senate: 57 |

### 2.2 多議員交易 Ticker 分布

共 **10 個 ticker** 被 2 位以上議員交易：

| Ticker | 議員數 | 總交易數 | 買入 | 賣出 | 議員名單 |
|--------|--------|----------|------|------|----------|
| **GS** | 4 | 4 | 0 | 4 | McCormick, Beyer, Biggs, Cohen |
| **NFLX** | 3 | 3 | 1 | 2 | Allen, Boozman, Cisneros |
| **PTC** | 2 | 5 | 1 | 4 | Cisneros, Delaney |
| **PWR** | 2 | 4 | 1 | 3 | Cisneros, Delaney |
| **BRO** | 2 | 3 | 2 | 1 | Cisneros, Delaney |
| **ETN** | 2 | 3 | 2 | 1 | Boozman, Cisneros |
| **AAPL** | 2 | 2 | 2 | 0 | **Pelosi**, Boozman |
| **DIS** | 2 | 2 | 2 | 0 | Boozman, Cisneros |
| **FISV** | 2 | 2 | 1 | 1 | Boozman, Cisneros |
| **XOM** | 2 | 2 | 1 | 1 | Boozman, Cisneros |

**觀察**：Cisneros（272 筆）和 Boozman（37 筆）是最活躍的交易者，他們的交易重疊可能部分反映高交易頻率的統計效應，而非真正的資訊匯聚。

### 2.3 匯聚事件識別

以 **30 天窗口 + 同方向 + 2 位以上不同議員** 為篩選條件，識別出 **5 個獨立匯聚事件**：

#### 事件 1：GS（Goldman Sachs）— 3 人賣出匯聚 ⭐ 最強信號

| 議員 | 院別 | 交易日 | 方向 | 金額 |
|------|------|--------|------|------|
| Steve Cohen | House | 2025-12-17 | Sale | $15,001–$50,000 |
| Donald Beyer | House | 2025-12-18 | Sale | $15,001–$50,000 |
| Sheri Biggs | House | 2025-12-22 | Sale | $1,001–$15,000 |
| David McCormick | Senate | 2026-01-23 | Sale | **$1M–$5M** |

- **窗口密度**：3 人在 5 天內賣出，第 4 人（McCormick）在 37 天後大額賣出
- **跨院匯聚**：House × 3 + Senate × 1
- **金額異常**：McCormick 的 $1M–$5M 賣出量級遠超其他交易
- **信號強度**：★★★★★（最高）

#### 事件 2：AAPL（Apple）— 2 人同日買入 ⭐ 精確匯聚

| 議員 | 院別 | 交易日 | 方向 | 金額 |
|------|------|--------|------|------|
| **Nancy Pelosi** | House | 2026-01-15 | Buy | $1,001–$15,000 |
| John Boozman | Senate | 2026-01-15 | Buy | $1,001–$15,000 |

- **同日交易**：完全時間匯聚
- **跨院匯聚**：House + Senate
- **Pelosi 效應**：Pelosi 的交易歷來被市場高度關注
- **信號強度**：★★★★☆

#### 事件 3：DIS（Disney）— 2 人隔日買入

| 議員 | 院別 | 交易日 | 方向 | 金額 |
|------|------|--------|------|------|
| John Boozman | Senate | 2026-01-08 | Buy | $1,001–$15,000 |
| Gilbert Cisneros | House | 2026-01-09 | Buy | $1,001–$15,000 |

- **1 天間隔**：高度時間匯聚
- **跨院匯聚**：Senate + House
- **信號強度**：★★★☆☆

#### 事件 4：ETN（Eaton Corp）— 2 人隔日買入

| 議員 | 院別 | 交易日 | 方向 | 金額 |
|------|------|--------|------|------|
| John Boozman | Senate | 2026-01-29 | Buy | $1,001–$15,000 |
| Gilbert Cisneros | House | 2026-01-30 | Buy | $1,001–$15,000 |

- **1 天間隔**：高度時間匯聚
- **跨院匯聚**：Senate + House
- **信號強度**：★★★☆☆

#### 事件 5：NFLX（Netflix）— 2 人賣出匯聚

| 議員 | 院別 | 交易日 | 方向 | 金額 |
|------|------|--------|------|------|
| Gilbert Cisneros | House | 2025-12-10 | Sale | $1,001–$15,000 |
| Richard W. Allen | House | 2025-12-12 | Sale | $1,001–$15,000 |

- **2 天間隔**
- **同院匯聚**：House only
- **信號強度**：★★☆☆☆

### 2.4 跨院匯聚統計

在 6 個多議員 ticker 中，**5 個（83%）為跨院交易**：

| Ticker | 跨院? | 意義 |
|--------|--------|------|
| AAPL | ✅ House + Senate | Pelosi（House）+ Boozman（Senate），同日 |
| DIS | ✅ Senate + House | 跨院隔日買入 |
| ETN | ✅ Senate + House | 跨院隔日買入 |
| GS | ✅ Senate + House | 3 House + 1 Senate 賣出 |
| NFLX | ✅ House + Senate | 跨院賣出（但不同方向交錯） |
| PWR | ❌ House only | 單院（Cisneros + Delaney） |

**跨院匯聚比例高達 83%**——這支持「資訊在兩院間傳播」的假設，但也可能反映樣本偏差（僅 11 位議員、2.5 個月數據）。

### 2.5 議員交易集中度風險

| 議員 | 交易數 | 佔比 |
|------|--------|------|
| Gilbert Cisneros | 272 | 77.1% |
| John Boozman | 37 | 10.5% |
| April McClain Delaney | 31 | 8.8% |
| 其他 8 位 | 13 | 3.7% |

**警告**：Cisneros 單一議員佔 77% 的交易量。他出現在大多數匯聚事件中，可能僅因為他的交易頻率極高，而非反映真正的資訊匯聚。**Cisneros 參與的匯聚事件應降低信號權重**。

排除 Cisneros 參與的匯聚事件後，僅剩：
- **GS 賣出匯聚**（Cohen + Beyer + Biggs + McCormick）
- **AAPL 買入匯聚**（Pelosi + Boozman）

這兩個事件的信號品質最高。

---

## 三、文獻支持

### 3.1 公司內部人聚集交易

**Alldredge, D. M. & Cicero, D. C. (2019). "Do Insiders Cluster Trades with Colleagues? Evidence from Daily Insider Trading." Journal of Financial Research, 42(2), 331-360.**

核心發現：
- 公司內部人傾向在同事交易附近聚集交易
- 聚集買入後月度超額報酬 **2.1%**（獨立交易僅 1.2%，高出 0.9%）
- 聚集效應在 **資訊不對稱高、投資人注意力低** 的環境中更顯著
- 結論：聚集交易反映資訊分享，而非巧合

**與本研究的關聯**：議員類似於公司「內部人」——他們有接觸非公開政策資訊的管道。多議員同時交易可類比為「insider cluster trading」。

### 3.2 國會議員交易 Alpha

**NBER 研究 (2025)**: 國會領導層的投資組合年化超額報酬達 **40-50%**，集中在半導體、AI 等聯邦資金決策高影響力的產業。

**Kavout 分析**: 當內部人（insiders）與國會議員同時買入同一股票時，兩個獨立的資訊優勢群體同向押注，信號可靠度顯著提升。

**Unusual Whales Congress Trading Report (2025)**: 2025 年國會議員執行超過 2,000 筆交易，涵蓋 700 家公司。

### 3.3 STOCK Act 的執行漏洞

STOCK Act（2012）要求議員揭露交易，但：
- 違規僅罰 $200
- 至今無議員因 STOCK Act 被起訴
- 實質上提供了「合法的資訊優勢交易」環境

**意涵**：議員知道違規成本極低，更可能基於政策資訊進行交易——這增強了匯聚信號的理論基礎。

---

## 四、策略設計建議

### 4.1 匯聚信號定義

```
匯聚信號 = {
    ticker:        被交易的股票
    direction:     BUY 或 SELL
    window:        匯聚時間窗口（天數）
    n_politicians: 參與議員數量
    cross_chamber: 是否跨院
    pelosi_flag:   是否含 Pelosi（高關注度溢價）
    max_amount:    最大單筆金額
}
```

### 4.2 信號強度評分模型（建議）

```python
def convergence_score(event):
    score = 0

    # 基礎分：議員數量
    score += event['n_politicians'] * 2          # 每位議員 +2

    # 時間密度加分
    if event['window_days'] <= 1:
        score += 5                                # 同日/隔日交易
    elif event['window_days'] <= 7:
        score += 3                                # 一週內
    elif event['window_days'] <= 14:
        score += 1                                # 兩週內

    # 跨院加分
    if event['cross_chamber']:
        score += 3                                # 跨院匯聚

    # 高頻交易者折扣
    if event['has_high_frequency_trader']:
        score -= 2                                # Cisneros 等高頻交易者降權

    # 金額加分
    if event['max_amount'] >= 1_000_000:
        score += 3                                # 百萬級交易
    elif event['max_amount'] >= 50_000:
        score += 1

    # Pelosi 溢價
    if event['pelosi_flag']:
        score += 2                                # 市場高關注度

    return score
```

### 4.3 各事件評分估算

| 事件 | 議員數 | 時間密度 | 跨院 | 高頻折扣 | 金額 | 特殊 | 總分 |
|------|--------|----------|------|----------|------|------|------|
| GS SELL | 4×2=8 | +3(5天) | +3 | 0 | +3($1M+) | — | **17** |
| AAPL BUY | 2×2=4 | +5(同日) | +3 | 0 | 0 | +2(Pelosi) | **14** |
| DIS BUY | 2×2=4 | +5(1天) | +3 | -2(Cisneros) | 0 | — | **10** |
| ETN BUY | 2×2=4 | +5(1天) | +3 | -2(Cisneros) | 0 | — | **10** |
| NFLX SELL | 2×2=4 | +5(2天) | +3 | -2(Cisneros) | 0 | — | **10** |

### 4.4 交易策略框架

```
進場條件:
  - convergence_score >= 12（強信號）
  - 至少 2 位非高頻交易者議員
  - 交易窗口 <= 14 天

執行方式:
  - BUY 匯聚 → 開多頭（MOO，次交易日開盤）
  - SELL 匯聚 → 開空頭或減持

持倉期間:
  - 核心持倉：5-20 交易日（對齊 RB-001 的回測期間）
  - 止損：-5%
  - 止盈：+10% 或持滿 20 交易日

部位大小:
  - 按 convergence_score 線性配置
  - 最大單一部位不超過投資組合 5%
```

---

## 五、研究限制

1. **樣本量不足**：僅 353 筆交易、11 位議員、2.5 個月數據。統計檢定力不足以做出可靠結論
2. **交易者集中度**：Cisneros 佔 77% 交易量，嚴重影響匯聚事件的獨立性
3. **缺乏價格數據**：目前無法回測匯聚事件後的實際報酬
4. **申報延遲**：交易日到申報日（filing_date）可能相隔數週至數月，實際可交易時間窗口受限
5. **倖存者偏差**：僅觀察到已申報的交易，可能遺漏未依規申報的交易
6. **混淆因素**：同時期的市場事件（財報季、聯準會決議）可能是匯聚的真正驅動力

---

## 六、後續行動

### 短期（1-2 週）
- [ ] 整合 yfinance 價格數據，回測 5 個匯聚事件的 5/10/20 日 CAR
- [ ] 建立 `src/convergence_detector.py` 模組，自動化匯聚事件偵測
- [ ] 將 convergence_score 整合進 ETL pipeline 的 post-processing

### 中期（1-2 月）
- [ ] 擴大數據集：回溯抓取 12 個月以上的歷史交易
- [ ] 加入委員會資訊：識別議員所屬委員會，檢驗「相同委員會議員匯聚」是否信號更強
- [ ] 交叉驗證：對比公司內部人交易 (SEC Form 4) 是否與議員匯聚事件吻合

### 長期（3+ 月）
- [ ] 建構多因子模型：匯聚信號 × 委員會權力 × 申報延遲 × 產業政策暴露度
- [ ] 對接即時交易系統：匯聚事件觸發 → Slack/Telegram 通知 → 自動下單
- [ ] 發表策略白皮書（如 alpha 顯著）

---

## 參考文獻

1. Alldredge, D. M. & Cicero, D. C. (2019). "Do Insiders Cluster Trades with Colleagues? Evidence from Daily Insider Trading." *Journal of Financial Research*, 42(2), 331-360.
2. CEPR VoxEU. "Political power and profitable trades in the US Congress."
3. Unusual Whales. "Congress Trading Report 2025."
4. Kim, J. et al. (2024). "What explains trading behaviors of members of congress?" *International Review of Economics & Finance*.
5. Huang, J. & Xuan, Y. "Trading Political Favors: Evidence from the Impact of the STOCK Act." Georgetown/GWU Working Paper.
6. Fortune (2025). "Leaders in Congress outperform rank-and-file lawmakers on stock trades by up to 47% a year."
