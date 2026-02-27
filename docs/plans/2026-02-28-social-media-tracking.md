# Social Media Tracking Module — Design Document

**日期**: 2026-02-28
**狀態**: Approved → Implementation
**決策者**: 高層主管

---

## 1. Understanding Summary

### Building
社群媒體追蹤模組 — 雙軌信號系統

- **軌道 A**: 國會議員社群帳號 → 與現有 `congress_trades` 交叉比對（言行一致/矛盾分析）
- **軌道 B**: 高影響力人物 (Trump, Musk 等) → 發言→股價影響偵測

### Because
- 軌道 A：市場獨特信號，幾乎沒人做議員「說什麼」vs「買什麼」的交叉
- 軌道 B：這些人的發言可直接移動市場，有即時 alpha
- 學術支持：[NBER w28749 (RFS 2024)](https://www.nber.org/papers/w28749) — 委員會成員推文幾分鐘內移動股價

### For
整合進現有 Political Alpha Monitor pipeline，最終輸出到 `alpha_signals` 和告警系統

### Constraints
- 每日批次：美股開盤前完成（台灣時間 ~20:00 出結果）
- 成本控制：~$5-49/mo (Apify) + Gemini (~$1-5/mo)
- NLP：FinTwitBERT (本地) + Gemini Flash (深度分析)

### Non-goals
- 不做即時串流監控（日頻足夠）
- 不做全網輿情（只追蹤特定人物）
- 不做高頻交易（秒級延遲不要求）

---

## 2. Architecture

### Chosen Approach: Apify-First Daily Batch

```
排程：每天台灣時間 ~19:00 (美東 6:00 AM)

Step 1: 抓取 (Apify + PRAW)
  Apify Twitter Actor  → 追蹤名單過去 24hr 貼文
  Apify Truth Social   → Trump 過去 24hr 貼文
  PRAW Reddit          → 追蹤的 subreddit 過去 24hr
        ↓
  寫入 social_posts 表

Step 2: NLP 分析 (FinTwitBERT + Gemini)
  social_posts → FinTwitBERT (本地) → confidence < 0.75 → Gemini Flash
                                    → confidence >= 0.75 → 直接標記
        ↓
  寫入 social_signals 表

Step 3: 交叉比對
  social_signals × congress_trades → speech_trade_alignment
  social_signals × 股價/sector    → 影響力評估
        ↓
  寫入 alpha_signals (新增 social 來源)

Step 4: 報告 + 告警
  → Telegram alert (CONTRADICTORY 信號)
  → Dashboard 更新
  → 每日報告
```

### New Modules

| 模組 | 路徑 | 功能 |
|------|------|------|
| Social Targets | `src/social_targets.py` | 追蹤名單配置 |
| Social Fetcher | `src/etl/social_fetcher.py` | Apify + PRAW 統一抓取層 |
| Social NLP | `src/social_nlp.py` | FinTwitBERT + Gemini 雙層分析 |
| Social Analyzer | `src/social_analyzer.py` | 交叉比對 + 信號生成 |

---

## 3. DB Schema

```sql
CREATE TABLE social_posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform TEXT NOT NULL,
    author_name TEXT NOT NULL,
    author_handle TEXT,
    author_type TEXT NOT NULL,
    post_id TEXT,
    post_text TEXT NOT NULL,
    post_url TEXT,
    post_time TEXT,
    likes INTEGER DEFAULT 0,
    retweets INTEGER DEFAULT 0,
    replies INTEGER DEFAULT 0,
    media_type TEXT,
    data_hash TEXT UNIQUE,
    fetched_at TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE social_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id INTEGER REFERENCES social_posts(id),
    author_name TEXT NOT NULL,
    author_type TEXT NOT NULL,
    platform TEXT NOT NULL,
    sentiment TEXT,
    sentiment_score REAL,
    signal_type TEXT,
    sarcasm_detected INTEGER DEFAULT 0,
    tickers_explicit TEXT,
    tickers_implied TEXT,
    sector TEXT,
    analysis_model TEXT,
    impact_score REAL,
    reasoning TEXT,
    congress_trade_match INTEGER DEFAULT 0,
    speech_trade_alignment TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
```

---

## 4. Tracking Lists

### Politicians (aligned with RB-005 Top Performers)
- Nancy Pelosi (@SpeakerPelosi)
- Tommy Tuberville (@SenTuberville)
- Rick Allen (@RepRickAllen)
- Gilbert Cisneros (@RepGilCisneros)
- John Boozman (@JohnBoozman)
- Dave McCormick (@DaveMcCormickPA)
- Dan Crenshaw (@DanCrenshawTX)
- Mark Cohen (@CohenMark)

### KOLs (High-Influence Figures)
- Donald Trump (Truth Social + X: @realDonaldTrump)
- Elon Musk (X: @elonmusk)
- Cathie Wood (X: @CathieDWood)
- Jim Cramer (X: @jimcramer) — CONTRARIAN indicator
- Bill Ackman (X: @BillAckman)
- Keith Gill / Roaring Kitty (X + Reddit)

---

## 5. NLP Pipeline

### Two-Stage Architecture
1. **Stage 1**: FinTwitBERT (local, free, ~100ms/post)
   - Model: `StephanAkkerman/FinTwitBERT-sentiment`
   - Output: {sentiment, confidence}
   - Route to Stage 2 if confidence < 0.75 or sarcasm detected

2. **Stage 2**: Gemini 2.5 Flash (API, ~$0.001-0.005/post)
   - Two specialized prompts: POLITICIAN vs KOL
   - Output: Full JSON (sentiment, tickers, signal_type, reasoning)

### Cross-Reference Logic
- CONSISTENT (say bullish + buy) → convergence_bonus +0.3
- CONTRADICTORY (say bullish + sell) → anomaly alert 🚨
- NO_TRADE → normal social signal weight

---

## 6. Dependencies

```bash
pip install transformers torch    # FinTwitBERT
pip install praw                  # Reddit API
pip install apify-client          # Apify SDK
```

---

## 7. Decision Log

| Decision | Alternatives | Rationale |
|----------|-------------|-----------|
| Apify for X/Truth Social | X API ($200+/mo) | 10-40x cheaper, daily batch sufficient |
| FinTwitBERT + Gemini hybrid | All Gemini | 75% API cost reduction |
| Daily batch | Real-time stream | Congress trades have day-level lag |
| Politician-specific prompt | Unified prompt | Committee context is strongest predictor |
| Cramer as contrarian | Normal processing | Inverse Cramer effect statistically validated |

---

*Document generated: 2026-02-28*
*Status: Approved for implementation*
