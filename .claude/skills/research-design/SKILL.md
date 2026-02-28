---
name: research-design
description: "研究 Phase 2：A/B 實驗設計、成功標準、guardrails。Use when 'experiment design', '實驗設計', 'A/B setup'."
allowed-tools: Read, Glob, Grep
---

# /research-design — 實驗設計

接續 `/research-scope` 的結果，設計對照實驗。

先讀 `docs/research_state.json` 取得研究主題和類型。

## Step 1: 定義 A/B 對照

| 項目 | Baseline (A) | Treatment (B) |
|------|-------------|---------------|
| 描述 | 現有做法 | 改進做法 |
| 樣本 | [全部議員交易] | [篩選後子集] |
| 參數 | [列出] | [列出差異] |
| 資料期間 | [相同] | [相同] |

**一次只改一個變數**，除非明確設計為多因子實驗。

## Step 2: 成功標準

### Primary Metric（至少選一）

| Metric | 達標門檻 |
|--------|---------|
| CAR_5d | 改善 ≥ 0.3% |
| CAR_20d | 改善 ≥ 0.5% |
| Hit Rate | 改善 ≥ 3% |
| Alpha vs SPY | 正向且統計顯著 (p<0.05) |

### Guardrails（不可違反）

- [ ] Alpha ≤ 5% CAR（否則觸發 look-ahead bias 審查）
- [ ] Hit Rate ≤ 75%（否則可能過擬合）
- [ ] 樣本量 ≥ 30 筆交易（統計顯著性需要足夠樣本）
- [ ] 使用 filing_date（非 transaction_date）作為事件日
- [ ] Benchmark = SPY 同期報酬

## Step 3: 實作路徑

選擇一條路徑：

**A — Event Study 回測**：
1. 使用 `src/alpha_backtest.py` 框架
2. 定義子集篩選條件
3. 計算 CAR_5d/20d/60d vs SPY

**B — 統計檢定**：
1. 使用 `src/stat_test.py` 框架
2. 定義分組（control vs treatment）
3. 執行 t-test, Mann-Whitney U, bootstrap

**C — 獨立腳本**：
1. 寫 minimal 測試腳本
2. 只測核心假說
3. 確認可行後再整合到主系統

## Step 4: 輸出 Design Doc

```markdown
## Experiment Design: [Topic] (RB-[XXX])

### A/B Setup
| Item | Baseline (A) | Treatment (B) |
|------|-------------|---------------|
| ... | ... | ... |

### Success Criteria
- Primary: [metric] ≥ [threshold]
- Guardrails: [all checked]

### Implementation Path
- Path: [A/B/C]
- Branch: `research/<topic>`
- Script: [filename]

### Next: `/research-run`
```

向用戶報告設計，等待確認。
