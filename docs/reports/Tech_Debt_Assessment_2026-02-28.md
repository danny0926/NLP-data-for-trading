# PAM 技術債評估報告

**日期**: 2026-02-28
**評估人**: CTO (Team Lead 代行)
**範圍**: `src/` 目錄下 35 個 Python 模組

---

## 評估摘要

| # | 技術債項目 | 嚴重度 | 優先級 | 狀態 |
|---|-----------|--------|--------|------|
| 1 | LLM JSON 解析脆弱 | Medium | P1 | OPEN |
| 2 | Senate Akamai bypass 可靠性 | Medium | P2 | MITIGATED |
| 3 | Legacy fetchers 清理 | Low | - | **RESOLVED** |
| 4 | src/main.py bare imports | Low | - | **RESOLVED** |
| 5 | Error handling 標準化 | Medium | P2 | OPEN |
| 6 | DB 連線管理散亂 (新發現) | High | P1 | OPEN |
| 7 | DB_PATH 硬編碼殘留 (新發現) | Low | P3 | OPEN |

**已解決**: 2/7 (Tech Debt #3, #4 在先前 sprint 已修復)
**需處理**: 5 項 (2× P1, 2× P2, 1× P3)

---

## 詳細評估

### TD-001: LLM JSON 解析脆弱 — P1 Medium

**位置**: `src/discovery_engine_v4.py:65-85` (`_extract_json()`)

**問題描述**:
使用 regex `(\{.*\}|\[.*\])` 從 LLM 自由文字輸出中提取 JSON。存在以下風險：
- Greedy match 可能抓到錯誤的 JSON 邊界
- 僅處理 trailing comma，不處理其他常見格式問題
- 失敗時 silently return None，無告警或 fallback

**影響範圍**:
- `discovery_engine_v4.py` 每次 AI Discovery 呼叫都經過此函數
- 目前功能正常（Gemini 2.5 Flash 輸出格式穩定），但換模型或 prompt 修改後可能斷裂

**現狀**: Gemini 支援 `response_mime_type="application/json"` 結構化輸出，但專案中 **0 處** 使用此功能。

**建議方案**:
1. **短期 (P1)**: 在 `_extract_json()` 加入 fallback 策略 — 先嘗試 `json.loads(text)`，再試 regex，最後 log warning
2. **中期 (P2)**: Discovery Engine 切換至 Gemini JSON mode (`response_mime_type="application/json"`)
3. **長期**: 統一所有 LLM 呼叫使用 structured output

**修復工時**: 短期 1hr, 中期 3hr, 長期 8hr
**不修復風險**: LLM 格式變化時 Discovery 全部失敗，且 silent failure 難以偵測

---

### TD-002: Senate Akamai Bypass 可靠性 — P2 Medium (已緩解)

**位置**: `src/etl/senate_fetcher.py`

**問題描述**:
使用 Playwright `headless=False` 繞過 Akamai Bot Manager。此方案隨時可能因 Akamai 更新而失效。

**已有緩解措施**:
- ✅ Capitol Trades 自動 fallback (`src/etl/pipeline.py:110-120`)
- ✅ WSL2 + Xvfb 生產環境穩定運行
- ✅ `extraction_log` 表記錄每次抓取結果

**缺少的**:
- ❌ 無主動健康檢查 (只有失敗時才知道)
- ❌ 無 Slack/Telegram 自動告警 (senate fetch 失敗時)
- ❌ Capitol Trades 也可能被 block (單點依賴)

**建議方案**:
1. 在 `smart_alerts.py` 加入 ETL 健康告警 (連續 2 次失敗 → Telegram 通知)
2. 加入每日 smoke test 驗證 Senate 端點可達性
3. 考慮第三個 fallback 來源 (如 OpenSecrets API)

**修復工時**: 2hr (告警) + 1hr (smoke test)
**不修復風險**: Senate 抓取無聲失敗數天才被發現

---

### TD-003: Legacy Fetchers 清理 — **已解決** ✅

**狀態**: 所有 legacy fetchers 已移至 `bk/` 目錄:
- `senate_fetcher_v1.py` → 已從 `src/` 移除
- `house_fetcher_v3_ajax.py` → 已從 `src/` 移除
- `congress_trading_fetcher.py` → 已從 `src/` 移除
- `main.py` → 已從 `src/` 移除

**驗證**: Grep 確認 `src/` 中無任何模組 import 這些 legacy 檔案。`bk/` 中的引用為歷史存檔，不影響運行。

---

### TD-004: src/main.py Bare Imports — **已解決** ✅

**狀態**: `src/main.py` 已不存在。所有活躍模組使用 `from src.xxx import` 或 `from .xxx import` (ETL 子模組)。

---

### TD-005: Error Handling 標準化 — P2 Medium

**現狀分析**:
- 自定義異常: **僅 1 個** (`TransformError` in `etl/llm_transformer.py:179`)
- `except Exception` / `except:` bare catches: **75 處** 跨 28 個模組
- 無統一 logging format (各模組自行 `logging.getLogger()`)
- 無異常分類 (網路錯誤、DB 錯誤、LLM 錯誤混在一起)

**Top 5 問題檔案** (bare except 最多):
| 檔案 | bare except 數量 |
|------|-----------------|
| `pdf_report.py` | 7 |
| `risk_manager.py` | 5 |
| `portfolio_simulator.py` | 3 |
| `discovery_engine_v4.py` | 3 |
| `daily_report.py` | 3 |

**建議方案**:
1. **短期**: 建立 `src/exceptions.py` — 定義 `PAMBaseError`, `ETLError`, `LLMError`, `DBError`, `SignalError`
2. **中期**: 逐步替換 bare except → 具體異常類型 (優先處理 ETL 和 Signal 模組)
3. **長期**: 統一 logging format 和 error reporting dashboard

**修復工時**: 短期 1hr, 中期 4hr, 長期 8hr
**不修復風險**: 除錯困難、silent failures、生產環境問題定位耗時

---

### TD-006: DB 連線管理散亂 — P1 High (新發現)

**現狀分析**:
- `sqlite3.connect()` / `DB_PATH` 引用: **142 處** 跨 29 個模組
- 每個函數各自 `sqlite3.connect()` → 操作 → `conn.close()`
- 無 context manager (`with` statement) 統一管理
- 無 connection pooling (SQLite 單檔鎖定問題)
- `discovery_engine_v4.py` 直接使用 `sqlite3.connect(self.db_path)` 而非通過 `database.py`

**風險**:
- 異常時 connection leak (close 不被呼叫)
- 並發寫入時 DB locked error
- DB schema 變更需要改 N 個地方

**建議方案**:
1. **短期 (P1)**: 在 `database.py` 加入 context manager `get_connection()`
2. **中期**: 各模組改用 `from src.database import get_connection`
3. **長期**: 考慮 SQLAlchemy 或 dataset 抽象層

```python
# 建議的 get_connection() pattern
from contextlib import contextmanager

@contextmanager
def get_connection(db_path=None):
    conn = sqlite3.connect(db_path or DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")  # 改善並發
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
```

**修復工時**: 短期 2hr, 中期 8hr (29 模組逐一遷移)
**不修復風險**: DB locked 錯誤、connection leak、難以遷移到其他 DB

---

### TD-007: DB_PATH 硬編碼殘留 — P3 Low

**現狀**: `config.py` 已集中定義 `DB_PATH`，但仍有 **5 個模組** hardcode `"data/data.db"`:
- `src/name_mapping.py:217, 276`
- `src/ticker_enricher.py:305, 411`
- `src/alpha_signal_generator.py:1168` (CLI help 字串)
- `src/politician_ranking.py:539` (CLI help 字串)
- `src/risk_manager.py:1240` (CLI help 字串)

**影響**: CLI help 字串中的 hardcode 影響低 (僅顯示用)。`name_mapping.py` 和 `ticker_enricher.py` 的 default 值需改為 `from src.config import DB_PATH`。

**修復工時**: 30min
**不修復風險**: 低，除非 DB 路徑改變

---

## 修復優先級總表

| 優先級 | 項目 | 工時估算 | 建議時程 |
|--------|------|---------|---------|
| **P1** | TD-006 DB 連線管理 (context manager) | 2hr | Sprint 1 |
| **P1** | TD-001 LLM JSON 解析 (fallback + warning) | 1hr | Sprint 1 |
| **P2** | TD-005 Error handling (exceptions.py) | 1hr | Sprint 1 |
| **P2** | TD-002 Senate 健康告警 | 2hr | Sprint 2 |
| **P2** | TD-005 Bare except 替換 (ETL 優先) | 4hr | Sprint 2 |
| **P3** | TD-007 DB_PATH hardcode 清理 | 0.5hr | Anytime |
| **中期** | TD-001 Gemini JSON mode | 3hr | Sprint 3 |
| **中期** | TD-006 全模組遷移至 get_connection | 8hr | Sprint 3-4 |

**總計**: ~21.5hr (分 4 個 Sprint，每 Sprint 約 5hr)

---

## 附錄: 正面發現

1. ✅ `src/config.py` 集中配置管理 — 良好模式
2. ✅ ETL Pipeline 有 fallback 架構 (Senate → Capitol Trades)
3. ✅ Pydantic 驗證 (ETL schemas) — 資料品質把關
4. ✅ `data_hash UNIQUE` 去重 — 防止重複寫入
5. ✅ `extraction_log` 審計追蹤 — ETL 可觀測性
6. ✅ 258 個測試案例 — 測試覆蓋持續改善
7. ✅ Legacy 清理完成 — 無死碼殘留在 `src/`
