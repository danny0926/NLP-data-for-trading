# PAM Research Log

Research findings organized by RB (Research Brief) number.

---

## 2026-03-07 RB-025: Alpha Time-Decay (Trading Day vs Filing Day)

**Hypothesis**: If alpha decays from transaction_date (as SSRN Ozlen & Batumoglu 2025 claims 70-80% gone by Day+1), then trades with shorter filing_lag should show LARGER post-filing CAR, because the filing is closer to the information event.
**Type**: ALPHA FACTOR
**Result**: REJECT (pure time-decay) / CONDITIONAL ADOPT (Late >45d penalty)

### Data Coverage
- N=17,480 trades with non-null CAR (16,882 with all fields non-null for stats)
- Buy=17,205, Sale=275
- Filing lag range: 0-999 days, median ~25 days
- Source: fama_french_results table (FF3-adjusted CARs measured from filing_date)

### Filing Lag Group Results (Buy Only, FF3-adjusted)

| Group | N | Avg Lag | FF3_CAR_5d | FF3_CAR_20d | Win Rate 20d |
|-------|---|---------|-----------|------------|-------------|
| Fast (<=7d) | 882 | 4.5d | -0.002% | +0.017% | 49.9% |
| Medium (8-15d) | 2,689 | 11.8d | -0.011% | +0.176% | 50.3% |
| **Normal (16-30d)** | **7,078** | **23.5d** | **-0.073%** | **+0.271%** | **50.8%** |
| Slow (31-45d) | 5,009 | 36.3d | -0.127% | +0.140% | 51.9% |
| Late (>45d) | 1,547 | 209.8d | +0.078% | -0.237% | 47.3% |

### Fine-Grained Monotonicity (Buy Only)

| Lag Range | N | FF3_5d | FF3_20d |
|-----------|---|--------|---------|
| 0-5d | 466 | +0.236% | +0.451% |
| 6-10d | 1,409 | -0.054% | +0.077% |
| 11-15d | 1,655 | -0.039% | +0.104% |
| 16-20d | 2,020 | -0.180% | +0.096% |
| 21-30d | 4,948 | -0.055% | +0.343% |
| 31-45d | 4,937 | -0.115% | +0.140% |
| 46-90d | 519 | +0.382% | +0.165% |
| 91-999d | 926 | -0.117% | -0.463% |

### Statistical Tests

| Test | Metric | Result | p-value | Sig |
|------|--------|--------|---------|-----|
| Spearman (lag vs CAR, Buy) | ff3_car_5d | rho=+0.015 | 0.048 | * |
| Spearman (lag vs CAR, Buy) | ff3_car_20d | rho=-0.002 | 0.753 | n.s. |
| Kruskal-Wallis (5 groups, Buy) | ff3_car_5d | H=4.77 | 0.312 | n.s. |
| Kruskal-Wallis (5 groups, Buy) | ff3_car_20d | H=6.98 | 0.137 | n.s. |
| Mann-Whitney Fast vs Normal | ff3_car_20d | +0.017 vs +0.271% | 0.224 | n.s. |
| Mann-Whitney Fast vs Slow | ff3_car_20d | +0.017 vs +0.140% | 0.302 | n.s. |
| Mann-Whitney Normal vs Late (one-sided) | ff3_car_20d | +0.271 vs -0.237% | 0.008 | ** |
| OLS regression (lag -> ff3_20d, Buy) | slope | -0.001%/day | 0.102 | n.s. |
| Cohen's d (Fast vs Normal) | ff3_car_20d | d=-0.032 | — | negligible |
| Cohen's d (Normal vs Late) | ff3_car_20d | d=+0.063 | — | negligible |

### Key Findings

1. **Pure time-decay hypothesis REJECTED**: Fast filers (<=7d) do NOT show higher alpha than Normal filers (16-30d). Normal filers have the highest 20d alpha (+0.271%). The relationship is non-monotonic.
2. **Late filers (>45d) are the only significantly worse group**: Normal vs Late is significant (p=0.008, one-sided), but the effect size is negligible (Cohen's d=0.063).
3. **Spearman correlation is essentially zero** (rho=-0.002 for 20d, p=0.75) — filing lag has no linear relationship with alpha.
4. **Super-fast filers (0-5d)** show +0.451% mean FF3_20d but high variance (std=8.25%), driven by small N=468 and dominated by Marjorie Taylor Greene (N=270). Not robust.
5. **Consistent with RB-015** (N=600, p=0.95): Both studies independently confirm filing lag is not a useful linear predictor of alpha.

### SSRN Comparison

The SSRN finding (70-80% alpha gone by Day+1 from trade date) may be true for corporate insiders, but congressional trades are fundamentally different:
- Congress trades based on **policy/regulatory foresight**, not earnings surprises
- Policy effects unfold over weeks/months, not days
- The "information" in a congressional trade may not even exist at trade date — it's a directional bet on future policy

### PACS Recommendation

- **Current**: filing_lag_inverse weight = 25% of PACS formula
- **Finding**: Linear filing_lag is NOT predictive (p=0.75)
- **Recommendation**: REDUCE filing_lag_inverse from 25% to 10%, convert to binary penalty (only penalize Late >45d filings). Redistribute 15% to signal_strength (proven predictor).
- **Alternative**: Use categorical encoding: Normal/Medium = 1.0x, Late >45d = 0.7x penalty

---

## 2026-03-07 RB-024: VIX Regime Alpha Validation (Updated Dataset)

**Hypothesis**: VIX low-volatility periods (<20) produce significantly higher signal alpha than high-volatility periods (>=20)
**Type**: REGIME
**Result**: CONDITIONAL SHELVE
**Previous**: N=485, p=0.036 (significant). Updated: N=537, p=0.0955 (not significant).

### Data Coverage
- N=537 signals, date range 2026-01-14 to 2026-02-27
- VIX range in period: 16.15 - 21.77 (only moderate + high zones observed)
- No data for ultra_low (<14), goldilocks (14-16), or extreme (>30) zones

### Per-Zone Results
| Zone | VIX Range | N | Avg alpha_5d | HR_5d | Avg alpha_20d | N_20d |
|------|-----------|---|-------------|-------|--------------|-------|
| moderate | 16-20 | 375 | +0.214% | 50.1% | +2.845% | 40 |
| high | 20-30 | 162 | +1.074% | 59.3% | +4.477% | 1 |
| **TOTAL** | all | 537 | +0.473% | 52.9% | +2.885% | 41 |

### Median Split (VIX <20 vs >=20)
| Group | N | Avg alpha_5d | HR_5d |
|-------|---|-------------|-------|
| Low (<20) | 375 | +0.214% | 50.1% |
| High (>=20) | 162 | +1.074% | 59.3% |

**Counterintuitive**: High VIX signals actually outperform Low VIX, opposite to hypothesis.

### Statistical Tests
| Test | Statistic | p-value | Sig |
|------|-----------|---------|-----|
| Mann-Whitney (alpha_5d) | U=27624 | 0.0955 | ns |
| Mann-Whitney (HR_5d) | U=27603 | 0.0521 | ns |
| Kruskal-Wallis (zones) | H=2.780 | 0.0955 | ns |
| Spearman (VIX vs alpha_5d) | rho=+0.011 | 0.794 | ns |
| Spearman (VIX vs alpha_20d) | rho=+0.053 | 0.740 | ns |
| Cohen's d (alpha_5d) | -0.142 | small effect | - |

### Multiplier Assessment
Current multipliers penalize high VIX (0.5x) and reward goldilocks (1.3x), but empirical data shows high VIX has 2.27x relative alpha vs 0.45x for moderate. The current multiplier scheme is **directionally wrong** for this dataset.

### Key Issues
1. **Narrow VIX range**: Only 16.15-21.77 observed (2 of 5 zones). Cannot validate full regime model.
2. **Direction reversal**: High VIX outperforms Low VIX (opposite of prior N=485 finding).
3. **Prior result likely spurious**: p=0.036 at N=485 did not replicate at N=537 (p=0.096).
4. **20d data sparse**: Only 41 signals have 20d alpha (40 in moderate, 1 in high).

### Recommendation
- **CONDITIONAL SHELVE** -- Do not use VIX multipliers for signal weighting until broader VIX range data is available (need bull market + bear market periods).
- Current VIX multipliers should be **neutralized** (set all to 1.0) or removed entirely.
- Revisit when dataset spans a full VIX cycle (12-24 months covering VIX 10-35+).
- The goldilocks (14-16) zone hypothesis from RB-004 remains unvalidated.

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

## 2026-03-07 RB-017 Mini: Filing Lag by Chamber (25K Dataset)

**Hypothesis**: Senate files faster, explaining Senate > House alpha
**Result**: REJECTED — Senate files SLOWER but has BETTER alpha

| Chamber | Avg Lag | Median Lag | N |
|---------|---------|------------|---|
| Senate | 51.3 days | 28 days | 2,394 |
| House | 41.2 days | 27 days | 21,203 |

- t=6.235, p<0.001 — Senate significantly slower filers
- But RB-004 shows Senate >> House in alpha (+1.39% vs -1.27% 20d)
- **Conclusion**: Senate alpha comes from INFORMATION QUALITY, not filing speed
- Senate has fewer members, more committee access, less scrutiny → better trades
- Median lag is almost identical (28 vs 27), mean skewed by Senate outliers

---

## 2026-03-07 RB-016 Mini: Bipartisan Alpha — Republican vs Democrat (25K Dataset)

**Hypothesis**: Party affiliation affects trading alpha
**Result**: MARGINAL — R buys outperform at 5d only

| Party | N (Buy) | CAR_5d | CAR_20d |
|-------|---------|--------|---------|
| Republican | 5,515 | +0.102% | +0.158% |
| Democrat | 10,394 | -0.074% | +0.170% |

- R vs D 5d: t=2.324, **p=0.020** — Republicans have higher short-term alpha
- R vs D 20d: t=-0.082, p=0.934 — No difference at 20 days
- Democrats trade 2x more volume but with less short-term edge
- Aligns with Unusual Whales 2025: bipartisan split (15D, 14R beat market)
- **Verdict: CONDITIONAL SHELVE** — too small effect size for practical use. Party is not a reliable alpha factor. May reflect policy access differences (R majority → more committee info).

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

---

## 2026-03-07 RB-018: Seasonality Analysis — Monthly Alpha Patterns

**Hypothesis**: Congressional trading alpha varies by month (January effect, tax-loss selling, etc.)
**Type**: PATTERN
**Status**: SHELVED (insufficient data)

### Findings
- Only 2 months of signal_performance data (Jan-Feb 2026): N=519
- Jan: N=16, HR=81.2%, Alpha=291% (extreme outliers, tiny sample)
- Feb: N=503, HR=51.9%, Alpha=41%
- Cannot test Q1 vs Q3 (no Q3 data)
- **Verdict: SHELVE** — need 12+ months of tracked signals. Revisit when data accumulates.

---

## 2026-03-07 RB-019: Politician Consistency — Repeat vs One-Off Traders

**Hypothesis**: Politicians who trade the same ticker 3+ times show better alpha than one-off traders
**Type**: PATTERN
**Status**: CONDITIONAL SHELVE

### Data
- Repeat traders (3+ same ticker): N=365, HR=55.3%, median_alpha=+51.8%
- One-off traders (<3 same ticker): N=167, HR=47.9%, median_alpha=-44.1%

### Statistical Test
- Mann-Whitney U test: p=0.0699 (not significant at 0.05)
- T-test: t=1.339, p=0.1812 (mean skewed by outliers)

### Findings
- Direction is correct: repeat traders show higher HR and median alpha
- Not statistically significant at p<0.05 (marginal at p=0.07)
- High variance suggests outlier-driven effect
- **Verdict: CONDITIONAL SHELVE** — directionally positive but not conclusive. Could be useful as a weak signal multiplier (5-10% weight) in ensemble. Revisit with more data.

---

## 2026-03-07 RB-020: Insider Confirmation Alpha Boost

**Hypothesis**: Signals where Congress + SEC Form 4 insider trade the same ticker (insider_confirmed=1) show higher alpha
**Type**: ALPHA
**Status**: REJECT

### Data
- Insider Confirmed: N=72, Mean_alpha=+41.9%, Median=+32.8%, HR=51.4%
- Not Confirmed: N=460, Mean_alpha=+51.3%, Median=+29.9%, HR=53.3%

### Statistical Test
- T-test: t=-0.122, p=0.9029
- Mann-Whitney U: p=0.9438
- Cohen's d: -0.016 (negligible)

### Findings
- No statistically significant difference between insider-confirmed and non-confirmed signals
- HR is marginally LOWER for confirmed signals (51.4% vs 53.3%)
- Possible explanations: (1) insiders trade for diverse reasons (exercise, diversification), (2) time lag between Congress and insider filings reduces co-occurrence signal value
- **Verdict: REJECT** — insider confirmation does not boost alpha. Keep as informational UI element but do not weight it in scoring.

---

## 2026-03-07 RB-021: Ticker Familiarity Alpha (Sector Concentration)

**Hypothesis**: Politicians who repeatedly trade the same ticker generate higher alpha than first-time traders
**Type**: ALPHA
**Status**: CONDITIONAL ADOPT

### Design
- H0: No difference in CAR_5d between repeat (3+) vs first-time ticker trades
- H1: Repeat ticker trades show higher alpha
- Dataset: 496 signal_performance records with ticker frequency data

### Data
| Frequency | N | Mean Alpha_5d |
|-----------|---|---------------|
| First-time (1x) | 57 | -1.036% |
| Twice (2x) | 98 | +0.225% |
| Repeat (3+) | 341 | +0.704% |

### Statistical Tests
- Mann-Whitney U (3+ vs 1x): U=11330.5, p=0.045 (significant at 5%)
- Spearman correlation (frequency vs alpha): r=0.145, p=0.0012 (significant)
- Politician-level concentration (median-split): p=0.32 (not significant — too noisy)

### Findings
- **Signal-level analysis confirms**: repeat ticker trades significantly outperform first-time trades
- Clear monotonic pattern: 1x (-1.04%) → 2x (+0.23%) → 3+ (+0.70%)
- Spearman r=0.145 is modest but highly significant (p=0.001)
- Politician-level analysis is too noisy (N=24, p=0.32) — insufficient power
- **Verdict: CONDITIONAL ADOPT** — ticker familiarity is a valid alpha factor. Consider adding as a bonus in PACS scoring for politicians with 3+ trades in the same ticker. Needs larger signal_performance dataset to confirm at politician level.

---

## 2026-03-07 RB-022: Filing Weekday Alpha Pattern

**Hypothesis**: Filing day of week predicts signal alpha
**Type**: ALPHA
**Status**: CONDITIONAL SHELVE

### Data (N=493 signals)
| Weekday | N | HR_5d | Alpha_5d |
|---------|---|-------|----------|
| Monday | 112 | 56.2% | +0.705% |
| Tuesday | 26 | 73.1% | +2.133% |
| Wednesday | 39 | 59.0% | +1.521% |
| Thursday | 8 | 87.5% | +0.929% |
| Friday | 308 | 47.7% | -0.109% |

### Statistical Tests
- Kruskal-Wallis H=9.199, p=0.056 (marginal, not significant at 5%)
- Tuesday vs Friday: Mann-Whitney U=5111, p=0.019 (significant pairwise)

### Findings
- Clear pattern: mid-week filings (Tue-Thu) outperform Monday and especially Friday
- Tuesday stands out: 73.1% HR with +2.13% alpha, but small N=26
- Friday dominates volume (308/493 = 62%) but has worst performance
- Possible explanation: Friday filings are "dump" filings (bad news buried before weekend)
- **Verdict: CONDITIONAL SHELVE** — suggestive pattern but underpowered (Tuesday N=26, Thursday N=8). Kruskal-Wallis p=0.056 just misses significance. Revisit when signal_performance N > 1000.

---

## 2026-03-07 RB-023: Convergence Window Timing vs Alpha

**Hypothesis**: Tight convergence (<=7 days) produces higher alpha than wide windows (16-30 days)
**Type**: ALPHA
**Status**: REJECT

### Data (N=1,292 matched pairs)
| Window | N | Mean Alpha_5d | Hit Rate |
|--------|---|---------------|----------|
| Tight (<=7d) | 232 | +0.951% | 53.4% |
| Medium (8-15d) | 253 | +0.608% | 53.0% |
| Wide (16-30d) | 807 | +0.835% | 55.8% |

### Statistical Tests
- Kruskal-Wallis: H=0.60, p=0.742 (not significant)
- Pairwise Mann-Whitney: all p > 0.4
- Spearman (span_days vs alpha): r=0.018, p=0.52
- Cohen's d (Tight vs Wide): 0.021 (negligible)
- Politician count (2 vs 3+): p=0.79 (not significant)

### Findings
- No significant difference between convergence window widths
- Current 30-day window with time_density weighting is optimal
- **Verdict: REJECT** — no changes to convergence_detector.py warranted

