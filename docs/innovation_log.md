# PAM Innovation Log

Innovation explorations organized chronologically.

---

## 2026-02-28 Innovation: Committee Assignment Alpha (RB-008)

**Direction**: DISCOVER
**Verdict**: CONDITIONAL GO (Spike)
**Score**: 7.2/10

### Key Findings
- Source: GitHub YAML (unitedstates/congress-legislators), NOT Congress.gov API
- Academic: Kempf 2022 — committee chair alpha +40-47%/year
- Limitation: Only current 119th Congress members, no historical data

### Next Steps
- [ ] Phase 1: Download YAML → committee_memberships table → CommitteeMatcher
- [ ] Phase 2: Historical committee members + backtest validation

---

## 2026-02-28 Innovation: USASpending Government Contracts (RB-009)

**Direction**: DISCOVER
**Verdict**: INTEGRATE (升級自 GO)
**Score**: 7.9/10

### Key Findings
- API: Completely free, no auth, generous rate limits
- Academic: CEPR 2025 confirms congress+contract convergence causal chain
- Risk: DoD contracts have 90-day public disclosure delay
- Need: Contractor→ticker 3-layer mapping (static + SEC + yfinance)

### POC Results (2026-02-28)
- **API confirmed**: POST endpoint, 1.25~2.81s/req, no rate limit issues
- **Top contract tickers**: ORCL ($6.5B), AVAV ($1.7B), MSFT ($1.6B), AMZN ($1.2B)
- **Cross-reference**: 5 trade-contract convergence pairs found in T±90d window
- **Best signal**: Cisneros BUY AVAV (2025-12-15) + DoD $62.3M contract — drone manufacturer, committee-informed trading model
- **Coverage**: 31/356 trades (8.7%) match contractors; expected 15-20% with Top 100 mapping
- **Note**: `recipient_uei` is null in search endpoint, use `recipient_parent_name` for fuzzy match

### Integration Plan (5-8 days)
- Phase 1 (1-2d): `usaspending_fetcher.py` + `data/contractor_tickers.json` (Top 30)
- Phase 2 (2-3d): `convergence_detector.py` contract_proximity_score + `signal_enhancer.py` contract_award_bonus
- Phase 3 (2-3d): Historical backtest validation

### Next Steps
- [ ] Complete usaspending_fetcher.py (skeleton exists at src/etl/)
- [ ] Build contractor_tickers.json static mapping (Top 30 tickers)
- [ ] Add contract_proximity_score to convergence_detector
- [ ] Backtest: BUY + contract convergence vs BUY-only alpha

---

## 2026-02-28 Innovation: SEC Form4 + Congress Convergence (RB-011)

**Direction**: DISCOVER
**Verdict**: INCONCLUSIVE
**Score**: 4.0/10

### Key Findings
- SEC Form 4 data: only 52 trades, 10 unique tickers
- Congress trades overlap: 1 common ticker only
- 30-day convergence window: 0 matches (zero convergence trades)
- Root cause: SEC Form 4 data volume critically insufficient

### Detailed Findings
- Form 4 DB has **zero P (Purchase) codes** — only S/M/A/F transactions
- Only overlapping ticker: DASH — Cisneros BUY vs COO Adarkar SELL (contradictory, not convergent)
- Sample n=5, far below t-test threshold (>=20)

### Root Cause
- `run_sec_form4.py` uses random/specific company fetching strategy
- Needs to be modified to fetch Form 4 by congress_trades' 264 tickers

### Next Steps
- [ ] Modify run_sec_form4.py: fetch by congress tickers (not random companies)
- [ ] Verify P (Purchase) transaction codes are not being filtered out
- [ ] Fetch 12-month historical data for congress-traded tickers
- [ ] Re-run convergence analysis with targeted dataset

---

## 2026-02-28 POC: Committee Alpha Validation (RB-008 Phase 1)

**Direction**: DISCOVER
**Verdict**: SHELVE (insufficient sample)

### POC Results
- Downloaded 119th Congress committee YAML data (3 files)
- Matched 222 chairs + 220 ranking members to congress_trades
- 4 chairs found in DB: John Boozman, David McCormick, etc.
- Alpha comparison: Leaders +0.20% 5d, +0.08% 20d vs Non-Leaders
- **t-test p=0.33 — NOT statistically significant**
- Sample imbalance: 305 leader signals vs 50 non-leader signals

### Limitations
- Current DB has only 404 trades; 305/355 signals from committee leaders
- Need 2000+ trades for statistical power to detect 0.2% alpha difference
- John Boozman alone accounts for disproportionate share

### Next Steps
- [ ] Accumulate more trades (target 2000+) before Phase 2
- [ ] Phase 2: Historical committee members + backtest validation

---

## 2026-02-28 Signal Tracker Baseline Validation

**Type**: SYSTEM VALIDATION
**Result**: CONFIRMED — signals perform as expected

### Findings
- 39 signals validated (filing_date <= 2026-02-15, sufficient time for 5d returns)
- Average CAR_5d: **+2.50%** (median +0.69%)
- Hit Rate: **64.1%** (25/39) — healthy range
- vs RB-001 baseline +0.77%: median close, mean inflated by outliers
- Top performer: OMC (Omnicom) +20.64%
- Worst: FISV (Fiserv) -7.47%
- 20d returns: all N/A (signals too recent, need data after 2026-03-15)

### Conclusion
System signals perform consistently with historical backtest expectations (RB-001)
