"""
RB-027: Pre-Disclosure Alpha Leakage Quantification
Analyzes how congressional trading alpha unfolds over time post-filing.
"""
import sqlite3
import statistics
import os

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'data.db')

def stats(values):
    n = len(values)
    if n == 0:
        return {'n': 0, 'mean': 0, 'median': 0, 'std': 0, 'se': 0, 't': 0}
    m = sum(values) / n
    med = statistics.median(values)
    sd = statistics.stdev(values) if n > 1 else 0
    se = sd / (n ** 0.5) if n > 0 else 0
    t = m / se if se > 0 else 0
    return {'n': n, 'mean': m, 'median': med, 'std': sd, 'se': se, 't': t}


def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Buy-only, both 5d and 20d non-null
    cur.execute('''
        SELECT ff3_car_5d, ff3_car_20d, filing_lag, mkt_car_5d, mkt_car_20d, chamber
        FROM fama_french_results
        WHERE transaction_type = 'Buy'
          AND ff3_car_5d IS NOT NULL
          AND ff3_car_20d IS NOT NULL
    ''')
    rows = cur.fetchall()

    all_data = []
    for r in rows:
        car5, car20, lag, mkt5, mkt20, chamber = r
        phase1 = car5
        phase2 = car20 - car5
        capture = (car5 / car20 * 100) if car20 != 0 else None
        all_data.append({
            'car5': car5, 'car20': car20,
            'phase1': phase1, 'phase2': phase2,
            'capture': capture, 'lag': lag,
            'mkt5': mkt5, 'mkt20': mkt20, 'chamber': chamber
        })

    print("=" * 70)
    print("RB-027: PRE-DISCLOSURE ALPHA LEAKAGE QUANTIFICATION")
    print("=" * 70)
    print(f"Dataset: Buy trades with both 5d & 20d FF3 CAR, N={len(all_data)}")
    print(f"ff3_car_60d: 0 non-null rows (excluded from analysis)")

    # ── OVERALL ALPHA UNFOLDING ──
    s5 = stats([d['car5'] for d in all_data])
    s20 = stats([d['car20'] for d in all_data])
    sp1 = stats([d['phase1'] for d in all_data])
    sp2 = stats([d['phase2'] for d in all_data])

    print("\n--- OVERALL ALPHA UNFOLDING (Buy Only) ---")
    header = f"{'Metric':<25} {'Mean%':>9} {'Median%':>9} {'Std%':>9} {'t-stat':>8} {'N':>7}"
    print(header)
    print("-" * len(header))
    for label, s in [("FF3 CAR 5d (Phase 1)", s5), ("FF3 CAR 20d (Total)", s20),
                     ("Phase 1 (0-5d)", sp1), ("Phase 2 (5-20d)", sp2)]:
        print(f"{label:<25} {s['mean']*100:>9.4f} {s['median']*100:>9.4f} {s['std']*100:>9.3f} {s['t']:>8.2f} {s['n']:>7}")

    # Alpha capture ratio
    if s20['mean'] != 0:
        capture_mean = s5['mean'] / s20['mean'] * 100
        print(f"\nAlpha Capture Ratio (Phase1 / Total): {capture_mean:.1f}%")
        print(f"  Phase 1 (0-5d)  captures {capture_mean:.1f}% of total 20d alpha")
        print(f"  Phase 2 (5-20d) adds     {100 - capture_mean:.1f}% additional alpha")

    # ── BY FILING LAG GROUP ──
    print("\n--- ALPHA UNFOLDING BY FILING LAG GROUP ---")
    lag_groups = [
        ('Fast (<=7d)', [d for d in all_data if d['lag'] <= 7]),
        ('Normal (8-30d)', [d for d in all_data if 8 <= d['lag'] <= 30]),
        ('Slow (>30d)', [d for d in all_data if d['lag'] > 30]),
    ]

    header2 = f"{'Group':<18} {'N':>6} {'CAR5d%':>9} {'CAR20d%':>9} {'Ph1%':>9} {'Ph2%':>9} {'Capture':>9} {'5d_t':>7} {'20d_t':>7}"
    print(header2)
    print("-" * len(header2))
    for name, group in lag_groups:
        if not group:
            print(f"{name:<18} {'N/A':>6}")
            continue
        g5 = stats([d['car5'] for d in group])
        g20 = stats([d['car20'] for d in group])
        gp2 = stats([d['phase2'] for d in group])
        cap = (g5['mean'] / g20['mean'] * 100) if g20['mean'] != 0 else float('inf')
        cap_str = f"{cap:.1f}%" if abs(cap) < 9999 else "N/A"
        print(f"{name:<18} {len(group):>6} {g5['mean']*100:>9.4f} {g20['mean']*100:>9.4f} {g5['mean']*100:>9.4f} {gp2['mean']*100:>9.4f} {cap_str:>9} {g5['t']:>7.2f} {g20['t']:>7.2f}")

    # ── ALPHA INTENSITY ──
    print("\n--- ALPHA INTENSITY (per trading day) ---")
    p1_per_day = sp1['mean'] * 100 / 5
    p2_per_day = sp2['mean'] * 100 / 15
    total_per_day = s20['mean'] * 100 / 20
    eff1 = "HIGH" if abs(p1_per_day) > abs(p2_per_day) else "LOW"
    eff2 = "HIGH" if abs(p2_per_day) > abs(p1_per_day) else "LOW"

    header3 = f"{'Phase':<20} {'Days':>5} {'Total%':>10} {'Per Day%':>10} {'Intensity':>10}"
    print(header3)
    print("-" * len(header3))
    print(f"{'Phase 1 (0-5d)':<20} {5:>5} {sp1['mean']*100:>10.4f} {p1_per_day:>10.4f} {eff1:>10}")
    print(f"{'Phase 2 (5-20d)':<20} {15:>5} {sp2['mean']*100:>10.4f} {p2_per_day:>10.4f} {eff2:>10}")
    print(f"{'Total (0-20d)':<20} {20:>5} {s20['mean']*100:>10.4f} {total_per_day:>10.4f} {'':>10}")

    # ── BY CHAMBER ──
    print("\n--- ALPHA UNFOLDING BY CHAMBER ---")
    for ch in ['senate', 'house']:
        group = [d for d in all_data if d['chamber'] and ch in d['chamber'].lower()]
        if not group:
            print(f"  {ch.title()}: No data")
            continue
        g5 = stats([d['car5'] for d in group])
        g20 = stats([d['car20'] for d in group])
        cap = (g5['mean'] / g20['mean'] * 100) if g20['mean'] != 0 else float('inf')
        cap_str = f"{cap:.1f}%" if abs(cap) < 9999 else "N/A"
        print(f"  {ch.title():<10} N={len(group):>5}  CAR5d={g5['mean']*100:>7.3f}%  CAR20d={g20['mean']*100:>7.3f}%  Capture={cap_str:>7}  5d_t={g5['t']:.2f}  20d_t={g20['t']:.2f}")

    # ── RISK-ADJUSTED COMPARISON ──
    print("\n--- RISK-ADJUSTED COMPARISON (5d vs 20d Holding Period) ---")
    sharpe5 = s5['mean'] / s5['std'] if s5['std'] > 0 else 0
    sharpe20 = s20['mean'] / s20['std'] if s20['std'] > 0 else 0
    sharpe5_ann = sharpe5 * (252 / 5) ** 0.5
    sharpe20_ann = sharpe20 * (252 / 20) ** 0.5
    print(f"  5d Holding:  Mean={s5['mean']*100:.4f}%  Std={s5['std']*100:.3f}%  IR={sharpe5:.4f}  Ann.IR={sharpe5_ann:.3f}")
    print(f"  20d Holding: Mean={s20['mean']*100:.4f}%  Std={s20['std']*100:.3f}%  IR={sharpe20:.4f}  Ann.IR={sharpe20_ann:.3f}")

    # Win rates
    wr5 = sum(1 for d in all_data if d['car5'] > 0) / len(all_data) * 100
    wr20 = sum(1 for d in all_data if d['car20'] > 0) / len(all_data) * 100
    print(f"\n  Win Rate 5d:  {wr5:.1f}%")
    print(f"  Win Rate 20d: {wr20:.1f}%")

    # ── PHASE 2 SIGNIFICANCE ──
    print("\n--- PHASE 2 (5-20d) SIGNIFICANCE TEST ---")
    print(f"  Phase 2 mean: {sp2['mean']*100:.4f}%")
    print(f"  t-stat:       {sp2['t']:.3f}")
    sig = "SIGNIFICANT (p<0.05)" if abs(sp2['t']) > 1.96 else "NOT significant"
    print(f"  Result:       {sig}")

    # ── MARKET-ADJUSTED COMPARISON ──
    mkt5 = stats([d['mkt5'] for d in all_data if d['mkt5'] is not None])
    mkt20 = stats([d['mkt20'] for d in all_data if d['mkt20'] is not None])
    print("\n--- MARKET-ADJUSTED CAR (comparison) ---")
    print(f"  MKT CAR 5d:  {mkt5['mean']*100:.4f}% (t={mkt5['t']:.2f})")
    print(f"  MKT CAR 20d: {mkt20['mean']*100:.4f}% (t={mkt20['t']:.2f})")

    # ── FILING LAG x ALPHA PATTERN DEEP DIVE ──
    print("\n--- FILING LAG x ALPHA PATTERN (Is faster filing = more alpha?) ---")
    # Quintiles
    lags = sorted(set(d['lag'] for d in all_data))
    quintile_bounds = [
        ('Q1 (fastest)', 0, 15),
        ('Q2', 16, 30),
        ('Q3', 31, 45),
        ('Q4', 46, 60),
        ('Q5 (slowest)', 61, 999),
    ]
    header4 = f"{'Quintile':<20} {'N':>6} {'CAR5d%':>9} {'CAR20d%':>9} {'Capture':>9} {'WR20d':>7}"
    print(header4)
    print("-" * len(header4))
    for label, lo, hi in quintile_bounds:
        group = [d for d in all_data if lo <= d['lag'] <= hi]
        if not group:
            continue
        g5 = stats([d['car5'] for d in group])
        g20 = stats([d['car20'] for d in group])
        cap = (g5['mean'] / g20['mean'] * 100) if g20['mean'] != 0 else float('inf')
        cap_str = f"{cap:.1f}%" if abs(cap) < 9999 else "N/A"
        wr = sum(1 for d in group if d['car20'] > 0) / len(group) * 100
        print(f"{label:<20} {len(group):>6} {g5['mean']*100:>9.4f} {g20['mean']*100:>9.4f} {cap_str:>9} {wr:>6.1f}%")

    # ── CONCLUSIONS ──
    print("\n" + "=" * 70)
    print("CONCLUSIONS & STRATEGY RECOMMENDATIONS")
    print("=" * 70)

    if capture_mean > 60:
        front_loaded = True
        print("\n[FINDING 1] Alpha is FRONT-LOADED")
        print(f"  {capture_mean:.0f}% of 20d alpha is captured in the first 5 trading days.")
        print(f"  Alpha intensity: Phase 1 = {p1_per_day:.4f}%/day vs Phase 2 = {p2_per_day:.4f}%/day")
    elif capture_mean < 40:
        front_loaded = False
        print("\n[FINDING 1] Alpha is BACK-LOADED")
        print(f"  Only {capture_mean:.0f}% of 20d alpha appears in first 5 days.")
        print(f"  Most alpha unfolds in days 5-20.")
    else:
        front_loaded = None
        print("\n[FINDING 1] Alpha is EVENLY DISTRIBUTED")
        print(f"  {capture_mean:.0f}% captured in 5d, rest in 5-20d.")

    # Phase 2 significance
    if abs(sp2['t']) > 1.96:
        print(f"\n[FINDING 2] Phase 2 alpha (5-20d) is statistically significant (t={sp2['t']:.2f})")
        print(f"  Holding beyond 5 days DOES capture additional significant alpha.")
    else:
        print(f"\n[FINDING 2] Phase 2 alpha (5-20d) is NOT statistically significant (t={sp2['t']:.2f})")
        print(f"  Holding beyond 5 days adds noise, not signal.")

    # Risk-adjusted recommendation
    print(f"\n[FINDING 3] Risk-Adjusted Comparison")
    print(f"  5d Annualized IR:  {sharpe5_ann:.3f}")
    print(f"  20d Annualized IR: {sharpe20_ann:.3f}")
    if sharpe5_ann > sharpe20_ann:
        print(f"  --> 5d holding is MORE efficient on risk-adjusted basis")
    else:
        print(f"  --> 20d holding is MORE efficient on risk-adjusted basis")

    print(f"\n[FINDING 4] Win Rate")
    print(f"  5d WR={wr5:.1f}%  vs  20d WR={wr20:.1f}%")
    if wr20 > wr5 + 2:
        print(f"  --> 20d has materially higher win rate (+{wr20-wr5:.1f}pp)")
    elif wr5 > wr20 + 2:
        print(f"  --> 5d has materially higher win rate (+{wr5-wr20:.1f}pp)")
    else:
        print(f"  --> Win rates are similar")

    # SSRN comparison
    print(f"\n[FINDING 5] Comparison to SSRN 'Death of Insider Trading Alpha'")
    print(f"  SSRN claims 70-80% of alpha is gone before public disclosure.")
    print(f"  Our data measures POST-filing alpha only (we cannot see pre-filing).")
    print(f"  Post-filing Buy alpha: CAR_5d={s5['mean']*100:.3f}%, CAR_20d={s20['mean']*100:.3f}%")
    if s20['mean'] > 0:
        print(f"  --> Residual post-filing alpha EXISTS and is {'significant' if abs(s20['t']) > 1.96 else 'marginal'}.")
        print(f"  --> Congressional trades may retain more post-disclosure alpha than")
        print(f"     corporate insiders due to: (1) less HFT attention, (2) longer filing lags,")
        print(f"     (3) policy information (not just earnings) that unfolds slowly.")
    else:
        print(f"  --> Post-filing alpha is NEGATIVE. SSRN thesis confirmed for Congress.")

    # Strategy recommendation
    print(f"\n[STRATEGY RECOMMENDATION]")
    if front_loaded:
        print(f"  PRIMARY: 5-day holding period (captures {capture_mean:.0f}% of alpha with 75% less time risk)")
        print(f"  SECONDARY: 20-day for high-conviction signals only (convergence, whale trades)")
    elif front_loaded is False:
        print(f"  PRIMARY: 20-day holding period (most alpha unfolds after day 5)")
        print(f"  SECONDARY: 5-day only for time-sensitive/high-volatility regimes")
    else:
        print(f"  HYBRID: Use 5-day for quick trades, 20-day for conviction trades")
        print(f"  Consider VIX regime: 5d in high-VIX, 20d in low-VIX")

    print(f"\n[RB-027 VERDICT]")
    print(f"  Status: COMPLETED")
    print(f"  Key metric: Alpha Capture Ratio = {capture_mean:.1f}%")

    conn.close()


if __name__ == '__main__':
    main()
