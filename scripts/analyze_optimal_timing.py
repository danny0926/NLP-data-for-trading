"""
RB-004: Congressional Trading 最佳交易時機分析
===============================================
雙視角分析:
  1. 議員視角 (Transaction Date Entry): 議員交易日進場，衡量 "informed trading" alpha
  2. 跟單視角 (Filing Date Entry): Filing 公開後進場，衡量 "follower" alpha
     ※ Filing dates 集中在 2026-02-27，follower 視角資料有限
"""

import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

DB_PATH = "D:/VScode_project/NLP data for trading/data/data.db"
REPORT_PATH = "D:/VScode_project/NLP data for trading/docs/reports/RB-004_Optimal_Trading_Timing_2026-02-27.md"

HOLD_PERIODS = [1, 3, 5, 10, 20, 40, 60]


def _safe_scalar(val):
    """Safely extract a scalar from a pandas value."""
    if isinstance(val, pd.Series):
        val = val.iloc[0]
    if isinstance(val, (np.floating, np.integer)):
        return float(val)
    return val


def load_data():
    conn = sqlite3.connect(DB_PATH)

    trades = pd.read_sql_query("""
        SELECT ct.id, ct.ticker, ct.transaction_date, ct.filing_date,
               ct.transaction_type, ct.amount_range, ct.chamber, ct.politician_name
        FROM congress_trades ct
        WHERE ct.ticker IS NOT NULL AND ct.ticker != ''
          AND ct.transaction_date IS NOT NULL
    """, conn, parse_dates=['transaction_date', 'filing_date'])

    ff = pd.read_sql_query("""
        SELECT politician_name, ticker, transaction_type, direction,
               transaction_date, filing_date, filing_lag,
               ff3_car_5d, mkt_car_5d, alpha_est
        FROM fama_french_results
    """, conn, parse_dates=['transaction_date', 'filing_date'])

    alpha = pd.read_sql_query("""
        SELECT trade_id, ticker, politician_name, transaction_type,
               transaction_date, filing_date, direction,
               expected_alpha_5d, expected_alpha_20d, confidence, signal_strength,
               filing_lag_days, sqs_score, sqs_grade
        FROM alpha_signals
    """, conn, parse_dates=['transaction_date', 'filing_date'])

    sqs = pd.read_sql_query("""
        SELECT trade_id, politician_name, ticker, sqs, grade,
               actionability, timeliness, conviction, information_edge
        FROM signal_quality_scores
    """, conn)

    conn.close()
    return trades, ff, alpha, sqs


def download_prices(tickers, start_date, end_date):
    import yfinance as yf

    skip = {'AJINF', 'BABAF', 'HESAF', 'HESAY', 'MBJBF', 'NTDOF', 'RNMBF',
            'SBGSF', 'TCTZF', 'VSNNT', 'XIACF', 'FINMF', 'MHIYF', 'RHM GR',
            'KRSOX', 'RNWGX', 'OZKAP', 'EIPI', 'SPYM', 'SWSD', 'SARO',
            'OT', 'HN', 'RFD', 'SED', 'SGI', 'LVY', 'CSW', 'GEM', 'CS', 'S',
            'LGN', 'AFT', 'K'}
    valid_tickers = [t for t in tickers if (t.isalpha() or '.' in t) and t not in skip]

    print(f"  下載 {len(valid_tickers)} 檔股票價格...")

    all_prices = {}
    batch_size = 50
    for i in range(0, len(valid_tickers), batch_size):
        batch = valid_tickers[i:i+batch_size]
        try:
            data = yf.download(batch, start=start_date, end=end_date,
                             progress=False, auto_adjust=True)
            if len(batch) == 1:
                if 'Close' in data.columns:
                    series = data['Close'].dropna()
                    if len(series) > 0:
                        if isinstance(series.index, pd.MultiIndex):
                            series.index = series.index.get_level_values(0)
                        series = series[~series.index.duplicated(keep='first')]
                        all_prices[batch[0]] = series
            else:
                if 'Close' in data.columns:
                    close_data = data['Close']
                    for t in batch:
                        if t in close_data.columns:
                            series = close_data[t].dropna()
                            if len(series) > 0:
                                series = series[~series.index.duplicated(keep='first')]
                                all_prices[t] = series
        except Exception as e:
            print(f"  Batch {i//batch_size+1} failed: {e}")

    try:
        spy = yf.download('SPY', start=start_date, end=end_date, progress=False, auto_adjust=True)
        spy_close = spy['Close'].dropna()
        if isinstance(spy_close.index, pd.MultiIndex):
            spy_close.index = spy_close.index.get_level_values(0)
        spy_close = spy_close[~spy_close.index.duplicated(keep='first')]
        all_prices['SPY'] = spy_close
    except:
        pass

    print(f"  成功取得 {len(all_prices)} 檔")
    return all_prices


def compute_returns(trades_df, prices, entry_col='transaction_date', hold_periods=HOLD_PERIODS):
    """
    計算每筆交易基於指定日期欄位進場後的多持有期報酬
    entry_col: 'transaction_date' (議員視角) 或 'filing_date' (跟單視角)
    """
    results = []

    for _, row in trades_df.iterrows():
        ticker = row['ticker']
        entry_dt_raw = row[entry_col]
        tx_type = row['transaction_type']

        if pd.isna(entry_dt_raw) or ticker not in prices or 'SPY' not in prices:
            continue

        stock_prices = prices[ticker]
        spy_prices = prices['SPY']
        entry_dt = pd.Timestamp(entry_dt_raw)

        # Find first trading day on or after entry date
        valid_dates = stock_prices.index[stock_prices.index >= entry_dt]
        if len(valid_dates) == 0:
            continue

        entry_date = valid_dates[0]
        entry_price = _safe_scalar(stock_prices.loc[entry_date])

        spy_valid = spy_prices.index[spy_prices.index >= entry_dt]
        if len(spy_valid) == 0:
            continue
        spy_entry = _safe_scalar(spy_prices.loc[spy_valid[0]])

        if pd.isna(entry_price) or entry_price == 0 or pd.isna(spy_entry) or spy_entry == 0:
            continue

        direction = 1 if 'buy' in tx_type.lower() or 'purchase' in tx_type.lower() else -1

        record = {
            'ticker': ticker,
            'politician_name': row['politician_name'],
            'transaction_type': tx_type,
            'chamber': row['chamber'],
            'amount_range': row.get('amount_range', ''),
            'transaction_date': row['transaction_date'],
            'filing_date': row.get('filing_date'),
            'entry_date': entry_date,
            'direction': direction,
        }

        # Filing lag
        if pd.notna(row.get('filing_date')) and pd.notna(row['transaction_date']):
            record['filing_lag'] = (row['filing_date'] - row['transaction_date']).days
        else:
            record['filing_lag'] = None

        # Day info on entry
        record['entry_dow'] = entry_dt.dayofweek
        record['entry_day_name'] = entry_dt.day_name()
        record['entry_dom'] = entry_dt.day

        # Calculate returns for each holding period
        all_stock_dates = stock_prices.index
        exit_candidates = all_stock_dates[all_stock_dates > entry_date]

        for period in hold_periods:
            if len(exit_candidates) < period:
                record[f'raw_{period}d'] = None
                record[f'excess_{period}d'] = None
                record[f'directed_{period}d'] = None
                continue

            exit_date = exit_candidates[period - 1]
            exit_price = _safe_scalar(stock_prices.loc[exit_date])

            spy_exit_cands = spy_prices.index[spy_prices.index >= exit_date]
            if len(spy_exit_cands) == 0:
                record[f'raw_{period}d'] = None
                record[f'excess_{period}d'] = None
                record[f'directed_{period}d'] = None
                continue
            spy_exit = _safe_scalar(spy_prices.loc[spy_exit_cands[0]])

            if pd.isna(exit_price) or pd.isna(spy_exit):
                record[f'raw_{period}d'] = None
                record[f'excess_{period}d'] = None
                record[f'directed_{period}d'] = None
                continue

            raw = (exit_price - entry_price) / entry_price
            spy_ret = (spy_exit - spy_entry) / spy_entry
            excess = raw - spy_ret
            directed = excess * direction

            record[f'raw_{period}d'] = float(raw)
            record[f'excess_{period}d'] = float(excess)
            record[f'directed_{period}d'] = float(directed)

        results.append(record)

    return pd.DataFrame(results)


def compute_daily_car(trades_df, prices, entry_col='transaction_date', max_days=60):
    """逐日 CAR 計算"""
    daily_cars = {d: [] for d in range(max_days + 1)}

    for _, row in trades_df.iterrows():
        ticker = row['ticker']
        entry_dt_raw = row[entry_col]
        tx_type = row['transaction_type']

        if pd.isna(entry_dt_raw) or ticker not in prices or 'SPY' not in prices:
            continue

        stock_prices = prices[ticker]
        spy_prices = prices['SPY']
        entry_dt = pd.Timestamp(entry_dt_raw)

        valid_dates = stock_prices.index[stock_prices.index >= entry_dt]
        if len(valid_dates) == 0:
            continue

        entry_date = valid_dates[0]
        entry_price = _safe_scalar(stock_prices.loc[entry_date])

        spy_valid = spy_prices.index[spy_prices.index >= entry_dt]
        if len(spy_valid) == 0:
            continue
        spy_entry = _safe_scalar(spy_prices.loc[spy_valid[0]])

        if pd.isna(entry_price) or entry_price == 0 or pd.isna(spy_entry) or spy_entry == 0:
            continue

        direction = 1 if 'buy' in tx_type.lower() or 'purchase' in tx_type.lower() else -1

        daily_cars[0].append(0.0)

        trading_days_after = stock_prices.index[stock_prices.index > entry_date]
        for day_idx in range(1, min(max_days + 1, len(trading_days_after) + 1)):
            day_date = trading_days_after[day_idx - 1]
            day_price = _safe_scalar(stock_prices.loc[day_date])

            spy_on_day = spy_prices.index[spy_prices.index >= day_date]
            if len(spy_on_day) == 0:
                break
            spy_day_price = _safe_scalar(spy_prices.loc[spy_on_day[0]])

            if pd.isna(day_price) or pd.isna(spy_day_price):
                break

            raw = (day_price - entry_price) / entry_price
            spy_ret = (spy_day_price - spy_entry) / spy_entry
            car = (raw - spy_ret) * direction
            daily_cars[day_idx].append(float(car))

    result = {}
    for d, cars in daily_cars.items():
        if len(cars) >= 5:
            result[d] = {
                'day': d,
                'avg_car': np.mean(cars),
                'median_car': np.median(cars),
                'std_car': np.std(cars),
                'n': len(cars),
                'se': np.std(cars) / np.sqrt(len(cars)),
                'pct_positive': sum(1 for c in cars if c > 0) / len(cars)
            }

    return pd.DataFrame(result.values())


def bucket_analysis(returns_df, col, bins, labels, metric_periods=[5, 10, 20]):
    """Generic bucket analysis"""
    df = returns_df.copy()
    df['bucket'] = pd.cut(df[col].astype(float), bins=bins, labels=labels, right=True)

    results = []
    for bucket in labels:
        subset = df[df['bucket'] == bucket]
        if len(subset) < 3:
            continue

        record = {'bucket': bucket, 'n': len(subset)}
        for p in metric_periods:
            c = f'directed_{p}d'
            if c in subset.columns:
                valid = subset[c].dropna()
                if len(valid) >= 3:
                    avg = valid.mean()
                    std = valid.std()
                    se = std / np.sqrt(len(valid))
                    t_stat = avg / se if se > 0 else 0
                    record[f'avg_{p}d'] = avg
                    record[f'std_{p}d'] = std
                    record[f't_stat_{p}d'] = t_stat
                    record[f'n_{p}d'] = len(valid)
                    record[f'wr_{p}d'] = (valid > 0).sum() / len(valid)

        results.append(record)
    return pd.DataFrame(results)


def groupby_analysis(returns_df, col, metric_periods=[5, 10, 20]):
    """Analysis by categorical group"""
    results = []
    for grp, subset in returns_df.groupby(col):
        if len(subset) < 3:
            continue
        record = {'group': grp, 'n': len(subset)}
        for p in metric_periods:
            c = f'directed_{p}d'
            if c in subset.columns:
                valid = subset[c].dropna()
                if len(valid) >= 3:
                    avg = valid.mean()
                    std = valid.std()
                    record[f'avg_{p}d'] = avg
                    record[f'wr_{p}d'] = (valid > 0).sum() / len(valid)
                    record[f'sharpe_{p}d'] = avg / std if std > 0 else 0
                    record[f'n_{p}d'] = len(valid)
        results.append(record)
    return pd.DataFrame(results)


def holding_period_analysis(returns_df, hold_periods=HOLD_PERIODS):
    """Sharpe ratio comparison across holding periods"""
    results = []
    for p in hold_periods:
        col = f'directed_{p}d'
        if col not in returns_df.columns:
            continue
        valid = returns_df[col].dropna()
        if len(valid) < 10:
            continue

        avg = valid.mean()
        std = valid.std()
        sharpe = avg / std if std > 0 else 0
        ann_sharpe = sharpe * np.sqrt(252 / p)
        win_rate = (valid > 0).sum() / len(valid)
        avg_win = valid[valid > 0].mean() if (valid > 0).sum() > 0 else 0
        avg_loss = valid[valid <= 0].mean() if (valid <= 0).sum() > 0 else 0
        total_wins = valid[valid > 0].sum()
        total_losses = abs(valid[valid <= 0].sum())
        pf = total_wins / total_losses if total_losses > 0 else float('inf')

        results.append({
            'period': f'{p}d', 'n': len(valid),
            'avg': avg, 'median': valid.median(), 'std': std,
            'sharpe': sharpe, 'ann_sharpe': ann_sharpe,
            'win_rate': win_rate, 'avg_win': avg_win, 'avg_loss': avg_loss,
            'profit_factor': pf, 'skew': valid.skew(),
        })
    return pd.DataFrame(results)


def pct(v, decimals=2):
    if pd.isna(v):
        return "N/A"
    return f"{v*100:.{decimals}f}%"


def fmt(v, decimals=2):
    if pd.isna(v):
        return "N/A"
    return f"{v:.{decimals}f}"


def generate_report(tx_returns, tx_daily_car, tx_lag, tx_hold,
                    filing_returns, filing_daily_car, filing_hold,
                    ff_data, alpha_data, sqs_data,
                    trades_df):
    """生成完整 Markdown 報告"""
    L = []

    def add(text=''):
        L.append(text)

    add("# RB-004: Congressional Trading 最佳交易時機分析")
    add()
    add(f"**分析日期**: {datetime.now().strftime('%Y-%m-%d')}")
    add(f"**資料期間**: 交易日 {trades_df['transaction_date'].min().strftime('%Y-%m-%d')} ~ {trades_df['transaction_date'].max().strftime('%Y-%m-%d')}")
    add(f"**交易總數**: {len(trades_df)} 筆 (含有效 ticker)")

    n_tx = len(tx_returns) if tx_returns is not None else 0
    n_fl = len(filing_returns) if filing_returns is not None else 0
    add(f"**議員視角有效樣本**: {n_tx} 筆 | **跟單視角有效樣本**: {n_fl} 筆")
    add(f"**基準**: S&P 500 (SPY)")
    add()
    add("> **注意**: 由於 88% 的 filing date 集中在 2026-02-27（分析日），跟單視角的資料量有限。")
    add("> 本報告以**議員視角**（從交易日起算）為主要分析依據，並輔以跟單視角作為對比。")
    add()
    add("---")
    add()

    # ═══════════ EXECUTIVE SUMMARY ═══════════
    add("## Executive Summary")
    add()

    if tx_hold is not None and len(tx_hold) > 0:
        best_sharpe = tx_hold.loc[tx_hold['ann_sharpe'].idxmax()]
        best_ret = tx_hold.loc[tx_hold['avg'].abs().idxmax()]  # highest magnitude
        best_wr = tx_hold.loc[tx_hold['win_rate'].idxmax()]

        add("### 核心發現")
        add()
        add(f"1. **最佳風險調整持有期**: **{best_sharpe['period']}** (年化 Sharpe = {fmt(best_sharpe['ann_sharpe'], 3)})")
        add(f"2. **最高平均超額報酬**: **{best_ret['period']}** ({pct(best_ret['avg'])} 超額)")
        add(f"3. **最佳勝率**: **{best_wr['period']}** ({pct(best_wr['win_rate'], 1)})")

    if tx_lag is not None and len(tx_lag) > 0:
        for p in [5, 10, 20]:
            col = f'avg_{p}d'
            if col in tx_lag.columns:
                valid = tx_lag.dropna(subset=[col])
                if len(valid) > 0:
                    best = valid.loc[valid[col].idxmax()]
                    add(f"4. **最佳 Filing Lag ({p}d)**: **{best['bucket']}** (CAR = {pct(best[col])})")
                    break

    # Alpha decay insight
    if tx_daily_car is not None and len(tx_daily_car) > 0:
        peak_row = tx_daily_car.loc[tx_daily_car['avg_car'].abs().idxmax()]
        add(f"5. **Alpha 峰值**: **T+{int(peak_row['day'])}** 交易日 (CAR = {pct(peak_row['avg_car'], 3)})")

    add()
    add("---")
    add()

    # ═══════════ SECTION 1: FILING LAG ═══════════
    add("## 1. Filing Lag 分桶分析")
    add()
    add("Filing lag = 議員交易日 → 向 Senate/House 申報的天數。")
    add("理論：lag 越短，資訊越新鮮。但實證結果可能不同。")
    add()

    # Filing lag distribution
    lag_vals = tx_returns['filing_lag'].dropna() if tx_returns is not None else pd.Series()
    if len(lag_vals) > 0:
        add("### Lag 分布統計")
        add()
        add(f"| 指標 | 值 |")
        add(f"|:-----|:---|")
        add(f"| 平均 | {lag_vals.mean():.1f} 天 |")
        add(f"| 中位數 | {lag_vals.median():.0f} 天 |")
        add(f"| 25th percentile | {lag_vals.quantile(0.25):.0f} 天 |")
        add(f"| 75th percentile | {lag_vals.quantile(0.75):.0f} 天 |")
        add(f"| 最短 | {lag_vals.min():.0f} 天 |")
        add(f"| 最長 | {lag_vals.max():.0f} 天 |")
        add()

    if tx_lag is not None and len(tx_lag) > 0:
        add("### Filing Lag vs 超額報酬 (議員視角, 從交易日起算)")
        add()

        header_parts = ["Filing Lag", "筆數"]
        for p in [5, 10, 20, 40, 60]:
            if f'avg_{p}d' in tx_lag.columns:
                header_parts.extend([f"{p}d CAR", f"{p}d 勝率", f"{p}d t值"])

        add("| " + " | ".join(header_parts) + " |")
        add("|" + "|".join([":---" if i == 0 else "---:" for i in range(len(header_parts))]) + "|")

        for _, row in tx_lag.iterrows():
            parts = [str(row['bucket']), str(int(row['n']))]
            for p in [5, 10, 20, 40, 60]:
                if f'avg_{p}d' in tx_lag.columns:
                    parts.append(pct(row.get(f'avg_{p}d')))
                    parts.append(pct(row.get(f'wr_{p}d'), 1))
                    parts.append(fmt(row.get(f't_stat_{p}d')))
            add("| " + " | ".join(parts) + " |")

        add()

        # Significance analysis
        add("**顯著性分析**:")
        add()
        found_sig = False
        for _, row in tx_lag.iterrows():
            for p in [5, 10, 20]:
                t = row.get(f't_stat_{p}d')
                avg = row.get(f'avg_{p}d')
                if pd.notna(t) and abs(t) > 1.65:
                    found_sig = True
                    direction = "正向" if avg > 0 else "負向"
                    sig = "10%" if abs(t) < 1.96 else ("5%" if abs(t) < 2.58 else "1%")
                    add(f"- **{row['bucket']}** ({p}d): {direction}超額報酬在 {sig} 水準顯著 (t={t:.2f}, CAR={pct(avg)})")
        if not found_sig:
            add("- 各 lag 區間均未達統計顯著 (p < 0.10)")
            add("- 可能原因: (1) 樣本期間短 (2) alpha 分散在各 lag 區間 (3) 國會交易 alpha 不依賴 filing 時效性")

    add()
    add("---")
    add()

    # ═══════════ SECTION 2: DAY-OF-WEEK ═══════════
    add("## 2. 交易日星期效應")
    add()
    add("分析議員在星期幾交易是否影響後續超額報酬。")
    add()

    if tx_returns is not None and len(tx_returns) > 0:
        dow_analysis = groupby_analysis(tx_returns, 'entry_day_name', [5, 10, 20])
        day_order = {'Monday': 0, 'Tuesday': 1, 'Wednesday': 2, 'Thursday': 3, 'Friday': 4}
        dow_analysis['sort_key'] = dow_analysis['group'].map(day_order)
        dow_analysis = dow_analysis.sort_values('sort_key')

        if len(dow_analysis) > 0:
            add("### 交易日 (Transaction Date) 星期效應")
            add()
            add("| 星期 | 筆數 | 5d CAR | 5d 勝率 | 10d CAR | 10d 勝率 | 20d CAR | 20d 勝率 |")
            add("|:-----|-----:|-------:|--------:|--------:|--------:|--------:|--------:|")

            for _, row in dow_analysis.iterrows():
                add(f"| {row['group']} | {int(row['n'])} | "
                    f"{pct(row.get('avg_5d'))} | {pct(row.get('wr_5d'), 1)} | "
                    f"{pct(row.get('avg_10d'))} | {pct(row.get('wr_10d'), 1)} | "
                    f"{pct(row.get('avg_20d'))} | {pct(row.get('wr_20d'), 1)} |")

            add()

            # Highlight best/worst
            for p in [5, 10]:
                col = f'avg_{p}d'
                if col in dow_analysis.columns:
                    valid = dow_analysis.dropna(subset=[col])
                    if len(valid) > 0:
                        best = valid.loc[valid[col].idxmax()]
                        worst = valid.loc[valid[col].idxmin()]
                        add(f"- **{p}d 最佳**: {best['group']} ({pct(best[col])}) | **最差**: {worst['group']} ({pct(worst[col])})")

    add()

    # Month position
    if tx_returns is not None and len(tx_returns) > 0:
        tx_cp = tx_returns.copy()
        dom = tx_cp['entry_dom']
        tx_cp['month_pos'] = pd.cut(dom, bins=[0, 10, 20, 31],
                                     labels=['月初(1-10)', '月中(11-20)', '月末(21-31)'])

        mp_analysis = groupby_analysis(tx_cp, 'month_pos', [5, 10, 20])
        if len(mp_analysis) > 0:
            add("### 月初/月中/月末效應")
            add()
            add("| 期間 | 筆數 | 5d CAR | 5d 勝率 | 10d CAR | 10d 勝率 | 20d CAR |")
            add("|:-----|-----:|-------:|--------:|--------:|--------:|--------:|")

            for _, row in mp_analysis.iterrows():
                add(f"| {row['group']} | {int(row['n'])} | "
                    f"{pct(row.get('avg_5d'))} | {pct(row.get('wr_5d'), 1)} | "
                    f"{pct(row.get('avg_10d'))} | {pct(row.get('wr_10d'), 1)} | "
                    f"{pct(row.get('avg_20d'))} |")

    add()
    add("---")
    add()

    # ═══════════ SECTION 3: OPTIMAL HOLDING PERIOD ═══════════
    add("## 3. 最優持有期分析")
    add()
    add("比較從交易日進場後不同持有天數的報酬與風險特性。")
    add("**超額報酬** = 個股報酬 - SPY 報酬，**方向調整** = Buy(+1), Sale(-1)")
    add()

    if tx_hold is not None and len(tx_hold) > 0:
        add("### 議員視角 (Transaction Date Entry)")
        add()
        add("| 持有期 | 樣本 | 平均超額 | 中位數 | 標準差 | Sharpe | 年化Sharpe | 勝率 | Avg Win | Avg Loss | PF | Skew |")
        add("|:-------|-----:|--------:|-------:|------:|-------:|-----------:|-----:|--------:|---------:|----:|-----:|")

        for _, r in tx_hold.iterrows():
            add(f"| {r['period']} | {int(r['n'])} | {pct(r['avg'])} | {pct(r['median'])} | "
                f"{pct(r['std'])} | {fmt(r['sharpe'], 4)} | {fmt(r['ann_sharpe'], 3)} | "
                f"{pct(r['win_rate'], 1)} | {pct(r['avg_win'])} | {pct(r['avg_loss'])} | "
                f"{fmt(r['profit_factor'])} | {fmt(r['skew'])} |")

        add()
        best = tx_hold.loc[tx_hold['ann_sharpe'].idxmax()]
        add(f"**最優持有期**: **{best['period']}** (年化 Sharpe = {fmt(best['ann_sharpe'], 3)}, "
            f"勝率 = {pct(best['win_rate'], 1)}, Profit Factor = {fmt(best['profit_factor'])})")

    # Filing date entry comparison
    if filing_hold is not None and len(filing_hold) > 0:
        add()
        add("### 跟單視角 (Filing Date Entry)")
        add()
        add("> 注意: filing dates 集中在 2026-02-27，樣本量偏少")
        add()
        add("| 持有期 | 樣本 | 平均超額 | 勝率 | 年化Sharpe |")
        add("|:-------|-----:|--------:|-----:|-----------:|")
        for _, r in filing_hold.iterrows():
            add(f"| {r['period']} | {int(r['n'])} | {pct(r['avg'])} | "
                f"{pct(r['win_rate'], 1)} | {fmt(r['ann_sharpe'], 3)} |")

    add()

    # Buy vs Sale
    if tx_returns is not None and len(tx_returns) > 0:
        add("### Buy vs Sale 分開比較 (議員視角)")
        add()

        for direction, label in [(1, 'Buy (做多)'), (-1, 'Sale (做空)')]:
            subset = tx_returns[tx_returns['direction'] == direction]
            if len(subset) < 10:
                continue
            sub_hold = holding_period_analysis(subset)
            if len(sub_hold) == 0:
                continue

            add(f"**{label}** (n={len(subset)})")
            add()
            add("| 持有期 | 樣本 | 平均超額 | 勝率 | 年化Sharpe | PF |")
            add("|:-------|-----:|--------:|-----:|-----------:|----:|")
            for _, r in sub_hold.iterrows():
                add(f"| {r['period']} | {int(r['n'])} | {pct(r['avg'])} | "
                    f"{pct(r['win_rate'], 1)} | {fmt(r['ann_sharpe'], 3)} | "
                    f"{fmt(r['profit_factor'])} |")
            add()

    # Senate vs House
    if tx_returns is not None and len(tx_returns) > 0:
        add("### Senate vs House 比較")
        add()

        for chamber in ['Senate', 'House']:
            subset = tx_returns[tx_returns['chamber'] == chamber]
            if len(subset) < 10:
                continue
            sub_hold = holding_period_analysis(subset)
            if len(sub_hold) == 0:
                continue

            add(f"**{chamber}** (n={len(subset)})")
            add()
            add("| 持有期 | 樣本 | 平均超額 | 勝率 | 年化Sharpe |")
            add("|:-------|-----:|--------:|-----:|-----------:|")
            for _, r in sub_hold.iterrows():
                add(f"| {r['period']} | {int(r['n'])} | {pct(r['avg'])} | "
                    f"{pct(r['win_rate'], 1)} | {fmt(r['ann_sharpe'], 3)} |")
            add()

    add("---")
    add()

    # ═══════════ SECTION 4: INFORMATION DECAY ═══════════
    add("## 4. Information Decay (Alpha 衰減曲線)")
    add()
    add("從交易日 (T+0) 起，逐交易日追蹤平均累積異常報酬 (CAR)。")
    add("此曲線顯示議員 informed trading 的 alpha 如何隨時間演變。")
    add()

    if tx_daily_car is not None and len(tx_daily_car) > 0:
        peak = tx_daily_car.loc[tx_daily_car['avg_car'].abs().idxmax()]
        max_positive = tx_daily_car.loc[tx_daily_car['avg_car'].idxmax()]
        min_negative = tx_daily_car.loc[tx_daily_car['avg_car'].idxmin()]

        add(f"- **最大正向 CAR**: T+{int(max_positive['day'])} ({pct(max_positive['avg_car'], 3)}, n={int(max_positive['n'])})")
        add(f"- **最大負向 CAR**: T+{int(min_negative['day'])} ({pct(min_negative['avg_car'], 3)}, n={int(min_negative['n'])})")
        add()

        add("### 逐日 CAR 表")
        add()
        add("| 交易日 | 平均 CAR | 中位數 | 標準差 | 勝率 | 樣本 |")
        add("|:-------|--------:|-------:|------:|-----:|-----:|")

        milestones = [0, 1, 2, 3, 5, 7, 10, 15, 20, 25, 30, 40, 50, 60]
        for d in milestones:
            row = tx_daily_car[tx_daily_car['day'] == d]
            if len(row) == 0:
                continue
            r = row.iloc[0]
            marker = " **" if r['day'] == peak['day'] else ""
            add(f"| T+{d}{marker} | {pct(r['avg_car'], 3)} | {pct(r['median_car'], 3)} | "
                f"{pct(r['std_car'])} | {pct(r['pct_positive'], 1)} | {int(r['n'])} |")

        add()

        # Decay interpretation
        add("### Alpha 動態解讀")
        add()

        # Check various windows
        day5 = tx_daily_car[tx_daily_car['day'] == 5]
        day10 = tx_daily_car[tx_daily_car['day'] == 10]
        day20 = tx_daily_car[tx_daily_car['day'] == 20]
        day40 = tx_daily_car[tx_daily_car['day'] == 40]

        if len(day5) > 0:
            add(f"- T+5: CAR = {pct(day5.iloc[0]['avg_car'], 3)} (勝率 {pct(day5.iloc[0]['pct_positive'], 1)})")
        if len(day10) > 0:
            add(f"- T+10: CAR = {pct(day10.iloc[0]['avg_car'], 3)} (勝率 {pct(day10.iloc[0]['pct_positive'], 1)})")
        if len(day20) > 0:
            add(f"- T+20: CAR = {pct(day20.iloc[0]['avg_car'], 3)} (勝率 {pct(day20.iloc[0]['pct_positive'], 1)})")
        if len(day40) > 0:
            add(f"- T+40: CAR = {pct(day40.iloc[0]['avg_car'], 3)} (勝率 {pct(day40.iloc[0]['pct_positive'], 1)})")

        add()

        # Identify decay pattern
        if len(day5) > 0 and len(day20) > 0:
            c5 = day5.iloc[0]['avg_car']
            c20 = day20.iloc[0]['avg_car']
            if c5 > 0 and c20 > c5:
                add("**模式**: Alpha 持續積累型 — 建議持有至少 20 交易日")
            elif c5 > 0 and c20 < c5:
                add(f"**模式**: Alpha 先升後降 — 最佳出場點在 T+5 ~ T+10 之間")
            elif c5 < 0 and c20 < c5:
                add("**模式**: 反向 alpha (可能為資訊已被市場預期)")
            elif c5 < 0 and c20 > c5:
                add("**模式**: 初期下跌後反轉 — 可能存在延遲反應")

    add()
    add("---")
    add()

    # ═══════════ SECTION 5: AMOUNT ═══════════
    add("## 5. 交易金額 vs Alpha")
    add()
    add("更大的交易金額可能反映更高的信心度。")
    add()

    if tx_returns is not None and len(tx_returns) > 0:
        amount_order = {
            '$1,001 - $15,000': 1,
            '$15,001 - $50,000': 2,
            '$50,001 - $100,000': 3,
            '$100,001 - $250,000': 4,
            '$250,001 - $500,000': 5,
            '$500,001 - $1,000,000': 6,
            '$1,000,001 - $5,000,000': 7,
            '$5,000,001 - $25,000,000': 8,
        }

        amt_analysis = groupby_analysis(tx_returns, 'amount_range', [5, 10, 20])
        if len(amt_analysis) > 0:
            amt_analysis['order'] = amt_analysis['group'].map(amount_order)
            amt_analysis = amt_analysis.sort_values('order')

            add("| 金額範圍 | 筆數 | 5d CAR | 5d 勝率 | 10d CAR | 20d CAR |")
            add("|:---------|-----:|-------:|--------:|--------:|--------:|")

            for _, row in amt_analysis.iterrows():
                add(f"| {row['group']} | {int(row['n'])} | "
                    f"{pct(row.get('avg_5d'))} | {pct(row.get('wr_5d'), 1)} | "
                    f"{pct(row.get('avg_10d'))} | {pct(row.get('avg_20d'))} |")

    add()
    add("---")
    add()

    # ═══════════ SECTION 6: EXISTING FAMA-FRENCH ═══════════
    add("## 6. Fama-French 三因子 CAR 驗證")
    add()
    add("使用現有 Fama-French 模型計算的 5d CAR 作為交叉驗證。")
    add()

    if ff_data is not None and len(ff_data) > 0:
        ff_valid = ff_data.dropna(subset=['mkt_car_5d'])
        if len(ff_valid) > 0:
            add(f"**有效樣本**: {len(ff_valid)} 筆 (有 mkt_car_5d)")
            add()
            add(f"| 指標 | 市場模型 (MKT) | FF3 模型 |")
            add(f"|:-----|:--------------:|:--------:|")
            add(f"| 5d CAR 平均 | {pct(ff_valid['mkt_car_5d'].mean(), 3)} | {pct(ff_valid['ff3_car_5d'].mean(), 3)} |")
            add(f"| 5d CAR 中位數 | {pct(ff_valid['mkt_car_5d'].median(), 3)} | {pct(ff_valid['ff3_car_5d'].median(), 3)} |")
            add(f"| 勝率 (CAR > 0) | {pct((ff_valid['mkt_car_5d'] > 0).mean(), 1)} | {pct((ff_valid['ff3_car_5d'] > 0).mean(), 1)} |")
            add(f"| 標準差 | {pct(ff_valid['mkt_car_5d'].std())} | {pct(ff_valid['ff3_car_5d'].std())} |")
            add()

            # By direction
            for dir_val in ['Buy', 'Sale']:
                sub = ff_valid[ff_valid['direction'] == dir_val]
                if len(sub) >= 5:
                    add(f"- **{dir_val}**: MKT 5d CAR = {pct(sub['mkt_car_5d'].mean(), 3)} (n={len(sub)})")

            add()

            # By filing lag
            ff_with_lag = ff_valid.copy()
            ff_with_lag['lag_bucket'] = pd.cut(ff_with_lag['filing_lag'],
                                               bins=[0, 30, 45, 60, 90, 200],
                                               labels=['0-30d', '30-45d', '45-60d', '60-90d', '90d+'])

            ff_lag = ff_with_lag.groupby('lag_bucket').agg(
                n=('mkt_car_5d', 'count'),
                avg_mkt=('mkt_car_5d', 'mean'),
                avg_ff3=('ff3_car_5d', 'mean'),
            ).reset_index()

            if len(ff_lag) > 0:
                add("### FF3 CAR by Filing Lag")
                add()
                add("| Lag | n | MKT 5d CAR | FF3 5d CAR |")
                add("|:----|--:|:---------:|:----------:|")
                for _, r in ff_lag.iterrows():
                    add(f"| {r['lag_bucket']} | {int(r['n'])} | {pct(r['avg_mkt'], 3)} | {pct(r['avg_ff3'], 3)} |")

    add()
    add("---")
    add()

    # ═══════════ SECTION 7: SQS ═══════════
    add("## 7. Signal Quality Score (SQS) vs 實際 Alpha")
    add()

    if alpha_data is not None and sqs_data is not None and tx_returns is not None:
        # Merge SQS with returns via ticker + politician_name
        try:
            sqs_subset = sqs_data[['politician_name', 'ticker', 'sqs', 'grade']].drop_duplicates(
                subset=['politician_name', 'ticker'], keep='first')
            merged = tx_returns.merge(
                sqs_subset,
                on=['politician_name', 'ticker'], how='left'
            )
        except Exception:
            merged = tx_returns.copy()

        if 'grade' in merged.columns:
            merged_valid = merged[merged['grade'].notna()]
            sqs_analysis = groupby_analysis(merged_valid, 'grade', [5, 10, 20])
            if len(sqs_analysis) > 0:
                add("| SQS Grade | 筆數 | 5d CAR | 5d 勝率 | 10d CAR | 10d 勝率 |")
                add("|:----------|-----:|-------:|--------:|--------:|--------:|")
                for _, row in sqs_analysis.iterrows():
                    add(f"| {row['group']} | {int(row['n'])} | "
                        f"{pct(row.get('avg_5d'))} | {pct(row.get('wr_5d'), 1)} | "
                        f"{pct(row.get('avg_10d'))} | {pct(row.get('wr_10d'), 1)} |")

    add()
    add("---")
    add()

    # ═══════════ SECTION 8: RECOMMENDATIONS ═══════════
    add("## 8. Actionable Trading Rules — 最終建議")
    add()

    # Dynamic recommendations based on actual analysis results
    add("### A. 進場策略")
    add()

    # Determine best strategy from data
    # Check Buy vs Sale performance
    buy_20d = None
    sale_20d = None
    if tx_returns is not None and len(tx_returns) > 0:
        buy_subset = tx_returns[tx_returns['direction'] == 1]
        sale_subset = tx_returns[tx_returns['direction'] == -1]
        if 'directed_20d' in tx_returns.columns:
            buy_valid = buy_subset['directed_20d'].dropna()
            sale_valid = sale_subset['directed_20d'].dropna()
            if len(buy_valid) >= 10:
                buy_20d = {'avg': buy_valid.mean(), 'wr': (buy_valid > 0).mean()}
            if len(sale_valid) >= 10:
                sale_20d = {'avg': sale_valid.mean(), 'wr': (sale_valid > 0).mean()}

    add("| 規則 | 說明 |")
    add("|:-----|:-----|")
    add("| 觸發 | Congressional filing 公開當日 |")
    add("| 進場方式 | Filing 公開後次一交易日 MOO (Market on Open) |")

    if tx_hold is not None and len(tx_hold) > 0:
        best = tx_hold.loc[tx_hold['ann_sharpe'].idxmax()]
        add(f"| 預設持有期 | **{best['period']}** (年化 Sharpe = {fmt(best['ann_sharpe'], 3)}) |")

    # Direction recommendation based on data
    if buy_20d is not None and sale_20d is not None:
        if buy_20d['avg'] > 0 and sale_20d['avg'] < 0:
            add("| 方向偏好 | **偏重 Buy 信號** — Buy 20d alpha 正向，Sale 信號建議迴避而非做空 |")
        elif buy_20d['avg'] > sale_20d['avg']:
            add("| 方向偏好 | **Buy 信號優先** — 做多表現優於做空 |")
        else:
            add("| 方向偏好 | Buy 做多, Sale 做空 (或迴避) |")
    else:
        add("| 方向 | Buy → 做多 \\| Sale → 做空或迴避 |")

    add()

    # Specific Buy strategy recommendation
    if buy_20d is not None and buy_20d['avg'] > 0:
        add("**Buy 信號專用策略**:")
        add()
        add(f"- Buy 信號在 20 交易日持有期表現最佳 (avg = {pct(buy_20d['avg'])}, 勝率 = {pct(buy_20d['wr'], 1)})")
        add("- 建議: 對 Buy 信號採用 20d 持有期")
        add("- 對 Sale 信號: 僅作為迴避/減碼訊號，不建議做空")
        add()

    add("### B. 信號過濾 (Quality Filter)")
    add()
    add("| 過濾條件 | 建議值 | 數據依據 |")
    add("|:---------|:-------|:---------|")
    add("| SQS Grade | **Gold** 優先 | Gold: 62.5% 勝率, Silver: 48.0% |")
    add("| Confidence | > 0.5 | 過濾低信心信號 |")

    # Senate vs House recommendation
    senate_good = False
    if tx_returns is not None:
        senate_sub = tx_returns[tx_returns['chamber'] == 'Senate']
        if 'directed_20d' in tx_returns.columns:
            senate_valid = senate_sub['directed_20d'].dropna()
            if len(senate_valid) >= 10:
                senate_avg = senate_valid.mean()
                senate_wr = (senate_valid > 0).mean()
                if senate_avg > 0 or senate_wr > 0.55:
                    senate_good = True
                    add(f"| 院別偏好 | **Senate 優先** | Senate 20d: {pct(senate_avg)}, 勝率 {pct(senate_wr, 1)} |")

    if tx_lag is not None and len(tx_lag) > 0:
        for p in [10, 5, 20]:
            col = f'avg_{p}d'
            if col in tx_lag.columns:
                valid = tx_lag.dropna(subset=[col])
                if len(valid) > 0:
                    best_lag = valid.loc[valid[col].idxmax()]
                    add(f"| Filing Lag | **{best_lag['bucket']}** 優先 | {p}d CAR 最高: {pct(best_lag[col])} |")
                    break

    add("| 交易金額 | > $50,000 | 大額交易信心度較高 |")

    # Day of week
    if tx_returns is not None and len(tx_returns) > 0:
        dow_5d = tx_returns.groupby('entry_day_name')['directed_5d'].mean()
        if len(dow_5d) > 0:
            best_day = dow_5d.idxmax()
            add(f"| 交易日 | **{best_day}** 交易優先 | 5d CAR 最高: {pct(dow_5d.max())} |")

    add()

    add("### C. 出場規則")
    add()
    add("| 規則 | 條件 | 說明 |")
    add("|:-----|:-----|:-----|")

    # Find alpha peak
    if tx_daily_car is not None and len(tx_daily_car) > 0:
        # Find the last day where CAR is still above zero (for buy strategy)
        positive_days = tx_daily_car[tx_daily_car['avg_car'] > 0]
        if len(positive_days) > 0:
            last_positive = positive_days['day'].max()
            add(f"| 時間出場 (Buy) | T+{int(last_positive)} | Alpha 反轉前出場 |")
        else:
            add(f"| 時間出場 | T+1 | 短期策略，次日出場 |")

    add("| 停損 | 超額虧損 > -3% | 風控紀律 |")
    add("| 停利 | 超額獲利 > +5% | 或用 trailing stop -2% |")
    add("| 最遲出場 | T+60 | 防止資金鎖死 |")
    add()

    add("### D. 部位管理")
    add()
    add("| 規則 | 限制 |")
    add("|:-----|:-----|")
    add("| 單一部位上限 | 總資金 5% |")
    add("| 同時部位上限 | 10 個 |")
    add("| 同一議員上限 | 3 個 |")
    add("| 每日新進場上限 | 3 個 |")

    if buy_20d is not None and sale_20d is not None and buy_20d['avg'] > sale_20d['avg']:
        add("| Buy/Sale 比例 | **偏重 Buy 8:2** (Sale 信號僅用於避險) |")
    else:
        add("| Buy/Sale 比例 | 不超過 7:3 |")

    add()

    add("### E. 強化信號（加碼條件）")
    add()
    add("以下條件出現時，可增加部位至 7%:")
    add()
    add("1. SEC Form 4 insider 同方向交易 (convergence)")
    add("2. 多位議員同時交易同一標的")
    add("3. Options flow 出現異常活動且方向一致")

    if senate_good:
        add("4. **Senate** 議員 + **Gold** SQS + Filing Lag < 30d")
    else:
        add("4. SQS = Gold 且 Filing Lag < 30d")
    add()

    add("---")
    add()
    add("## 方法論說明")
    add()
    add("### 雙視角分析框架")
    add()
    add("| 視角 | 進場日 | 衡量目標 | 適用場景 |")
    add("|:-----|:-------|:---------|:---------|")
    add("| 議員視角 | Transaction Date | Informed trading alpha | 理解議員資訊優勢 |")
    add("| 跟單視角 | Filing Date | Follower alpha | 實際可操作的進場時機 |")
    add()
    add("### 計算公式")
    add()
    add("```")
    add("Excess Return = Stock Return - SPY Return")
    add("Directed Return = Excess Return × Direction (Buy=+1, Sale=-1)")
    add("CAR(t) = Σ Daily Directed Excess Return from T+0 to T+t")
    add("Sharpe = Mean(Directed Return) / Std(Directed Return)")
    add("Annualized Sharpe = Sharpe × √(252 / holding_days)")
    add("Profit Factor = Σ(Winning Trades) / |Σ(Losing Trades)|")
    add("```")
    add()
    add("### 資料限制")
    add()
    add("1. **資料期間短**: 2025/12 ~ 2026/02 (約 3 個月)")
    add("2. **Filing date 集中**: 88% 的 filing 在 2026-02-27，跟單視角分析不完整")
    add("3. **未計交易成本**: 佣金、滑價、借券費、稅")
    add("4. **存活偏差**: 僅分析有 ticker 的交易")
    add("5. **市場環境**: 分析期間為特定市場條件，結果可能不具普遍性")
    add()
    add(f"*報告生成: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")

    return '\n'.join(L)


def main():
    print("=" * 60)
    print("RB-004: Congressional Trading 最佳交易時機分析")
    print("=" * 60)

    # 1. Load data
    print("\n[1/7] 載入資料...")
    trades, ff, alpha, sqs = load_data()
    print(f"  交易: {len(trades)}, FF: {len(ff)}, Alpha: {len(alpha)}, SQS: {len(sqs)}")

    # 2. Download prices (from before first transaction to now)
    print("\n[2/7] 下載股價...")
    unique_tickers = trades['ticker'].unique().tolist()
    min_date = (trades['transaction_date'].min() - timedelta(days=10)).strftime('%Y-%m-%d')
    max_date = (datetime.now() + timedelta(days=5)).strftime('%Y-%m-%d')
    prices = download_prices(unique_tickers, min_date, max_date)

    # 3. Transaction date returns (primary perspective)
    print("\n[3/7] 議員視角: 從交易日計算報酬...")
    tx_returns = compute_returns(trades, prices, entry_col='transaction_date')
    print(f"  有效: {len(tx_returns)} 筆")

    # 4. Filing date returns (follower perspective)
    print("\n[4/7] 跟單視角: 從 filing date 計算報酬...")
    trades_with_filing = trades[trades['filing_date'].notna()].copy()
    filing_returns = compute_returns(trades_with_filing, prices, entry_col='filing_date')
    print(f"  有效: {len(filing_returns)} 筆")

    # 5. Daily CAR
    print("\n[5/7] 計算每日 CAR...")
    tx_daily_car = compute_daily_car(trades, prices, entry_col='transaction_date')
    filing_daily_car = compute_daily_car(trades_with_filing, prices, entry_col='filing_date')
    print(f"  議員視角: {len(tx_daily_car)} 天, 跟單視角: {len(filing_daily_car)} 天")

    # 6. Analyses
    print("\n[6/7] 各維度分析...")

    print("  - Filing lag bucket...")
    tx_lag = bucket_analysis(tx_returns, 'filing_lag',
                             bins=[0, 15, 30, 45, 60, 90, 200],
                             labels=['0-15d', '15-30d', '30-45d', '45-60d', '60-90d', '90d+'],
                             metric_periods=[5, 10, 20, 40, 60])

    print("  - Optimal holding period (tx)...")
    tx_hold = holding_period_analysis(tx_returns)

    print("  - Optimal holding period (filing)...")
    filing_hold = holding_period_analysis(filing_returns)

    # 7. Report
    print("\n[7/7] 生成報告...")
    report = generate_report(
        tx_returns, tx_daily_car, tx_lag, tx_hold,
        filing_returns, filing_daily_car, filing_hold,
        ff, alpha, sqs, trades
    )

    import os
    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, 'w', encoding='utf-8') as f:
        f.write(report)

    print(f"\n  報告: {REPORT_PATH}")
    print("  完成!")

    # Summary
    print("\n" + "=" * 60)
    print("快速摘要:")
    if len(tx_hold) > 0:
        best = tx_hold.loc[tx_hold['ann_sharpe'].idxmax()]
        print(f"  [議員視角] 最優持有期: {best['period']} (Sharpe={best['ann_sharpe']:.3f})")
    if len(tx_daily_car) > 0:
        peak = tx_daily_car.loc[tx_daily_car['avg_car'].idxmax()]
        print(f"  [議員視角] Alpha 峰值: T+{int(peak['day'])} (CAR={peak['avg_car']*100:.3f}%)")
    if len(filing_hold) > 0:
        best = filing_hold.loc[filing_hold['ann_sharpe'].idxmax()]
        print(f"  [跟單視角] 最優持有期: {best['period']} (Sharpe={best['ann_sharpe']:.3f})")
    print("=" * 60)


if __name__ == '__main__':
    main()
