"""
tests/test_rb009_integration.py -- RB-009 USASpending contract integration tests

Tests:
- contractor_tickers.json format validation
- ConvergenceDetector contract proximity scoring
- SignalEnhancer contract_award_bonus in PACS
"""

import json
import sqlite3
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

CONTRACTOR_TICKERS_PATH = PROJECT_ROOT / "data" / "contractor_tickers.json"


# ─────────────────────────────────────────
# contractor_tickers.json validation
# ─────────────────────────────────────────

class TestContractorTickersJSON:

    @pytest.fixture(scope="class")
    def tickers_data(self):
        with open(CONTRACTOR_TICKERS_PATH, encoding="utf-8") as f:
            return json.load(f)

    def test_json_has_meta_and_tickers_keys(self, tickers_data):
        """JSON root has _meta and tickers keys."""
        assert "_meta" in tickers_data
        assert "tickers" in tickers_data

    def test_ticker_count_at_least_80(self, tickers_data):
        """At least 80 ticker mappings."""
        assert len(tickers_data["tickers"]) >= 80

    def test_all_entries_have_required_fields(self, tickers_data):
        """Every ticker entry has company, search_terms, sector."""
        for ticker, info in tickers_data["tickers"].items():
            assert "company" in info, f"{ticker}: missing company"
            assert "search_terms" in info, f"{ticker}: missing search_terms"
            assert "sector" in info, f"{ticker}: missing sector"

    def test_search_terms_is_nonempty_list(self, tickers_data):
        """search_terms should be a non-empty list for every entry."""
        for ticker, info in tickers_data["tickers"].items():
            assert isinstance(info["search_terms"], list), f"{ticker}: search_terms not a list"
            assert len(info["search_terms"]) >= 1, f"{ticker}: search_terms is empty"

    def test_required_defense_tickers_present(self, tickers_data):
        """Key defense contractors are mapped."""
        tickers = tickers_data["tickers"]
        required = ["LMT", "RTX", "NOC", "GD", "BA", "HII", "LHX"]
        for t in required:
            assert t in tickers, f"Missing defense contractor: {t}"

    def test_required_tech_tickers_present(self, tickers_data):
        """Key tech government contractors are mapped."""
        tickers = tickers_data["tickers"]
        required = ["CRM", "GOOGL", "IBM", "CSCO", "PANW", "PLTR"]
        for t in required:
            assert t in tickers, f"Missing tech contractor: {t}"

    def test_required_healthcare_tickers_present(self, tickers_data):
        """Key healthcare contractors are mapped."""
        tickers = tickers_data["tickers"]
        required = ["UNH", "HUM", "CI", "CVS", "MCK"]
        for t in required:
            assert t in tickers, f"Missing healthcare contractor: {t}"

    def test_required_energy_tickers_present(self, tickers_data):
        """Key energy contractors are mapped."""
        tickers = tickers_data["tickers"]
        required = ["HAL", "SLB", "BKR"]
        for t in required:
            assert t in tickers, f"Missing energy contractor: {t}"


# ─────────────────────────────────────────
# Helper: create test DB with contract tables
# ─────────────────────────────────────────

def make_contract_db(tmp_path, contracts=None, cross_refs=None, trades=None):
    """Create a test DB with government_contracts, contract_cross_refs, and congress_trades."""
    db = tmp_path / "test_rb009.db"
    conn = sqlite3.connect(str(db))
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE government_contracts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            award_id TEXT NOT NULL,
            recipient_name TEXT NOT NULL,
            ticker TEXT,
            award_amount REAL,
            start_date TEXT,
            end_date TEXT,
            awarding_agency TEXT,
            naics_code TEXT,
            data_hash TEXT UNIQUE,
            fetched_at TEXT DEFAULT (datetime('now'))
        )
    """)

    cur.execute("""
        CREATE TABLE contract_cross_refs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_id TEXT NOT NULL,
            ticker TEXT NOT NULL,
            politician_name TEXT,
            transaction_type TEXT,
            transaction_date TEXT,
            award_id TEXT,
            award_amount REAL,
            awarding_agency TEXT,
            contract_start_date TEXT,
            days_before_trade INTEGER,
            signal_type TEXT,
            convergence_score REAL,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)

    cur.execute("""
        CREATE TABLE congress_trades (
            id TEXT PRIMARY KEY,
            chamber TEXT,
            politician_name TEXT,
            transaction_date TEXT,
            filing_date TEXT,
            ticker TEXT,
            asset_name TEXT,
            asset_type TEXT,
            transaction_type TEXT,
            amount_range TEXT,
            owner TEXT,
            comment TEXT,
            source_url TEXT,
            source_format TEXT,
            extraction_confidence REAL,
            data_hash TEXT UNIQUE,
            created_at TEXT
        )
    """)

    if contracts:
        for c in contracts:
            cur.execute("""
                INSERT INTO government_contracts
                (award_id, recipient_name, ticker, award_amount, start_date, end_date,
                 awarding_agency, data_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                c.get("award_id", "AW-001"),
                c.get("recipient_name", "Test Corp"),
                c.get("ticker", "AAPL"),
                c.get("award_amount", 1000000),
                c.get("start_date", "2025-01-15"),
                c.get("end_date", "2026-01-15"),
                c.get("awarding_agency", "Department of Defense"),
                c.get("data_hash", f"hash-{c.get('award_id', 'x')}"),
            ))

    if cross_refs:
        for cr in cross_refs:
            cur.execute("""
                INSERT INTO contract_cross_refs
                (trade_id, ticker, politician_name, transaction_type, transaction_date,
                 award_id, award_amount, awarding_agency, contract_start_date,
                 days_before_trade, signal_type, convergence_score)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                cr.get("trade_id", "t-001"),
                cr.get("ticker", "AAPL"),
                cr.get("politician_name", "Alice Smith"),
                cr.get("transaction_type", "Buy"),
                cr.get("transaction_date", "2025-01-20"),
                cr.get("award_id", "AW-001"),
                cr.get("award_amount", 1000000),
                cr.get("awarding_agency", "Department of Defense"),
                cr.get("contract_start_date", "2025-01-15"),
                cr.get("days_before_trade", 5),
                cr.get("signal_type", "PRE_CONTRACT_BUY"),
                cr.get("convergence_score", 0.7),
            ))

    if trades:
        for i, t in enumerate(trades):
            cur.execute("""
                INSERT INTO congress_trades
                (id, chamber, politician_name, transaction_date, filing_date,
                 ticker, asset_name, transaction_type, amount_range, data_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                t.get("id", f"trade-{i}"),
                t.get("chamber", "Senate"),
                t.get("politician_name", f"Politician {i}"),
                t.get("transaction_date", "2025-01-10"),
                t.get("filing_date", "2025-01-20"),
                t.get("ticker", "AAPL"),
                t.get("asset_name", "Apple Inc."),
                t.get("transaction_type", "Buy"),
                t.get("amount_range", "$15,001 - $50,000"),
                t.get("data_hash", f"hash-{i}"),
            ))

    conn.commit()
    conn.close()
    return str(db)


# ─────────────────────────────────────────
# ConvergenceDetector contract proximity tests
# ─────────────────────────────────────────

class TestContractProximity:

    def test_no_contract_table_returns_zero(self, tmp_path):
        """When contract_cross_refs table doesn't exist, returns 0.0."""
        from src.convergence_detector import ConvergenceDetector

        db = tmp_path / "empty.db"
        conn = sqlite3.connect(str(db))
        conn.execute("CREATE TABLE dummy (id INTEGER)")
        conn.close()

        detector = ConvergenceDetector(db_path=str(db))
        score = detector._get_contract_proximity("AAPL", "2025-01-10")
        assert score == 0.0

    def test_no_matching_contracts_returns_zero(self, tmp_path):
        """When no contracts match the ticker, returns 0.0."""
        from src.convergence_detector import ConvergenceDetector

        db = make_contract_db(tmp_path, cross_refs=[
            {"ticker": "MSFT", "days_before_trade": 10, "award_amount": 5000000,
             "awarding_agency": "Department of Defense", "signal_type": "PRE_CONTRACT_BUY"},
        ])
        detector = ConvergenceDetector(db_path=db)
        score = detector._get_contract_proximity("AAPL", "2025-01-10")
        assert score == 0.0

    def test_buy_dod_large_contract_high_score(self, tmp_path):
        """BUY + DoD + $100M+ + close time = high proximity score."""
        from src.convergence_detector import ConvergenceDetector

        db = make_contract_db(tmp_path, cross_refs=[
            {"ticker": "AVAV", "days_before_trade": 5,
             "award_amount": 150_000_000,
             "awarding_agency": "Department of Defense",
             "signal_type": "PRE_CONTRACT_BUY"},
        ])
        detector = ConvergenceDetector(db_path=db)
        score = detector._get_contract_proximity("AVAV", "2025-01-15")
        # BUY=0.3 + $100M+=0.3 + DoD=0.1 + time(5/90)=0.3*(1-5/90)~0.28 = ~0.98
        assert score > 0.9

    def test_sell_small_contract_low_score(self, tmp_path):
        """SELL signal + small contract + far time = low proximity score."""
        from src.convergence_detector import ConvergenceDetector

        db = make_contract_db(tmp_path, cross_refs=[
            {"ticker": "AAPL", "days_before_trade": 80,
             "award_amount": 500_000,
             "awarding_agency": "Department of Energy",
             "signal_type": "CONTRACT_SELL"},
        ])
        detector = ConvergenceDetector(db_path=db)
        score = detector._get_contract_proximity("AAPL", "2025-01-10")
        # No BUY=0 + small=0.1 + no DoD=0 + time(80/90)=0.3*(1-80/90)~0.03 = ~0.13
        assert score < 0.2

    def test_contract_proximity_integrated_in_calc_score(self, tmp_path):
        """contract_proximity > 0 increases total score via score_contract."""
        from src.convergence_detector import ConvergenceDetector

        detector = ConvergenceDetector(db_path=":memory:")
        trades = [{"amount_range": "$15,001 - $50,000", "chamber": "Senate"} for _ in range(2)]

        score_no_contract, bd_no = detector._calc_score(
            politician_count=2, chambers=["Senate"], span_days=10, trades=trades,
            contract_proximity=0.0,
        )
        score_with_contract, bd_with = detector._calc_score(
            politician_count=2, chambers=["Senate"], span_days=10, trades=trades,
            contract_proximity=0.8,
        )
        assert score_with_contract > score_no_contract
        assert bd_with["score_contract"] > 0
        assert bd_no["score_contract"] == 0

    def test_calc_score_backward_compatible(self):
        """_calc_score works without contract_proximity argument."""
        from src.convergence_detector import ConvergenceDetector

        detector = ConvergenceDetector(db_path=":memory:")
        trades = [{"amount_range": "$15,001 - $50,000", "chamber": "Senate"} for _ in range(2)]
        score, breakdown = detector._calc_score(
            politician_count=2, chambers=["Senate"], span_days=10, trades=trades,
        )
        assert "score_contract" in breakdown
        assert breakdown["score_contract"] == 0


# ─────────────────────────────────────────
# SignalEnhancer contract_award_bonus tests
# ─────────────────────────────────────────

class TestSignalEnhancerContractBonus:

    def test_pacs_no_contract_data(self):
        """Without contract data, contract_bonus is 0."""
        from src.signal_enhancer import SignalEnhancer

        enhancer = SignalEnhancer(db_path=":memory:")
        signal = {"signal_strength": 1.0, "filing_lag_days": 10}
        pacs, components = enhancer._calc_pacs_score(signal, None, None, None)
        assert components["contract_bonus"] == 0.0

    def test_pacs_small_contract_bonus_01(self):
        """Contract < $100M gives +0.1 bonus."""
        from src.signal_enhancer import SignalEnhancer

        enhancer = SignalEnhancer(db_path=":memory:")
        signal = {"signal_strength": 1.0, "filing_lag_days": 10}
        contract = {"max_amount": 50_000_000, "contract_count": 3}
        pacs, components = enhancer._calc_pacs_score(signal, None, None, contract)
        assert components["contract_bonus"] == pytest.approx(0.1, abs=1e-4)

    def test_pacs_large_contract_bonus_02(self):
        """Contract >= $100M gives +0.2 bonus."""
        from src.signal_enhancer import SignalEnhancer

        enhancer = SignalEnhancer(db_path=":memory:")
        signal = {"signal_strength": 1.0, "filing_lag_days": 10}
        contract = {"max_amount": 200_000_000, "contract_count": 1}
        pacs, components = enhancer._calc_pacs_score(signal, None, None, contract)
        assert components["contract_bonus"] == pytest.approx(0.2, abs=1e-4)

    def test_pacs_contract_increases_total(self):
        """Contract bonus increases total PACS score."""
        from src.signal_enhancer import SignalEnhancer

        enhancer = SignalEnhancer(db_path=":memory:")
        signal = {"signal_strength": 1.0, "filing_lag_days": 10}

        pacs_no, _ = enhancer._calc_pacs_score(signal, None, None, None)
        pacs_with, _ = enhancer._calc_pacs_score(
            signal, None, None, {"max_amount": 100_000_000, "contract_count": 1}
        )
        assert pacs_with > pacs_no

    def test_load_contract_data_no_table(self, tmp_path):
        """When government_contracts table doesn't exist, returns empty dict."""
        from src.signal_enhancer import SignalEnhancer

        db = tmp_path / "no_contracts.db"
        conn = sqlite3.connect(str(db))
        conn.execute("CREATE TABLE dummy (id INTEGER)")
        conn.close()

        enhancer = SignalEnhancer(db_path=str(db))
        result = enhancer._load_contract_data()
        assert result == {}

    def test_load_contract_data_with_data(self, tmp_path):
        """Loads contract data grouped by ticker."""
        from src.signal_enhancer import SignalEnhancer

        db = make_contract_db(tmp_path, contracts=[
            {"award_id": "AW-1", "ticker": "AVAV", "award_amount": 50_000_000,
             "data_hash": "h1"},
            {"award_id": "AW-2", "ticker": "AVAV", "award_amount": 150_000_000,
             "data_hash": "h2"},
            {"award_id": "AW-3", "ticker": "MSFT", "award_amount": 10_000_000,
             "data_hash": "h3"},
        ])
        enhancer = SignalEnhancer(db_path=db)
        result = enhancer._load_contract_data()
        assert "AVAV" in result
        assert "MSFT" in result
        assert result["AVAV"]["max_amount"] == 150_000_000
        assert result["AVAV"]["contract_count"] == 2
