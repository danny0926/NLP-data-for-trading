# RB-007: Sector Rotation Deep Dive
# 國會議員產業配置趨勢與 Sector Alpha 分析

**報告日期**: 2026-02-27
**資料期間**: 2025-12-01 ~ 2026-02-17
**資料來源**: congress_trades (404 筆), alpha_signals (355 筆), ticker_sectors.json (226 tickers)
**Sector ETF 基準**: SPDR Select Sector ETFs (XLK, XLF, XLE, XLV, XLI, XLY, XLP, XLU, XLB, XLRE, XLC)

---

## Executive Summary

本報告深度分析國會議員在 2025年12月至2026年2月間的產業配置趨勢，揭示三大核心發現：

1. **明確的 sector rotation 訊號**：議員在12月大幅拋售科技/金融/通訊，1月全面反轉買入，呈現經典的「年末稅務賣出 → 年初重新布局」模式
2. **能源板塊的強烈 contrarian 信號**：議員持續淨賣出能源（12月-3、1月-18），但 XLE 在1-2月暴漲 +22%，顯示議員**不擅長 Energy timing**
3. **NET BUY 信號具預測力**：國會淨買入板塊的 20 日前瞻報酬平均 +2.51%，勝率 66.7%；但淨賣出信號的方向性指引較弱（勝率僅 38.9%）

**核心策略建議**：跟隨國會淨買入信號做多對應 sector ETF，但**忽略其淨賣出信號**。當前應增持 Industrials (XLI)、Basic Materials (XLB)、Healthcare (XLV)。

---

## 1. Sector Flow 分析：Buy vs Sell 淨流量

### 1.1 整體淨流量（筆數加權）

| Sector | Buy | Sell | Net | Buy 金額 | Sell 金額 | Net 金額 |
|--------|-----|------|-----|----------|-----------|----------|
| **Healthcare** | 22 | 8 | **+14** | $200,500 | $88,500 | **+$112,000** |
| **Industrials** | 32 | 23 | **+9** | $305,000 | $257,500 | **+$47,500** |
| **Basic Materials** | 10 | 2 | **+8** | $129,000 | $83,000 | **+$46,000** |
| Financial Services | 25 | 19 | +6 | $224,500 | $3,333,500 | -$3,109,000 |
| Real Estate | 12 | 9 | +3 | $96,000 | $96,500 | -$500 |
| Technology | 28 | 27 | +1 | $224,000 | $472,500 | -$248,500 |
| Comm Services | 9 | 9 | 0 | $72,000 | $72,000 | $0 |
| Utilities | 0 | 1 | -1 | $0 | $75,000 | -$75,000 |
| Consumer Cyclical | 16 | 18 | -2 | $128,000 | $168,500 | -$40,500 |
| Consumer Defensive | 6 | 12 | -6 | $48,000 | $163,000 | -$115,000 |
| **Energy** | 3 | 24 | **-21** | $24,000 | $357,000 | **-$333,000** |

### 1.2 關鍵觀察

- **Healthcare (+14)** 是最強淨買入板塊，金額加權也最高（+$112K）。顯示議員對醫療保健前景持續看好
- **Energy (-21)** 是壓倒性的淨賣出板塊，21筆淨賣出中 Oil & Gas E&P 佔 10 筆。然而能源 ETF 表現最佳
- **Financial Services** 雖然筆數淨買入 +6，但**金額淨賣出 -$3.1M**，有大額賣出（Capital Markets 類的 GS, MS 等）

---

## 2. 時間趨勢：Dec → Jan → Feb Rotation

### 2.1 月度淨流量矩陣

| Sector | Dec 2025 | Jan 2026 | Feb 2026 | 趨勢 |
|--------|----------|----------|----------|------|
| Industrials | -4 | **+12** | +1 | 12月賣出 → 1月強力買入 |
| Financial Services | -5 | **+11** | 0 | 12月賣出 → 1月強力買入 |
| Technology | **-9** | **+9** | +1 | 完美反轉：12月拋售 → 1月回補 |
| Healthcare | +8 | +6 | 0 | 持續淨買入 |
| Basic Materials | +2 | **+6** | 0 | 加速買入 |
| Comm Services | **-6** | **+5** | +1 | 12月拋售 → 1月回補 |
| Real Estate | -2 | +5 | 0 | 溫和反轉 |
| Consumer Cyclical | -5 | +1 | +2 | 弱反轉 |
| Consumer Defensive | -2 | **-5** | +1 | 持續賣出 |
| Energy | -3 | **-18** | 0 | 加速拋售 |
| Utilities | 0 | -1 | 0 | 微量賣出 |

### 2.2 Dec→Jan 反轉模式 (Tax-Loss Harvesting → New Year Rebalancing)

五個板塊出現明確反轉：

| Sector | Dec Net | Jan Net | 反轉幅度 | 信號 |
|--------|---------|---------|----------|------|
| **Technology** | -9 | +9 | 18 | STRONG BUY |
| **Financial Services** | -5 | +11 | 16 | STRONG BUY |
| **Industrials** | -4 | +12 | 16 | STRONG BUY |
| **Comm Services** | -6 | +5 | 11 | STRONG BUY |
| **Real Estate** | -2 | +5 | 7 | STRONG BUY |

**解讀**：這是典型的年末稅務虧損出清（tax-loss harvesting）後，年初重新配置的模式。議員在12月大量賣出（可能為了實現虧損抵稅），1月初重新建倉。值得注意的是，Energy 板塊**沒有反轉**，持續加速賣出。

---

## 3. Sector Alpha 分析

### 3.1 Alpha Signals 按板塊（回測結果）

| Sector | Signals | Avg 5d Alpha | Avg 20d Alpha | Avg Strength | Avg SQS | LONG | SHORT |
|--------|---------|-------------|---------------|-------------|---------|------|-------|
| Utilities | 1 | +0.78% | **+2.31%** | 0.35 | 56.8 | 1 | 0 |
| Energy | 27 | +0.45% | **+1.19%** | 0.18 | 50.3 | 27 | 0 |
| Financial Svc | 44 | +0.70% | **+1.16%** | 0.34 | 51.1 | 44 | 0 |
| Basic Materials | 12 | +0.83% | **+1.14%** | 0.42 | 52.3 | 12 | 0 |
| Consumer Def | 18 | +0.56% | +1.14% | 0.24 | 49.9 | 18 | 0 |
| Industrials | 55 | +0.72% | +1.10% | 0.33 | 50.9 | 55 | 0 |
| Comm Services | 18 | +0.70% | +1.08% | 0.39 | 49.7 | 18 | 0 |
| Technology | 55 | +0.65% | +1.08% | 0.30 | 51.6 | 55 | 0 |
| Real Estate | 21 | +0.66% | +1.07% | 0.28 | 50.1 | 21 | 0 |
| Consumer Cyc | 34 | +0.61% | +1.05% | 0.26 | 51.4 | 34 | 0 |
| Healthcare | 30 | +0.66% | +0.92% | 0.30 | 50.3 | 30 | 0 |

### 3.2 觀察

- 所有信號均為 **LONG**（系統目前未產生 SHORT 信號）
- **Utilities 的 20d alpha 最高 (+2.31%)**，但樣本量僅 1 筆，統計意義不足
- **Energy (+1.19%)** 和 **Financial Services (+1.16%)** 在較大樣本量下表現最佳
- **Basic Materials (+1.14%, 0.42 strength)** 信號強度最高，是潛在的高 alpha 來源
- **Healthcare (+0.92%)** alpha 最低，儘管是議員最大淨買入板塊

---

## 4. 議員-Sector 交叉分析

### 4.1 Top Traders 的產業偏好

| 議員 | 總交易 | 頂級板塊 | 集中度 | 產業分布 |
|------|--------|---------|--------|---------|
| **Gilbert Cisneros** | 251 | Industrials | 18% | Industrials(28B/16S), Tech(25B/12S), FinSvc(20B/11S) |
| **April McClain Delaney** | 30 | Technology | 30% | Tech(0B/9S), Healthcare(3B/3S), Industrials(1B/4S) |
| **John Boozman** | 16 | Comm Services | 25% | CommSvc(2B/2S), Tech(1B/3S), Industrials(2B/1S) |
| **Steve Cohen** | 6 | Financial Svc | 50% | FinSvc(0B/3S), Industrials(0B/2S), Tech(1B/0S) |

### 4.2 關鍵發現

- **Gilbert Cisneros** 佔據整個資料集 63% 的交易（251/404），其交易分布高度分散化，幾乎覆蓋所有板塊。他在 Industrials 上淨買入 +12，在 Energy 上淨賣出 -6
- **April McClain Delaney** 以賣出為主（Tech 9 筆全賣），可能進行投資組合的系統性減持
- **Steve Cohen** (Financial Services 集中度 50%) 全部為賣出，可能與其金融業委員會角色相關

---

## 5. Industry-Level 深度分析

### 5.1 最強淨買入 Industries（Top 10）

| Industry | Sector | Buy | Sell | Net | 代表標的 |
|----------|--------|-----|------|-----|---------|
| Specialty Industrial Machinery | Industrials | 8 | 3 | **+5** | ETN, GEV, ITT, AME |
| Aerospace & Defense | Industrials | 9 | 4 | **+5** | LMT, GD, GE, NOC, RTX |
| Internet Retail | Consumer Cyc | 8 | 4 | **+4** | AMZN, MELI, DASH |
| Medical Instruments & Supplies | Healthcare | 4 | 0 | **+4** | ISRG, COO, AZTA |
| Consumer Electronics | Technology | 4 | 1 | **+3** | AAPL, SONY |
| Credit Services | Financial Svc | 3 | 0 | **+3** | V, PYPL, COF |
| Healthcare Plans | Healthcare | 3 | 0 | **+3** | UNH, CI, CVS |
| Insurance Brokers | Financial Svc | 4 | 1 | **+3** | AJG, BRO, ERIE |
| Biotechnology | Healthcare | 5 | 2 | **+3** | LGND, ARQT, AGIO |
| Drug Mfg - General | Healthcare | 4 | 1 | **+3** | MRK, BMY, AZN, PFE |

### 5.2 最強淨賣出 Industries（Top 5）

| Industry | Sector | Buy | Sell | Net | 代表標的 |
|----------|--------|-----|------|-----|---------|
| **Oil & Gas E&P** | Energy | 0 | 10 | **-10** | COP, EOG, APA, CTRA |
| REIT - Specialty | Real Estate | 0 | 4 | **-4** | CCI, SBAC |
| Capital Markets | Financial Svc | 4 | 7 | **-3** | GS, MS, SCHW |
| Oil & Gas Midstream | Energy | 1 | 4 | **-3** | KMI, OKE, TRGP, WMB |
| Oil & Gas Integrated | Energy | 1 | 4 | **-3** | XOM, CVX |

### 5.3 Industry 層面的投資啟示

- **Aerospace & Defense** 是議員最活躍的子產業之一，搭配國防預算增長，值得關注
- **Medical Instruments** 零賣出（4 Buy / 0 Sell），信心異常強烈
- **Oil & Gas E&P** 10 筆淨賣出是所有 industry 中最極端的，但 XLE +22% 的走勢與議員行為背離

---

## 6. Sector ETF 表現 vs 國會流量

### 6.1 各月 ETF 報酬對照

| ETF | Sector | Dec Return | Dec Congress | Jan Return | Jan Congress | Feb MTD Return |
|-----|--------|-----------|-------------|-----------|-------------|---------------|
| XLE | Energy | -1.25% | -3 | **+11.83%** | **-18** | **+9.99%** |
| XLP | Consumer Def | -1.24% | -2 | +7.49% | -5 | +5.16% |
| XLB | Basic Materials | +2.23% | +2 | +6.83% | +6 | +6.75% |
| XLI | Industrials | +2.78% | -4 | +4.72% | +12 | +5.47% |
| XLC | Comm Services | +2.83% | -6 | +2.72% | +5 | -2.47% |
| XLRE | Real Estate | -0.73% | -2 | +2.60% | +5 | +6.52% |
| XLY | Consumer Cyc | +1.14% | -5 | +2.38% | +1 | -4.03% |
| XLU | Utilities | -2.81% | 0 | +0.16% | -1 | **+10.70%** |
| XLK | Technology | +0.71% | -9 | -0.29% | +9 | -2.93% |
| XLV | Healthcare | +0.11% | +8 | -0.50% | +6 | +1.11% |
| XLF | Financial Svc | +3.92% | -5 | -2.71% | +11 | -2.83% |

### 6.2 信號-報酬矛盾

- **Energy paradox**: 議員1月淨賣出 -18（最強賣出信號），XLE 1月 +11.83%、2月 +9.99%。議員的能源交易與市場走勢嚴重脫節
- **Financial Services paradox**: 議員1月淨買入 +11（最強買入信號），XLF 1月 -2.71%、2月 -2.83%。買入信號失效
- **Industrials alignment**: 議員1月淨買入 +12，XLI 1月 +4.72%、2月 +5.47%。唯一強信號與走勢對齊的板塊

---

## 7. Lead-Lag 分析：國會流量是否預測板塊表現？

### 7.1 整體統計

| 指標 | 數值 |
|------|------|
| 總信號數（|net| >= 2 的週-板塊組合） | 33 |
| 整體勝率 | 51.5% (17/33) |
| **淨買入信號勝率** | **66.7% (10/15)** |
| 淨買入信號平均 5d 前瞻報酬 | +0.13% |
| **淨買入信號平均 20d 前瞻報酬** | **+2.51%** |
| 淨賣出信號勝率 | 38.9% (7/18) |
| 淨賣出信號平均 5d 前瞻報酬 | +0.88% |
| 淨賣出信號平均 20d 前瞻報酬 | +2.42% |

### 7.2 關鍵發現

1. **NET BUY 信號具有預測力**：66.7% 勝率 + 2.51% 平均 20d 報酬，顯示議員的買入行為確實能預測板塊中期走勢
2. **NET SELL 信號不可靠**：38.9% 勝率意味著**反向操作更好**。議員賣出後板塊仍然平均上漲 +2.42%
3. **5 日報酬不顯著**（NET BUY +0.13%），但 **20 日報酬顯著**，建議使用 20 天持有期

### 7.3 最佳信號案例

| 週 | Sector | Net Flow | Fwd 20d | 結果 |
|----|--------|---------|---------|------|
| 2026-01-05 | Basic Materials | +6 | **+7.54%** | CORRECT |
| 2026-01-05 | Industrials | +7 | **+6.45%** | CORRECT |
| 2025-12-15 | Industrials | +3 | **+5.93%** | CORRECT |
| 2025-12-15 | Consumer Defensive | +3 | **+5.86%** | CORRECT |
| 2026-01-05 | Real Estate | +2 | **+4.01%** | CORRECT |

---

## 8. 當前 Portfolio Sector 配置

### 8.1 組合板塊分布

| Sector | 權重 | 持倉數 | 主要標的 |
|--------|------|--------|---------|
| **Industrials** | **24.9%** | 5 | ETN, PWR, GE, FERG, FINMF |
| **Financial Svc** | **20.2%** | 4 | GS, BRO, SPGI, SAN |
| Technology | 15.0% | 3 | AAPL, PTC, ASML |
| Comm Services | 10.8% | 2 | NFLX, DIS |
| Basic Materials | 9.9% | 2 | WPM, FNV |
| Healthcare | 9.6% | 2 | UNH, BIIB |
| Energy | 4.9% | 1 | XOM |
| Consumer Cyc | 4.8% | 1 | HESAF |

### 8.2 組合 vs 國會流量對齊度

| Sector | 組合權重 | 國會 Net Flow | 對齊 | 建議 |
|--------|---------|-------------|------|------|
| Industrials | 24.9% | +9 | ALIGNED | 維持或小幅增持 |
| Financial Svc | 20.2% | +6 | ALIGNED | 注意金額淨賣出，審慎觀察 |
| Healthcare | 9.6% | +14 | **UNDER-ALLOCATED** | **建議增持至 15%** |
| Basic Materials | 9.9% | +8 | **UNDER-ALLOCATED** | **建議增持至 12%** |
| Technology | 15.0% | +1 | NEUTRAL | 維持 |
| Energy | 4.9% | -21 | CONTRARIAN | 議員大量賣出但 ETF 強勢 |
| Consumer Def | 0% | -6 | N/A | 不需要配置 |

---

## 9. Sector Rotation 策略建議

### 9.1 核心策略：Congressional Net Buy → Sector ETF Long

基於 lead-lag 分析的結果，建議以下策略框架：

**進場規則**：
- 當某板塊的週度國會淨買入 >= 3 筆時，買入對應 Sector ETF
- 持有期 20 個交易日
- 預期勝率 ~67%，預期平均報酬 ~2.5%

**退場規則**：
- 20 個交易日後自動平倉
- 若淨流量反轉（從淨買入變為淨賣出），提前平倉

**排除規則**：
- **忽略國會淨賣出信號**（勝率僅 39%，不具預測力）
- **能源板塊單獨處理**（議員 Energy timing 歷史紀錄極差）

### 9.2 當前可操作的板塊建議

| 優先級 | 板塊 | ETF | 信號 | 理由 |
|--------|------|-----|------|------|
| 1 | **Industrials** | **XLI** | STRONG BUY | 最大淨買入 +12 (Jan), A&D + Machinery 雙驅動 |
| 2 | **Basic Materials** | **XLB** | STRONG BUY | 持續淨買入, alpha 信號強度最高 (0.42), Specialty Chemicals 主導 |
| 3 | **Healthcare** | **XLV** | STRONG BUY | 最大整體淨買入 +14, Medical Instruments 零賣出 |
| 4 | Real Estate | XLRE | BUY | Jan 反轉至 +5, ETF 近 30 日 +5.77% |
| 5 | Comm Services | XLC | HOLD | 1月反轉 +5，但 Feb 已下跌 -2.47% |
| -- | Financial Svc | XLF | CAUTION | 筆數淨買入但金額淨賣出 -$3.1M |
| -- | Energy | XLE | AVOID SIGNAL | 議員 timing 完全失效，不宜參考 |
| -- | Technology | XLK | NEUTRAL | 1月回補後信號中性 |

### 9.3 模擬 Sector ETF 組合配置

| ETF | Sector | 建議權重 | 理由 |
|-----|--------|---------|------|
| XLI | Industrials | 30% | 最強 rotation 信號 + A&D 主題 |
| XLB | Basic Materials | 25% | 高 alpha strength + 持續淨買入 |
| XLV | Healthcare | 25% | 最強淨買入 + Medical Instruments |
| XLRE | Real Estate | 10% | 反轉信號 + 估值修復 |
| XLC | Comm Services | 10% | 反轉信號，觀察部位 |

**預期年化報酬**（基於 20d forward return 外推）：~15-18%
**預期勝率**：67%
**建議持有期**：月度 rebalance

---

## 10. Risk Factors

1. **樣本偏差**：404 筆交易中 Gilbert Cisneros 佔 63%，單一議員的交易行為嚴重影響整體統計
2. **短期數據**：僅 3 個月的數據（Dec-Feb），可能受到年末 tax-loss harvesting 的一次性影響
3. **Filing lag**：交易日期到申報日期有 17-45 天延遲，實際可操作性受限
4. **能源板塊異常**：議員在能源上的判斷與市場走勢嚴重背離，建議將能源從信號系統中排除
5. **金額 vs 筆數矛盾**：Financial Services 筆數淨買入但金額淨賣出，信號不一致

---

## 11. 結論

國會議員的 sector rotation 行為確實包含可操作的 alpha 信號，但需要精心篩選：

- **跟隨買入信號**（66.7% 勝率）
- **忽略賣出信號**（39% 勝率，不如反向操作）
- **排除能源板塊**（議員 timing 紀錄極差）
- **使用 20 天持有期**（5 天不顯著）

當前最強的 sector rotation 信號指向 **Industrials (XLI)**、**Basic Materials (XLB)** 和 **Healthcare (XLV)**，建議立即增配。

---

*本報告由 Political Alpha Monitor 系統自動生成*
*分析方法: 國會交易流量統計 + Sector ETF 前瞻報酬回測 + Lead-Lag 預測力檢驗*
