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
