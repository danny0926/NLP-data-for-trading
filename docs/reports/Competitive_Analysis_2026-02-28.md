# PAM 競品分析報告

**日期**: 2026-02-28
**研究員**: Market Research Team
**報告代號**: MR-001

---

## 執行摘要

國會交易追蹤市場呈現明顯功能斷層：免費平台 (Capitol Trades) 僅提供原始數據，付費平台 (Unusual Whales $42-$170/月, Quiver $25/月) 提供視覺化但缺乏學術級量化驗證。PAM 以 7 份量化研究報告 + FF3 因子模型 + PACS 多信號融合填補此空白。

---

## 競品比較矩陣

| 功能 | Capitol Trades | Quiver | Unusual Whales | Autopilot | **PAM** |
|------|---------------|--------|----------------|-----------|---------|
| 定價 | 免費 | $25/月 | $42-170/月 | $100/年 | 規劃中 |
| API | 無 | $10-75/月 | $125/月 | 無 | FastAPI |
| AI 分析 | 無 | 有(基礎) | 無 | 無 | Gemini 2.5 Flash |
| FF3 回測 | 無 | 無 | 無 | 無 | **已驗證** |
| PACS 多信號 | 無 | 無 | 無 | 無 | **已實作** |
| VIX 過濾 | 無 | 無 | 無 | 無 | **Goldilocks 1.3x** |
| 收斂偵測 | 無 | 無 | 無 | 無 | **30天窗口+跨院** |
| 議員排名 | 列表 | Alpha指標 | 無 | AUM | **PIS 四維度** |
| 板塊輪動 | 無 | 部分 | 部分 | 無 | **RB-007驗證** |
| SEC Form4 | 無 | 另計費 | 無 | 無 | **交叉比對** |
| 社群情報 | 無 | 無 | 無 | 無 | **FinTwitBERT+Gemini** |
| 中文 UI | 無 | 無 | 無 | 無 | **完整繁中** |

---

## 競品深度分析

### Capitol Trades (免費)
- **定位**: 資料集聚合平台，強調公民監督
- **優勢**: 產業知名度最高，媒體可信度強，零門檻
- **弱點**: 純原始資料，零分析層
- **PAM 差異**: Capitol Trades 是資料庫，PAM 是決策引擎

### Quiver Quantitative ($25/月)
- **規模**: 750K 註冊用戶，5K+ 付費，ARR>$200萬，$263萬融資
- **優勢**: 最廣替代數據覆蓋 (國會+13F+遊說+政府合約+Google Trends)
- **弱點**: 回測停留在基礎統計，無 FF3/PACS/VIX
- **PAM 差異**: Quiver 是「誰賺更多」，PAM 是「p值多少、CAR 置信區間多寬」

### Unusual Whales ($42-$170/月)
- **定位**: 選擇權流 + 國會交易，社群驅動
- **優勢**: 唯一整合選擇權流+國會數據，NANC/KRUZ ETF 合作
- **弱點**: 國會是附加功能，非核心；定價複雜
- **PAM 差異**: 我們在 PACS 中整合選擇權情緒作為因子，無需額外收費

### Autopilot ($100/年)
- **規模**: 100K+ 用戶，累計執行 $20 億交易
- **優勢**: 最低技術門檻的自動跟單
- **弱點**: 盲目跟單無分析，申報延遲問題
- **PAM 差異**: PAM 是 Autopilot 的「前置智慧過濾層」

---

## 定價環境

| 定價帶 | 代表 | 用戶類型 |
|--------|------|---------|
| 免費 | Capitol Trades | 休閒投資者/記者 |
| $10-29/月 | Quiver($25), Autopilot($9.67) | 積極個人投資者 |
| $42-65/月 | Unusual Whales Basic, InsiderFinance | 活躍交易者 |
| $125/月+ | UW API, Quiver API | 量化開發者 |
| $1,728+/年 | UW Professional | 機構/RIA |
| 客製 | Quiver Institution | 對沖基金 |

---

## 建議定價策略

| 方案 | 月費 | 年費 | 目標用戶 | 核心功能 |
|------|------|------|---------|---------|
| **Free** | $0 | $0 | 試用者 | 7天交易列表、基礎議員排名 |
| **Signal** | $29/月 | $290/年 | 積極投資者 | SQS評分、PACS排名、PIS、告警 |
| **Alpha** | $79/月 | $790/年 | 進階交易者/RIA | 收斂信號+板塊輪動+回測+API基礎 |
| **Institution** | 客製 | $5K-20K/年 | 對沖基金/量化RIA | 全功能API+FF3+白牌報告 |

---

## PAM 核心 Pitch

> PAM 是全球唯一以學術級量化研究支撐的國會交易 alpha 信號系統。5,000+ 筆交易回測中，Buy-Only 策略 +1.10% 20d CAR (59.2% WR)；VIX Goldilocks Zone (14-16) +1.03% (p<0.05)。7 份研究報告每個聲明都有 p 值和 FF3 因子調整可引用。其他平台告訴你議員買了什麼，PAM 告訴你該不該跟、有多大信心、預期賺多少。

---

## 關鍵風險

| 風險 | 緩解 |
|------|------|
| STOCK Act 改革/國會交易禁令 | 擴展至 SEC Form 4 + 13F + 歐洲議會 |
| Quiver 加速量化功能 ($263萬資金) | 加速發表 RB-008/009 保持先發 |
| Unusual Whales 整合 AI 分析 | 社群媒體交叉比對為獨有護城河 |

---

## 參考資料

- [Quiver Quantitative Review — Find My Moat](https://www.findmymoat.com/tools/quiver-quantitative)
- [Unusual Whales Pricing](https://unusualwhales.com/pricing)
- [Autopilot Review — Wall Street Zen](https://www.wallstreetzen.com/blog/autopilot-investment-app-review/)
- [NANC vs KRUZ — ETF.com](https://www.etf.com/sections/etf-basics/nanc-vs-kruz-battle-congress-stock-trackers)
- [Congress Leaders Outperform 47% — Fortune 2025](https://fortune.com/2025/12/07/congress-stock-market-trades-leadership-outperformance-trading-ban-bill-discharge-petition/)
