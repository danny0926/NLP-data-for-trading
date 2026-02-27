# LLM-Driven ETL Fusion Pipeline 設計文件

> **日期**: 2026-02-14
> **狀態**: 已實作並驗證通過

---

## 1. Understanding Summary

| 項目 | 內容 |
|------|------|
| **Building** | LLM-Driven ETL Fusion Pipeline — 用 LLM 作為資料解析核心的國會交易資料管線 |
| **Because** | 現有爬蟲依賴硬編碼格式解析，維護成本高；House PDF 完全未處理；每新增來源都要重寫 parser |
| **For** | 自動化系統使用，產出結構化交易紀錄供 discovery engine 分析 |
| **Constraints** | Gemini API (`GOOGLE_API_KEY`)、SQLite (`data/data.db`)、Python 3.9+ |
| **Non-goals** | 不重寫 Extract 層反爬蟲邏輯、不做即時串流處理、不建 UI |
| **Assumptions** | Gemini Flash 能穩定解析 Senate HTML 和 House PDF；API 成本可接受 |

---

## 2. 架構概覽

```
┌──────────────────────────────────────────────────────────┐
│                    Orchestrator                           │
│         (調度、監控、錯誤佇列、重試策略)                      │
└────┬────────────────────┬───────────────────┬─────────────┘
     │                    │                   │
     ▼                    ▼                   ▼
╔════════════╗    ╔══════════════╗    ╔══════════════╗
║  EXTRACT   ║    ║  TRANSFORM   ║    ║    LOAD      ║
║  (傳統)    ║    ║  (LLM 驅動)  ║    ║   (規則)     ║
╠════════════╣    ╠══════════════╣    ╠══════════════╣
║ curl_cffi  ║    ║ 格式分類器   ║    ║ Pydantic     ║
║ + CSRF     ║──→║ 專用 Prompt  ║──→║ 驗證         ║
║ + PDF DL   ║    ║ Gemini API   ║    ║ SHA256 去重  ║
║            ║    ║ 重試機制     ║    ║ SQLite 寫入  ║
╚════════════╝    ╚══════════════╝    ╚══════════════╝
```

**核心原則**: LLM 只用在 Transform 層（語意理解），Extract 和 Load 使用確定性邏輯。

---

## 3. 設計詳情

### 3.1 Pydantic Schema（統一資料合約）

```python
from pydantic import BaseModel, Field, validator
from typing import Optional, Literal
from datetime import date

class CongressTrade(BaseModel):
    """統一的國會交易紀錄 schema"""
    politician_name: str = Field(..., description="議員全名")
    chamber: Literal["Senate", "House"]
    transaction_date: date
    filing_date: date
    ticker: Optional[str] = Field(None, max_length=10)
    asset_name: str = Field(..., description="資產名稱")
    asset_type: str = Field(default="Stock")
    transaction_type: Literal["Buy", "Sale", "Exchange"]
    amount_range: str = Field(..., description="金額區間，如 $1,001 - $15,000")
    owner: Optional[str] = Field(None, description="Owner: Self/Spouse/Child/Joint")
    comment: Optional[str] = None
    source_url: str = Field(..., description="原始揭露頁面 URL")

    @validator('ticker')
    def clean_ticker(cls, v):
        if v in ('--', 'N/A', '', 'n/a'):
            return None
        return v.upper().strip() if v else None

    @validator('amount_range')
    def validate_amount(cls, v):
        if '$' not in v:
            raise ValueError(f"金額區間格式異常: {v}")
        return v

class ExtractionResult(BaseModel):
    """LLM 萃取結果的包裝"""
    trades: list[CongressTrade]
    source_format: Literal["senate_html", "house_pdf", "thirteenf_xml", "unknown"]
    confidence: float = Field(..., ge=0.0, le=1.0)
    raw_record_count: int = Field(..., description="原始資料中的紀錄數，用於比對是否遺漏")
```

### 3.2 Extract 層 — UniversalFetcher 介面

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

class SourceType(Enum):
    SENATE_HTML = "senate_html"
    HOUSE_PDF = "house_pdf"
    THIRTEEN_F = "thirteenf_xml"

@dataclass
class FetchResult:
    source_type: SourceType
    content: bytes          # 原始內容 (HTML / PDF / JSON bytes)
    content_type: str       # "text/html" / "application/pdf" / "application/json"
    source_url: str
    metadata: dict          # 額外資訊 (議員姓名、filing ID 等)

class BaseFetcher(ABC):
    @abstractmethod
    def fetch(self, **kwargs) -> list[FetchResult]:
        ...
```

- `content: bytes` — 統一用 bytes，不預先解碼
- `metadata: dict` — 放 fetcher 已知的資訊，減少 LLM 萃取工作量
- 沿用現有 curl_cffi + CSRF 反爬蟲邏輯

### 3.3 Transform 層 — LLM 解析核心

**流程**:
1. **Format Router** — 根據 `source_type` 選擇處理路徑
2. **Content Preparation** — HTML 清理 / PDF 轉圖片 / JSON 直傳
3. **LLM Call** — Gemini Flash (text) 或 Gemini Vision (PDF 圖片)
4. **Parse & Validate** — JSON 萃取 → Pydantic 驗證 → 失敗時附錯誤重試 (≤3 次)

**Prompt 策略**: 分類 Prompt — 已知來源用專用 prompt，未知來源用通用 prompt。

**PDF 處理**: Gemini Vision — PDF 轉圖片後用多模態 LLM 直接「看」，表格結構保留最完整。

**重試機制**:
```python
for attempt in range(MAX_RETRIES):
    raw_output = call_llm(prompt, content)
    json_data = extract_json(raw_output)
    try:
        result = ExtractionResult(**json_data)
        return result
    except ValidationError as e:
        prompt = append_error_feedback(prompt, str(e))
raise TransformError(f"LLM 解析失敗 ({MAX_RETRIES}次)")
```

### 3.4 Load 層 — 統一新表 + 驗證

**新資料庫表**:

```sql
CREATE TABLE IF NOT EXISTS congress_trades (
    id TEXT PRIMARY KEY,
    chamber TEXT NOT NULL,             -- 'Senate' / 'House'
    politician_name TEXT NOT NULL,
    transaction_date DATE,
    filing_date DATE,
    ticker TEXT,
    asset_name TEXT,
    asset_type TEXT DEFAULT 'Stock',
    transaction_type TEXT,
    amount_range TEXT,
    owner TEXT,
    comment TEXT,
    source_url TEXT,
    source_format TEXT,
    extraction_confidence REAL,
    data_hash TEXT UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_congress_politician ON congress_trades(politician_name);
CREATE INDEX idx_congress_ticker ON congress_trades(ticker);
CREATE INDEX idx_congress_date ON congress_trades(transaction_date);

CREATE TABLE IF NOT EXISTS extraction_log (
    id TEXT PRIMARY KEY,
    source_type TEXT NOT NULL,
    source_url TEXT,
    confidence REAL,
    raw_record_count INTEGER,
    extracted_count INTEGER,
    status TEXT DEFAULT 'success',     -- success / partial / failed / manual_review
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Load 流程**:
- `confidence < 0.7` → 寫入 `extraction_log` (status='manual_review')，不入 `congress_trades`
- `confidence ≥ 0.7` → 計算 SHA256 hash → 去重 → INSERT
- 業務檢查異常 → 仍入庫，在 `extraction_log` 標記 'partial'

**向後相容**: 經程式碼分析確認，`discovery_engine_v4.py` 完全不讀取 `senate_trades` / `house_trades`，無向後相容包袱。舊表保留不刪，新 pipeline 只寫 `congress_trades`。

---

## 4. 檔案結構

```
src/
├── etl/
│   ├── __init__.py
│   ├── schemas.py                ← Pydantic models
│   ├── base_fetcher.py           ← BaseFetcher ABC + FetchResult
│   ├── senate_fetcher.py         ← 沿用 curl_cffi 邏輯
│   ├── house_fetcher.py          ← curl_cffi + PDF 下載
│   ├── llm_transformer.py        ← LLM 解析核心
│   ├── loader.py                 ← 驗證 + 去重 + SQLite
│   └── pipeline.py               ← Orchestrator
│
├── senate_fetcher_v1.py          ← 保留 (舊版參考)
├── house_fetcher_v3_ajax.py      ← 保留
├── discovery_engine_v4.py        ← 保留 (獨立模組)
└── database.py                   ← 新增表定義

run_etl_pipeline.py               ← 新入口點
```

---

## 5. 實作順序

| Phase | 內容 | 依賴 |
|-------|------|------|
| **Phase 1** | schemas.py + base_fetcher.py + database.py 新增表 | 無 |
| **Phase 2** | senate_fetcher.py + llm_transformer.py (Senate prompt) + loader.py | Phase 1 |
| **Phase 3** | house_fetcher.py + llm_transformer.py (Vision prompt) | Phase 2 |
| **Phase 4** | pipeline.py + run_etl_pipeline.py | Phase 3 |

---

## 6. 決策記錄

| 決策 | 考慮過的替代方案 | 選擇理由 |
|------|----------------|---------|
| LLM 只用在 Transform 層 | 全 Agent / 全傳統 | Extract 和 Load 不需語意理解，確定性邏輯更可靠 |
| 分類 Prompt 策略 | 通用 Prompt / 混合式 | 已知來源用專用 prompt 品質更高 |
| Gemini Vision 解析 PDF | pdfplumber + LLM / 並行 | 表格結構保留最完整，已有 API 基礎設施 |
| Pydantic 強制驗證 | 寬鬆 JSON 解析 | 金融資料不容許幻覺，必須硬性驗證 |
| 統一 congress_trades 新表 | 維持雙表 | 無向後相容包袱，統一更乾淨 |
| ETL + Top 3 融合架構 | 純簡單管線 / 全 Agent | 關注點分離但不過度工程化 |

---

## 7. 待解決問題

- [ ] PDF 轉圖片的具體工具選型 (pdf2image / PyMuPDF)
- [ ] Gemini Vision API 單次可處理的頁數限制
- [ ] House PDF 多頁報告的分頁策略
- [ ] API 成本估算 (每次 pipeline run 的預期 call 數)
- [ ] 是否需要非同步 (async) 處理以加速多文件解析
