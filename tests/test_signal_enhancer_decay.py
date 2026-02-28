"""
tests/test_signal_enhancer_decay.py -- Signal decay mechanism unit tests

Tests the filing-date-based linear decay in SignalEnhancer.enhance_signals():
  - No decay within first 20 days after filing
  - Linear decay from day 20 to day 40: strength * max(0, 1-(days-20)/20)
  - Zero strength at or beyond day 40
  - decay_factor key present in output dict
  - Decay reduces enhanced_strength vs fresh signal baseline
"""

import os
import sqlite3
import tempfile
from datetime import date, timedelta

import pytest

from src.signal_enhancer import SignalEnhancer


def _make_db(filing_date_str, signal_strength=1.0):
    f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = f.name
    f.close()
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE alpha_signals (
            id INTEGER PRIMARY KEY, trade_id TEXT UNIQUE, ticker TEXT,
            asset_name TEXT, politician_name TEXT, chamber TEXT,
            transaction_type TEXT, transaction_date TEXT, filing_date TEXT,
            amount_range TEXT, direction TEXT,
            expected_alpha_5d REAL, expected_alpha_20d REAL,
            confidence REAL, signal_strength REAL, has_convergence INTEGER,
            politician_grade TEXT, filing_lag_days INTEGER, sqs_score REAL,
            created_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE signal_quality_scores (
            id INTEGER PRIMARY KEY, trade_id TEXT, ticker TEXT,
            sqs REAL, grade TEXT, actionability REAL,
            timeliness REAL, conviction REAL,
            information_edge REAL, market_impact REAL
        )
    """)
    conn.execute(
        "INSERT INTO alpha_signals "
        "(trade_id, ticker, politician_name, chamber, transaction_type, "
        " filing_date, transaction_date, direction, "
        " expected_alpha_5d, expected_alpha_20d, confidence, signal_strength, "
        " has_convergence, filing_lag_days, sqs_score) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("trade-001", "AAPL", "Test Senator", "Senate", "Buy",
         filing_date_str, filing_date_str, "LONG",
         0.77, 1.10, 0.65, signal_strength, 0, 10, 60.0)
    )
    conn.commit()
    conn.close()
    return db_path


def _run(filing_date_str, signal_strength=1.0):
    db_path = _make_db(filing_date_str, signal_strength)
    try:
        enhancer = SignalEnhancer(db_path=db_path)
        enhancer.vix_detector.classify_regime = lambda: {
            "zone": "moderate", "vix": 18.0, "multiplier": 1.0, "label": "test"
        }
        results = enhancer.enhance_signals()
        assert len(results) == 1
        return results[0]
    finally:
        os.unlink(db_path)


class TestSignalDecay:
    """Tests for decay formula: max(0, 1 - (days_since_filing - 20) / 20)."""

    def test_no_decay_day0(self):
        """Day 0: decay_factor = 1.0 (within grace period)."""
        filing = date.today().strftime("%Y-%m-%d")
        assert _run(filing)["decay_factor"] == 1.0

    def test_no_decay_day10(self):
        """Day 10: still in grace period, decay_factor = 1.0."""
        filing = (date.today() - timedelta(days=10)).strftime("%Y-%m-%d")
        assert _run(filing)["decay_factor"] == 1.0

    def test_no_decay_at_boundary_day20(self):
        """Day 20 exactly: boundary, decay_factor = 1.0."""
        filing = (date.today() - timedelta(days=20)).strftime("%Y-%m-%d")
        assert _run(filing)["decay_factor"] == 1.0

    def test_half_decay_at_day30(self):
        """Day 30: 1 - (30-20)/20 = 0.5."""
        filing = (date.today() - timedelta(days=30)).strftime("%Y-%m-%d")
        sig = _run(filing)
        assert abs(sig["decay_factor"] - 0.5) < 0.01

    def test_zero_decay_at_day40(self):
        """Day 40: fully decayed, decay_factor = 0.0."""
        filing = (date.today() - timedelta(days=40)).strftime("%Y-%m-%d")
        assert _run(filing)["decay_factor"] == 0.0

    def test_decay_never_negative(self):
        """Day 60: clamped to 0.0, never negative."""
        filing = (date.today() - timedelta(days=60)).strftime("%Y-%m-%d")
        sig = _run(filing)
        assert sig["decay_factor"] >= 0.0
        assert sig["decay_factor"] == 0.0

    def test_decay_factor_key_present(self):
        """decay_factor must be a key in the enhanced signal output dict."""
        filing = date.today().strftime("%Y-%m-%d")
        assert "decay_factor" in _run(filing)

    def test_stale_weaker_than_fresh(self):
        """Stale (day 35) enhanced_strength < fresh (day 5) for same raw strength."""
        fresh = _run((date.today() - timedelta(days=5)).strftime("%Y-%m-%d"), 1.0)
        stale = _run((date.today() - timedelta(days=35)).strftime("%Y-%m-%d"), 1.0)
        assert stale["enhanced_strength"] < fresh["enhanced_strength"]

    def test_fully_decayed_enhanced_strength_zero(self):
        """Day 40+: enhanced_strength should be 0."""
        filing = (date.today() - timedelta(days=40)).strftime("%Y-%m-%d")
        assert _run(filing, signal_strength=1.0)["enhanced_strength"] == 0.0

    def test_decay_does_not_alter_original_strength(self):
        """Decay must only affect enhanced_strength, not original_strength."""
        filing = (date.today() - timedelta(days=40)).strftime("%Y-%m-%d")
        sig = _run(filing, signal_strength=1.2)
        assert sig["original_strength"] == 1.2

    def test_null_filing_date_no_crash(self):
        """NULL filing_date: no exception, decay_factor defaults to 1.0."""
        db_path = _make_db("2025-01-10")
        try:
            conn = sqlite3.connect(db_path)
            conn.execute("UPDATE alpha_signals SET filing_date = NULL WHERE trade_id = 'trade-001'")
            conn.commit()
            conn.close()
            enhancer = SignalEnhancer(db_path=db_path)
            enhancer.vix_detector.classify_regime = lambda: {
                "zone": "moderate", "vix": 18.0, "multiplier": 1.0, "label": "test"
            }
            results = enhancer.enhance_signals()
            if results:
                assert results[0]["decay_factor"] == 1.0
        finally:
            os.unlink(db_path)
