import os
import sqlite3
import tempfile
from datetime import date, timedelta

import pytest

from src.signal_enhancer import SignalEnhancer, VIXRegimeDetector


def _make_db(trades=None, sqs=None):
    f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = f.name
    f.close()
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE alpha_signals (id INTEGER PRIMARY KEY, trade_id TEXT UNIQUE,"
        " ticker TEXT, asset_name TEXT, politician_name TEXT, chamber TEXT,"
        " transaction_type TEXT, transaction_date TEXT, filing_date TEXT,"
        " amount_range TEXT, direction TEXT,"
        " expected_alpha_5d REAL, expected_alpha_20d REAL,"
        " confidence REAL, signal_strength REAL, has_convergence INTEGER,"
        " politician_grade TEXT, filing_lag_days INTEGER, sqs_score REAL,"
        " created_at TEXT)"
    )
    conn.execute(
        "CREATE TABLE signal_quality_scores (id INTEGER PRIMARY KEY,"
        " trade_id TEXT, ticker TEXT, sqs REAL, grade TEXT,"
        " actionability REAL, timeliness REAL, conviction REAL,"
        " information_edge REAL, market_impact REAL)"
    )
    conn.execute(
        "CREATE TABLE enhanced_signals (trade_id TEXT PRIMARY KEY,"
        " ticker TEXT, politician_name TEXT, chamber TEXT,"
        " transaction_type TEXT, direction TEXT,"
        " original_strength REAL, original_confidence REAL,"
        " pacs_score REAL, confidence_v2 REAL, enhanced_strength REAL,"
        " vix_zone TEXT, vix_multiplier REAL,"
        " pacs_signal_component REAL, pacs_lag_component REAL,"
        " pacs_options_component REAL, pacs_convergence_component REAL,"
        " pacs_contract_component REAL DEFAULT 0,"
        " options_sentiment TEXT, options_signal_type TEXT,"
        " social_alignment TEXT, social_bonus REAL,"
        " has_convergence INTEGER, politician_grade TEXT,"
        " filing_lag_days INTEGER, sqs_score REAL,"
        " insider_confirmed INTEGER DEFAULT 0,"
        " decay_factor REAL DEFAULT 1.0, updated_at TEXT)"
    )
    conn.execute(
        "CREATE TABLE sec_form4_trades (id INTEGER PRIMARY KEY,"
        " accession_number TEXT, filer_name TEXT, filer_title TEXT,"
        " issuer_name TEXT, ticker TEXT, transaction_type TEXT,"
        " transaction_date TEXT, shares REAL, price_per_share REAL,"
        " total_value REAL, ownership_type TEXT, source_url TEXT,"
        " data_hash TEXT UNIQUE, created_at TEXT)"
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
    if trades is None:
        today = date.today().strftime("%Y-%m-%d")
        trades = [(
            "t-001", "AAPL", "Test Senator", "Senate", "Buy",
            today, today, "LONG",
            0.77, 1.10, 0.65, 1.0, 0, "A", 10, 60.0
        )]
    for t in trades:
        conn.execute(
            "INSERT INTO alpha_signals (trade_id, ticker, politician_name,"
            " chamber, transaction_type, filing_date, transaction_date,"
            " direction, expected_alpha_5d, expected_alpha_20d,"
            " confidence, signal_strength, has_convergence,"
            " politician_grade, filing_lag_days, sqs_score)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", t
        )
    if sqs:
        for s in sqs:
            conn.execute(
                "INSERT INTO signal_quality_scores (trade_id, ticker,"
                " sqs, grade, actionability, timeliness,"
                " conviction, information_edge, market_impact)"
                " VALUES (?,?,?,?,?,?,?,?,?)", s
            )
    conn.commit()
    conn.close()
    return db_path


def _enhancer(db_path, zone="moderate", vix=18.0, mult=1.0):
    e = SignalEnhancer(db_path=db_path)
    e.vix_detector.classify_regime = lambda: {
        "zone": zone, "vix": vix, "multiplier": mult, "label": "test"
    }
    return e


class TestVIXZones:

    def test_ultra_low(self):
        db = _make_db()
        try:
            r = _enhancer(db, "ultra_low", 12.0, 0.6).enhance_signals()
            assert r[0]["vix_zone"] == "ultra_low"
            assert r[0]["vix_multiplier"] == 0.6
        finally:
            os.unlink(db)

    def test_goldilocks(self):
        db = _make_db()
        try:
            r = _enhancer(db, "goldilocks", 15.0, 1.3).enhance_signals()
            assert r[0]["vix_zone"] == "goldilocks"
            assert r[0]["vix_multiplier"] == 1.3
        finally:
            os.unlink(db)

    def test_moderate(self):
        db = _make_db()
        try:
            r = _enhancer(db, "moderate", 18.0, 0.8).enhance_signals()
            assert r[0]["vix_zone"] == "moderate"
            assert r[0]["vix_multiplier"] == 0.8
        finally:
            os.unlink(db)

    def test_high(self):
        db = _make_db()
        try:
            r = _enhancer(db, "high", 25.0, 0.5).enhance_signals()
            assert r[0]["vix_zone"] == "high"
            assert r[0]["vix_multiplier"] == 0.5
        finally:
            os.unlink(db)

    def test_extreme(self):
        db = _make_db()
        try:
            r = _enhancer(db, "extreme", 35.0, 0.3).enhance_signals()
            assert r[0]["vix_zone"] == "extreme"
            assert r[0]["vix_multiplier"] == 0.3
        finally:
            os.unlink(db)

    def test_goldilocks_beats_extreme(self):
        db = _make_db()
        try:
            r1 = _enhancer(db, "goldilocks", 15.0, 1.3).enhance_signals()
            r2 = _enhancer(db, "extreme", 35.0, 0.3).enhance_signals()
            assert r1[0]["enhanced_strength"] > r2[0]["enhanced_strength"]
        finally:
            os.unlink(db)

    def test_goldilocks_beats_ultra_low(self):
        db = _make_db()
        try:
            r1 = _enhancer(db, "goldilocks", 15.0, 1.3).enhance_signals()
            r2 = _enhancer(db, "ultra_low", 12.0, 0.6).enhance_signals()
            assert r1[0]["enhanced_strength"] > r2[0]["enhanced_strength"]
        finally:
            os.unlink(db)

    def test_vix_keys_present(self):
        db = _make_db()
        try:
            r = _enhancer(db).enhance_signals()
            assert "vix_zone" in r[0]
            assert "vix_multiplier" in r[0]
        finally:
            os.unlink(db)


class TestPACSScore:

    def test_pacs_range(self):
        db = _make_db()
        try:
            r = _enhancer(db).enhance_signals()
            assert 0.0 <= r[0]["pacs_score"] <= 1.5
        finally:
            os.unlink(db)

    def test_pacs_components(self):
        db = _make_db()
        try:
            r = _enhancer(db).enhance_signals()
            for k in ["pacs_signal_component", "pacs_lag_component", "pacs_convergence_component"]:
                assert k in r[0]
        finally:
            os.unlink(db)

    def test_higher_strength_higher_pacs(self):
        today = date.today().strftime("%Y-%m-%d")
        th = [("t-h", "AAPL", "A", "Senate", "Buy", today, today, "LONG", 0.77, 1.10, 0.65, 1.0, 0, "A", 10, 60.0)]
        tl = [("t-l", "AAPL", "A", "Senate", "Buy", today, today, "LONG", 0.77, 1.10, 0.65, 0.3, 0, "A", 10, 60.0)]
        dh, dl = _make_db(th), _make_db(tl)
        try:
            rh = _enhancer(dh).enhance_signals()
            rl = _enhancer(dl).enhance_signals()
            assert rh[0]["pacs_score"] > rl[0]["pacs_score"]
        finally:
            os.unlink(dh)
            os.unlink(dl)

    def test_low_lag_better_pacs(self):
        today = date.today().strftime("%Y-%m-%d")
        tf = [("t-f", "AAPL", "A", "Senate", "Buy", today, today, "LONG", 0.77, 1.10, 0.65, 0.8, 0, "A", 3, 60.0)]
        ts = [("t-s", "AAPL", "A", "Senate", "Buy", today, today, "LONG", 0.77, 1.10, 0.65, 0.8, 0, "A", 40, 60.0)]
        df, ds = _make_db(tf), _make_db(ts)
        try:
            rf = _enhancer(df).enhance_signals()
            rs = _enhancer(ds).enhance_signals()
            assert rf[0]["pacs_lag_component"] > rs[0]["pacs_lag_component"]
        finally:
            os.unlink(df)
            os.unlink(ds)

    def test_convergence_boosts_pacs(self):
        today = date.today().strftime("%Y-%m-%d")
        tc = [("t-c", "AAPL", "A", "Senate", "Buy", today, today, "LONG", 0.77, 1.10, 0.65, 0.8, 1, "A", 10, 60.0)]
        tn = [("t-n", "AAPL", "A", "Senate", "Buy", today, today, "LONG", 0.77, 1.10, 0.65, 0.8, 0, "A", 10, 60.0)]
        dc, dn = _make_db(tc), _make_db(tn)
        try:
            rc = _enhancer(dc).enhance_signals()
            rn = _enhancer(dn).enhance_signals()
            assert rc[0]["pacs_convergence_component"] >= rn[0]["pacs_convergence_component"]
        finally:
            os.unlink(dc)
            os.unlink(dn)

    def test_signal_component_dominant(self):
        db = _make_db()
        try:
            r = _enhancer(db).enhance_signals()
            # signal component = strength_norm (0.6667), lag = 0.8 for lag=10
            # Signal weight is 50% vs lag 25%, so weighted signal > weighted lag
            assert r[0]["pacs_signal_component"] * 0.50 >= r[0]["pacs_lag_component"] * 0.25
        finally:
            os.unlink(db)


class TestConfidenceV2:

    def test_range(self):
        db = _make_db()
        try:
            r = _enhancer(db).enhance_signals()
            assert 0.0 <= r[0]["confidence_v2"] <= 1.0
        finally:
            os.unlink(db)

    def test_key_present(self):
        db = _make_db()
        try:
            r = _enhancer(db).enhance_signals()
            assert "confidence_v2" in r[0]
        finally:
            os.unlink(db)


class TestBuyOnlyFilter:

    def test_excludes_sale(self):
        today = date.today().strftime("%Y-%m-%d")
        trades = [
            ("t-buy", "AAPL", "A", "Senate", "Buy", today, today, "LONG", 0.77, 1.10, 0.65, 1.0, 0, "A", 10, 60.0),
            ("t-sale", "MSFT", "B", "Senate", "Sale", today, today, "SHORT", 0.77, 1.10, 0.65, 1.0, 0, "A", 10, 60.0),
        ]
        db = _make_db(trades)
        try:
            r = _enhancer(db).enhance_signals(buy_only=True)
            tickers = [s["ticker"] for s in r]
            assert "AAPL" in tickers
            assert "MSFT" not in tickers
        finally:
            os.unlink(db)

    def test_includes_purchase(self):
        today = date.today().strftime("%Y-%m-%d")
        trades = [("t-pur", "GOOG", "A", "Senate", "Purchase", today, today, "LONG", 0.77, 1.10, 0.65, 1.0, 0, "A", 10, 60.0)]
        db = _make_db(trades)
        try:
            r = _enhancer(db).enhance_signals(buy_only=True)
            assert len(r) == 1
        finally:
            os.unlink(db)

    def test_no_filter_all(self):
        today = date.today().strftime("%Y-%m-%d")
        trades = [
            ("t-b2", "AAPL", "A", "Senate", "Buy", today, today, "LONG", 0.77, 1.10, 0.65, 1.0, 0, "A", 10, 60.0),
            ("t-s2", "MSFT", "B", "Senate", "Sale", today, today, "SHORT", 0.77, 1.10, 0.65, 1.0, 0, "A", 10, 60.0),
        ]
        db = _make_db(trades)
        try:
            r = _enhancer(db).enhance_signals(buy_only=False)
            assert len(r) == 2
        finally:
            os.unlink(db)


class TestSocialBonus:

    def test_no_social_zero(self):
        db = _make_db()
        try:
            r = _enhancer(db).enhance_signals()
            assert r[0]["social_bonus"] == 0.0
        finally:
            os.unlink(db)


class TestInsiderConfirmed:

    def test_insider_match(self):
        today = date.today().strftime("%Y-%m-%d")
        trades = [("t-ins", "AAPL", "Test Senator", "Senate", "Buy",
                    today, today, "LONG", 0.77, 1.10, 0.65, 0.8, 0, "A", 10, 60.0)]
        db = _make_db(trades)
        conn = sqlite3.connect(db)
        conn.execute(
            "INSERT INTO congress_trades (chamber, politician_name,"
            " transaction_date, filing_date, ticker, transaction_type, data_hash)"
            " VALUES (?,?,?,?,?,?,?)",
            ("Senate", "Test Senator", today, today, "AAPL", "Buy", "h1"))
        conn.execute(
            "INSERT INTO sec_form4_trades (filer_name, ticker,"
            " transaction_type, transaction_date, shares, price_per_share,"
            " total_value, data_hash, created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            ("Insider", "AAPL", "Purchase", today, 1000, 150, 150000, "sh1", today))
        conn.commit()
        conn.close()
        try:
            e = _enhancer(db)
            r = e.enhance_signals()
            e.save_enhanced(r)
            conn = sqlite3.connect(db)
            row = conn.execute("SELECT insider_confirmed FROM enhanced_signals WHERE trade_id=?", ("t-ins",)).fetchone()
            conn.close()
            assert row is not None
            assert row[0] == 1
        finally:
            os.unlink(db)

    def test_no_insider(self):
        db = _make_db()
        try:
            e = _enhancer(db)
            r = e.enhance_signals()
            e.save_enhanced(r)
            conn = sqlite3.connect(db)
            row = conn.execute("SELECT insider_confirmed FROM enhanced_signals WHERE trade_id=?", ("t-001",)).fetchone()
            conn.close()
            assert row is not None
            assert row[0] == 0
        finally:
            os.unlink(db)


class TestCompareV1V2:

    def test_returns_dict(self):
        db = _make_db()
        try:
            e = _enhancer(db)
            r = e.enhance_signals()
            comp = e.compare_v1_v2(r)
            assert isinstance(comp, dict)
        finally:
            os.unlink(db)

    def test_has_keys(self):
        db = _make_db()
        try:
            e = _enhancer(db)
            r = e.enhance_signals()
            comp = e.compare_v1_v2(r)
            assert "total_signals" in comp
        finally:
            os.unlink(db)

    def test_empty(self):
        db = _make_db(trades=[])
        try:
            e = _enhancer(db)
            r = e.enhance_signals()
            comp = e.compare_v1_v2(r)
            assert comp == {}
        finally:
            os.unlink(db)


class TestEnhancedStrength:

    def test_non_negative(self):
        db = _make_db()
        try:
            r = _enhancer(db).enhance_signals()
            assert r[0]["enhanced_strength"] >= 0.0
        finally:
            os.unlink(db)

    def test_original_preserved(self):
        db = _make_db()
        try:
            r = _enhancer(db).enhance_signals()
            assert r[0]["original_strength"] == 1.0
        finally:
            os.unlink(db)

    def test_save_creates_rows(self):
        db = _make_db()
        try:
            e = _enhancer(db)
            r = e.enhance_signals()
            e.save_enhanced(r)
            conn = sqlite3.connect(db)
            count = conn.execute("SELECT COUNT(*) FROM enhanced_signals").fetchone()[0]
            conn.close()
            assert count == 1
        finally:
            os.unlink(db)

    def test_empty_db(self):
        db = _make_db(trades=[])
        try:
            r = _enhancer(db).enhance_signals()
            assert r == []
        finally:
            os.unlink(db)


class TestMultipleSignals:

    def test_all_enhanced(self):
        today = date.today().strftime("%Y-%m-%d")
        trades = [
            ("t-m1", "AAPL", "A", "Senate", "Buy", today, today, "LONG", 0.77, 1.10, 0.65, 0.9, 0, "A", 10, 60.0),
            ("t-m2", "GOOG", "B", "House", "Buy", today, today, "LONG", 0.50, 0.80, 0.55, 0.6, 0, "B", 20, 45.0),
        ]
        db = _make_db(trades)
        try:
            r = _enhancer(db).enhance_signals()
            assert len(r) == 2
        finally:
            os.unlink(db)

    def test_sorted(self):
        today = date.today().strftime("%Y-%m-%d")
        trades = [
            ("t-r1", "AAPL", "A", "Senate", "Buy", today, today, "LONG", 0.77, 1.10, 0.65, 1.0, 1, "A", 5, 80.0),
            ("t-r2", "GOOG", "B", "House", "Buy", today, today, "LONG", 0.30, 0.50, 0.40, 0.3, 0, "C", 35, 30.0),
        ]
        db = _make_db(trades)
        try:
            r = _enhancer(db).enhance_signals()
            assert r[0]["enhanced_strength"] >= r[1]["enhanced_strength"]
        finally:
            os.unlink(db)

    def test_save_multiple(self):
        today = date.today().strftime("%Y-%m-%d")
        trades = [
            ("t-sm1", "AAPL", "A", "Senate", "Buy", today, today, "LONG", 0.77, 1.10, 0.65, 0.9, 0, "A", 10, 60.0),
            ("t-sm2", "GOOG", "B", "House", "Buy", today, today, "LONG", 0.50, 0.80, 0.55, 0.6, 0, "B", 20, 45.0),
        ]
        db = _make_db(trades)
        try:
            e = _enhancer(db)
            r = e.enhance_signals()
            result = e.save_enhanced(r)
            assert result["inserted"] == 2
        finally:
            os.unlink(db)
