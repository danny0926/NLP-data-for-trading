# CDO 數據品質報告

日期: 2026-02-27
分析者: CDO (Chief Data Officer)
資料庫: `data/data.db`

---

## 一、數據概覽

| 指標 | 數值 |
|------|------|
| congress_trades 總筆數 | 404 |
| House 交易筆數 | 347 (85.9%) |
| Senate 交易筆數 | 57 (14.1%) |
| 不重複議員人數 | 17 |
| 不重複交易日期數 | 39 |
| 交易日期範圍 | 2025-12-01 ~ 2026-12-26 |
| 申報日期範圍 | 2026-02-01 ~ 2026-02-27 |
| extraction_log 記錄數 | 41 |
| AI 智能信號數 | 102 |
| SHA256 去重衝突數 | 0 (無重複) |

### 資料來源分布

| 來源格式 | 筆數 | 占比 |
|----------|------|------|
| house_pdf (House PDF + Gemini Vision) | 347 | 85.9% |
| senate_html (Senate EFD DataTable) | 48 | 11.9% |
| capitoltrades_html (Capitol Trades fallback) | 9 | 2.2% |

---

## 二、品質問題分析

### 2.1 Ticker 覆蓋率

| 院別 | 總筆數 | 缺少 Ticker | 缺失率 |
|------|--------|-------------|--------|
| House | 347 | 31 | 8.9% |
| Senate | 57 | 20 | 35.1% |
| **合計** | **404** | **51** | **12.6%** |

**嚴重度: 中高** -- Senate 缺失率達 35.1%，需優先處理。

**缺失原因分析：**

- **House 缺失 (31 筆)**: 全部為**債券 (Bond)** 類資產（如 "King CNTY Wash Ltd 4.00% 12/1/32"）。債券本身沒有標準 ticker，此為**預期中的缺失**，非系統錯誤。
- **Senate 缺失 (20 筆)**: 包含以下幾種情況：
  - 私人實體 / LLC (如 "ELCM2 LLC", "NOT FADE AWAY LLC", "MH BUILT TO LAST LLC") — 無公開 ticker，**預期中缺失**
  - 私募基金 (如 "KIRKOSWALD GLOBAL MACRO FUND LP", "3G RADAR PRIVATE FUND I LP", "Contour Venture Partners V, LP") — **預期中缺失**
  - 市政債券 (如 "ME St Health & Higher Ed", "MARYLAND ST TRANSN AUTH") — **預期中缺失**
  - **SPYM** — 這筆被歸類為 Stock 但 ticker 為 NULL，asset_name 本身看似就是 ticker。**此為 LLM 抽取錯誤**，應在 `ticker` 欄填入 "SPYM"。

**結論**: 51 筆缺失中，約 50 筆為結構性缺失（債券/私募/LLC 本無 ticker），僅 1 筆為 LLM 抽取錯誤。實質 ticker 覆蓋率為 **99.7%**（扣除非股票類資產後）。

### 2.2 Confidence 分布

| 信心度區間 | 筆數 | 占比 |
|-----------|------|------|
| 0.9 - 1.0 (High) | 403 | 99.8% |
| 0.7 - 0.89 (Medium) | 1 | 0.2% |
| **< 0.7 (Low/Manual Review)** | **0** | **0%** |

| 指標 | 數值 |
|------|------|
| 最低信心度 | 0.88 |
| 最高信心度 | 0.99 |
| 平均信心度 | 0.975 |
| House 平均 | 0.979 |
| Senate 平均 | 0.950 |

**嚴重度: 低** -- 信心度普遍極高，所有記錄均通過 0.7 門檻自動寫入。

**潛在問題**: Senate 全部記錄的 confidence 固定為 0.95，缺乏變異，可能代表 LLM 在 Senate 路徑中**未依實際抽取品質動態評估信心度**，而是返回固定值。建議在 `SENATE_HTML_PROMPT` 中強化 confidence 評估指引。

### 2.3 欄位完整性

| 欄位 | 缺失筆數 | 缺失率 | 嚴重度 |
|------|---------|--------|--------|
| chamber | 0 | 0% | - |
| politician_name | 0 | 0% | - |
| transaction_date | 0 | 0% | - |
| filing_date | 0 | 0% | - |
| ticker | 51 | 12.6% | 中 (結構性缺失為主) |
| asset_name | 0 | 0% | - |
| asset_type | 0 | 0% | - |
| transaction_type | 0 | 0% | - |
| amount_range | 0 | 0% | - |
| **owner** | **134** | **33.2%** | **高** |
| **comment** | **346** | **85.6%** | 低 (非必填) |
| source_url | 0 | 0% | - |
| source_format | 0 | 0% | - |

**Owner 欄位分析 (嚴重度: 高)**:

134 筆 `owner` 為空，全部來自 **House** 院。進一步檢視 House 中的 owner 分布：

| Owner 值 | House 筆數 | 備註 |
|----------|-----------|------|
| (NULL/empty) | 134 | **問題記錄** |
| Self | 145 | 標準值 |
| DC | 31 | 疑似縮寫 (Dependent Child?) |
| SP | 14 | 疑似縮寫 (Spouse?) |
| JT | 10 | 疑似縮寫 (Joint?) |
| Joint | 7 | 標準值 |
| Spouse | 6 | 標準值 |

Senate 的 owner 值較為標準化：Joint (37), Spouse (19), Self (1)。

**問題**:
1. House 有 134 筆 owner 完全為空，可能是 PDF 中未揭露或 LLM 未抽取。
2. House 存在**縮寫不一致**: "DC" vs 完整名稱, "SP" vs "Spouse", "JT" vs "Joint"。需要在 `HOUSE_PDF_PROMPT` 中明確要求 LLM 輸出標準化 owner 值。

### 2.4 議員名字標準化

**嚴重度: 高** -- 存在多個名字格式問題。

| 問題名字 | 推測正確寫法 | 類型 |
|---------|-------------|------|
| Donald Sternoff Jr. Beyer | Donald S. Beyer Jr. | 中間名錯誤插入 "Jr." 位置 |
| Michael A. Jr. Collins | Michael A. Collins Jr. | 同上，"Jr." 位置錯誤 |
| William F Hagerty, IV | William F. Hagerty IV | 格式含逗號，句號缺失 |
| Susan M Collins | Susan Collins | 多餘中間名縮寫 (Senate) |
| Richard W. Allen | Rick W. Allen | 正式名 vs 常用名 |
| David H McCormick | Dave McCormick | 正式名 vs AI 信號中的常用名 |

**跨系統名字不匹配 (ETL vs AI Discovery)**:

congress_trades 與 ai_intelligence_signals 之間存在嚴重的名字不匹配，僅 **2 位議員** (Nancy Pelosi, Richard Blumenthal) 的名字完全一致。其餘差異：

| congress_trades | ai_intelligence_signals | 差異原因 |
|----------------|------------------------|---------|
| David H McCormick | Dave McCormick | 正式名 vs 暱稱 |
| Susan M Collins | Susan Collins | 多餘中間名 |

其餘 15 位在 congress_trades 中的議員完全不存在於 ai_intelligence_signals 中，23 位 AI 信號來源議員不存在於 congress_trades 中。兩個系統尚未建立**統一的議員 ID 體系**。

### 2.5 時間異常

**嚴重度: 高** -- 發現 1 筆明確的未來日期錯誤。

| 問題 | 詳情 |
|------|------|
| 未來日期 | Steve Cohen: transaction_date = **2026-12-26**, ticker = SONY |
| 今日日期 | 2026-02-27 |
| 推測正確日期 | **2025-12-26** (LLM 年份抽取錯誤) |

交易日期 2026-12-26 距今約 10 個月後，明顯為年份錯誤。原始資料中可能為 "12/26" 而 LLM 推測了錯誤的年份。

**日期分布合理性**: 除上述 1 筆外，其餘交易日期集中在 2025-12-01 至 2026-02-17，與 filing_date (2026-02 月) 對應合理。最密集交易日為 2026-01-09 (72 筆) 和 2025-12-19 (54 筆)，均來自 Gilbert Cisneros 的大量交易，屬正常（該議員共 272 筆交易）。

**Filing Date 集中度**: 338/404 筆 (83.7%) 的 filing_date 為 2026-02-27 (今日)，說明系統主要抓取的是近期申報。

### 2.6 Owner 值標準化問題

**嚴重度: 中** -- 同一語義使用不同表示方式。

| 標準值 | 縮寫變體 | 筆數 |
|--------|---------|------|
| Spouse | SP | 14 |
| Joint | JT | 10 |
| Dependent Child (?) | DC | 31 |

DC 可能代表 "Dependent Child"，但在 Pydantic schema 中無驗證。建議統一為完整英文名稱。

### 2.7 Asset Type 標準化

**嚴重度: 低** -- 存在輕微分類不一致。

| 類型 | 筆數 | 問題 |
|------|------|------|
| Stock | 352 | 主類別 |
| Common Stock | 2 | 應統一為 "Stock" |
| Preferred Stock | 1 | 合理保留 |

### 2.8 Extraction Log 異常

**嚴重度: 中**

| 問題 | 詳情 |
|------|------|
| extraction_rate > 100% | 2 筆 house_pdf 的 extracted_count > raw_record_count（raw=72 extracted=122, raw=87 extracted=151） |
| manual_review | 2 筆 senate_html：1 筆 confidence=0.0（空報告），1 筆 confidence=0.5（測試資料 url=example.com） |
| 測試資料殘留 | `source_url = https://example.com/low` 為測試資料，不應存在於正式環境中 |

**Extraction rate > 100% 分析**: 這代表 LLM 從單份 PDF 中抽取出的記錄數超過了預估的原始記錄數。可能原因：`raw_record_count` 統計方式有誤（如只計算了 PDF 頁數而非交易筆數），或 LLM 將單筆交易拆分為多筆。

---

## 三、AI 信號品質

### 3.1 概覽

| 指標 | 數值 |
|------|------|
| 總信號數 | 102 |
| CONGRESS 來源 | 96 (94.1%) |
| 13F 來源 | 3 (2.9%) |
| SOCIAL 來源 | 3 (2.9%) |

### 3.2 Ticker 覆蓋率

| 指標 | 數值 |
|------|------|
| 缺少 Ticker | 65 (63.7%) |
| 有 Ticker | 37 (36.3%) |

**嚴重度: 極高** -- 近 2/3 的 AI 信號缺少 ticker，嚴重限制了信號的可操作性。無法直接用於下單或回測。

### 3.3 Impact Score 分布

| 分數區間 | 筆數 | 占比 | 執行建議 |
|---------|------|------|---------|
| 9-10 | 3 | 2.9% | MOO (Market On Open) |
| 7-8 | 37 | 36.3% | MOO |
| 5-6 | 36 | 35.3% | MOC (Market On Close) |
| 1-4 | 26 | 25.5% | MOC / 不執行 |

| 指標 | 數值 |
|------|------|
| 最低分 | 2 |
| 最高分 | 9 |
| 平均分 | 6.48 |

分布大致呈現正態，高信號 (>=8) 占 39.2%，低信號 (<=4) 占 25.5%。

### 3.4 Sentiment 分布

| 情緒 | 筆數 | 占比 |
|------|------|------|
| Positive | 50 | 49.0% |
| Neutral | 31 | 30.4% |
| Negative | 18 | 17.6% |
| NULL | 3 | 2.9% |

### 3.5 執行建議分布

| 類型 | 筆數 | 占比 |
|------|------|------|
| CLOSE (收盤執行) | 85 | 83.3% |
| OPEN (開盤執行) | 17 | 16.7% |

大量 CLOSE 建議（83.3%）與 impact_score < 8 的比例一致。

---

## 四、改善建議（優先級排序）

### P0 — 緊急修復

1. **修正未來日期錯誤**: Steve Cohen 的 SONY 交易日期 `2026-12-26` 應為 `2025-12-26`。需在 `llm_transformer.py` 增加日期合理性校驗（transaction_date 不應超過 filing_date 或當前日期）。

2. **移除測試資料**: extraction_log 中存在 `source_url = https://example.com/low` 的測試記錄，應清理。

### P1 — 高優先級

3. **統一 Owner 值標準化**: 在 `HOUSE_PDF_PROMPT` 中明確要求 LLM 將 owner 輸出為標準值（"Self", "Spouse", "Joint", "Dependent Child"），或在 `loader.py` 增加映射邏輯：
   ```python
   OWNER_MAPPING = {"SP": "Spouse", "JT": "Joint", "DC": "Dependent Child"}
   ```

4. **修復 Owner 空值問題**: 134 筆 House 交易缺少 owner。檢查 PDF 原始資料是否包含此欄位，若有則調整 prompt；若 PDF 中確實無此資訊，考慮設預設值 "Unknown" 或 "Not Disclosed"。

5. **建立統一議員 ID 體系**: ETL 與 AI Discovery 之間的議員名字無法對應。建議：
   - 建立 `politicians` 參照表 (canonical_name, aliases[], chamber, state)
   - 在兩個系統入庫時統一對照

6. **修正議員名字格式**: 調整 LLM prompt 或後處理邏輯，處理 "Jr." / "IV" 等後綴的正確位置：
   - "Donald Sternoff Jr. Beyer" → "Donald S. Beyer Jr."
   - "Michael A. Jr. Collins" → "Michael A. Collins Jr."

### P2 — 中等優先級

7. **提升 AI 信號 Ticker 覆蓋率**: 63.7% 的 AI 信號缺少 ticker，嚴重影響可操作性。建議在 Discovery Engine 的 prompt 中強制要求輸出 ticker，或增加後處理步驟透過議員名字反查 congress_trades 表補全。

8. **修正 Senate Confidence 固定值問題**: 所有 Senate 記錄的 confidence 均為 0.95，缺乏區分度。調整 `SENATE_HTML_PROMPT` 要求 LLM 根據實際抽取品質動態評分。

9. **統一 Asset Type**: 將 "Common Stock" 統一為 "Stock"，在 schema 或 loader 中做映射。

10. **修正 Extraction Log raw_record_count**: 2 筆 house_pdf 的 extracted > raw，表示 raw_record_count 計算有誤。檢查 `house_fetcher.py` 的 raw_record_count 統計邏輯。

### P3 — 低優先級

11. **增加日期格式驗證**: 在 Pydantic schema 中增加 `transaction_date` 的 validator，確保格式為 YYYY-MM-DD 且不超過當前日期。

12. **Comment 欄位**: 85.6% 為空屬正常現象（多數交易無特殊說明），無需修復。

---

## 五、對研究團隊的建議

### 5.1 數據使用注意事項

1. **議員集中度風險**: Gilbert Cisneros 一人佔 272/404 筆 (67.3%) 交易，進行統計分析時須注意此偏態。按議員加權或排除異常大量交易者後再做整體趨勢分析。

2. **Ticker 缺失的預期行為**: 非股票資產（Bond, Municipal Security, Fund, LLC）缺少 ticker 屬正常現象，研究時可用 `WHERE ticker IS NOT NULL AND asset_type = 'Stock'` 過濾。

3. **跨系統 Join**: 目前 congress_trades 與 ai_intelligence_signals 的議員名字無法直接 JOIN，需先建立名字映射表。短期可用模糊匹配 (`LIKE '%McCormick%'`) 但長期需要正式的 politician_id。

4. **Owner 資料品質**: House 的 owner 欄位有 33.2% 空值和縮寫不一致，在分析「議員本人 vs 家人交易」時需額外處理。

### 5.2 推薦的數據子集

針對量化研究，建議使用以下過濾條件獲取高品質子集：

```sql
SELECT * FROM congress_trades
WHERE ticker IS NOT NULL
  AND ticker != ''
  AND asset_type IN ('Stock', 'Common Stock')
  AND extraction_confidence >= 0.9
  AND transaction_date <= DATE('now')
ORDER BY transaction_date DESC;
-- 預計返回約 350 筆高品質股票交易記錄
```

### 5.3 數據品質總評

| 維度 | 評分 | 說明 |
|------|------|------|
| 完整性 | **B+** | 核心欄位完整，owner 缺失為主要扣分項 |
| 準確性 | **B** | 1 筆日期錯誤，數筆名字格式問題 |
| 一致性 | **B-** | Owner 縮寫不一致，asset_type 輕微不一致 |
| 唯一性 | **A** | SHA256 去重完美，0 重複記錄 |
| 時效性 | **A** | 83.7% 記錄為今日抓取 |
| 可操作性 | **B-** | ETL 數據可用，AI 信號 ticker 覆蓋率不足 |
| **綜合** | **B** | 系統基礎穩固，需在標準化和跨系統整合上加強 |

---

*報告生成時間: 2026-02-27*
*資料庫快照: data/data.db (404 congress_trades, 102 ai_signals, 41 extraction_logs)*
