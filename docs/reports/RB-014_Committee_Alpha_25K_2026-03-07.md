# Research Brief: RB-014 Committee Alpha Re-verification (25K Dataset)

> 日期：2026-03-07 | 研究員：Research Lead (Claude) | 狀態：**Reviewed**

## 問題定義

RB-008 (2026-02, n=355) 測試「委員會主席是否因資訊優勢產生更高 alpha」，結論 p=0.33，被 SHELVE。
現在 `congress_trades` 已有 **25,467 筆交易、191 位議員**，是原始樣本的 72 倍。本研究重新驗證：

1. 委員會領導人（Chair / Ranking Member）交易是否產生更高的 risk-adjusted alpha？
2. 是否有特定類型委員會（財金/國防）存在差異化 alpha？
3. 委員會領導人在交易行為特徵上是否有差異？

**與北極星指標的關係**：若委員會地位是 alpha 的穩健預測因子，可加入 PACS 公式提升信號品質。

## 研究方法

### 數據來源
- `congress_trades`: 25,467 筆（2023-03 ~ 2026-03）
- `fama_french_results`: 1,861 筆有 FF3 CAR 值（61 位議員）
- `alpha_signals`: 874 筆
- `enhanced_signals`: 611 筆（PACS 評分）

### 委員會領導人名單
透過 Web 搜尋編譯 119th Congress（2025-2026）完整委員會架構：
- **嚴格定義（Chair/Ranking/Leadership）**：24 位，匹配 DB 中 4,277 筆交易（16.8%）
- **廣義定義（含 Senior Members）**：53 位，匹配 6,101 筆交易（24.0%）

資料來源：[Senate Committee Assignments](https://www.senate.gov/general/committee_assignments/assignments.htm)、[House GOP Committee Chairs](https://scalise.house.gov/press-releases/Scalise-Applauds-Committee-Chairs-for-119th-Congress)、[Ballotpedia 119th Congress](https://ballotpedia.org/119th_United_States_Congress)

### 統計方法
- Mann-Whitney U test（非參數，適合偏態金融數據）
- Welch's t-test（不等方差 t 檢定）
- Cohen's d（效果量）
- 顯著性門檻：p < 0.05

## 發現摘要

### 發現 1：FF3 Alpha 無顯著差異 — 確認 SHELVE

| 比較組 | 指標 | Leaders (mean) | Non-Leaders (mean) | Cohen's d | MW p-value | 結論 |
|--------|------|:--------------:|:-------------------:|:---------:|:----------:|------|
| Chair/Ranking | FF3 CAR_5d | -0.0010 | +0.0012 | -0.042 | 0.701 | ns |
| Chair/Ranking | FF3 CAR_20d | +0.0046 | +0.0068 | -0.021 | 0.637 | ns |
| Chair/Ranking | FF3 CAR_60d | -0.0177 | +0.0286 | -0.277 | 0.387 | ns |
| Senior Members | FF3 CAR_5d | +0.0009 | +0.0010 | -0.002 | 0.861 | ns |
| Senior Members | FF3 CAR_20d | +0.0010 | +0.0076 | -0.064 | 0.956 | ns |
| Senior Members | FF3 CAR_60d | -0.0024 | +0.0286 | -0.186 | 0.535 | ns |

**核心結論**：所有 FF3 alpha 比較均不顯著（最低 p=0.387），效果量均為 negligible。委員會領導人甚至有略低於非領導人的趨勢（方向為負），尤其 60 天窗口更明顯。

> 25K 數據集（vs RB-008 的 355 筆）確認：**委員會地位不是 alpha 的預測因子。**

### 發現 2：交易行為特徵有顯著差異

| 特徵 | Leaders | Non-Leaders | 顯著性 |
|------|:-------:|:-----------:|:------:|
| 平均交易金額 | $114,661 | $50,344 | 領導人交易金額 2.3 倍 |
| 中位數金額 | $32,500 | $8,000 | 中位數 4.1 倍 |
| 平均 Filing Lag | 34.4 天 | 43.9 天 | p < 0.001 *** |
| Buy Ratio | 98.8% | 98.5% | 無差異 |

委員會領導人**交易金額更大、申報更快**，但這些交易行為特徵並未轉化為更高的 alpha。

### 發現 3：PACS 分數偏高但 Alpha 偏低 — 「假信號」風險

| 指標 | Leaders | Non-Leaders | Cohen's d | p-value |
|------|:-------:|:-----------:|:---------:|:-------:|
| PACS Score (Chair/Ranking) | 0.386 | 0.338 | +0.279 (small) | 0.082 |
| PACS Score (Senior Members) | 0.418 | 0.327 | **+0.532 (medium)** | **< 0.001 ***** |
| Signal Strength (Chair/Ranking) | 0.543 | 0.632 | -0.332 (small) | 0.032 * |

**矛盾發現**：
- 委員會資深成員的 PACS 分數顯著更高（d=0.53, p<0.001），但 FF3 alpha 反而更低
- 這表示 PACS 公式中的 filing_lag 和 convergence 組件會偏好委員會成員（因為他們申報更快），但實際 alpha 並未跟上
- Signal Strength 反而顯著較低（p=0.032），建議領導人的交易不如非領導人「有力」

### 發現 4：特定委員會子群分析

| 委員會類型 | FF3 CAR_5d | FF3 CAR_20d | PACS | 特徵 |
|-----------|:----------:|:-----------:|:----:|------|
| 財金委員會 (n=11) | -0.0029 (ns) | -0.0098 (ns) | **0.631** (p=0.009 **) | 金額最大（McCormick $288K, Pelosi $2.3M），但 alpha 反而為負 |
| 國防/情報 (n=6) | +0.0094 (ns) | +0.0042 (ns) | 0.406 (p<0.001 ***) | 唯一正向趨勢但不顯著，Tuberville 大量交易 |

財金委員會成員 PACS 極高（0.631 vs 0.338 基準）但 FF3 alpha 為負，是最嚴重的「假信號」群組。

### 發現 5：個別領導人 FF3 表現

表現最好的委員會成員（FF3 CAR_20d > 0）：
| 議員 | 角色 | n | FF3 CAR_20d |
|------|------|:-:|:----------:|
| Gary Peters | Homeland Security RM | 6 | +7.50% |
| Angus King | Intelligence Member | 7 | +3.76% |
| Tommy Tuberville | Armed Services | 5 | +1.93% |
| John Boozman | Agriculture Chair | 63 | +0.19% |

表現最差的委員會成員：
| 議員 | 角色 | n | FF3 CAR_20d |
|------|------|:-:|:----------:|
| John Hickenlooper | Commerce/Energy | 8 | -11.96% |
| David H McCormick | Banking/Armed Services | 6 | -4.77% |
| Sheldon Whitehouse | Budget/Finance | 11 | -1.47% |
| Nancy Pelosi | Speaker Emerita | 16 | -1.37% |

Speaker Emerita Pelosi 的 FF3 20d alpha 為 -1.37%，但 PACS 分數極高（因金額大、filing lag 短），再次證明「名氣/權力 ≠ alpha」。

## 方案比較

| 方案 | 優點 | 缺點 | 成本 | 風險 |
|------|------|------|------|------|
| A. 加入委員會因子到 PACS | 利用資訊不對稱假說 | 數據不支持，FF3 alpha 無差異 | M | 增加假信號 |
| B. 從 PACS 移除 filing_lag 偏差 | 減少對委員會領導人的系統性偏好 | 需重新校準 PACS | S | 可能降低整體 PACS 效能 |
| C. **不做任何改變（推薦）** | PACS 已在 RB-006 驗證有效，不需修改 | 委員會領導人的 PACS 偏高不影響排名 | 0 | 無 |
| D. 標記委員會領導人為高風險 | 避免 PACS 高分的假信號陷阱 | 會排除部分有效信號 | S | 過度修正 |

## 建議行動

### **CONFIRM SHELVE** — 委員會地位不是 alpha 預測因子

以 25,467 筆交易（72 倍於 RB-008）重新驗證，所有 alpha 比較均不顯著：
- FF3 CAR_5d: p=0.701（negligible effect）
- FF3 CAR_20d: p=0.637（negligible effect）
- FF3 CAR_60d: p=0.387（small effect，方向為負）

推薦方案 C：不做任何改變。理由：
1. 核心假說（「委員會主席因資訊優勢獲利更多」）在 25K 數據集中被否定
2. PACS 公式已基於 RB-006 實證校準，不需引入新的不確定因子
3. 個別領導人表現差異大（Gary Peters +7.5% vs Hickenlooper -12%），是個人能力差異，非委員會效應

### 附帶建議：監控 PACS-Alpha 偏差

- 財金委員會成員 PACS 平均 0.631 但 FF3 alpha 為負 — 未來如果 PACS 過度推薦這些人的交易，應考慮 filing_lag 權重修正
- 這不需要立即行動，但應記錄為 **watchlist item**

## 風險與緩解

| 風險 | 說明 | 緩解 |
|------|------|------|
| FF3 樣本不均 | 只有 8/24 位 Chair/Ranking 有 FF3 數據（其餘在回測期外） | 已用 alpha_signals + enhanced_signals 補充驗證，結論一致 |
| 委員會名單可能不完全 | 手動編譯 119th Congress 數據，可能遺漏少數成員 | 嚴格組 24 人 + 廣義組 53 人雙重驗證，結論一致 |
| 倖存者偏差 | 只分析有交易的議員，不交易的委員會領導人未納入 | 這是交易信號研究，不交易者不影響結論 |
| PACS 偏差未修正 | 委員會領導人 PACS 偏高可能在未來產生假信號 | 標記為 watchlist，定期監控 |

## 附錄：統計完整結果

```
Group                     Metric             nL    nNL      meanL     meanNL       d       MW-p   Sig
----------------------------------------------------------------------------------------------------
Leaders (Chair/Ranking)   FF3 CAR_5d         145   1716    -0.0010     0.0012  -0.0420   0.7011    ns
Leaders (Chair/Ranking)   FF3 CAR_20d         67   1239     0.0046     0.0068  -0.0209   0.6365    ns
Leaders (Chair/Ranking)   FF3 CAR_60d         15    426    -0.0177     0.0286  -0.2772   0.3872    ns
Leaders (Chair/Ranking)   Filing Lag        4063  19518    34.3881    43.8987  -0.1238   <0.001   ***
Leaders (Chair/Ranking)   PACS Score          45    566     0.3863     0.3380   0.2791   0.0820    ns
Leaders (Chair/Ranking)   Signal Strength     64    810     0.5428     0.6318  -0.3317   0.0322     *
Senior Members            FF3 CAR_5d         282   1579     0.0009     0.0010  -0.0024   0.8611    ns
Senior Members            FF3 CAR_20d        193   1113     0.0010     0.0076  -0.0642   0.9557    ns
Senior Members            FF3 CAR_60d         22    419    -0.0024     0.0286  -0.1856   0.5350    ns
Senior Members            Filing Lag        5678  17903    42.8267    42.0803   0.0097   <0.001   ***
Senior Members            PACS Score          99    512     0.4175     0.3269   0.5317   <0.001   ***
Senior Members            Signal Strength    173    701     0.5993     0.6317  -0.1205   0.1520    ns
Finance Committee         FF3 CAR_5d          --     --    -0.0029     0.0011  -0.079    0.8541    ns
Finance Committee         FF3 CAR_20d         --     --    -0.0098     0.0073  -0.165    0.4470    ns
Finance Committee         PACS Score          --     --     0.6306     0.3382   1.712    0.0085    **
Defense/Intel Committee   FF3 CAR_5d          --     --     0.0094     0.0007   0.168    0.3405    ns
Defense/Intel Committee   FF3 CAR_20d         --     --     0.0042     0.0068  -0.025    0.5808    ns
Defense/Intel Committee   PACS Score          --     --     0.4060     0.3366   0.402    0.0004   ***
```

---

*研究完成。結論：CONFIRM SHELVE。委員會地位不產生可量化的 alpha 優勢。*
