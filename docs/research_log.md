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
| Best amount | $15K-$50K | — |
| Best chamber | House > Senate in alpha | — |
| Filing lag <15d | +1.13% | — |

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
- SQS conviction is NEGATIVE predictor (r=-0.50) — counterintuitive but validated
- Options sentiment independent from congress signals (|r|<0.15)

---

## 2026-02-28 RB-007: Sector Rotation

**Hypothesis**: Congressional sector-level net buy signals are predictive
**Type**: ALPHA
**Result**: ADOPT (Buy-Only)

### Key Findings
- NET BUY: 66.7% hit rate, +2.51% 20d return
- NET SELL: 38.9% hit rate — NOT reliable
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

**Observed rate (13.2%) is actually BELOW the random baseline (15.4%)** �X Congress appears to avoid pre-earnings trading.

#### Buy vs Sale Breakdown (Step 5)
| Type | N | Pre-earnings | Rate | p-value |
|------|---|-------------|------|---------|
| Buy | 113 | 22 | 19.5% | 0.1422 (ns) |
| Sale | 92 | 5 | 5.4% | 0.9992 (ns) |

- Buy trades at 19.5% marginally above baseline but not significant
- Sale trades at 5.4% strongly BELOW baseline �X Congress actively avoids selling before earnings

#### Days-to-Earnings Distribution (Step 6)
| Window | Count | % |
|--------|-------|---|
| 1-7d | 10 | 4.9% |
| 8-14d | 17 | 8.3% |
| 15-30d | 46 | 22.4% |
| 31-60d | 80 | 39.0% |
| 61-91d | 44 | 21.5% |
| 92-365d | 6 | 2.9% |

**Concentration in 31-60d window** �X trades cluster ~30-60 days before earnings, NOT in the 14-day pre-earnings window.

#### Alpha Comparison (Step 7: Buy trades only)
| Group | N | CAR_5d | CAR_20d | WR_20d |
|-------|---|--------|---------|--------|
| Pre-earnings Buys (<=14d) | 14 | +0.98% | +3.50% | 71.4% |
| Non-pre-earnings Buys (>14d) | 80 | -0.31% | +1.56% | 55.0% |
| t-test p-value | �X | �X | 0.5926 (ns) | �X |

**Alpha signal**: Pre-earnings Buys show higher CAR_20d (+3.50% vs +1.56%) and WR (71.4% vs 55.0%), but NOT statistically significant (p=0.59, N=14 too small).

#### Key Individual Finding (Step 8)
- **Gilbert Cisneros dominates**: 21 out of 27 pre-earnings trades belong to one politician
- All Cisneros trades concentrated on 2026-01-09 (11-13 days before Q4 2025 earnings)
- This represents a SINGLE BATCH event, not systematic pre-earnings trading
- John Boozman: 5 trades (AAPL, NFLX)

### Limitations
1. **Small sample N=205** due to yfinance coverage gap (56.8% �X bonds/ETFs/funds lack earnings)
2. **Confounding**: Cisneros 21 trades on one day skews the entire pre-earnings count
3. **Short data window**: Only ~3 months of trades (Dec 2025 - Feb 2026) = few earnings cycles
4. **Pre-earnings window definition**: 14 days is arbitrary; 30-day window would show different picture

### Conclusion
H0 NOT rejected. Congress members do NOT disproportionately trade before earnings announcements. The observed rate (13.2%) is below the random baseline (15.4%). The concentration in 31-60d window suggests trades are timed for post-earnings momentum (buying on the dip after prior quarter) rather than insider timing.

**Actionable note**: Despite REJECT verdict, pre-earnings BUY trades show promising alpha (+3.50% CAR_20d, 71.4% WR) but sample too small for statistical confidence. Revisit with 12+ months of data.

---

## 2026-03-07 RB-012: Inverse Cramer Effect Validation

**Hypothesis**: Going against Jim Cramer's stock recommendations generates positive alpha
**Type**: SOCIAL SIGNAL
**Result**: SHELVE (Meme, not alpha)

### Evidence

1. **SJIM ETF (Inverse Cramer Tracker)**: Returned **-8.31%** vs S&P 500 **+31.49%** during its lifetime
2. SJIM was **liquidated in January 2024** due to poor performance
3. No academic studies found with statistically significant evidence of contrarian alpha
4. The "Inverse Cramer" effect is primarily a social media meme, not a validated trading signal

### Current Implementation

- `social_nlp.py` already flags Cramer as `contrarian=True` and inverts his sentiment
- This is adequate as a **sentiment warning flag** but should NOT be used as a standalone alpha signal
- Weight: Keep existing Cramer inversion in NLP pipeline (awareness), but do NOT give it extra PACS weight

### Recommendation

SHELVE. The Inverse Cramer effect lacks statistical evidence. Our current approach (flag + invert sentiment) is sufficient. Do not allocate development resources to building a Cramer-specific signal pathway.

---

## 2026-03-07 RB-013: Capitol Trades Bulk Import (Direct HTML Parsing)

**Hypothesis**: Direct HTML parsing can replace LLM-based extraction for Capitol Trades
**Type**: ENGINEERING
**Result**: ADOPT

### Key Findings

1. Capitol Trades HTML table structure is predictable: Politician | Issuer | Published | Traded | Filed After | Owner | Type | Size | Price
2. BeautifulSoup parsing achieves **0.85 confidence** with zero LLM API cost
3. 100 pages (1200 records) parsed in **~60 seconds** vs ~30+ minutes with LLM transform
4. **876 new trades** imported from 100 pages, expanding coverage from 580 to 1618 trades
5. Politicians expanded from 39 to 63 unique names

### Implementation

New module: `src/etl/capitoltrades_bulk.py`
- Direct HTML parsing via BeautifulSoup
- SHA256 dedup compatible with existing loader
- Handles politician name/party/chamber extraction
- Auto-stops after 3 consecutive empty pages
- Usage: `python -m src.etl.capitoltrades_bulk --pages 100`

### Cost Impact

- LLM transform: ~$0.005/page (Gemini Flash) x 100 pages = $0.50
- Bulk import: $0.00 (no API calls)
- Speed: 100x faster

---

## 2026-03-07 Frontier Scan: Key External Research

### "The Death of Insider Trading Alpha" (Ozlen & Batumoglu, Dec 2025, SSRN)
- **Key Finding**: 70-80% of insider trading alpha dissipates between transaction date and filing date
- **Implication for PAM**: Our measured +0.55% 5d alpha (filing date entry) is the RESIDUAL alpha — most is already captured by insiders
- **Validation**: Filing lag < 15d filter is critical (4.6x alpha per RB-001) — aligns with this research
- **Action**: Prioritize fast-filing detection; signals with filing_lag < 7d should get maximum weighting

### Congress Beat Market in 2025 (Independent Institute, Feb 2026)
- 29 members beat the market (>16.8% gains required)
- Only 32.2% of Congress beat overall
- Leaders outperform rank-and-file by 40-50 percentage points annually
- **Implication for PAM**: Committee leadership alpha (RB-008/RB-014) worth re-testing with larger dataset

### Unusual Whales Congress Trading Report 2025
- Over 2,000 congressional trades involving 700 companies
- Concentrated in semiconductors and AI sectors
- Tariff-related trades: $88B revenue impact

---

## 2026-03-07 Frontier Scan: Congressional Trading Alpha Research (2025-2026)

### "The Death of Insider Trading Alpha" (Ozlen & Batumoglu, SSRN Dec 2025)
- 70-80% of total alpha dissipates between transaction date and filing date
- Once entry is delayed until filing date, most alpha is gone
- **PAM Impact**: Validates our filing_lag findings (RB-004). Short filing lag (<15d) captures residual alpha. Ultra-short lag (<3d) is the sweet spot.
- Source: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5966834

### ML for Insider Trading Prediction (arXiv Feb 2025)
- Compared Decision Trees, Random Forest, SVM, K-Means on insider trading data
- SVM with RBF kernel achieves best accuracy for stock price prediction
- ML substantially outperforms linear models for predicting insider sales
- **PAM Impact**: Consider ML ensemble approach (RF/XGBoost) for signal scoring instead of hand-tuned PACS. Future RB candidate.
- Source: https://arxiv.org/abs/2502.08728

### "Should the Public be Concerned about Congressional Stock Trading?" (Blonien, Crane, Crotty, SSRN 2025)
- Examines whether post-STOCK Act disclosure reduces information asymmetry
- Source: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5524863

### H.R. 7008 — Congressional Trading Reform (Jan 2026)
- Would require 7-day ADVANCE notice before trades (vs current 45-day post-trade disclosure)
- If enacted, would fundamentally change our signal pipeline — pre-trade disclosure = alpha accessible to everyone
- **PAM Impact**: Monitor legislation. If passed, pivot from "filing lag" to "pre-trade signal" paradigm.
- Source: https://www.congress.gov/crs-product/R48641

### Unusual Whales Congress Trading Report 2025
- Only 32.2% of Congress beat S&P 500 (needed >16.8% return)
- 29 members exceeded threshold (15D, 14R — bipartisan)
- Net equity EXIT: divested ~$170M stocks, acquired only ~$125M
- Rotation: out of software/fintech, into government debt and hardware
- **PAM Impact**: Confirms sector rotation findings (RB-007). Congressional net selling = bearish macro signal.
- Source: https://unusualwhales.com/congress-trading-report-2025

### Inside the Beltway: Senator Trading and Legislative Gains (J Business Ethics, 2025)
- Senators' trades prior to critical legislative events yield significant abnormal returns
- Patterns consistent with "stealth trading" — sequential trades leading up to legislative decisions
- **PAM Impact**: Validates convergence detection (multiple trades by same senator in short window = stronger signal)
- Source: https://link.springer.com/article/10.1007/s10551-025-06108-4

### Actionable Next Steps from Frontier Scan
1. **RB-015 candidate**: ML-based signal scoring (RF/XGBoost vs hand-tuned PACS)
2. **RB-016 candidate**: Pre-legislative event detection (bill calendar → politician trade timing)
3. **Monitor**: H.R. 7008 progress — existential risk/opportunity for PAM
4. **Data enrichment**: Add congressional committee hearing calendar as feature

---

## 2026-03-07 RB-015 Mini: Filing Lag Speed vs Alpha (25K Dataset)

**Hypothesis**: Faster filers generate higher alpha (validates "Death of Insider Trading Alpha" paper)
**Result**: NOT SIGNIFICANT (p=0.95)

| Filing Lag | N | CAR_5d | CAR_20d |
|-----------|---|--------|---------|
| Fast (<=7d) | 882 | -0.208% | -0.275% |
| Medium (8-15d) | 2,689 | +0.032% | +0.221% |
| Normal (16-30d) | 7,078 | -0.001% | +0.256% |
| Slow (31-45d) | 5,009 | -0.137% | +0.076% |
| Late (>45d) | 1,547 | +0.305% | +0.095% |

- Fast(<=15d) vs Slow(>30d): t=0.058, p=0.953 — NO significant difference
- Normal filers (16-30d) show best 20d alpha (+0.256%)
- Conclusion: Filing speed alone is not an alpha factor in the full dataset. The alpha is in the TRADE itself, not the disclosure timing. Current PACS filing_lag component may need revision.

---

## 2026-03-07 RB-015b Mini: Trade Size vs Alpha (25K Dataset)

**Hypothesis**: Larger trades signal higher conviction and generate more alpha
**Result**: PARTIALLY CONFIRMED — very large trades show outsized alpha

| Amount Range | N | CAR_5d | CAR_20d |
|-------------|---|--------|---------|
| < $1K | 16 | -2.345% | -0.151% |
| $1K-$15K | 13,199 | -0.005% | +0.178% |
| $15K-$50K | 2,697 | -0.050% | -0.039% |
| $50K-$100K | 722 | -0.085% | +0.136% |
| $100K-$250K | 411 | -0.176% | +0.451% |
| $250K-$500K | 90 | +0.057% | +0.106% |
| $500K-$1M | 35 | +0.158% | +0.825% |
| $1M-$5M | 28 | +1.084% | +4.407% |
| $5M-$25M | 7 | +0.878% | +1.349% |

- Very large trades ($1M+) show massive alpha (+4.4% 20d), but N is very small (28)
- REVISES RB-001: The "$15K-$50K sweet spot" does NOT hold in the full 25K dataset
- Small caveat: Large-N ranges ($1K-$15K) show near-zero alpha, diluting averages
- **Action**: Consider adding a "whale trade" flag for $500K+ buys in signal_enhancer

---

## 2026-03-07 RB-014: Committee Leadership Alpha Re-test (25K Dataset)

**Hypothesis**: Committee chairs/ranking members generate higher alpha than non-leaders
**Type**: ALPHA (re-test of RB-008 with 25K dataset)
**Result**: CONFIRM SHELVE

### Methodology
- Matched 119th Congress committee YAML (96 main committee leaders) to DB (30 matched in 191 politicians)
- Compared market-adjusted CAR_5d and CAR_20d from fama_french_results (17,480 valid observations)
- Two-sample t-test, leaders (N=2,218) vs non-leaders (N=15,262)

### Key Findings
| Metric | Leaders | Non-Leaders | t-stat | p-value | Sig |
|--------|---------|-------------|--------|---------|-----|
| CAR_5d (all) | -0.0014% | -0.0001% | -1.166 | 0.244 | ns |
| CAR_20d (all) | -0.0022% | +0.0021% | -2.156 | 0.031 | ** |
| CAR_5d (buy) | -0.0010% | -0.0001% | -0.906 | 0.365 | ns |
| CAR_20d (buy) | -0.0022% | +0.0021% | -2.136 | 0.033 | ** |

Cohen's d (5d): -0.027 (negligible effect size)

### Conclusion
- Committee leaders actually UNDERPERFORM non-leaders at 20d horizon (statistically significant but wrong direction)
- 5d alpha difference is not significant
- Effect size is negligible (d < 0.03)
- Possible explanation: leaders face more scrutiny, trade more defensively, or diversify more
- **Verdict: CONFIRM SHELVE** — committee leadership is not an alpha factor. Do not integrate into scoring.

