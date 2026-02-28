# Spike Report: RB-009 USASpending.gov Government Contracts API

**日期**: 2026-02-28
**評估人**: CDO (Research Team)
**評估結果**: **GO** (8.0/10 — 建議推進 POC)

---

## 評估摘要

| 維度 | 權重 | 評分 | 加權 |
|------|------|------|------|
| 資料品質 | 30% | 8/10 | 2.4 |
| 技術整合 | 25% | 7/10 | 1.75 |
| Alpha 潛力 | 25% | 7/10 | 1.75 |
| 成本 | 10% | 10/10 | 1.0 |
| 合規 | 10% | 10/10 | 1.0 |
| **加權總分** | | | **7.9/10** |

**建議**: GO — 免費 API、學術研究支持、與 PAM 現有信號可形成強力收斂。主要風險為 DoD 合約 90 天延遲。

---

## 1. API 技術規格

| 項目 | 詳情 |
|------|------|
| 基礎 URL | `https://api.usaspending.gov/api/v2/` |
| 認證 | **不需要** — 完全開放 |
| 格式 | JSON (搜尋) / CSV (批量下載) |
| 歷史深度 | FY2001 (批量) / FY2008 (API) |
| 更新頻率 | 每週六 (FPDS 提交後 ~5 天) |
| 速率限制 | 無明文限制 (建議 1 req/sec) |
| 頁面大小 | 最大 5,000 筆/請求 |

### 核心端點

```
POST /api/v2/search/spending_by_award/     # 合約搜尋 (最常用)
GET  /api/v2/awards/{AWARD_ID}/            # 單一合約詳情
POST /api/v2/bulk_download/awards/          # 批量下載 (非同步)
POST /api/v2/search/spending_by_category/naics/  # NAICS 板塊聚合
```

### 請求範例

```python
payload = {
    "filters": {
        "award_type_codes": ["A", "B", "C", "D"],
        "time_period": [{"start_date": "2025-01-01", "end_date": "2026-02-28"}],
        "recipient_search_text": ["Lockheed Martin"],
        "award_amounts": [{"lower_bound": 1000000}]
    },
    "fields": ["Award ID", "Recipient Name", "Start Date", "Award Amount", "NAICS", "Awarding Agency"],
    "limit": 100, "page": 1, "sort": "Award Amount", "order": "desc"
}
resp = requests.post("https://api.usaspending.gov/api/v2/search/spending_by_award/", json=payload)
```

---

## 2. Alpha 潛力

### 學術研究支持

| 研究 | 核心發現 | Alpha 估計 |
|------|---------|-----------|
| CEPR 2025 | 議員購股後公司獲得更多獨家合約 | 委員會主席: +40-47%/年 |
| HEC Montreal 2024 | 合約公告後 D+15 CAR | +1.4% |
| Oxford Academic | 政府依賴型公司長期超額報酬 | +6.0%/年 vs 非政府依賴 |

### PAM 整合信號預期

| 信號類型 | 預期 Alpha | 可信度 |
|---------|-----------|--------|
| 議員買入 + 後續合約授予 (收斂) | +3.0% - +5.0% | 高 |
| 大型合約公告 ($100M+) | +1.0% - +2.0% | 中 |
| 板塊輪動 (NAICS 聚合) | +2.0% - +3.0% | 中高 |
| DoD 合約 (90天延遲後) | +0.5% | 低 |

---

## 3. 承包商 → Ticker 映射策略

三層策略：

1. **靜態白名單** (Top 100 承包商): 覆蓋率 ~70%, 精確度 ~99%
2. **SEC EDGAR API** (`company_tickers.json` fuzzy match): 覆蓋率 ~85%, 精確度 ~90%
3. **yfinance 搜尋** (現有 `ticker_enricher.py`): 兜底

關鍵映射欄位: `recipient_parent_name` (母公司) + `recipient_uei` (穩定 ID)

---

## 4. 主要風險

| 風險 | 嚴重度 | 緩解方式 |
|------|--------|---------|
| DoD 合約 90 天公開延遲 | 高 | 聚焦非 DoD (HHS/NASA/DHS)；DoD 用於離線驗證 |
| 子公司 → 母公司映射 | 中 | 使用 `recipient_parent_name` + UEI |
| 委員會歸因不精確 | 中 | 手工維護 politician_committee_map |
| 合約修訂噪音 | 低 | 以 Award ID 去重，取最新版本 |

---

## 5. 建議實作路徑

### Phase 1: POC (1-2 天)
- 建立 `src/etl/usaspending_fetcher.py` (~200 行)
- 建立 Top 100 承包商 ticker 映射表
- 交叉比對: congress_trades 買入 → T-90~T+30 有大額合約？

### Phase 2: 整合 (3-5 天)
- `government_contracts` 新表
- 擴展 `convergence_detector.py`: contract_proximity_score
- 擴展 `signal_enhancer.py`: contract_award_bonus

### Phase 3: 回測 (2-3 天)
- FY2020-2024 歷史 event study
- 「議員買入 + 合約授予」收斂信號 CAR 計算

**總工時估計**: 6-10 天

---

## 參考資料

- [USASpending API Documentation](https://api.usaspending.gov/docs/endpoints)
- [Political Power and Profitable Trades - CEPR VoxEU 2025](https://cepr.org/voxeu/columns/political-power-and-profitable-trades-us-congress)
- [Trading on Government Contracts - ScienceDirect 2025](https://www.sciencedirect.com/science/article/abs/pii/S0165176525001727)
- [Asset Pricing and Government Sales Dependency - Oxford Academic](https://academic.oup.com/raps/article/13/1/146/6575918)
