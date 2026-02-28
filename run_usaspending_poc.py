import argparse, logging, sqlite3, sys
from datetime import datetime, timedelta
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("RB009")
try:
    import yfinance as yf
    import pandas as pd
    HAS_YF = True
except ImportError:
    HAS_YF = False
from src.etl.usaspending_fetcher import USASpendingFetcher
from src.config import DB_PATH


def get_congress_trades(conn, days=730):
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    rows = conn.execute(
        "SELECT id, ticker, politician_name, transaction_type, transaction_date "
        "FROM congress_trades WHERE ticker IS NOT NULL AND transaction_date >= ? "
        "ORDER BY transaction_date DESC", (cutoff,)).fetchall()
    return [dict(r) for r in rows]


def compute_car(ticker, event_date_str, window_days=5, benchmark="SPY"):
    if not HAS_YF:
        return None
    try:
        event_dt = datetime.strptime(event_date_str, "%Y-%m-%d")
        s = (event_dt - timedelta(days=10)).strftime("%Y-%m-%d")
        e = (event_dt + timedelta(days=window_days + 10)).strftime("%Y-%m-%d")
        data = yf.download([ticker, benchmark], start=s, end=e, progress=False, auto_adjust=True)
        if data.empty:
            return None
        closes = data["Close"]
        if not hasattr(closes, "columns"):
            return None
        if ticker not in closes.columns or benchmark not in closes.columns:
            return None
        tp = closes[ticker]
        sp = closes[benchmark]
        idx = tp.index.searchsorted(pd.Timestamp(event_dt))
        if idx >= len(tp) - window_days:
            return None
        p0t = tp.iloc[idx]
        p5t = tp.iloc[min(idx + window_days, len(tp) - 1)]
        p0s = sp.iloc[idx]
        p5s = sp.iloc[min(idx + window_days, len(sp) - 1)]
        if p0t == 0 or p0s == 0:
            return None
        return float((p5t - p0t) / p0t - (p5s - p0s) / p0s)
    except Exception as ex:
        logger.debug(f"CAR {ticker}: {ex}")
        return None


def main():
    parser = argparse.ArgumentParser(description="RB-009 USASpending POC")
    parser.add_argument("--days", type=int, default=730)
    parser.add_argument("--top-n", type=int, default=40)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print("=" * 60)
    print("RB-009 USASpending API POC")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")

    trades = get_congress_trades(conn, days=args.days)
    tickers = list(dict.fromkeys(t["ticker"] for t in trades if t["ticker"]))
    print(f"[1] Trades: {len(trades)}, unique tickers: {len(tickers)}")

    fetcher = USASpendingFetcher()
    mapped = [t for t in tickers[:args.top_n] if t in fetcher.contractor_map]
    print(f"[2] Mapped tickers: {len(mapped)} / {len(tickers)}")
    start_date = (datetime.now() - timedelta(days=args.days)).strftime("%Y-%m-%d")
    contracts = fetcher.fetch_contracts_for_tickers(mapped, start_date=start_date)
    print(f"    Contracts found: {len(contracts)}")

    cross_refs = fetcher.cross_reference_with_trades(contracts, trades)
    buy_pairs = [cr for cr in cross_refs if "BUY" in cr.signal_type]
    sell_pairs = [cr for cr in cross_refs if "SELL" in cr.signal_type]
    high = [cr for cr in cross_refs if cr.convergence_score >= 0.7]
    print(f"[3] Cross-refs: {len(cross_refs)} (BUY={len(buy_pairs)}, SELL={len(sell_pairs)}, high={len(high)})")

    if not args.dry_run:
        n1 = fetcher.save_contracts_to_db(contracts, conn)
        n2 = fetcher.save_cross_refs_to_db(cross_refs, conn)
        conn.commit()
        print(f"[4] Saved: {n1} contracts, {n2} cross-refs to DB")
    else:
        print("[4] dry-run: skipping DB write")

    print()
    print("=== Convergence Pairs ===")
    for cr in sorted(cross_refs, key=lambda x: x.convergence_score, reverse=True):
        d = "BEFORE" if cr.days_before_trade > 0 else "AFTER"
        amt = f"${cr.award_amount / 1e6:.1f}M"
        print(
            f"  [{cr.signal_type}] {cr.ticker} | {cr.politician_name[:22]:<22} | "
            f"{cr.transaction_date} | contract:{cr.contract_start_date} | "
            f"{abs(cr.days_before_trade)}d {d} | {amt} | score={cr.convergence_score:.2f}"
        )

    print()
    print("=== CAR Analysis (5d) ===")
    if HAS_YF and buy_pairs:
        cars_conv = []
        for cr in sorted(buy_pairs, key=lambda x: x.convergence_score, reverse=True)[:15]:
            c = compute_car(cr.ticker, cr.transaction_date)
            if c is not None:
                cars_conv.append(c)

        bt = [
            t for t in trades
            if "buy" in (t.get("transaction_type") or "").lower()
            or "purchase" in (t.get("transaction_type") or "").lower()
        ]
        cars_all = []
        for t in bt[:25]:
            if not t.get("transaction_date"):
                continue
            c = compute_car(t["ticker"], t["transaction_date"])
            if c is not None:
                cars_all.append(c)

        if cars_conv:
            avg_c = sum(cars_conv) / len(cars_conv)
            print(f"  Convergence BUY CAR_5d: {avg_c * 100:.2f}% (n={len(cars_conv)})")
        if cars_all:
            avg_a = sum(cars_all) / len(cars_all)
            print(f"  All BUY CAR_5d:         {avg_a * 100:.2f}% (n={len(cars_all)})")
        if cars_conv and cars_all:
            print(f"  Alpha premium:          {(avg_c - avg_a) * 100:.2f}%")
    else:
        print("  Skipped (yfinance unavailable or no BUY pairs)")

    conn.close()
    print()
    print("[DONE] RB-009 POC complete")


if __name__ == "__main__":
    sys.exit(main())
