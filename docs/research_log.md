# PAM Research Log

Research findings organized by RB (Research Brief) number.

---

## 2026-02-28 RB-001: Signal Quality + Alpha Validation

**Hypothesis**: Congressional Buy trades have positive abnormal returns
**Type**: ALPHA
**Result**: ADOPT

### Key Findings
| Metric | Buy | Sale |
|--------|-----|------|
| CAR_5d | +0.77% (p<0.001) | Contrarian (stocks UP) |
| CAR_20d | +0.79% (p=0.007) | -3.21% |
| Best amount | $15K-$50K | â€” |
| Best chamber | House > Senate in alpha | â€” |
| Filing lag <15d | +1.13% | â€” |

---

## 2026-02-28 RB-004: Optimal Trading Timing

**Hypothesis**: Buy-only strategy outperforms buy+sell
**Type**: TIMING
**Result**: ADOPT

### Key Findings
- Buy-Only: +1.10% 20d CAR (59.2% WR) vs Sale -3.21%
- Senate >> House: +1.39% 20d (69.2% WR) vs House -1.27%
- VIX Goldilocks 14-16: +1.03% 20d CAR (p<0.05)
- Thursday trades best; mid-month outperforms

---

## 2026-02-28 RB-005: Politician Deep Dive

**Hypothesis**: Individual politician performance varies significantly
**Type**: ALPHA
**Result**: ADOPT

### Key Findings
- Top 5: Richard Allen (83.3% WR), Gilbert Cisneros, John Boozman, David McCormick, Steve Cohen
- K-means clustering: "Active Stock Traders" cluster best for copy-trading
- PIS ranking system validated across 17 ranked politicians

---

## 2026-02-28 RB-006: Multi-Signal Fusion (PACS Formula)

**Hypothesis**: Composite signal outperforms individual components
**Type**: SIGNAL
**Result**: ADOPT

### Key Findings
- PACS = 50% signal_strength + 25% filing_lag_inv + 15% options_sentiment + 10% convergence
- Q1-Q4 spread: 6.5% alpha difference
- SQS conviction is NEGATIVE predictor (r=-0.50) â€” counterintuitive but validated
- Options sentiment independent from congress signals (|r|<0.15)

---

## 2026-02-28 RB-007: Sector Rotation

**Hypothesis**: Congressional sector-level net buy signals are predictive
**Type**: ALPHA
**Result**: ADOPT (Buy-Only)

### Key Findings
- NET BUY: 66.7% hit rate, +2.51% 20d return
- NET SELL: 38.9% hit rate â€” NOT reliable
- Energy paradox: Congress massive sell but XLE +22%
- Recommendation: Buy-only, exclude Energy, overweight XLI/XLB/XLV

---

## 2026-02-28 RB-010: Earnings Calendar Cross-Reference

**Hypothesis**: H1: Congress members trade disproportionately within 14 days before earnings announcements (pre-earnings clustering)
**Type**: TIMING
**Result**: REJECT

### Methodology
- Data: 356 trades, 264 unique tickers (date range 2025-12-02 to 2026-02-17)
- Earnings dates: yfinance earnings_dates API, 150/264 tickers covered (56.8%)
- Testable sample (has earnings data + next earnings calculable): N=205
- Pre-earnings window: 0 < days_to_next_earnings <= 14
- Statistical test: One-sided Binomial test (H1: observed > expected)
- Expected baseline: 14/91 = 15.4% (quarterly earnings)

### Key Findings

#### Statistical Test (Step 4)
| Metric | Value |
|--------|-------|
| Sample size (N) | 205 |
| Pre-earnings trades | 27 (13.2%) |
| Expected (random) | 15.4% |
| Binomial p-value | 0.8352 |
| Effect size h | -0.063 (negligible, negative direction) |
| 95% CI | [9.2%, 18.5%] |
| Significant? | NO (p=0.8352 >> 0.05) |

**Observed rate (13.2%) is actually BELOW the random baseline (15.4%)** ¡X Congress appears to avoid pre-earnings trading.

#### Buy vs Sale Breakdown (Step 5)
| Type | N | Pre-earnings | Rate | p-value |
|------|---|-------------|------|---------|
| Buy | 113 | 22 | 19.5% | 0.1422 (ns) |
| Sale | 92 | 5 | 5.4% | 0.9992 (ns) |

- Buy trades at 19.5% marginally above baseline but not significant
- Sale trades at 5.4% strongly BELOW baseline ¡X Congress actively avoids selling before earnings

#### Days-to-Earnings Distribution (Step 6)
| Window | Count | % |
|--------|-------|---|
| 1-7d | 10 | 4.9% |
| 8-14d | 17 | 8.3% |
| 15-30d | 46 | 22.4% |
| 31-60d | 80 | 39.0% |
| 61-91d | 44 | 21.5% |
| 92-365d | 6 | 2.9% |

**Concentration in 31-60d window** ¡X trades cluster ~30-60 days before earnings, NOT in the 14-day pre-earnings window.

#### Alpha Comparison (Step 7: Buy trades only)
| Group | N | CAR_5d | CAR_20d | WR_20d |
|-------|---|--------|---------|--------|
| Pre-earnings Buys (<=14d) | 14 | +0.98% | +3.50% | 71.4% |
| Non-pre-earnings Buys (>14d) | 80 | -0.31% | +1.56% | 55.0% |
| t-test p-value | ¡X | ¡X | 0.5926 (ns) | ¡X |

**Alpha signal**: Pre-earnings Buys show higher CAR_20d (+3.50% vs +1.56%) and WR (71.4% vs 55.0%), but NOT statistically significant (p=0.59, N=14 too small).

#### Key Individual Finding (Step 8)
- **Gilbert Cisneros dominates**: 21 out of 27 pre-earnings trades belong to one politician
- All Cisneros trades concentrated on 2026-01-09 (11-13 days before Q4 2025 earnings)
- This represents a SINGLE BATCH event, not systematic pre-earnings trading
- John Boozman: 5 trades (AAPL, NFLX)

### Limitations
1. **Small sample N=205** due to yfinance coverage gap (56.8% ¡X bonds/ETFs/funds lack earnings)
2. **Confounding**: Cisneros 21 trades on one day skews the entire pre-earnings count
3. **Short data window**: Only ~3 months of trades (Dec 2025 - Feb 2026) = few earnings cycles
4. **Pre-earnings window definition**: 14 days is arbitrary; 30-day window would show different picture

### Conclusion
H0 NOT rejected. Congress members do NOT disproportionately trade before earnings announcements. The observed rate (13.2%) is below the random baseline (15.4%). The concentration in 31-60d window suggests trades are timed for post-earnings momentum (buying on the dip after prior quarter) rather than insider timing.

**Actionable note**: Despite REJECT verdict, pre-earnings BUY trades show promising alpha (+3.50% CAR_20d, 71.4% WR) but sample too small for statistical confidence. Revisit with 12+ months of data.
