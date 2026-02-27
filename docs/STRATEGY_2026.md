# Political Alpha Monitor — 2026 戰略決議

> C-Suite Board Meeting 決議文件
> 日期：2026-02-27
> 參與者：CEO、CTO、CPO、CDO

---

## 一、北極星指標 (North Star Metric)

### 決議：每週可交易信號數 (Weekly Actionable Signals)

**定義**：每週產出的「有明確 ticker + 有交易方向 + extraction_confidence >= 0.7」的投資信號數量。

**計算方式**：
```sql
SELECT COUNT(*) FROM congress_trades
WHERE ticker IS NOT NULL
  AND transaction_type IN ('Buy', 'Sale')
  AND extraction_confidence >= 0.7
  AND created_at >= date('now', '-7 days');
```

**現狀**：約 0-1 筆/週（24 筆交易中僅 6 筆有 ticker）
**Phase 1 目標**：10+ 筆/週
**Phase 2 目標**：50+ 筆/週（含 13F + Insider Trading 數據源）

### 為何選此指標

四位 C-Suite 各自提出不同北極星候選：

| 主管 | 提案 | 採納方式 |
|------|------|---------|
| CEO | 可執行訊號數/週 | ✅ **採納為北極星**（與 CDO 提案合併，增加 ticker 約束） |
| CTO | Signal-to-Insight Latency | ✅ 採納為**速度護欄指標** |
| CPO | Weekly Active Signal Consumers | ✅ 採納為 **Phase 2 北極星**（需先有用戶系統） |
| CDO | 可交易信號數 | ✅ 合併入北極星定義（強調 ticker 必須存在） |

### 決議理由

1. **CDO 的關鍵發現**：94.7% 的 AI 信號沒有 ticker，75% 的交易沒有 ticker。系統的管道品質好（confidence 0.956），但產出的可交易價值接近零。北極星必須反映「對交易者有用」而非「系統跑了多少筆」。
2. **階段適配**：Phase 1 沒有用戶系統，CPO 的「活躍消費者」無法衡量。先用產出側指標驅動開發，Phase 2 有用戶後再切換。
3. **端到端覆蓋**：此指標驅動 ETL 穩定性（更多數據）+ AI 品質（更高 confidence）+ 數據源擴展（更多 ticker 覆蓋），涵蓋所有部門。

### 護欄指標體系

| 層級 | 指標 | 定義 | 當前值 | 目標 |
|------|------|------|--------|------|
| 速度 | Signal-to-Insight Latency | 官方揭露 → 入庫的時間差 | 未追蹤 | < 4 小時 |
| 品質 | Avg Extraction Confidence | 平均提取信心度 | 0.956 | >= 0.90 |
| 覆蓋 | Ticker Coverage Rate | 有 ticker 交易 / 總交易 | 25% | >= 50% |
| 成本 | Cost per Signal | 每個信號的 Gemini API 成本 | 未追蹤 | < $0.05 |
| 可靠 | ETL Success Rate | extraction_log 成功率 | 87.5% | >= 95% |

---

## 二、核心價值主張

**「將國會議員的資訊優勢，轉化為散戶投資人的可執行交易訊號。」** — CEO

---

## 三、現狀診斷（四位 C-Suite 共識）

### 優勢
- ✅ ETL 管道架構成熟（三源融合、Pydantic 驗證、LLM retry）
- ✅ Akamai WAF bypass 是短期技術護城河
- ✅ LLM 提取品質高（confidence 0.956）
- ✅ 繁體中文定位在華語市場無競品

### 致命弱點
- 🔴 **數據量體極小**：24 筆交易、38 筆信號（CDO）
- 🔴 **75% 交易無 ticker**：對交易者幾乎無用（CDO）
- 🔴 **無回測能力**：無法證明信號有 alpha（CDO）
- 🔴 **無用戶介面**：僅 CLI，觸及不到 90% 潛在用戶（CPO）
- 🔴 **零測試覆蓋**：無 pytest、無 CI/CD（CTO）
- 🔴 **ETL 與 Discovery 斷裂**：兩個子系統數據不互通（CTO）

---

## 四、統一產品發展方向

### Phase 1：數據基礎 + MVP（0-3 個月）

**主題：「讓數據有用、讓產品可見」**

| 優先序 | 項目 | 負責 | 產出 |
|--------|------|------|------|
| P0 | Capitol Trades 歷史回填 2-3 年 | CDO → data-analyst | 5000-10000 筆交易 |
| P0 | 串接 yfinance 股價 → Signal-to-Return 追蹤 | CDO → data-analyst | price_at_trade + price_after_30d 欄位 |
| P0 | 清理技術債（遺留檔案、統一 requirements、DB 路徑） | CTO → tech-lead | 乾淨的 codebase |
| P0 | 擴展議員追蹤至 Top 50 | CDO → prompt-engineer | 50 位議員的 AI Discovery |
| P1 | Web Dashboard v1（Streamlit） | CPO → product-manager | 交易瀏覽 + 信號排名 |
| P1 | Telegram Bot 高影響力信號推播 | CTO → devops | 即時通知管道 |
| P1 | 統一 logging + ETL 成功/失敗告警 | CTO → devops | 監控基礎設施 |
| P2 | ETL Load 層增加「可交易信號」過濾器 | CDO → tech-lead | ticker 覆蓋率追蹤 |
| P2 | 清理測試資料 + staging 環境 | CTO → devops | 數據品質保障 |

**Phase 1 結束標準**：北極星 >= 10 筆可交易信號/週 + Web Dashboard 可公開展示

### Phase 2：產品化 + 用戶獲取（3-6 個月）

**主題：「讓用戶來、讓用戶留」**

| 優先序 | 項目 | 負責 | 產出 |
|--------|------|------|------|
| P0 | FastAPI REST API | CTO → tech-lead | /trades、/signals、/reports 端點 |
| P0 | 回測引擎 v1 | CDO → data-analyst | 議員歷史跟單回報 vs S&P 500 |
| P0 | SEC Form 4 Insider Trading 整合 | CDO → data-analyst | 第二信號源 |
| P1 | 用戶系統（註冊/登入/Watchlist） | CTO → tech-lead | 個人化體驗 |
| P1 | ETL-Discovery 串接 | CTO → tech-lead | Discovery 讀取 congress_trades |
| P1 | 多模型支援（OpenAI fallback） | CTO → prompt-engineer | 降低 Gemini 單點風險 |
| P2 | 13F 機構持倉整合 | CDO → data-analyst | 多維信號 |
| P2 | Freemium 計費系統 | CPO → product-manager | Free / Pro ($19/月) |

**Phase 2 結束標準**：北極星切換至「Weekly Active Signal Consumers」>= 100 人

### Phase 3：規模化 + 商業化（6-12 個月）

**主題：「證明 Alpha、擴大規模」**

| 優先序 | 項目 | 負責 | 產出 |
|--------|------|------|------|
| P0 | PostgreSQL 遷移 | CTO → devops | 多用戶併發支援 |
| P0 | Alpha Hit Rate 公開追蹤 | CDO → data-analyst | 可行銷的績效數據 |
| P1 | 正式 Web App（Next.js） | CPO → product-manager | 專業 UI/UX |
| P1 | Enterprise API（SLA + 高可用） | CTO → tech-lead | B2B 收入 |
| P2 | 多語言（英文版） | CPO → product-manager | 全球市場 |
| P2 | 雲端部署（Railway/AWS） | CTO → devops | 脫離本地 WSL2 |

**Phase 3 結束標準**：ARR $180K+，可展示的 Alpha Hit Rate

---

## 五、各部門 OKR（Phase 1, Q1-Q2 2026）

### CEO Office
| Objective | Key Result |
|-----------|-----------|
| 確立產品市場定位 | 完成競品差異化定位文件 |
| 驗證核心假設 | 北極星達到 10+ 可交易信號/週 |
| 建立品牌存在 | Web Dashboard 公開上線 |

### CTO Office
| Objective | Key Result |
|-----------|-----------|
| 消除技術債 | 移除 15 個遺留檔案 + 統一 requirements.txt |
| 建立監控基礎 | 統一 logging + Telegram 告警 |
| Pipeline 穩定化 | ETL Success Rate >= 95% |

### CPO Office
| Objective | Key Result |
|-----------|-----------|
| 推出 MVP | Streamlit Dashboard 上線 |
| 建立通知管道 | Telegram Bot 每日推播 |
| 定義 Freemium 邊界 | Pro 功能清單確認 |

### CDO Office
| Objective | Key Result |
|-----------|-----------|
| 累積歷史數據 | Capitol Trades 回填至 5000+ 筆 |
| 建立回測基礎 | 串接 yfinance，追蹤 Signal → Return |
| 提升 Ticker 覆蓋率 | 從 25% 提升至 50%+ |

---

## 六、風險登記簿

| 風險 | 可能性 | 影響 | 擁有者 | 緩解措施 |
|------|--------|------|--------|----------|
| STOCK Act 禁止國會交易 | 中 | 致命 | CEO | 擴展至 13F + Insider Trading 對沖 |
| Senate EFD 強化 WAF | 高 | 高 | CTO | Capitol Trades fallback + 持續更新 bypass |
| Gemini API 漲價/停用 | 中 | 高 | CTO | 多模型支援（Phase 2） |
| 數據品質下降 | 中 | 中 | CDO | 品質監控儀表板 + 告警 |
| 競品搶先 | 中 | 中 | CPO | 聚焦 AI 分析層差異化 |

---

## 七、立即行動項（Next 2 Weeks）

1. **CDO**: 用 `capitoltrades_fetcher.py` 回填 2023-2026 歷史交易數據
2. **CTO**: 移除 `src/` 下 15 個遺留檔案至 `bk/legacy/`
3. **CTO**: 統一 `requirements.txt`（補齊所有實際依賴）
4. **CDO**: 清理 DB 中的測試資料（Mock Senator 等）
5. **CPO**: 建立 Streamlit Dashboard 骨架（交易列表 + 信號排名）

---

*本文件由 CEO、CTO、CPO、CDO 四位 AI Agent 平行研究後，經 Board Meeting 彙整產出。*
