# Research Brief: Alternative Data Sources for Congressional Trading Expansion (RB-013)
> 日期：2026-03-07 | 研究員：Research Lead | 狀態：Draft

## 問題定義

**現狀：** PAM 系統目前僅涵蓋 39 位不重複議員（Senate 13 位、House 26 位），共 585 筆交易。Capitol Trades 網站列出 201 位活躍交易議員，代表我們的覆蓋率僅 19.4%。

**目標：** 擴展至 100+ 位議員，提升北極星指標（每週可行動文本信號數）。更多議員 = 更多收斂信號 = 更高信號品質。

**瓶頸分析：** 當前限制並非資料來源不足，而是 **scraping 深度不夠** -- Capitol Trades fetcher 僅抓取 5 頁/chamber（`pages = max(1, days // 3)`），而該站實際有 17+ 頁、201 位議員。

## 研究方法

搜尋並評估了以下 7 類資料來源：
1. OpenSecrets.org API
2. ProPublica Congress API
3. Congress.gov API
4. GovTrack.us
5. Quiver Quantitative
6. House/Senate Stock Watcher (GitHub)
7. Financial Modeling Prep (FMP) API
8. 其他 GitHub 資料集

每個來源評估：成本、覆蓋率、資料新鮮度、API 品質、整合難度。

## 發現摘要

### 1. Capitol Trades（已有，但未充分利用）-- **最大快速勝利**

| 項目 | 詳情 |
|------|------|
| 成本 | **FREE**（公開 HTML） |
| 覆蓋率 | **201 位議員**，含 Senate + House |
| 資料新鮮度 | 即時更新（基於官方揭露） |
| 整合難度 | **極低** -- 已有 `CapitolTradesFetcher`，只需調整參數 |
| 現狀問題 | `pipeline.py` 第 115 行：`pages = max(1, days // 3)` -- 預設 7 天只抓 2 頁 |
| 修正方案 | 改為固定 50 頁或新增 `--ct-pages` 參數 |
| 預期新增 | **~160 位議員**（201 - 已有 ~40） |

**關鍵發現：** Capitol Trades 有 14,451 筆 2025 年交易（140 位議員），價值 $720M。我們目前只抓到 110 筆（5 頁 x 12 筆/頁 x 2 chamber），覆蓋率不到 1%。

### 2. House Stock Watcher / Senate Stock Watcher

| 項目 | 詳情 |
|------|------|
| 成本 | **FREE** |
| House API | `https://housestockwatcher.com/api` |
| Senate API | `https://senatestockwatcher.com/api` |
| S3 Data Dump | `https://house-stock-watcher-data.s3-us-west-2.amazonaws.com/data/all_transactions.json` |
| GitHub Repo | `timothycarambat/senate-stock-watcher-data` |
| 資料格式 | JSON（全部交易一次下載） |
| 資料新鮮度 | 每日更新（聲稱），但 S3 端點返回 403（可能已停用） |
| 整合難度 | **中等** -- 需新增 fetcher，JSON 格式不需 LLM 解析 |
| 預期新增 | 需驗證，歷史資料可能到 2022 年 |

**風險：** S3 端點已返回 HTTP 403 Forbidden，House Stock Watcher 主站可能仍運作但 API 存取受限。Senate Stock Watcher 網站仍在線但 API 狀態不確定。**需進一步驗證。**

### 3. Financial Modeling Prep (FMP) API

| 項目 | 詳情 |
|------|------|
| 成本 | Free plan: 250 requests/day；**但國會交易 endpoint 為 Premium 限定** |
| Senate Trading API | `https://financialmodelingprep.com/stable/senate-trading` |
| House Trading API | `https://financialmodelingprep.com/stable/house-trading` |
| 覆蓋率 | 全部議員（基於官方揭露） |
| 資料格式 | 結構化 JSON（ticker, date, amount, type 全部已解析） |
| 整合難度 | **低** -- REST API + JSON，不需 LLM 解析 |

**結論：Senate/House trading endpoints 需要付費方案（$29/mo Starter 起），Free plan 不含國會交易資料。** 性價比不如直接擴充 Capitol Trades scraping。

### 4. OpenSecrets.org API

| 項目 | 詳情 |
|------|------|
| 成本 | **API 已於 2025-04-15 停用** |
| 替代 | 可聯繫 info@opensecrets.org 取得客製化資料 |
| Bulk Data | 可下載歷史資金流向資料（非交易資料） |
| 整合難度 | N/A |

**結論：API 已停用，不可用。** Bulk data 為競選捐獻資料，非個人交易資料，與 PAM 需求不符。

### 5. ProPublica Congress API

| 項目 | 詳情 |
|------|------|
| 成本 | **Free（5,000 requests/day）** |
| 覆蓋資料 | 立法資料（投票、法案、委員會）-- **無交易資料** |
| API Key | 已停止核發新 API Key |
| 用途 | 可補充議員委員會資訊（輔助交叉比對） |

**結論：不含財務揭露/交易資料。** API Key 已不可申請。若已有 key 可用於補充委員會資訊，但無直接價值。

### 6. Congress.gov API

| 項目 | 詳情 |
|------|------|
| 成本 | **Free（5,000 requests/hour）** |
| 覆蓋資料 | 法案、投票、修正案 -- **無交易/財務揭露 endpoint** |
| 整合難度 | 低（REST + JSON） |

**結論：官方 API 不提供財務揭露資料。** 財務揭露由 Senate Ethics Committee 和 House Clerk 分別管理，不在 Congress.gov API 範圍內。

### 7. GovTrack.us

| 項目 | 詳情 |
|------|------|
| 成本 | **Free** |
| 覆蓋資料 | 立法追蹤、投票記錄 -- **無交易資料** |

**結論：純立法追蹤平台，無財務揭露資料。**

### 8. Quiver Quantitative

| 項目 | 詳情 |
|------|------|
| 成本 | Dashboard 免費瀏覽；API 需 $10/mo（Hobbyist）起 |
| 覆蓋率 | 全部活躍交易議員 |
| 資料格式 | JSON API（結構化） |
| 整合難度 | 低 |

**結論：$10/mo Hobbyist 方案有 API 存取，但 Capitol Trades 已是免費替代。** 若需要歷史回測資料，QuantConnect 提供 Quiver 的國會交易資料集（需 QuantConnect 帳號）。

### 9. GitHub 資料集（補充來源）

| Repo | 描述 | 狀態 |
|------|------|------|
| `timothycarambat/senate-stock-watcher-data` | Senate JSON 交易檔案 | 維護中但更新頻率不明 |
| `semerriam/congress-stock-trades` | Senate + House 合併 + yfinance | 歷史資料 |
| `neelsomani/senator-filings` | efdsearch scraper + 報酬計算 | 參考用 |
| `tg12/congressional-filings-explorer` | AI-OCR 分析 House PDF | 2025 活躍 |
| `johnisanerd/Apify-Congressional-Trading-Data-Scraper` | Apify actor (House+Senate) | 2025-11 更新 |

**最有價值：** `tg12/congressional-filings-explorer` -- 使用 AI OCR 解析 House 揭露 PDF，與我們的 House fetcher (Gemini Vision) 類似，可參考其解析邏輯。

## 方案比較

| 方案 | 成本 | 新增議員 | 資料新鮮度 | 整合難度 | 風險 | 推薦 |
|------|------|----------|------------|----------|------|------|
| A. 擴充 Capitol Trades 頁數 | $0 | +160 | 即時 | S (1-2h) | 低（被限速） | **第一優先** |
| B. House/Senate Stock Watcher API | $0 | 需驗證 | 每日 | M (4-8h) | 中（API 可能已失效） | 第二優先（需先驗證） |
| C. FMP API (Starter) | $29/mo | +200 | 即時 | S (2-4h) | 低 | 第三備選 |
| D. Quiver API (Hobbyist) | $10/mo | +200 | 每日 | S (2-4h) | 低 | 第四備選 |
| E. 不做（維持現狀） | $0 | 0 | N/A | 0 | 覆蓋率停滯 | 不推薦 |
| F. 自建 Senate EFD 全量爬蟲 | $0 | +50 | 即時 | L (16-24h) | 高（Akamai 封鎖） | 長期考慮 |
| G. 自建 House 全量爬蟲 | $0 | +80 | 即時 | L (16-24h) | 中（PDF 量大） | 長期考慮 |

## 建議行動

### 推薦方案：A → B → C（漸進式擴展）

#### Phase 1: 擴充 Capitol Trades（立即執行，1-2 小時）

**修改內容：**
1. `src/etl/pipeline.py` 第 115 行：`pages = max(1, days // 3)` → `pages = min(50, max(5, days * 2))`
2. 新增 `--ct-pages` CLI 參數到 `run_etl_pipeline.py`
3. `CapitolTradesFetcher.fetch()` 加入 rate limiting（每頁間隔 2 秒）
4. 同時抓取 House chamber（目前 Capitol Trades fallback 只抓 Senate）

**預期效果：**
- 議員數：39 → ~150+
- 交易數：585 → ~2,000+
- 收斂信號品質大幅提升（更多議員 = 更多交叉驗證機會）

#### Phase 2: 驗證 Stock Watcher API（2-4 小時）

手動測試：
```bash
curl https://housestockwatcher.com/api
curl https://senatestockwatcher.com/api
```
- 若 API 仍運作 → 新增 `StockWatcherFetcher`，JSON 直接解析（不需 LLM）
- 若 API 失效 → 跳過，Phase 1 已足夠

#### Phase 3: FMP API 備案（如需更高覆蓋率）

- 只在 Phase 1+2 未達 100+ 議員時啟用
- $29/mo Starter 方案，結構化 JSON 不需 LLM
- 作為 Capitol Trades 的驗證來源（交叉比對資料正確性）

## POC 規格（Phase 1）

- **範圍：** 修改 Capitol Trades fetcher 參數 + pipeline 整合 + 新增 House chamber 抓取
- **不做：** 不改 LLM Transform 邏輯、不改 DB schema、不加新資料來源
- **預估工時：** S（1-2 小時）
- **需要的資源：** 無額外 API key 或費用
- **成功標準：**
  - 單次執行可抓取 100+ 位不重複議員
  - 新增交易資料通過 SHA256 去重（不重複寫入）
  - 不影響現有 Senate EFD / House PDF 路徑

## 風險與緩解

| 風險 | 可能性 | 影響 | 緩解 |
|------|--------|------|------|
| Capitol Trades 限速/封鎖 | 中 | 抓取中斷 | 加入 rate limiting（2s/page）+ exponential backoff |
| LLM Token 成本爆增 | 中 | Gemini API 費用 | `_trim_capitoltrades_html()` 已壓縮 HTML（243KB→1.7KB），50 頁 ≈ 85KB tokens |
| 資料品質下降（更多低活躍議員） | 低 | 噪音增加 | SQS 評分已有品質閘門（< 20 分淘汰） |
| Stock Watcher API 已死 | 高 | Phase 2 失敗 | Phase 1 已足夠覆蓋目標 |
| 抓取時間過長 | 低 | pipeline 逾時 | 50 頁 x 2s = ~2 分鐘，加 LLM ≈ 10 分鐘，可接受 |

## 附錄：各來源狀態總覽

```
[AVAILABLE]  Capitol Trades (HTML scraping)    -- 201 politicians, FREE, 已整合
[UNCERTAIN]  House Stock Watcher API           -- 需驗證 API 存活
[UNCERTAIN]  Senate Stock Watcher API          -- 需驗證 API 存活
[PAID]       FMP API ($29/mo+)                 -- 結構化 JSON, Premium only
[PAID]       Quiver Quantitative ($10/mo+)     -- API 需付費
[DEAD]       OpenSecrets API                   -- 2025-04-15 停用
[NO_DATA]    ProPublica Congress API           -- 無交易資料, Key 不可申請
[NO_DATA]    Congress.gov API                  -- 無財務揭露 endpoint
[NO_DATA]    GovTrack.us                       -- 純立法追蹤
[REFERENCE]  GitHub repos                      -- 歷史資料/參考實作
```

---

**結論：最大投資報酬率方案是擴充現有 Capitol Trades scraping 深度，零成本即可從 39 議員擴展至 150+ 議員。** 不需新增任何資料來源或 API key。
