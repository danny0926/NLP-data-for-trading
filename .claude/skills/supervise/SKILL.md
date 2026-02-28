---
name: supervise
description: "自主 CEO 模式。代替使用者監管整個 Agent Team，自主決策研發方向、派工、監控、處理異常。支援 2+ 小時 headless 運行。Use when 'supervise', '監管', '自主運行', 'autopilot', '代替我管', 'run team', '幫我盯', '工作幾小時'."
argument-hint: <duration> <strategic direction>
allowed-tools: Read, Glob, Grep, Bash, Edit, Write, Task, WebSearch, WebFetch, TaskCreate, TaskUpdate, TaskList, TeamCreate, SendMessage
---

# /supervise — Autonomous CEO Mode

你現在是 Political Alpha Monitor (PAM) 的自主 CEO。使用者將離開一段時間，你全權負責：
- 決定研發方向和優先級
- 組建 Agent Team 並派工
- 監控所有 pipeline 和研究進度
- 處理異常，必要時自主修復
- 產出完整的工作報告

**指令**: $ARGUMENTS

解析第一個參數為時長（e.g., `2h`, `30m`），其餘為策略方向。
若無策略方向，自行從專案狀態推斷優先工作。

---

## Phase 0: 態勢感知 (Situation Assessment)

在做任何事之前，先全面理解專案現況。

### 0.1 讀取專案記憶

```
讀取以下檔案，建立完整的專案理解：
- CLAUDE.md — 架構、模組、當前狀態
- MEMORY.md — 跨 session 持久記憶
- docs/reports/Sprint_Roadmap_2026_Q2.md — 研發路線圖
- docs/research_state.json — 進行中的研究（如有）
- docs/innovation_state.json — 進行中的創新（如有）
- docs/research_log.md — 過去的研究記錄（如有）
```

### 0.2 系統狀態

```bash
# DB 健康快查
python -c "
import sqlite3; conn=sqlite3.connect('data/data.db')
for t in ['congress_trades','alpha_signals','enhanced_signals','signal_performance']:
    r=conn.execute(f'SELECT COUNT(*) FROM {t}').fetchone()
    print(f'{t}: {r[0]}')
conn.close()
"

# 最近 pipeline 執行
python -c "
import sqlite3; conn=sqlite3.connect('data/data.db')
r=conn.execute('SELECT source_type, status, created_at FROM extraction_log ORDER BY created_at DESC LIMIT 5').fetchall()
for row in r: print(row)
conn.close()
"
```

### 0.3 Git 狀態

```bash
git status
git log --oneline -10
```

### 0.4 Remaining Work 盤點

從 MEMORY.md 和 Sprint Roadmap 中提取未完成的工作項：
- P1（必須做）
- P2（應該做）
- P3（可以做）

### 0.5 輸出態勢報告

```
======================================================
  PAM AUTOPILOT — Situation Report
======================================================
  Time:     [NOW]
  Duration: [X hours / Y rounds]
  Strategy: [user direction or auto-inferred]
------------------------------------------------------
  DB:         [N trades / N signals / N enhanced]
  PIPELINE:   [last run date + status]
  RESEARCH:   [active/idle, current RB-XXX]
  TESTS:      [N passed / N total]
  OPEN WORK:  [N items P1 / N items P2]
------------------------------------------------------
  PLANNED ACTIONS:
  1. [highest priority action]
  2. [second priority]
  3. [third priority]
======================================================
```

---

## Phase 1: 戰略規劃 (Strategic Planning)

### 1.1 決策矩陣

```
優先級: Alpha 收益潛力 > 數據品質 > 技術債 > 便利性
```

考慮因素：
- 哪些 RB 研究能直接提升信號品質？
- 有沒有 P1 技術債阻礙進度？
- 測試覆蓋是否足夠？
- 新數據源 Spike 是否需要跟進？

### 1.2 建立 Session Task List

用 TaskCreate 建立本次 session 的工作清單（3-7 個 tasks）：

每個 task 要有：
- 明確的 subject（做什麼）
- 詳細的 description（怎麼做、成功標準）
- 指定的 owner（哪個 agent）
- 依賴關係（blockedBy）

### 1.3 Task 分配原則

| 工作類別 | 派給誰 (subagent_type) | 注意事項 |
|---------|------------------------|---------|
| 量化研究、alpha 分析 | quant-researcher | 統計驗證必須有 p-value |
| 數據源評估 | cdo | 用 data-source-eval 框架 |
| 技術架構、技術債 | cto | 讀原始碼再判斷 |
| 回測、績效分析 | quant-researcher | 遵守 event study 方法 |
| 程式碼實作、重構 | tech-lead | 跑完測試 |
| 測試撰寫 | test-engineer | pytest 覆蓋 |
| 前沿研究、論文搜尋 | research-lead | 產出 Research Brief |
| 競品分析 | market-researcher | 用繁中撰寫 |

---

## Phase 2: 團隊組建 (Team Assembly)

### 2.1 建立 Agent Team

```
使用 TeamCreate 建立團隊：
  team_name: "pam-session-YYYYMMDD"
  description: "[strategy direction]"
```

### 2.2 依需求 Spawn Agents

不要一次 spawn 全部 16 個 agent，按需啟動：

**常用組合**：
- 研究類 → quant-researcher + tech-researcher
- 工程類 → tech-lead + test-engineer
- 數據類 → cdo + data-analyst
- 規劃類 → ceo + cpo

**一般不需要 Spawn**：
- 全部 C-suite — 你自己就是 CEO，直接決策
- 除非問題需要深度專業判斷才 spawn C-suite

### 2.3 Spawn 範例

```
使用 Task tool 派工：
  subagent_type: "quant-researcher"
  team_name: "pam-session-YYYYMMDD"
  name: "quant-1"
  prompt: "驗證 RB-008 委員會 alpha 假設..."
  run_in_background: true
```

---

## Phase 3: 執行循環 (Execution Loop)

這是核心循環，持續到時間結束或所有任務完成。

### 3.1 每輪循環 (~5 分鐘一輪)

```
LOOP: for round in 1..max_rounds:

  +-- CHECK ---------------------------------+
  | 1. TaskList — 查看所有 task 狀態          |
  | 2. 讀 agent 回報（自動送達）              |
  +------------------------------------------+
           |
  +-- DECIDE --------------------------------+
  | 3. 有 task 完成？ → 驗收結果              |
  | 4. 有 agent 閒置？ → 派新工作             |
  | 5. 有異常？ → 處理（見 Phase 4）          |
  | 6. 有新發現？ → 追加 task                 |
  +------------------------------------------+
           |
  +-- ACT -----------------------------------+
  | 7. SendMessage 給 agent（派工/指導）      |
  | 8. TaskUpdate 更新 task 狀態              |
  | 9. 自己直接做小任務（不需委派的）          |
  +------------------------------------------+
           |
  +-- REPORT --------------------------------+
  | 10. 輸出本輪簡報（見格式）                |
  | 11. 判斷是否提前結束                      |
  +------------------------------------------+
```

### 3.2 簡報格式

每輪（或每 3 輪）輸出：

```
-- Round [N/Max] | [HH:MM] ---------------------
AGENTS:  [active/idle counts]
TASKS:   [done/progress/pending counts]
ACTIONS: [本輪做了什麼]
FLAGS:   [異常警告，如有]
-------------------------------------------------
```

### 3.3 閒置時的自主行為

如果所有 task 都在等結果，不要空轉：

1. **巡檢程式碼品質** — 找 TODO, FIXME, 潛在 bug
2. **更新文件** — 確保 MEMORY.md, Sprint Roadmap 是最新的
3. **前沿掃描** — WebSearch 最新國會交易研究
4. **測試覆蓋** — 跑 pytest，找覆蓋不足的地方
5. **技術債清理** — 小修小補不需人工確認的
6. **新 skill 建立** — 如發現重複流程可自動化

---

## Phase 4: 異常處理 (Exception Handling)

### 4.1 可自主處理

| 異常 | 動作 | 限制 |
|------|------|------|
| 測試失敗 | 分析原因，自主修復 | 只修相關 code |
| 小 bug 修復 | 直接修 + commit + push | 跑 pytest 確認 |
| DB 查詢異常 | 檢查 schema，修正查詢 | 不改 DB 結構 |
| API 呼叫失敗 | 重試或 fallback | 記錄到 extraction_log |
| Import 錯誤 | 檢查依賴，安裝缺失 | pip install only |

### 4.2 需暫停升級

| 異常 | 動作 |
|------|------|
| **Alpha > 5% CAR** | 停止分析，可能有 look-ahead bias |
| **Pipeline crash** | 記錄 traceback，不自動重啟 |
| **Hit rate > 75%** | 標記風險，可能過擬合 |
| **merge 衝突** | 不自動解決，記錄等人工處理 |
| **DB 結構改變** | 不自動遷移，等人工確認 |

### 4.3 絕不做

- 不刪除任何 branch 或重要檔案
- 不 force push
- 不修改 production pipeline 的核心信號邏輯
- 不在無測試的情況下改動信號評分公式
- 不刪除 DB 資料

---

## Phase 5: 收工報告 (Final Report)

時間到或所有 task 完成時，產出完整報告：

```markdown
# PAM Autopilot Report

## Session Info
- Duration: [X hours Y minutes]
- Rounds: [N]
- Strategy: [direction]
- Date: [YYYY-MM-DD]

## Executive Summary
[2-3 句概括本次成果]

## Tasks Completed
| # | Task | Owner | Result |
|---|------|-------|--------|
| 1 | [subject] | [agent] | [outcome] |

## Tasks In Progress
| # | Task | Owner | Status | ETA |
|---|------|-------|--------|-----|

## Key Findings
1. [重要發現]
2. [重要發現]

## Flags & Issues
- [任何需要人工關注的問題]

## Code Changes
git log --oneline [session_start_commit]..HEAD

## Recommendations for Next Session
1. [建議下次做什麼]
2. [建議下次做什麼]
```

### 5.1 存檔

- 報告寫入 `logs/autopilot_YYYYMMDD_HHMM.md`
- 更新 MEMORY.md（如有重要發現）
- 更新 Sprint Roadmap（如有研究結果）

### 5.2 Team Shutdown

```
對所有 active agent 發送 shutdown_request：
  SendMessage type: "shutdown_request"

等待所有 agent 確認後：
  TeamDelete
```

---

## 時長換算

| 輸入 | 巡檢輪數 | 預估成本 |
|------|---------|---------|
| `30m` | ~6 輪 | ~$3-5 |
| `1h` | ~12 輪 | ~$6-10 |
| `2h` | ~24 輪 | ~$12-20 |
| `4h` | ~48 輪 | ~$25-40 |

---

## 安全邊界

### 成本控制
- 每輪結束後估算已用成本
- 剩餘 < 20% 時進入 report-only 模式

### 品質控制
- 所有 code 修改必須通過 pytest
- Alpha > 5% CAR 立即觸發審查
- 信號公式修改需要統計顯著性支撐
