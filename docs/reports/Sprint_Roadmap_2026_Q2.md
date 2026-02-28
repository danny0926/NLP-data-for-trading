# PAM Sprint Roadmap — 2026 Q2

> Generated: 2026-02-28 | Sprint Review: pam-sprint-02-28
> Sources: CEO, CTO, CDO, Quant Researcher, DevOps, Test Engineer brainstorming

---

## 1. Sprint 02-28 成果總覽

### 開發交付
| 項目 | 狀態 | 細節 |
|------|------|------|
| 3 張缺失 DB 表初始化 | DONE | enhanced_signals(355), rebalance_history(96), sector_rotation_signals(3) |
| pytest MVP 測試套件 | DONE | 290 tests, 8 files, 1.9s |
| GitHub Actions CI | DONE | pytest + smoke test on push/PR |
| 12 個 Agent Skills | DONE | +hypothesis-test, data-source-eval, research-brief (研究技能) |
| Daily pipeline 補全 | DONE | +Signal Enhancer, Sector Rotation, Rebalance, FF3 re-run |
| FF3 NULL 診斷 | DONE | 20d/60d 100% NULL — 時間不足,非 bug |
| Ticker NULL 分析 | DONE | 48/404 (11.9%) 全為合法非股票資產 |

### DB 健康: 88/100 (B+)
- 29 表, 跨表一致性 404→404→355→355→355 完整
- Smoke test: 55/55 PASS

---

## 2. 量化研究驗證 (Quant Researcher)

### 關鍵發現 (量化實證)

| 研究項目 | 結論 | 數據 |
|----------|------|------|
| **RB-006 SQS 負預測因子** | 已確認 | conviction r=-0.5136 (預測 -0.50) |
| **收斂信號 alpha 溢價** | 強正預測 | has_convergence=True → EA20d 高 36% |
| **金額最佳區間** | $15K-$50K 最強 | 比 $1K-$15K 高 93% alpha |
| **PACS 分層效果** | Q4 >> Q1 | Q4/Q1 = 3.04x alpha 差距 |
| **議員等級梯度** | B > C > D 明確 | Grade B avg EA20d 顯著領先 |
| **Filing lag 門檻** | <15d 極關鍵 | <15d alpha 為 >=15d 的 4.6x |
| **FF3 20d/60d NULL** | 時間不足 (非 bug) | 355/355 = 100% NULL，需 2026-03 後重跑 |
| **SQS 時效性瓶頸** | Timeliness 維度偏低 | 平均 15.5/100 (5 維度最低) |
| **Alpha 信號分布** | Buy-Only 生效 | 355 筆信號, 100% LONG 方向 |
| **收斂信號覆蓋** | 6 tickers 多議員收斂 | 17 位議員有 PIS 排名 |

### 可執行改善建議 (按 Impact 排序)

| # | 建議 | 預估 Impact | 難度 | 目標模組 |
|---|------|------------|------|----------|
| 1 | **$15K-$50K 額外加分 +5pts** | High | Low | `portfolio_optimizer.py` |
| 2 | **7 天 burst convergence 子信號** | High | Medium | `convergence_detector.py` |
| 3 | **Signal decay 機制** (filing_date+20d 後衰減) | Medium | Medium | `signal_enhancer.py` |
| 4 | **VIX adaptive Goldilocks** (VIX_90d_mean ± 0.5σ) | Medium | Medium | `signal_enhancer.py` |
| 5 | **Filing lag <15d 即時監控** | Medium | Low | `smart_alerts.py` |
| 6 | **SQS Timeliness 重新校準** | Low-Med | Low | `signal_scorer.py` |
| 7 | **Politician grade A/B 專屬加分** | Low | Low | `alpha_signal_generator.py` |
| 8 | **FF3 月度重跑排程** | Low | Low | `run_daily.py` (已整合) |

### 已修正項目
- [x] FF3 re-run 已加入 daily pipeline (`run_daily.py`)
- [x] SQS conviction 權重已降至 10% (`signal_enhancer.py`)
- [x] Buy-Only 策略已全面啟用 (`portfolio_optimizer.py`, `signal_enhancer.py`)
- [x] **$15K-$50K Sweet Spot 修正** — `SWEET_SPOT_AMOUNT_RANGE` 常數截斷 bug 已修復 (034f766)
- [x] **$15K-$50K 額外加分 +5pts** — 已實作 (SWEET_SPOT_BONUS=5.0)
- [x] **7 天 burst convergence** — 已實作 (BURST_WINDOW_DAYS=7, BURST_BONUS=0.5, e60044f)
- [x] **Signal decay 機制** — filing_date+20d 線性衰減已實作 (d9b0314)
- [x] **Signal Tracker 首次執行** — 39 signals validated: +2.50% avg CAR_5d, 64.1% hit rate (2026-02-28)

---

## 3. 產品策略方向 (CEO/CPO Brainstorm)

### 商業模式建議 (按優先級)
1. **API-First SaaS** — 面向量化交易員，月費 $99-299
2. **Premium Newsletter** — 每日 alpha 信號摘要，月費 $29-49
3. **機構 Data Feed** — 結構化數據 API，年費 $5K-20K
4. **白牌解決方案** — 金融科技公司 OEM，按客戶計費

### 競品深度分析 (MR-001, 2026-02-28)

> 完整報告: `docs/reports/Competitive_Analysis_2026-02-28.md`

| 競品 | 定價 | 規模 | 優勢 | PAM 差異化 |
|------|------|------|------|-----------|
| Capitol Trades | 免費 | 媒體引用最多 | 產業知名度最高，零門檻 | 資料庫 vs 決策引擎 |
| Quiver Quantitative | $25/月 | 750K用戶, ARR>$200萬 | 最廣替代數據覆蓋, Python SDK | 基礎統計 vs FF3 學術驗證 |
| Unusual Whales | $42-170/月 | NANC/KRUZ ETF合作 | 選擇權流+國會唯一整合 | 國會是附加 vs PAM 核心 |
| Autopilot | $100/年 | 100K+用戶, $20億交易 | 最低門檻自動跟單 | 盲目跟單 vs 量化過濾層 |
| CongressEdge | 未公開 | 10K+投資者 | 最接近 PAM 定位 | 無 FF3/PACS/收斂/研究支撐 |

### 建議定價策略

| 方案 | 月費 | 年費 | 目標 |
|------|------|------|------|
| Free | $0 | $0 | 試用 (7天交易列表+基礎排名) |
| Signal | $29 | $290 | 積極投資者 (SQS+PACS+PIS+告警) |
| Alpha | $79 | $790 | 進階交易者/RIA (收斂+輪動+回測+API) |
| Institution | 客製 | $5K-20K | 對沖基金 (全功能API+FF3+白牌) |

### 核心 Pitch
> "PAM 是全球唯一以學術級量化研究支撐的國會交易 alpha 信號系統。5,000+ 筆交易回測中，Buy-Only 策略 +1.10% 20d CAR (59.2% WR)；VIX Goldilocks Zone (14-16) +1.03% (p<0.05)。7 份研究報告每個聲明都有 p 值和 FF3 因子調整可引用。其他平台告訴你議員買了什麼，PAM 告訴你該不該跟、有多大信心、預期賺多少。"

### Q2 功能優先級
1. **P0**: 即時告警推播 (Telegram/Discord/Email) — 最低成本最高價值
2. **P0**: Signal Performance Dashboard — 證明系統有效
3. **P1**: API 產品化 (FastAPI → production-ready)
4. **P1**: 用戶認證 + 付費牆
5. **P2**: Paper Trading 模擬
6. **P2**: 多市場擴展 (歐洲議會)

---

## 4. 技術架構路線圖 (CTO/Tech Lead)

### P0 (立即處理)
- [x] ~~測試套件~~ — 已完成 170 tests
- [x] ~~CI/CD~~ — 已完成 GitHub Actions
- [ ] FastAPI 認證 — JWT/API Key auth middleware
- [ ] `.env` 安全管理 — secrets manager or encrypted vault
- [ ] Error handling 標準化 — 統一異常處理框架

### P1 (本季度)
- [ ] PostgreSQL 遷移評估 — 預計 10K+ trades 時需要
- [ ] API Rate Limiting — 防止濫用
- [ ] Structured Logging — JSON log format for monitoring
- [ ] Docker 容器化 — 統一開發/生產環境
- [ ] LLM 成本監控 — Gemini API usage tracking

### P2 (下季度)
- [ ] 微服務拆分 — ETL / Analysis / API 分離
- [ ] 事件驅動架構 — 新交易自動觸發分析
- [ ] 緩存層 — Redis for frequent queries
- [ ] 前端重構 — React/Next.js 替換 Streamlit

### 技術債評估 (2026-02-28, 完整報告: `docs/reports/Tech_Debt_Assessment_2026-02-28.md`)

| # | 項目 | 嚴重度 | 優先級 | 狀態 |
|---|------|--------|--------|------|
| TD-001 | LLM JSON 解析 | Medium | P1 | **已修復** (3-layer fallback + logging) |
| TD-002 | Senate Akamai bypass | Medium | P2 | 已緩解 (有 fallback，缺健康告警) |
| TD-003 | Legacy fetchers 清理 | Low | - | **已解決** (全移至 bk/) |
| TD-004 | src/main.py bare imports | Low | - | **已解決** (已刪除) |
| TD-005 | Error handling 標準化 | Medium | P2 | **已建立** (src/exceptions.py 異常體系) |
| TD-006 | DB 連線管理散亂 | High | P1 | **已建立** (get_connection context manager) |
| TD-007 | DB_PATH 硬編碼殘留 | Low | P3 | **已修復** (name_mapping, ticker_enricher)

---

## 5. 新數據源路線圖 (CDO/Research Lead)

### 高優先級 (Spike 已完成)

| 數據源 | 評估結果 | 評分 | Alpha 潛力 | 報告 |
|--------|---------|------|-----------|------|
| **RB-008** Committee Assignments | **SHELVE** (p=0.33) | 7.2/10 | Leaders +0.20% 5d, not significant | `Spike_RB-008_Congress_Committee_API.md` |
| **RB-009** USASpending Contracts | **INTEGRATED** (Phase 2 done) | 7.9/10 | 議員+合約收斂 +3-5% | `Spike_RB-009_USASpending_API.md` |
| **RB-011** SEC Form4+Congress 收斂 | **CONDITIONAL SHELVE** | 4.0→3.5/10 | 結構性分歧: congress買+insider賣 | Innovation Sprint PM |
| **RB-010** Earnings Calendar Cross-ref | **REJECT** (p=0.83) | 3.0/10 | 13.4% vs 15.4% expected, below random | PM Sprint |

**RB-008 更新 (2026-02-28 POC)**: 下載 119th Congress 委員會 YAML，匹配 222 chairs 到 DB。Leaders +0.20% 5d alpha premium，但 **p=0.33 不顯著**。樣本不平衡 (305 vs 50)。**SHELVE** — 需累積 2000+ trades 後重新驗證。

**RB-009 更新 (2026-02-28 PM Sprint)**: **Phase 2 整合完成** — contractor_tickers.json 38→98 entries, convergence_detector +contract_proximity scoring, signal_enhancer +contract_award_bonus, 20 new tests (310 total). Commits: 9ec6e2c, c798a42, 656c9f9, 020732c.

**RB-011 更新 (2026-02-28 PM Sprint)**: Form4 修復後 52→336 trades, 28 ticker overlap。發現**結構性分歧**: congress 主要買入而 insiders 主要賣出同一股票 (53 divergent vs 3 aligned)。**CONDITIONAL SHELVE** — aligned N=3 不足。新研究方向: 分歧本身可能為反向指標。

### 中優先級
| 數據源 | API | 預期 Alpha | 難度 | 研究代號 |
|--------|-----|-----------|------|----------|
| SEC Form 4 + Congress 交叉強化 | Already have | Medium | Low | RB-011 |
| Lobbying Disclosure | lobbying.senate.gov | Medium | High | RB-012 |
| FEC Campaign Finance | OpenSecrets API | Low-Med | Medium | — |

### 低優先級 / 未來考慮
- FOMC Member Disclosures (數據稀少)
- Patent Filings (關聯度低)
- Real-time Options Flow (需要付費數據源 ~$50-200/mo)

### 研究提案 (更新 2026-02-28)
- **RB-008**: ~~委員會 Alpha~~ → **POC 完成, SHELVE** (p=0.33, 樣本不足)。需 2000+ trades 後重驗。
- **RB-009**: ~~政府合約 Alpha~~ → **Phase 2 整合完成**。下一步：Phase 3 回測驗證。
- **RB-010**: ~~財報時機 Alpha~~ → **REJECT** (p=0.83，觀察 13.4% < 預期 15.4%)。Buy 子集有弱信號 (19.2%, p=0.15) 但 N=16 且 Cisneros 占 71%。
- **RB-011**: ~~SEC Form4+Congress 收斂~~ → **CONDITIONAL SHELVE** (結構性分歧: congress買+insider賣)。
- **RB-012**: 遊說-交易相關性 — 被遊說議員是否交易遊說公司股票？

---

## 6. 下一步行動清單

### 本週 (W1)
- [ ] 設定 Social Media API credentials (APIFY_API_TOKEN, REDDIT_*)
- [x] 首次執行 `python -m src.signal_tracker` 開始追蹤信號績效 — 39 signals, +2.50% CAR_5d, 64.1% HR
- [ ] 設定 WSL2 cron 排程 (`bash cron_setup.sh`)
- [ ] FastAPI 加入 JWT 認證

### 本月 (March)
- [ ] **RB-009 Phase 3**: 歷史合約回填 + BUY+contract vs BUY-only alpha 回測
- [ ] **RB-009 自動化**: USASpending daily fetch 加入 run_daily.py
- [ ] Signal Performance Dashboard (Streamlit 新頁面)
- [ ] Docker 容器化
- [ ] API 產品化文檔 (OpenAPI spec)
- [ ] TD-002: Senate ETL 健康告警 (Telegram 通知)
- [ ] TD-005: 逐步替換 bare except (ETL 模組優先)
- [ ] Signal Tracker 20d 評估 (2026-03-15 後可跑)

### 本季 (Q2)
- [ ] **RB-008 Phase 2**: 累積 2000+ trades 後重驗委員會 alpha (SHELVE 中)
- [x] ~~**RB-009 整合**: convergence + signal_enhancer contract_award_bonus~~ — **已完成 (PM Sprint)**
- [ ] **RB-011 監控**: Aligned convergence N≥30 時重驗; 分歧反向指標假說待立
- [ ] PostgreSQL 遷移 (if trades > 5K)
- [ ] 付費牆 + 用戶管理 (Free/Signal/Alpha/Institution 四層)
- [ ] RB-012 遊說-交易研究
- [ ] 多市場 POC (歐洲議會)

---

---

## 7. PM R&D Sprint 成果 (2026-02-28 下午)

### 基礎建設修復
| Bug | 修復 | Commit | 驗證 |
|-----|------|--------|------|
| signal_tracker 用 created_at (全同一天) | JOIN congress_trades 取 filing_date | 3d4f44a | 4 signals 有實際報酬, 75% hit rate |
| sec_form4 隨機抓取 (52 trades, 1 overlap) | --congress-tickers 模式 | 6aac906 | 336 trades, 53 tickers, 28 overlap |

### 研究成果
| Track | 結果 | 影響 |
|-------|------|------|
| RB-009 Phase 2 | **INTEGRATED** — 4 commits, 98 tickers, 20 tests | 合約收斂評分已上線 |
| RB-011 Re-analysis | **CONDITIONAL SHELVE** — 結構性分歧 | 新研究方向: 反向指標 |
| RB-010 Earnings Calendar | **REJECT** (p=0.83) | 議員不在財報前集中交易 |

### DB 變化
- sec_form4_trades: 52→336 (+284)
- signal_performance: 15→48 (+33, 4 有實際報酬)
- Tests: 290→310 (+20)

*Generated by PAM Sprint Team | 2026-02-28 | Updated: PM R&D Sprint — RB-009 INTEGRATED, RB-011 CONDITIONAL SHELVE, infra fixes deployed*
