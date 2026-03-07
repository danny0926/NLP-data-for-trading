# RB-023: Convergence Signal Time Window vs Alpha

**Date**: 2026-03-07
**Status**: REJECT
**Hypothesis**: Short-window convergence signals (span_days <= 7) produce higher alpha than long-window (16-30 days).

---

## Methodology

- Joined `convergence_signals` -> `alpha_signals` (same ticker, has_convergence=1, created within +/-3 days of detection) -> `signal_performance`
- Deduplicated by (ticker, span_days, detected_at) to avoid double-counting
- Final sample: N=1,292 matched convergence-performance pairs
- Groups: Tight (<=7d), Medium (8-15d), Wide (16-30d)
- Tests: Kruskal-Wallis, pairwise Mann-Whitney U, Spearman correlation, Bootstrap CI

## Results

### Span Days vs Alpha (5d)

| Group      |   N | Mean alpha_5d | Median alpha_5d | Hit Rate 5d | Mean alpha_20d | HR 20d |
|------------|----:|-------------:|----------------:|------------:|---------------:|-------:|
| Tight <=7  | 232 |       +0.951%|          +0.679%|       53.4% |         +5.369%|  77.8% |
| Medium 8-15| 253 |       +0.608%|          +0.487%|       53.0% |         +5.109%|  76.9% |
| Wide 16-30 | 807 |       +0.835%|          +0.729%|       55.8% |         +4.240%|  75.0% |

### Fine-Grained Breakdown

| Span    |   N | Mean alpha_5d | Median | HR 5d |
|---------|----:|--------------:|-------:|------:|
| 0-3d    | 109 |       +1.277% | +1.233%| 56.9% |
| 4-7d    | 123 |       +0.662% | +0.019%| 50.4% |
| 8-14d   | 209 |       +0.566% | +0.548%| 54.5% |
| 15-21d  | 283 |       +0.675% | +0.180%| 51.9% |
| 22-30d  | 568 |       +0.913% | +0.810%| 56.9% |

### Statistical Tests

| Test | Statistic | p-value | Significant? |
|------|----------:|--------:|:------------:|
| Kruskal-Wallis (alpha_5d) | H=0.596 | 0.7424 | NO |
| Tight vs Medium (MWU) | U=29923.0 | 0.7094 | NO |
| Tight vs Wide (MWU) | U=92815.5 | 0.8433 | NO |
| Medium vs Wide (MWU) | U=98723.0 | 0.4288 | NO |
| Kruskal-Wallis (alpha_20d) | H=0.440 | 0.8027 | NO |
| Spearman (span vs alpha_5d) | rho=0.018 | 0.5214 | NO |
| Spearman (span vs alpha_20d) | rho=-0.137 | 0.2880 | NO |

**Bootstrap 95% CI for (Tight - Wide) mean alpha_5d**: [-0.761%, +1.019%] -- contains zero.

**Cohen's d (Tight vs Wide)**: 0.021 -- negligible effect size.

### Politician Count vs Alpha

| Group  |   N | Mean alpha_5d | Median | HR 5d |
|--------|----:|--------------:|-------:|------:|
| 2 pols | 764 |       +0.965% | +0.552%| 53.9% |
| 3 pols | 306 |       +0.352% | +0.692%| 55.6% |
| 4+ pols| 222 |       +0.915% | +1.472%| 56.8% |
| 3+ pols| 528 |       +0.589% | +0.759%| 56.1% |

Mann-Whitney 2 vs 3+: U=203446.5, p=0.7907 -- NOT significant.

### Cross-Tab: Span x Politician Count

| Span       | 2 pols (N, alpha) | 3+ pols (N, alpha) |
|------------|------------------:|-------------------:|
| Tight <=7  | N=206, +0.81%     | N=26, +2.07%       |
| Medium 8-15| N=172, +0.89%     | N=81, +0.00%       |
| Wide 16-30 | N=386, +1.08%     | N=421, +0.61%      |

The Tight+3pol cell (+2.07%) is interesting but N=26 is too small, driven by outliers (WDAY +14.9%, VLO +11.75%).

## Conclusion: REJECT

**The hypothesis is rejected.** There is no statistically significant relationship between convergence window length and subsequent alpha.

Key findings:
1. **All p-values > 0.4** across every test. No group difference is even close to significant.
2. **Cohen's d = 0.021** -- the effect size is negligible.
3. **Spearman rho = 0.018** -- essentially zero correlation between span_days and alpha_5d.
4. **Bootstrap CI comfortably contains zero** -- the observed +0.12% difference (Tight vs Wide) is well within noise.
5. **Politician count also shows no significant effect** (p=0.79). The 4+ politician group has slightly higher hit rate (56.8%) but the mean alpha difference is not significant.
6. The 0-3d sub-group shows the highest mean (+1.277%) but this is driven by high variance (std=6.3%) and small N.

## Recommendation

**No changes to `convergence_detector.py`** are warranted. The current 30-day window and scoring formula (which already weights time_density) are appropriate. There is no evidence that restricting to shorter windows would improve signal quality.

The convergence system already awards higher `score_time_density` to tighter clusters, which is the correct approach -- it provides a slight boost without discarding valid longer-window signals that perform equally well.
