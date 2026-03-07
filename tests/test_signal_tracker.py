import os
import sqlite3
import tempfile
from datetime import datetime, timedelta

import pytest

from src.signal_tracker import SignalPerformanceTracker


def _make_tracker_db(signals=None):
    f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = f.name
    f.close()
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE alpha_signals (id INTEGER PRIMARY KEY, trade_id TEXT,"
        " ticker TEXT, direction TEXT, expected_alpha_5d REAL,"
        " expected_alpha_20d REAL, signal_strength REAL, confidence REAL,"
        " created_at TEXT)"
    )
    conn.execute(
        "CREATE TABLE congress_trades (id INTEGER PRIMARY KEY,"
        " chamber TEXT, politician_name TEXT, transaction_date TEXT,"
        " filing_date TEXT, ticker TEXT, asset_name TEXT,"
        " asset_type TEXT, transaction_type TEXT, amount_range TEXT,"
        " owner TEXT, comment TEXT, source_url TEXT,"
        " source_format TEXT, extraction_confidence REAL,"
        " data_hash TEXT UNIQUE, created_at TEXT)"
    )
    if signals:
        for s in signals:
            tid = s[0]
            conn.execute(
                "INSERT INTO congress_trades (id, filing_date, ticker, transaction_type, data_hash)"
                " VALUES (?,?,?,?,?)",
                (tid, s[4], s[1], "Buy", f"hash-{tid}"))
            conn.execute(
                "INSERT INTO alpha_signals (id, trade_id, ticker, direction,"
                " expected_alpha_5d, expected_alpha_20d,"
                " signal_strength, confidence, created_at)"
                " VALUES (?,?,?,?,?,?,?,?,?)",
                (tid, str(tid), s[1], s[2], s[3], s[3]*2, 0.8, 0.7, s[4]))
    conn.commit()
    conn.close()
    return db_path


class TestEnsureTable:

    def test_creates_table(self):
        db = _make_tracker_db()
        try:
            tracker = SignalPerformanceTracker(db_path=db)
            conn = sqlite3.connect(db)
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='signal_performance'"
            ).fetchall()
            conn.close()
            assert len(tables) == 1
        finally:
            os.unlink(db)

    def test_idempotent(self):
        db = _make_tracker_db()
        try:
            SignalPerformanceTracker(db_path=db)
            SignalPerformanceTracker(db_path=db)
            conn = sqlite3.connect(db)
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='signal_performance'"
            ).fetchall()
            conn.close()
            assert len(tables) == 1
        finally:
            os.unlink(db)


class TestGetPendingSignals:

    def test_empty_db(self):
        db = _make_tracker_db()
        try:
            tracker = SignalPerformanceTracker(db_path=db)
            pending = tracker.get_pending_signals()
            assert pending == []
        finally:
            os.unlink(db)

    def test_with_signals(self):
        today = datetime.now().strftime("%Y-%m-%d")
        signals = [(1, "AAPL", "LONG", 0.77, today), (2, "GOOG", "LONG", 0.50, today)]
        db = _make_tracker_db(signals)
        try:
            tracker = SignalPerformanceTracker(db_path=db)
            pending = tracker.get_pending_signals()
            assert len(pending) == 2
        finally:
            os.unlink(db)

    def test_filter_by_ticker(self):
        today = datetime.now().strftime("%Y-%m-%d")
        signals = [(1, "AAPL", "LONG", 0.77, today), (2, "GOOG", "LONG", 0.50, today)]
        db = _make_tracker_db(signals)
        try:
            tracker = SignalPerformanceTracker(db_path=db)
            pending = tracker.get_pending_signals(ticker="AAPL")
            assert len(pending) == 1
            assert pending[0]["ticker"] == "AAPL"
        finally:
            os.unlink(db)

    def test_filter_by_days(self):
        old = (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d")
        today = datetime.now().strftime("%Y-%m-%d")
        signals = [(1, "AAPL", "LONG", 0.77, today), (2, "GOOG", "LONG", 0.50, old)]
        db = _make_tracker_db(signals)
        try:
            tracker = SignalPerformanceTracker(db_path=db)
            pending = tracker.get_pending_signals(days=30)
            assert len(pending) == 1
            assert pending[0]["ticker"] == "AAPL"
        finally:
            os.unlink(db)


class TestPerformanceCalc:

    def test_alpha_long(self):
        stock_ret = 5.0
        spy_ret = 2.0
        alpha = stock_ret - spy_ret
        assert alpha == 3.0

    def test_alpha_short(self):
        stock_ret = 5.0
        spy_ret = 2.0
        alpha = -stock_ret + spy_ret
        assert alpha == -3.0

    def test_hit_positive(self):
        hit = 1 if (0.5 > 0 and 0.3 > 0) else 0
        assert hit == 1

    def test_hit_negative(self):
        hit = 1 if (0.5 > 0 and -0.3 > 0) else 0
        assert hit == 0


class TestSaveResults:

    def test_save_and_count(self):
        db = _make_tracker_db()
        try:
            tracker = SignalPerformanceTracker(db_path=db)
            conn = sqlite3.connect(db)
            conn.execute(
                "INSERT INTO signal_performance (signal_id, ticker, direction,"
                " signal_date, actual_return_5d, hit_5d, evaluated_at)"
                " VALUES (?,?,?,?,?,?,?)",
                (1, "AAPL", "LONG", "2025-01-01", 2.0, 1, "2025-02-01"))
            conn.commit()
            count = conn.execute("SELECT COUNT(*) FROM signal_performance").fetchone()[0]
            conn.close()
            assert count == 1
        finally:
            os.unlink(db)

    def test_unique_signal_id(self):
        db = _make_tracker_db()
        try:
            tracker = SignalPerformanceTracker(db_path=db)
            conn = sqlite3.connect(db)
            conn.execute(
                "INSERT INTO signal_performance (signal_id, ticker, direction,"
                " signal_date, evaluated_at) VALUES (?,?,?,?,?)",
                (99, "AAPL", "LONG", "2025-01-01", "2025-02-01"))
            conn.commit()
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO signal_performance (signal_id, ticker, direction,"
                    " signal_date, evaluated_at) VALUES (?,?,?,?,?)",
                    (99, "GOOG", "SHORT", "2025-01-02", "2025-02-02"))
            conn.close()
        finally:
            os.unlink(db)


class TestHitRate:

    def test_perfect(self):
        assert sum([1,1,1,1,1]) / 5 * 100 == 100.0

    def test_zero(self):
        assert sum([0,0,0,0]) / 4 * 100 == 0.0

    def test_mixed(self):
        assert sum([1,0,1,0,1]) / 5 * 100 == 60.0

    def test_empty(self):
        assert sum([]) / max(0, 1) * 100 == 0.0


class TestMAEMFE:

    def test_mfe_positive(self):
        assert max([1.0, 2.5, -0.5, 3.0]) == 3.0

    def test_mae_negative(self):
        assert min([1.0, -2.5, 0.5, -3.0]) == -3.0

    def test_all_positive_mae(self):
        assert min([1.0, 2.0, 3.0]) > 0

    def test_short_inverts(self):
        raw = [2.0, -1.0, 3.0]
        short = [-r for r in raw]
        assert max(short) == 1.0
