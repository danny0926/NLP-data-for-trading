---
name: research
description: "研發 Pipeline 指揮官。完整研究循環：假說 → 實驗設計 → 回測驗證 → 分析結論。可一鍵跑完整流程或逐步執行子 skill。Use when 'research', '研究', '測試假說', 'A/B test', 'pipeline iteration', 'RB研究'."
argument-hint: <hypothesis or research question>
allowed-tools: Read, Glob, Grep, Bash, Task
---

# /research — 研發 Pipeline 指揮官

協調 5 個子 skill 完成完整研究循環。

**研究主題**: $ARGUMENTS

## Pipeline 總覽

```
/research-scope   → 問題定義 + 背景調查 + 偏差預檢
       ↓ (人工確認)
/research-design  → A/B 實驗設計 + 成功標準
       ↓ (人工確認)
/research-run     → 實作 + 執行回測 [fork, 自主執行]
       ↓ (等待結果)
/research-analyze → 結果分析 + 偏差快篩
       ↓ (人工確認)
/research-log     → 結論判定 + 寫入 research_log
```

## 使用方式

### 方式 A：逐步執行（推薦，可介入）
```
/research-scope "委員會主席交易是否有更高 alpha"
  → 確認問題定義
/research-design
  → 確認實驗設計
/research-run
  → 等待回測完成
/research-analyze
  → 確認分析結果
/research-log
  → 記錄結論
```

### 方式 B：一鍵跑完整流程
當用戶說 `/research <topic>` 且沒有指定子步驟時，**依序呼叫所有子 skill**。

每個子 skill 完成後，簡短報告結果並詢問：
> "繼續下一步？[Y / 修改 / 停止]"

如果用戶選擇「修改」，等待指示後重跑該步。
如果用戶選擇「停止」，將目前進度存入 `docs/research_state.json`。

## 研究狀態追蹤

每個子 skill 完成後，更新 `docs/research_state.json`：

```json
{
  "topic": "委員會主席 alpha 研究",
  "rb_id": "RB-010",
  "status": "in_progress",
  "current_phase": "design",
  "started_at": "2026-02-28",
  "phases": {
    "scope": {"status": "done", "type": "ALPHA", "risk": "low"},
    "design": {"status": "in_progress"},
    "run": {"status": "pending"},
    "analyze": {"status": "pending"},
    "log": {"status": "pending"}
  }
}
```

## 研究類型速查

| 類型 | 關鍵字 | 子 skill 重點 |
|------|--------|-------------|
| ALPHA | alpha, CAR, 超額報酬 | scope 查 RB 歷史 → design 設 event study 對照 |
| SIGNAL | 信號, SQS, 收斂 | scope 查信號品質 → design 設 A/B 比較 |
| DATA | 新數據源, API, 交叉比對 | scope 做 spike → design 評估整合架構 |
| TIMING | 時機, VIX, filing lag | scope 查現有參數 → design 設分組回測 |

## Hard Rules

1. **不跳步** — 每一步都要做，除非用戶明確說跳過
2. **Alpha > 5% CAR = 停止** — 任何階段發現都立即暫停（可能有 look-ahead bias）
3. **一次一個實驗** — 不要同時跑多個不相關的假說
4. **所有結果寫入 research_log** — 包括失敗的
5. **RB 編號連續** — 查最新 RB-XXX，新研究用下一個
