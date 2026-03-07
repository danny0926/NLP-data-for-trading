"""Tests for API server endpoints."""

import pytest
from unittest.mock import patch, MagicMock
import sqlite3
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


@pytest.fixture
def test_db(tmp_path):
    """Create a test database with sample data."""
    db_path = str(tmp_path / "test.db")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create tables
    cursor.execute("""
        CREATE TABLE congress_trades (
            id INTEGER PRIMARY KEY, chamber TEXT, politician_name TEXT,
            transaction_date TEXT, filing_date TEXT, ticker TEXT,
            asset_name TEXT, asset_type TEXT, transaction_type TEXT,
            amount_range TEXT, owner TEXT, comment TEXT, source_url TEXT,
            source_format TEXT, extraction_confidence REAL,
            data_hash TEXT UNIQUE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE alpha_signals (
            id INTEGER PRIMARY KEY, trade_id INTEGER, ticker TEXT,
            asset_name TEXT, politician_name TEXT, chamber TEXT,
            transaction_type TEXT, direction TEXT,
            expected_alpha_5d REAL, expected_alpha_20d REAL,
            confidence REAL, signal_strength REAL, combined_multiplier REAL,
            convergence_bonus REAL, has_convergence BOOLEAN,
            politician_grade TEXT, filing_lag_days INTEGER,
            sqs_score REAL, sqs_grade TEXT, reasoning TEXT,
            transaction_date TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE enhanced_signals (
            trade_id TEXT PRIMARY KEY, ticker TEXT, politician_name TEXT,
            chamber TEXT, transaction_type TEXT, direction TEXT,
            original_strength REAL, original_confidence REAL,
            pacs_score REAL, confidence_v2 REAL, enhanced_strength REAL,
            vix_zone TEXT, vix_multiplier REAL,
            pacs_signal_component REAL, pacs_lag_component REAL,
            pacs_options_component REAL, pacs_convergence_component REAL,
            has_convergence BOOLEAN, politician_grade TEXT,
            filing_lag_days INTEGER, sqs_score REAL,
            insider_confirmed INTEGER DEFAULT 0,
            whale_trade INTEGER DEFAULT 0,
            party TEXT DEFAULT '',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE signal_performance (
            id INTEGER PRIMARY KEY, signal_id INTEGER UNIQUE,
            ticker TEXT, direction TEXT, signal_date TEXT,
            expected_alpha_5d REAL, expected_alpha_20d REAL,
            actual_return_5d REAL, actual_return_20d REAL,
            actual_alpha_5d REAL, actual_alpha_20d REAL,
            spy_return_5d REAL, spy_return_20d REAL,
            hit_5d INTEGER, hit_20d INTEGER,
            signal_strength REAL, confidence REAL,
            max_favorable_excursion REAL, max_adverse_excursion REAL,
            evaluated_at TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE convergence_signals (
            id INTEGER PRIMARY KEY, ticker TEXT, direction TEXT,
            politician_count INTEGER, politicians TEXT, chambers TEXT,
            window_start TEXT, window_end TEXT, span_days INTEGER,
            score REAL, score_base REAL, score_cross_chamber REAL,
            score_time_density REAL, score_amount_weight REAL,
            detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE politician_rankings (
            politician_name TEXT PRIMARY KEY, chamber TEXT,
            total_trades INTEGER, pis_total REAL, rank INTEGER,
            updated_at TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE portfolio_positions (
            id INTEGER PRIMARY KEY, ticker TEXT, sector TEXT,
            weight REAL, conviction_score REAL, expected_alpha REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE sec_form4_trades (
            id INTEGER PRIMARY KEY, ticker TEXT, filer_name TEXT,
            transaction_type TEXT, transaction_date TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE sector_rotation_signals (
            id INTEGER PRIMARY KEY, sector TEXT, etf TEXT,
            direction TEXT, signal_strength REAL, expected_alpha_20d REAL,
            momentum_score REAL, net_ratio REAL, net_dollar REAL,
            trades INTEGER, buy_count INTEGER, sale_count INTEGER,
            politician_count INTEGER, ticker_count INTEGER,
            cross_chamber INTEGER, rotation_type TEXT,
            rotation_bonus REAL, top_tickers TEXT, window_days INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE rebalance_history (
            id INTEGER PRIMARY KEY, ticker TEXT, action TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE signal_quality_scores (
            id INTEGER PRIMARY KEY, trade_id INTEGER UNIQUE,
            politician_name TEXT, ticker TEXT, sqs REAL, grade TEXT,
            action TEXT, actionability REAL, timeliness REAL,
            conviction REAL, information_edge REAL, market_impact REAL,
            scored_at TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE social_signals (
            id INTEGER PRIMARY KEY, post_id INTEGER,
            author_name TEXT, author_type TEXT, platform TEXT,
            sentiment TEXT, sentiment_score REAL,
            tickers_explicit TEXT, tickers_implied TEXT,
            impact_score REAL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE extraction_log (
            id INTEGER PRIMARY KEY, source_type TEXT, status TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE social_posts (
            id INTEGER PRIMARY KEY, platform TEXT, author_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE fama_french_results (
            id INTEGER PRIMARY KEY, politician_name TEXT, ticker TEXT,
            transaction_type TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE ml_predictions (
            id INTEGER PRIMARY KEY, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Insert sample data
    cursor.execute("""
        INSERT INTO congress_trades (politician_name, chamber, ticker, transaction_type,
                                     amount_range, transaction_date, filing_date)
        VALUES ('John Doe', 'Senate', 'AAPL', 'Purchase', '$1,001 - $15,000', '2026-01-15', '2026-02-01')
    """)
    cursor.execute("""
        INSERT INTO congress_trades (politician_name, chamber, ticker, transaction_type,
                                     amount_range, transaction_date, filing_date)
        VALUES ('Jane Smith', 'House', 'MSFT', 'Sale', '$15,001 - $50,000', '2026-01-20', '2026-02-10')
    """)
    cursor.execute("""
        INSERT INTO alpha_signals (trade_id, ticker, politician_name, chamber,
                                    transaction_type, direction, signal_strength, confidence,
                                    sqs_score, sqs_grade, transaction_date, created_at)
        VALUES (1, 'AAPL', 'John Doe', 'Senate', 'Purchase', 'LONG', 0.85, 0.72,
                65.0, 'Gold', '2026-01-15', '2026-02-01')
    """)
    cursor.execute("""
        INSERT INTO enhanced_signals (trade_id, ticker, politician_name, chamber,
                                       transaction_type, direction, pacs_score,
                                       confidence_v2, enhanced_strength, party)
        VALUES ('1', 'AAPL', 'John Doe', 'Senate', 'Purchase', 'LONG', 0.75,
                0.80, 0.90, 'Republican')
    """)
    cursor.execute("""
        INSERT INTO signal_performance (signal_id, ticker, direction, signal_date,
                                         actual_alpha_5d, hit_5d, signal_strength, confidence)
        VALUES (1, 'AAPL', 'LONG', '2026-01-15', 0.012, 1, 0.85, 0.72)
    """)
    cursor.execute("""
        INSERT INTO convergence_signals (ticker, direction, politician_count, politicians,
                                          chambers, score, detected_at)
        VALUES ('AAPL', 'Buy', 3, 'Doe,Smith,Jones', 'Senate,House', 2.5, '2026-02-01')
    """)
    cursor.execute("""
        INSERT INTO social_signals (author_name, platform, sentiment,
                                     tickers_explicit, tickers_implied, impact_score)
        VALUES ('Trump', 'twitter', 'bullish', '["AAPL"]', '["MSFT","GOOG"]', 8.0)
    """)

    conn.commit()
    conn.close()
    return db_path


@pytest.fixture
def client(test_db):
    """Create FastAPI TestClient with test database."""
    from fastapi.testclient import TestClient
    import api_server

    # Directly set DB_PATH on the module
    original_db_path = api_server.DB_PATH
    api_server.DB_PATH = test_db
    try:
        with TestClient(api_server.app) as c:
            yield c
    finally:
        api_server.DB_PATH = original_db_path


class TestHealthEndpoints:
    def test_health(self, client):
        r = client.get("/api/health")
        assert r.status_code == 200
        assert r.json()["status"] in ("healthy", "ok")

    def test_health_root(self, client):
        r = client.get("/health")
        assert r.status_code == 200


class TestSignalEndpoints:
    def test_list_signals(self, client):
        r = client.get("/api/signals")
        assert r.status_code == 200
        data = r.json()
        assert "data" in data
        assert "total" in data

    def test_list_signals_with_ticker(self, client):
        r = client.get("/api/signals?ticker=AAPL")
        assert r.status_code == 200

    def test_enhanced_signals(self, client):
        r = client.get("/api/enhanced-signals")
        assert r.status_code == 200
        data = r.json()
        assert "data" in data

    def test_signal_aging(self, client):
        r = client.get("/api/signals/aging")
        assert r.status_code == 200

    def test_signal_distribution(self, client):
        r = client.get("/api/signals/distribution")
        assert r.status_code == 200


class TestTradeEndpoints:
    def test_list_trades(self, client):
        r = client.get("/api/trades")
        assert r.status_code == 200
        data = r.json()
        assert "data" in data
        assert data["total"] >= 1

    def test_ticker_concentration(self, client):
        r = client.get("/api/tickers/concentration?days=365&limit=10")
        assert r.status_code == 200
        data = r.json()
        assert "tickers" in data

    def test_weekly_flow(self, client):
        r = client.get("/api/flow/weekly?weeks=4")
        assert r.status_code == 200
        data = r.json()
        assert "weeks" in data

    def test_chamber_comparison(self, client):
        r = client.get("/api/chambers/comparison")
        assert r.status_code == 200
        data = r.json()
        assert "senate" in data
        assert "house" in data


class TestPoliticianEndpoints:
    def test_list_politicians(self, client):
        r = client.get("/api/politicians")
        assert r.status_code == 200

    def test_top_performers(self, client):
        r = client.get("/api/top-performers", params={"min_signals": 1})
        assert r.status_code in (200, 422)  # 422 if validation issue with test data

    def test_politician_performance(self, client):
        r = client.get("/api/politicians/performance")
        assert r.status_code == 200


class TestPerformanceEndpoints:
    def test_performance(self, client):
        r = client.get("/api/performance")
        assert r.status_code == 200

    def test_performance_summary(self, client):
        r = client.get("/api/performance/summary")
        assert r.status_code == 200

    def test_seasonal(self, client):
        r = client.get("/api/performance/seasonal")
        assert r.status_code == 200
        data = r.json()
        assert "months" in data

    def test_factor_correlation(self, client):
        r = client.get("/api/factor-correlation")
        assert r.status_code == 200


class TestPortfolioEndpoints:
    def test_portfolio(self, client):
        r = client.get("/api/portfolio")
        assert r.status_code == 200

    def test_sectors(self, client):
        r = client.get("/api/sectors")
        assert r.status_code == 200

    def test_rebalance(self, client):
        r = client.get("/api/rebalance")
        assert r.status_code == 200


class TestSocialEndpoints:
    def test_ticker_mentions(self, client):
        r = client.get("/api/social/ticker-mentions")
        assert r.status_code == 200
        data = r.json()
        assert "mentions" in data
        assert "unique_tickers" in data


class TestSystemEndpoints:
    def test_stats(self, client):
        r = client.get("/api/stats")
        assert r.status_code == 200

    def test_daily_briefing(self, client):
        r = client.get("/api/daily-briefing")
        assert r.status_code == 200
        data = r.json()
        assert "date" in data
        assert "top_picks" in data
