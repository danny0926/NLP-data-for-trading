"""
Signal Performance Tracker — Political Alpha Monitor
追蹤 Alpha 信號的實際表現，計算命中率和 P&L

功能:
1. 從 alpha_signals 讀取歷史信號
2. 用 yfinance 取得實際價格變動
3. 計算 hit rate、actual alpha、MAE/MFE
4. 寫入 signal_performance 表

使用方式:
    python -m src.signal_tracker                # 追蹤所有信號
    python -m src.signal_tracker --days 7       # 只追蹤最近 7 天的信號
    python -m src.signal_tracker --ticker AAPL  # 追蹤特定 ticker
"""

import argparse
import logging
import os
import sqlite3
import sys
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.config import DB_PATH

logger = logging.getLogger(__name__)


def _safe_print(text: str) -> None:
    """安全列印。"""
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode('ascii', 'replace').decode('ascii'))


class SignalPerformanceTracker:
    """追蹤信號實際表現。"""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._ensure_table()

    def _ensure_table(self) -> None:
        """建立 signal_performance 表。"""
        conn = sqlite3.connect(self.db_path)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS signal_performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                signal_id INTEGER,
                ticker TEXT NOT NULL,
                direction TEXT,
                signal_date TEXT,
                expected_alpha_5d REAL,
                expected_alpha_20d REAL,
                actual_return_5d REAL,
                actual_return_20d REAL,
                actual_alpha_5d REAL,
                actual_alpha_20d REAL,
                spy_return_5d REAL,
                spy_return_20d REAL,
                hit_5d INTEGER,
                hit_20d INTEGER,
                signal_strength REAL,
                confidence REAL,
                max_favorable_excursion REAL,
                max_adverse_excursion REAL,
                evaluated_at TEXT,
                UNIQUE(signal_id)
            )
        ''')
        conn.commit()
        conn.close()

    def get_pending_signals(self, days: Optional[int] = None,
                            ticker: Optional[str] = None) -> List[Dict]:
        """取得尚未評估的信號。"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        sql = '''
            SELECT a.id, a.ticker, a.direction, a.created_at,
                   a.expected_alpha_5d, a.expected_alpha_20d,
                   a.signal_strength, a.confidence
            FROM alpha_signals a
            LEFT JOIN signal_performance sp ON a.id = sp.signal_id
            WHERE sp.id IS NULL
              AND a.ticker IS NOT NULL
              AND a.ticker != ''
        '''
        params = []

        if days:
            cutoff = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            sql += ' AND a.created_at >= ?'
            params.append(cutoff)

        if ticker:
            sql += ' AND a.ticker = ?'
            params.append(ticker)

        sql += ' ORDER BY a.signal_strength DESC'

        rows = conn.execute(sql, tuple(params)).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def fetch_prices(self, ticker: str, start_date: str,
                     lookback_days: int = 30) -> Optional[Dict]:
        """用 yfinance 取得價格資料。"""
        try:
            import yfinance as yf

            start = datetime.strptime(start_date, '%Y-%m-%d')
            # Fetch from signal date to +25 trading days
            fetch_start = start - timedelta(days=5)
            fetch_end = start + timedelta(days=lookback_days + 5)

            # Don't fetch future data
            if fetch_end > datetime.now():
                fetch_end = datetime.now()

            stock = yf.download(
                ticker, start=fetch_start.strftime('%Y-%m-%d'),
                end=fetch_end.strftime('%Y-%m-%d'),
                progress=False, auto_adjust=True
            )
            spy = yf.download(
                'SPY', start=fetch_start.strftime('%Y-%m-%d'),
                end=fetch_end.strftime('%Y-%m-%d'),
                progress=False, auto_adjust=True
            )

            if stock.empty or spy.empty:
                return None

            return {
                'stock': stock,
                'spy': spy,
                'signal_date': start_date
            }
        except Exception as e:
            logger.warning(f"Price fetch failed for {ticker}: {e}")
            return None

    def calculate_performance(self, ticker: str, direction: str,
                              signal_date: str,
                              price_data: Dict) -> Optional[Dict]:
        """計算信號的實際表現。"""
        try:
            stock = price_data['stock']
            spy = price_data['spy']

            signal_dt = datetime.strptime(signal_date, '%Y-%m-%d')

            # Find the closest trading day on or after signal date
            stock_dates = stock.index
            valid_dates = [d for d in stock_dates if d >= signal_dt]
            if not valid_dates:
                return None

            base_date = valid_dates[0]
            base_idx = list(stock_dates).index(base_date)

            # Handle MultiIndex columns from yfinance
            close_col = 'Close'
            if hasattr(stock.columns, 'levels'):
                stock = stock.droplevel(level=1, axis=1) if stock.columns.nlevels > 1 else stock
            if hasattr(spy.columns, 'levels'):
                spy = spy.droplevel(level=1, axis=1) if spy.columns.nlevels > 1 else spy

            base_price = float(stock[close_col].iloc[base_idx])

            results = {}

            # 5-day return
            if base_idx + 5 < len(stock):
                price_5d = float(stock[close_col].iloc[base_idx + 5])
                stock_ret_5d = (price_5d / base_price - 1) * 100

                # SPY return for same period
                spy_dates = spy.index
                spy_base = [d for d in spy_dates if d >= signal_dt]
                if spy_base:
                    spy_base_idx = list(spy_dates).index(spy_base[0])
                    if spy_base_idx + 5 < len(spy):
                        spy_base_price = float(spy[close_col].iloc[spy_base_idx])
                        spy_5d_price = float(spy[close_col].iloc[spy_base_idx + 5])
                        spy_ret_5d = (spy_5d_price / spy_base_price - 1) * 100
                    else:
                        spy_ret_5d = 0
                else:
                    spy_ret_5d = 0

                # Adjust for direction
                if direction == 'SHORT':
                    actual_alpha_5d = -stock_ret_5d + spy_ret_5d
                else:
                    actual_alpha_5d = stock_ret_5d - spy_ret_5d

                results['actual_return_5d'] = stock_ret_5d
                results['spy_return_5d'] = spy_ret_5d
                results['actual_alpha_5d'] = actual_alpha_5d

            # 20-day return
            if base_idx + 20 < len(stock):
                price_20d = float(stock[close_col].iloc[base_idx + 20])
                stock_ret_20d = (price_20d / base_price - 1) * 100

                spy_dates = spy.index
                spy_base = [d for d in spy_dates if d >= signal_dt]
                if spy_base:
                    spy_base_idx = list(spy_dates).index(spy_base[0])
                    if spy_base_idx + 20 < len(spy):
                        spy_base_price = float(spy[close_col].iloc[spy_base_idx])
                        spy_20d_price = float(spy[close_col].iloc[spy_base_idx + 20])
                        spy_ret_20d = (spy_20d_price / spy_base_price - 1) * 100
                    else:
                        spy_ret_20d = 0
                else:
                    spy_ret_20d = 0

                if direction == 'SHORT':
                    actual_alpha_20d = -stock_ret_20d + spy_ret_20d
                else:
                    actual_alpha_20d = stock_ret_20d - spy_ret_20d

                results['actual_return_20d'] = stock_ret_20d
                results['spy_return_20d'] = spy_ret_20d
                results['actual_alpha_20d'] = actual_alpha_20d

            # MAE / MFE (Max Adverse/Favorable Excursion)
            window_end = min(base_idx + 20, len(stock))
            if window_end > base_idx:
                window_prices = stock[close_col].iloc[base_idx:window_end]
                window_returns = [(float(p) / base_price - 1) * 100 for p in window_prices]

                if direction == 'SHORT':
                    window_returns = [-r for r in window_returns]

                results['max_favorable_excursion'] = max(window_returns) if window_returns else 0
                results['max_adverse_excursion'] = min(window_returns) if window_returns else 0

            return results if results else None

        except Exception as e:
            logger.warning(f"Performance calc failed for {ticker}: {e}")
            return None

    def evaluate_signals(self, signals: List[Dict]) -> List[Dict]:
        """批次評估信號表現。"""
        results = []
        tickers_seen = set()

        for signal in signals:
            ticker = signal['ticker']

            # Skip duplicates (same ticker, different signal IDs)
            if ticker in tickers_seen:
                continue
            tickers_seen.add(ticker)

            signal_date = signal.get('created_at', '')
            if not signal_date:
                continue

            # Extract date part only
            if ' ' in signal_date:
                signal_date = signal_date.split(' ')[0]

            _safe_print(f"  Evaluating {ticker} ({signal.get('direction', '?')})...")

            price_data = self.fetch_prices(ticker, signal_date)
            if not price_data:
                _safe_print(f"    [SKIP] No price data for {ticker}")
                continue

            perf = self.calculate_performance(
                ticker, signal.get('direction', 'LONG'),
                signal_date, price_data
            )

            if not perf:
                _safe_print(f"    [SKIP] Not enough trading days for {ticker}")
                continue

            # Determine hit (alpha > 0 = hit)
            hit_5d = None
            hit_20d = None
            if 'actual_alpha_5d' in perf:
                hit_5d = 1 if perf['actual_alpha_5d'] > 0 else 0
            if 'actual_alpha_20d' in perf:
                hit_20d = 1 if perf['actual_alpha_20d'] > 0 else 0

            result = {
                'signal_id': signal['id'],
                'ticker': ticker,
                'direction': signal.get('direction', 'LONG'),
                'signal_date': signal_date,
                'expected_alpha_5d': signal.get('expected_alpha_5d'),
                'expected_alpha_20d': signal.get('expected_alpha_20d'),
                'actual_return_5d': perf.get('actual_return_5d'),
                'actual_return_20d': perf.get('actual_return_20d'),
                'actual_alpha_5d': perf.get('actual_alpha_5d'),
                'actual_alpha_20d': perf.get('actual_alpha_20d'),
                'spy_return_5d': perf.get('spy_return_5d'),
                'spy_return_20d': perf.get('spy_return_20d'),
                'hit_5d': hit_5d,
                'hit_20d': hit_20d,
                'signal_strength': signal.get('signal_strength'),
                'confidence': signal.get('confidence'),
                'max_favorable_excursion': perf.get('max_favorable_excursion'),
                'max_adverse_excursion': perf.get('max_adverse_excursion'),
                'evaluated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            }
            results.append(result)

            # Print summary
            alpha_5d = perf.get('actual_alpha_5d')
            alpha_20d = perf.get('actual_alpha_20d')
            hit_icon = '[+]' if hit_5d else '[-]'
            alpha_str = f"alpha_5d={alpha_5d:+.2f}%" if alpha_5d is not None else "5d=N/A"
            _safe_print(f"    {hit_icon} {alpha_str}")

        return results

    def save_results(self, results: List[Dict]) -> int:
        """儲存評估結果到 signal_performance 表。"""
        if not results:
            return 0

        conn = sqlite3.connect(self.db_path)
        saved = 0

        for r in results:
            try:
                conn.execute('''
                    INSERT OR REPLACE INTO signal_performance
                    (signal_id, ticker, direction, signal_date,
                     expected_alpha_5d, expected_alpha_20d,
                     actual_return_5d, actual_return_20d,
                     actual_alpha_5d, actual_alpha_20d,
                     spy_return_5d, spy_return_20d,
                     hit_5d, hit_20d,
                     signal_strength, confidence,
                     max_favorable_excursion, max_adverse_excursion,
                     evaluated_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ''', (
                    r['signal_id'], r['ticker'], r['direction'],
                    r['signal_date'], r['expected_alpha_5d'],
                    r['expected_alpha_20d'], r['actual_return_5d'],
                    r['actual_return_20d'], r['actual_alpha_5d'],
                    r['actual_alpha_20d'], r['spy_return_5d'],
                    r['spy_return_20d'], r['hit_5d'], r['hit_20d'],
                    r['signal_strength'], r['confidence'],
                    r['max_favorable_excursion'],
                    r['max_adverse_excursion'], r['evaluated_at'],
                ))
                saved += 1
            except Exception as e:
                logger.warning(f"Save failed for {r['ticker']}: {e}")

        conn.commit()
        conn.close()
        return saved

    def print_summary(self, results: List[Dict]) -> None:
        """印出績效摘要。"""
        if not results:
            _safe_print("\n  No results to summarize.\n")
            return

        _safe_print(f"\n{'='*70}")
        _safe_print(f"  Signal Performance Summary")
        _safe_print(f"{'='*70}")

        # Hit rate
        hits_5d = [r for r in results if r.get('hit_5d') is not None]
        hits_20d = [r for r in results if r.get('hit_20d') is not None]

        if hits_5d:
            hit_rate_5d = sum(r['hit_5d'] for r in hits_5d) / len(hits_5d)
            avg_alpha_5d = sum(r.get('actual_alpha_5d', 0) or 0 for r in hits_5d) / len(hits_5d)
            _safe_print(f"\n  5-Day Performance:")
            _safe_print(f"    Evaluated: {len(hits_5d)} signals")
            _safe_print(f"    Hit Rate:  {hit_rate_5d:.1%} ({sum(r['hit_5d'] for r in hits_5d)}/{len(hits_5d)})")
            _safe_print(f"    Avg Alpha: {avg_alpha_5d:+.3f}%")

        if hits_20d:
            hit_rate_20d = sum(r['hit_20d'] for r in hits_20d) / len(hits_20d)
            avg_alpha_20d = sum(r.get('actual_alpha_20d', 0) or 0 for r in hits_20d) / len(hits_20d)
            _safe_print(f"\n  20-Day Performance:")
            _safe_print(f"    Evaluated: {len(hits_20d)} signals")
            _safe_print(f"    Hit Rate:  {hit_rate_20d:.1%} ({sum(r['hit_20d'] for r in hits_20d)}/{len(hits_20d)})")
            _safe_print(f"    Avg Alpha: {avg_alpha_20d:+.3f}%")

        # Best/worst performers
        alpha_5d_results = [r for r in results if r.get('actual_alpha_5d') is not None]
        if alpha_5d_results:
            best = max(alpha_5d_results, key=lambda x: x['actual_alpha_5d'])
            worst = min(alpha_5d_results, key=lambda x: x['actual_alpha_5d'])
            _safe_print(f"\n  Best:  {best['ticker']} alpha_5d={best['actual_alpha_5d']:+.2f}%")
            _safe_print(f"  Worst: {worst['ticker']} alpha_5d={worst['actual_alpha_5d']:+.2f}%")

        # Excursion analysis
        mfe_results = [r for r in results if r.get('max_favorable_excursion') is not None]
        if mfe_results:
            avg_mfe = sum(r['max_favorable_excursion'] for r in mfe_results) / len(mfe_results)
            avg_mae = sum(r['max_adverse_excursion'] for r in mfe_results) / len(mfe_results)
            _safe_print(f"\n  Avg MFE (max gain):  {avg_mfe:+.2f}%")
            _safe_print(f"  Avg MAE (max loss):  {avg_mae:+.2f}%")
            if avg_mae != 0:
                _safe_print(f"  MFE/MAE Ratio:       {abs(avg_mfe/avg_mae):.2f}x")

        _safe_print(f"\n{'='*70}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Political Alpha Monitor — Signal Performance Tracker"
    )
    parser.add_argument("--days", type=int, default=None,
                        help="Only track signals from last N days")
    parser.add_argument("--ticker", type=str, default=None,
                        help="Track specific ticker only")
    parser.add_argument("--limit", type=int, default=20,
                        help="Max signals to evaluate (default 20)")
    parser.add_argument("--db", type=str, default=DB_PATH,
                        help="Database path")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    _safe_print(f"\n{'='*60}")
    _safe_print(f"  Signal Performance Tracker")
    _safe_print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    _safe_print(f"{'='*60}\n")

    tracker = SignalPerformanceTracker(db_path=args.db)

    # Get pending signals
    signals = tracker.get_pending_signals(days=args.days, ticker=args.ticker)
    _safe_print(f"  Found {len(signals)} pending signals")

    if not signals:
        _safe_print("  No signals to evaluate.")
        return

    # Limit to avoid too many API calls
    signals = signals[:args.limit]
    _safe_print(f"  Evaluating top {len(signals)} signals...\n")

    # Evaluate
    results = tracker.evaluate_signals(signals)

    # Save
    saved = tracker.save_results(results)
    _safe_print(f"\n  Saved {saved} results to signal_performance table")

    # Summary
    tracker.print_summary(results)


if __name__ == '__main__':
    main()
