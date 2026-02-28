# PAM R&D Sprint Report — 2026-02-28 PM Session

> **Duration**: ~2 hours | **Team**: pam-rnd-0228-pm (3 agents + team lead)
> **Focus**: R&D — infrastructure fixes, RB-009 integration, RB-010/RB-011 research

---

## Executive Summary

Applied lessons from morning sprint (data audit first), dispatched 3 parallel research tracks. Successfully integrated RB-009 government contracts into core analysis engine, fixed 2 critical infrastructure bugs, re-analyzed RB-011 with expanded data, and initiated RB-010 earnings calendar research.

**Key deliverables**: 6 commits, 20 new tests (290→310), 284 new Form4 trades, RB-009 production-ready.

---

## Track A: RB-009 Phase 2 — Government Contract Integration (rb009-integrator)

**Status**: COMPLETE | **Commits**: 4

### Deliverables

1. **contractor_tickers.json** (9ec6e2c) — Expanded from 38→98 tickers
   - Coverage by sector: Industrials(27), Technology(23), Healthcare(16), Financials(7), Energy(6), Communication(6), Consumer(6), Real Estate(4), Utilities(3)
   - Each entry: search_terms, sector, optional naics/primary_agency/gov_revenue_pct

2. **convergence_detector.py** (c798a42) — +91 lines
   - New `_get_contract_proximity(ticker, trade_date)` method
   - Scoring: BUY direction +0.3, $100M+ +0.3, DoD +0.1, time proximity +0.3
   - New `score_contract` component in breakdown (×0.5 weight)
   - Backward compatible: returns 0.0 if contract_cross_refs table absent

3. **signal_enhancer.py** (656c9f9) — +53 lines
   - New `_load_contract_data()` → grouped by ticker
   - PACS contract_award_bonus: +0.1 any contract, +0.2 for $100M+
   - New `pacs_contract_component` column in enhanced_signals
   - ALTER TABLE fallback for backward compatibility

4. **tests/test_rb009_integration.py** (020732c) — 20 new tests
   - 8 format validation tests (contractor_tickers.json structure)
   - 6 contract proximity scoring tests (edge cases, no-data, DoD bonus)
   - 6 signal enhancer contract bonus tests
   - All 310 tests pass

---

## Track B: Infrastructure Fixes + RB-011 Re-analysis (infra-fixer)

**Status**: COMPLETE | **Commits**: 2

### Bug 1: signal_tracker.py Filing Date (3d4f44a)

**Problem**: All 355 alpha_signals had `created_at = 2026-02-27` (same batch creation day). Signal tracker thought no signals were old enough for return calculation → all actual returns NULL.

**Fix**:
- Changed SQL to JOIN alpha_signals with congress_trades via trade_id
- SELECT `ct.filing_date` instead of `created_at` as event date
- Added `_flatten_columns()` for yfinance MultiIndex protection
- Added `--force-reevaluate` CLI flag to clear stale NULL records

**Verification**: 4 signals now have actual returns:
| Ticker | Filing Date | Actual Return 5d | Hit? |
|--------|------------|-------------------|------|
| AAPL   | 2026-02-06 | +2.01% | YES |
| AAPL   | 2026-02-03 | +2.47% | YES |
| NFLX   | 2026-02-10 | +0.69% | YES |
| DIS    | 2026-02-10 | -0.08% | NO  |

Hit rate: **75%** (3/4) — consistent with RB-001 baseline (64.1%)

### Bug 2: sec_form4_fetcher.py Targeted Fetching (6aac906)

**Problem**: Generic `q="form 4"` search returned random companies → 52 trades, 10 tickers, 1 overlap with congress_trades. Zero Purchase (P) codes because random mega-caps mostly have insider sells.

**Fix**:
- Added `fetch_by_tickers(tickers, days, max_filings_per_ticker)` method
- Added `_search_filings_by_ticker()` for targeted EDGAR search
- Added `--congress-tickers` and `--max-tickers` CLI flags to `run_sec_form4.py`
- Confirmed XML parser does NOT filter Purchase transaction code

**After fix**: 336 trades, 53 tickers, 28 overlap with congress_trades, 13 Purchase transactions

### RB-011 Re-analysis Results

With expanded Form4 data (52→336 trades, 1→28 ticker overlap):

**Structural Divergence Finding**:
- 53 divergent records: Congress members BUY while insiders SELL
- 3 aligned SELL records: Both congress and insider sell
- 0 aligned BUY records: No case where both bought
- Root cause: Insiders predominantly sell (compensation liquidation, 10b5-1 plans), congress predominantly buys

**Verdict**: CONDITIONAL SHELVE (N=3 aligned far too small for alpha testing)
**New research lead**: Divergence pattern itself may be a contrarian indicator

---

## Track C: RB-010 Earnings Calendar (rb010-researcher + team-lead)

**Status**: COMPLETE | **Verdict**: REJECT (p=0.83)

### Methodology
- yfinance `earnings_dates` for 264 unique tickers (168 covered, 63.6%)
- Cross-reference: days_to_next_earnings for each of 232 testable trades
- Binomial test: observed pre-earnings (≤14d) rate vs expected 15.4% (14/91 days)
- Alpha comparison: pre-earnings trades vs non-pre-earnings trades

### Key Results
| Metric | Value |
|--------|-------|
| Testable trades | 232 |
| Pre-earnings trades | 31 (13.4%) |
| Expected (random) | 15.4% |
| Binomial p-value | **0.8272** (not significant) |
| Effect size h | -0.058 (negligible) |

### Buy vs Sale
- **Buy**: 19.2% pre-earnings (p=0.15) — slightly elevated, not significant
- **Sale**: 7.1% pre-earnings (p=0.997) — below random, sales avoid pre-earnings

### Alpha (Suggestive but N too small)
- Pre-earnings Buys (N=16): **CAR20 +2.51%, WR 68.8%**
- Non-pre-earnings Buys (N=86): CAR20 +1.30%, WR 53.5%
- t-test p=0.72 — NOT significant

### Concentration Issue
- Cisneros: 22/31 pre-earnings trades (71%) — single politician dominates

### Conclusion
Congress members do NOT trade disproportionately before earnings. The observed rate is actually below random. Buy trades show a weak suggestive signal but N=16 with extreme Cisneros concentration makes it unreliable. **REJECT** at current data volume.

---

## Data Audit (Applied Lesson from AM Sprint)

Before dispatching agents, conducted comprehensive data audit:
- congress_trades: 404 rows, 264 unique tickers
- sec_form4_trades: 52 (pre-fix), zero Purchase codes
- signal_performance: 15 rows, all actual returns NULL
- filing_date range: 2026-02-01 to 2026-02-27
- RB-010 feasibility: 264 tickers, 15 with 3+ trades

This prevented the morning sprint's mistake of launching research without verifying data quality.

---

## DB Changes Summary

| Table | Before | After | Delta |
|-------|--------|-------|-------|
| sec_form4_trades | 52 | 336 | +284 |
| signal_performance | 15 (0 with returns) | 48 (4 with returns) | +33 |
| contractor_tickers.json | 38 | 98 | +60 |
| Tests | 290 | 310 | +20 |

---

## Git History (PM Sprint)

```
020732c test: add 20 tests for RB-009 contract integration
656c9f9 feat: add contract_award_bonus to signal_enhancer PACS calculation (RB-009)
6aac906 feat: add --congress-tickers mode for targeted SEC Form 4 fetching
c798a42 feat: add contract proximity scoring to convergence_detector (RB-009)
9ec6e2c feat: expand contractor_tickers.json to 98 entries (RB-009)
3d4f44a fix: use filing_date instead of created_at for signal performance tracking
```

---

## Next Steps

1. **RB-010 completion**: Process earnings calendar results when available
2. **RB-009 Phase 3**: Historical contract backfill + alpha backtest (BUY+contract vs BUY-only)
3. **USASpending automation**: Add daily fetch to run_daily.py
4. **Signal Tracker 20d**: Re-run after 2026-03-15 for 20-day return evaluation
5. **RB-011 monitoring**: Watch aligned convergence count; re-evaluate at N≥30
6. **New hypothesis**: Congress-insider DIVERGENCE as contrarian signal (dedicated RB study)

---

*Generated by PAM R&D Sprint Team | 2026-02-28 PM | Team: pam-rnd-0228-pm*
