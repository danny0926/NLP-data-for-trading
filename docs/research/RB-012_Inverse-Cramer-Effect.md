# Research Brief: Inverse Cramer Effect — 作為驗證信號的可行性評估
> 日期：2026-03-07 | 研究員：Research Lead | 狀態：Draft | 編號：RB-012

## 問題定義

**為什麼要研究這個？**
我們的社群媒體情報管線 (`social_nlp.py`) 已內建 Inverse Cramer 反轉邏輯——當偵測到 Jim Cramer 推薦時自動翻轉 sentiment。但這個反轉的統計基礎有多強？是否應該正式整合進 PACS 評分公式，還是僅作為 meme 級提示？

**與北極星指標的關係：**
如果 Inverse Cramer 信號有真正的 alpha，每週可多產出 2-5 個可行動文本信號。如果只是 meme，那麼目前的寬鬆反轉可能引入噪音，反而降低信號品質。

## 研究方法

1. **學術文獻搜尋** — 搜尋 "Inverse Cramer"、"Jim Cramer stock picks performance"、"Mad Money contrarian indicator" 相關研究
2. **SJIM ETF 實際績效** — 蒐集 Inverse Cramer Tracker ETF (SJIM) 從開盤到清算的完整表現
3. **量化追蹤器分析** — Quiver Quantitative 的 Inverse Cramer Strategy 回測數據
4. **現有程式碼審查** — 檢視我們系統中 Cramer 反轉的實作方式與影響範圍

## 發現摘要

### 發現一：學術研究顯示 Cramer 選股能力確實低於大盤，但 alpha 極小

Wharton 研究 (Hartley & Olson, 2016) 分析 Cramer 的 Action Alerts PLUS 慈善信託 17+ 年表現：
- **AAP 年化報酬：4.08%** vs **S&P 500：7.07%**（差距 ~3%/yr）
- **Sharpe Ratio：0.16** vs S&P 500 **0.41**（風險調整後大幅落後）
- **年化波動率：17.65%** vs S&P 500 **14.16%**（承擔更多風險卻獲得更少報酬）
- 研究歸因：長期持有大量現金部位（慈善捐贈用途）導致 underleveraged

Penn State 學位論文 (2017) 評估 Cramer 選股歷史表現，結論為：推薦後短期有注意力驅動的價格衝擊，但中長期回歸甚至反轉。

來源：[Wharton Study via IFA](https://www.ifa.com/articles/cramer_chasing_mad_money) | [Penn State Thesis](https://honors.libraries.psu.edu/catalog/17814) | [ResearchGate Paper](https://www.researchgate.net/publication/260321449_How_Mad_is_Mad_Money_Jim_Cramer_as_a_Stock_Picker_and_Portfolio_Manager)

### 發現二：SJIM ETF 實戰慘敗 — Inverse Cramer 不等於印鈔機

SJIM (Inverse Cramer Tracker ETF) 由 Tuttle Capital Management 於 2023-03-01 發行：
- **存續期間**：~10 個月（2023-03 至 2024-01 清算）
- **淨資產**：僅 $2.37M（極度缺乏投資人信心）
- **費用率**：1.20%（主動管理 ETF）
- **YTD 報酬 (截至清算前)**：**-8.31%**，同期 S&P 500 **+9.47%**
- **結局**：2024 年 1 月 Board 決議有序清算

這是 Inverse Cramer 策略在真實市場中最直接的壓力測試。結果明確：作為系統化策略，反向 Cramer **虧損**。

來源：[YCharts SJIM](https://ycharts.com/companies/SJIM:DL) | [Yahoo Finance SJIM](https://finance.yahoo.com/quote/SJIM/) | [CoinTelegraph Report](https://cointelegraph.com/news/jim-cramer-inverse-etf-shuts-down-10-months-after-launch)

### 發現三：Quiver Quantitative 長期回測 — 43% 勝率，負 Sharpe

Quiver Quantitative 從 2021-01 至今持續追蹤 Inverse Cramer Strategy（做空 Cramer 前 30 天推薦最多的 10 檔 + 做多大盤對沖）：
- **CAGR**：1.81%（遠低於大盤）
- **Win Rate**：**43.12%**（低於 50% — 比丟硬幣還差）
- **Sharpe Ratio**：**-0.087**（負值 = 風險調整後虧損）
- **最大回撤**：**-46.30%**（極端風險）
- **Alpha**：**0.00**（字面上零 alpha）
- **Beta**：-0.24
- **總交易數**：3,244

關鍵數據：平均獲利交易 +0.61%，平均虧損交易 -0.47%。看似 profit factor > 1，但 43% 勝率意味著虧損次數遠多於獲利次數，整體盈虧比不足以覆蓋交易成本。

來源：[Quiver Strategies](https://www.quiverquant.com/strategies/s/Inverse%20Cramer/)

### 發現四：短期內偶有獲利期（regime-dependent），但不可持續

- Q1 2023 曾達到 +6.59% YTD 超額報酬（策略歷史高點）
- 2022 年（熊市）表現相對較好——Cramer 在牛市中推薦多頭股更容易被 mean-revert
- 但 2023 下半年（牛市回歸）策略迅速回吐所有獲利
- 結論：Inverse Cramer 本質上是**做空注意力溢價**，在牛市結構性虧損

來源：[Seeking Alpha Q1 2023](https://seekingalpha.com/article/4590547-inverse-jim-cramer-strategy-q1-2023) | [Finbold 2023](https://finbold.com/heres-how-much-copy-trading-inverse-jim-cramer-portfolio-gained-in-2023/)

### 發現五：Finance Club 量化分析 — Alpha 0.05%，統計顯著但經濟不顯著

ETH Zurich Finance Club 分析 ~30,000 則 Cramer 推文，4 年回測：
- **Alpha**：0.05%（統計顯著但經濟上無意義）
- **Beta**：~1.0（報酬幾乎完全來自市場曝險）
- 作者自述：「此為 coding 學習專案，不構成交易建議」

來源：[Finance Club](https://www.financeclub.ch/blog/can-inverse-jim-cramer-generate-alpha)

## 方案比較

| 方案 | 優點 | 缺點 | 成本 | 風險 |
|------|------|------|------|------|
| **A. 全面整合進 PACS** — 加入 Cramer 反向作為 PACS 第 5 維度 | 增加信號多樣性 | 43% WR + 0 alpha，會引入系統性噪音 | M (需修改 PACS 公式 + 回測) | 高：基於 meme 而非實證的權重會汙染整個評分體系 |
| **B. 保留現有反轉但不加權** — 維持 `social_nlp.py` 的 sentiment flip，但 PACS 不給額外權重 | 零開發成本，不引入噪音 | Cramer 信號仍通過 impact_score 門檻進入 alpha_signals | S (無需修改) | 低：最壞情況是偶爾一個弱信號 |
| **C. 降級為提示標籤** — 移除自動反轉，改為標記 "Inverse Cramer flag" 供人工參考 | 最誠實反映證據品質 | 需要修改 `social_nlp.py` prompt | S (小幅修改) | 最低：不自動反轉，避免 false confidence |
| **D. 不做 (維持現狀)** | 零工作量 | 目前的 `CRAMER_CONTRARIAN_NOTE` 宣稱「推薦後 30 天平均 -5%」，這個數字 **無任何來源支撐**，是虛構的 | 0 | 中：prompt 中的虛假數據可能誤導 Gemini 分析 |

## 建議行動

**推薦方案：C — 降級為提示標籤 + 修正虛假 prompt**

理由：
1. **零 alpha、43% WR、負 Sharpe** — 三重否定，不具備整合進量化系統的資格
2. **SJIM ETF 實戰失敗** — 真金白銀的市場驗證已經否決了這個策略
3. **目前 prompt 中有虛假數據** — `CRAMER_CONTRARIAN_NOTE` 聲稱「推薦後 30 天平均 -5%」，但所有研究都顯示 alpha 接近 0，不是 -5%。這個虛假數字必須修正
4. **作為人類直覺輔助仍有價值** — Cramer 的推薦確實會造成短期注意力溢價，知道某檔股票被 Cramer 推薦是有用的「情境資訊」，但不應自動化交易

## 具體實作變更（如果採用方案 C）

### 1. 修改 `src/social_nlp.py` — 修正虛假 prompt

```python
# 修改前 (L174-177):
CRAMER_CONTRARIAN_NOTE = """
⚠️ 此人物為已知反向指標。Inverse Cramer 效應：推薦後 30 天平均 -5%。
sentiment 應反轉：他推薦 = Bearish，他看壞 = Bullish。
"""

# 修改後:
CRAMER_CONTRARIAN_NOTE = """
⚠️ 注意：Jim Cramer 為高曝光度電視評論員。學術研究顯示其選股長期低於大盤 (AAP 年化 4.08% vs S&P 7.07%)，
但 "Inverse Cramer" 策略回測同樣無 alpha (Quiver: 43% WR, Sharpe -0.087)。
分析此人推薦時：
1. 不要自動反轉 sentiment — 直接分析推薦的基本面邏輯
2. 標記 cramer_flag=true 供下游系統參考
3. 注意短期注意力效應：推薦後 1-3 天可能有溢價，隨後回歸
"""
```

### 2. 修改 `_gemini_analyze()` — 新增 cramer_flag 欄位

在 Cramer 信號的返回 dict 中加入：
```python
signal["cramer_flag"] = True
signal["cramer_note"] = "Inverse Cramer evidence: WEAK (43% WR, 0 alpha, SJIM ETF failed)"
```

### 3. 不修改 PACS 公式

`signal_enhancer.py` 的 PACS 四維度公式 (50/25/15/10) 保持不變。Cramer 信號不獲得額外權重或懲罰。

### 4. 修改 `social_targets.py` — 更新 Cramer 描述

```python
{
    "name": "Jim Cramer",
    ...
    "contrarian": False,  # 改為 False — 不再自動反轉
    "note": "CNBC 主持人。Inverse Cramer 統計證據薄弱 (RB-012)，保留作為情境標記",
}
```

## 風險與緩解

| 風險 | 機率 | 影響 | 緩解 |
|------|------|------|------|
| 修改後 Cramer 推薦的 bullish 信號「恰好」造成虧損 | 中 | 低（社群信號本來就是輔助角色，不是主力） | impact_score 門檻 (>=7) 已做品質控管 |
| 移除反轉後 Cramer 信號方向與國會交易交叉比對可能變化 | 低 | 低（Cramer 不是議員，不走 speech_trade_alignment 路徑） | 僅 KOL 路徑受影響，且 Cramer key_tickers=[] |
| 社群中 "Inverse Cramer" 迷因持續流行，用戶期待看到反轉信號 | 中 | 低 | 在 Dashboard 中標記 cramer_flag，說明為何不自動反轉 |

## 證據品質評估

**整體評級：Weak — 接近 Meme-only**

| 維度 | 評級 | 說明 |
|------|------|------|
| 學術研究 | Moderate | Wharton 研究確認 Cramer 低於大盤，但差距主因是現金部位，非選股能力 |
| ETF 實戰 | Strong (反面) | SJIM -8.31% vs SPY +9.47%，直接否決策略可行性 |
| 量化回測 | Strong (反面) | 43% WR, 0 alpha, -0.087 Sharpe，3244 筆交易樣本量充足 |
| 反向 alpha 存在性 | Weak | 所有研究指向 alpha ≈ 0，不是正也不是負 |
| 作為 regime-dependent 信號 | Moderate | 熊市有短期效用，但無法事前判斷 regime |

## 結論

**SHELVE — Inverse Cramer 效應不應作為自動化交易信號。**

核心真相：Jim Cramer 既不是好的選股者，也不是可靠的反向指標。他本質上是一個**噪音源**。最正確的處理方式是：承認他是噪音，標記他的推薦讓用戶知情，但不要基於噪音做系統性交易決策。

當前系統中 `CRAMER_CONTRARIAN_NOTE` 宣稱的「推薦後 30 天平均 -5%」是虛假數據，應立即修正，無論最終是否執行方案 C 的其他變更。

---

*本研究遵循 Competing Hypotheses 模式：H1(有效反向指標) vs H2(噪音) vs H3(regime-dependent)。*
*數據支持 H2，H3 有限支持但不具可操作性。*
