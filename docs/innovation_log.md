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

### Phase 2 Integration (2026-02-28 PM Sprint)
- [x] **contractor_tickers.json** expanded: 38→98 tickers (9 sectors: Industrials 27, Tech 23, Healthcare 16, Financials 7, Energy 6, Communication 6, Consumer 6, Real Estate 4, Utilities 3)
- [x] **convergence_detector.py** +91 lines: `_get_contract_proximity()` — BUY direction +0.3, $100M+ +0.3, DoD +0.1, time proximity +0.3, `score_contract` component (×0.5)
- [x] **signal_enhancer.py** +53 lines: `_load_contract_data()` + `pacs_contract_component` — +0.1 any contract, +0.2 for $100M+
- [x] **20 new tests**: `tests/test_rb009_integration.py` — 8 format, 6 proximity, 6 bonus tests (310 total pass)
- Commits: 9ec6e2c, c798a42, 656c9f9, 020732c

### Next Steps
- [ ] Backtest: BUY + contract convergence vs BUY-only alpha (requires more contract data)
- [ ] Automate USASpending daily fetch in run_daily.py
- [ ] Historical contract data backfill (2024-2025)

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

### Re-Analysis (2026-02-28 PM Sprint)

After fixing both the fetcher and analysis pipeline:
- **Fixes applied**: `--congress-tickers` mode added to `run_sec_form4.py` (commit 6aac906), `signal_tracker.py` filing_date fix (commit 3d4f44a)
- **Expanded data**: 52→336 Form 4 trades, 10→53 unique tickers, 1→28 overlap with congress_trades
- **Purchase codes confirmed**: 13 P (Purchase) transactions found — original fetcher's generic search was the root cause, NOT a filter bug

#### Structural Divergence Finding
- **53 divergent records**: Congress members BUY while insiders SELL the same stocks
- **3 aligned records**: Both sell (far below threshold for alpha testing)
- **0 aligned BUY records**: No case where congress and insiders both bought
- **Root cause**: Insiders predominantly sell (compensation liquidation, 10b5-1 plans), while congress predominantly buys

**Updated Verdict**: CONDITIONAL SHELVE (N=3 aligned too small)
**New Research Lead**: The divergence pattern itself (congress buys what insiders sell) may be a contrarian indicator — worth a dedicated study if data accumulates to N>=30 aligned.

### Next Steps
- [ ] Monitor aligned convergence count; re-evaluate when N≥30
- [ ] New hypothesis: Congress-insider DIVERGENCE as contrarian signal (requires dedicated RB)

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

---

## 2026-02-28 RB-010: Earnings Calendar Cross-Reference

**Direction**: TIMING
**Verdict**: REJECT
**Score**: 3.0/10

### Hypothesis
- **H1**: Congress members trade disproportionately within 14 days before earnings announcements
- **H0**: Trading timing is independent of earnings calendar

### Data
- 356 trades, 264 tickers; yfinance earnings coverage: 168/264 (63.6%)
- Testable: 232 trades with earnings dates; Pre-earnings (≤14d): 31 trades

### Statistical Results
- **Observed pre-earnings rate: 13.4%** vs expected 15.4% (14/91 days)
- **Binomial test p=0.8272** — NOT significant (actually below random!)
- Effect size h=-0.058 (negligible, negative direction)
- 95% CI: [9.6%, 18.3%]

### Buy vs Sale Breakdown
- **Buy**: 19.2% pre-earnings (p=0.1534) — slightly elevated but not significant
- **Sale**: 7.1% pre-earnings (p=0.9973) — significantly LOWER than random

### Alpha Comparison (Suggestive but N too small)
- Pre-earnings Buys (N=16): CAR20 +2.51%, WR 68.8%
- Non-pre-earnings Buys (N=86): CAR20 +1.30%, WR 53.5%
- t-test p=0.7173 — NOT significant

### Concentration Issue
- Gilbert Cisneros: 22/31 pre-earnings trades (71%) — extreme concentration
- Only 4 politicians have any pre-earnings trades

### Days-to-Earnings Distribution
- 1-7d: 5.2%, 8-14d: 8.2%, 15-30d: 22.8%, 31-60d: 36.2%, 61-91d: 23.7%
- Slightly front-loaded but well within random variation

### Verdict
**REJECT** — Congress members do NOT trade more before earnings. The overall rate (13.4%) is actually below random (15.4%). Buy trades show a weak suggestive signal (19.2%, p=0.15) but N=16 with 71% Cisneros concentration makes this unreliable.

### Next Steps
- [ ] Re-evaluate when DB reaches 2000+ trades (larger sample may reveal signal in Buy subset)
- [ ] Not recommended for implementation at current data volume
