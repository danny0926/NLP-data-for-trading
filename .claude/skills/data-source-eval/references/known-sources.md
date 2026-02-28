# PAM 已知數據源清單

## 已整合 (Production)

| 數據源 | Fetcher | Status | Notes |
|--------|---------|--------|-------|
| Senate EFD | src/etl/senate_fetcher.py | Active | Playwright + Akamai bypass |
| Capitol Trades | src/etl/capitoltrades_fetcher.py | Fallback | 1-based pagination |
| House Clerk | src/etl/house_fetcher.py | Active | PDF + Gemini Vision |
| SEC EDGAR Form 4 | src/etl/sec_form4_fetcher.py | Active | XML parsing |
| Twitter/X | src/etl/social_fetcher.py | Ready | Needs APIFY_API_TOKEN |
| Truth Social | src/etl/social_fetcher.py | Ready | Needs APIFY_API_TOKEN |
| Reddit | src/etl/social_fetcher.py | Ready | Needs REDDIT_* creds |
| Kenneth French Library | src/fama_french.py | Active | Daily CSV auto-download |
| Yahoo Finance (VIX/Prices) | yfinance | Active | Used by signal_enhancer, alpha_backtest |

## 計畫中 (Roadmap)

| 數據源 | 研究代號 | API | 預期 Alpha | 難度 |
|--------|----------|-----|-----------|------|
| Congressional Committee Assignments | RB-008 | congress.gov API (免費) | High | Medium |
| Government Contracts (USASpending) | RB-009 | USASpending API (免費) | High | Medium |
| Earnings Calendar Cross-ref | RB-010 | Yahoo Finance / EarningsWhispers | Medium | Low |
| SEC Form 4 + Congress Cross | RB-011 | Already have data | Medium | Low |
| Lobbying Disclosure | RB-012 | lobbying.senate.gov | Medium | High |
| FEC Campaign Finance | — | OpenSecrets API | Low-Med | Medium |

## 已排除

| 數據源 | 原因 |
|--------|------|
| FOMC Member Disclosures | 數據稀少 |
| Patent Filings | 關聯度低 |
| Real-time Options Flow | 需付費 $50-200/mo，ROI 不確定 |
