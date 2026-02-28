---
name: innovate
description: "創新 Pipeline 指揮官。前沿探索 → 跨域映射 → 數據源評估 → POC 原型 → 可行性裁定。可一鍵跑完或逐步執行。Use when 'innovate', '創新', '新方法', '探索', 'what if we try', '新數據源', '新想法'."
argument-hint: [topic or direction]
allowed-tools: Read, Glob, Grep, Bash, Task
---

# /innovate — 創新 Pipeline 指揮官

協調 4 個子 skill 完成完整創新探索。與 `/brainstorm`（純思考不寫碼）不同，`/innovate` 產出可執行的 POC。

**探索方向**: $ARGUMENTS

## Pipeline 總覽

```
/innovate-scan     → 方向偵測 + 前沿掃描（論文/GitHub/社群）
       ↓ (人工確認)
/innovate-map      → 跨域映射 + 數據源評估
       ↓ (人工確認)
/innovate-poc      → POC 原型實作 [自主執行]
       ↓ (等待結果)
/innovate-verdict  → 可行性裁定 + 記錄 + 銜接
```

## 使用方式

### 方式 A：逐步執行（推薦）
```
/innovate-scan "Committee hearing transcripts 做 NLP 信號"
  → 確認前沿報告
/innovate-map
  → 確認映射和數據評估
/innovate-poc
  → 等待 POC 完成
/innovate-verdict
  → 記錄裁定
```

### 方式 B：一鍵跑完整流程
當用戶說 `/innovate <topic>` 時，依序呼叫所有子 skill。
每步完成後詢問：
> "繼續下一步？[Y / 修改 / 停止]"

## 象限分類

```
              已知技術              未知技術
          +---------------+---------------+
已知問題   |  OPTIMIZE     |  TRANSFER     |
          |  優化現有信號    |  跨域遷移      |
          +---------------+---------------+
未知問題   |  DISCOVER     |  FRONTIER     |
          |  新數據源發現    |  前沿探索      |
          +---------------+---------------+
```

| 象限 | PAM 範例 |
|------|---------|
| OPTIMIZE | PACS 權重微調、VIX 區間重新劃分 |
| TRANSFER | 選舉權預測→交易信號、ESG 情緒→議員行為 |
| DISCOVER | USASpending 合約數據、委員會聽證文字稿 |
| FRONTIER | LLM 即時議員行為模型、圖神經網路議員關聯 |

## 狀態追蹤

每個子 skill 完成後更新 `docs/innovation_state.json`：

```json
{
  "topic": "Committee hearing NLP signal",
  "quadrant": "DISCOVER",
  "status": "in_progress",
  "phases": {
    "scan": {"status": "done"},
    "map": {"status": "in_progress"},
    "poc": {"status": "pending"},
    "verdict": {"status": "pending"}
  }
}
```

## Hard Rules

1. **必須搜外部資訊** — 至少 3 次 WebSearch
2. **POC 也要反 look-ahead bias** — 使用 filing_date, benchmark=SPY
3. **不直接改 production** — POC 放 `poc/` 目錄
4. **記錄所有探索** — 包括 PASS 的（寫入 innovation_log）
5. **給出明確裁定** — FAST-TRACK/PROMISING/SHELVE/PASS
