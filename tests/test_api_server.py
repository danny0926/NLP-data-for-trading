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
            filer_title TEXT, transaction_type TEXT, transaction_date TEXT,
            shares REAL, total_value REAL,
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

    # Additional sample data for broader test coverage
    cursor.execute("""
        INSERT INTO politician_rankings (politician_name, chamber, total_trades, pis_total, rank)
        VALUES ('John Doe', 'Senate', 15, 72.5, 1)
    """)
    cursor.execute("""
        INSERT INTO politician_rankings (politician_name, chamber, total_trades, pis_total, rank)
        VALUES ('Jane Smith', 'House', 8, 45.0, 2)
    """)
    cursor.execute("""
        INSERT INTO portfolio_positions (ticker, sector, weight, conviction_score, expected_alpha)
        VALUES ('AAPL', 'Technology', 0.08, 75.0, 0.015)
    """)
    cursor.execute("""
        INSERT INTO sec_form4_trades (ticker, filer_name, transaction_type, transaction_date)
        VALUES ('AAPL', 'Tim Cook', 'Sale', '2026-01-18')
    """)
    cursor.execute("""
        INSERT INTO sector_rotation_signals (sector, etf, direction, signal_strength,
                                              expected_alpha_20d, momentum_score, net_ratio,
                                              net_dollar, trades, buy_count, sale_count,
                                              politician_count, ticker_count, cross_chamber,
                                              rotation_type, rotation_bonus, top_tickers, window_days)
        VALUES ('Technology', 'XLK', 'Buy', 0.82, 0.025, 0.75, 0.68,
                500000, 10, 7, 3, 5, 4, 1, 'ACCELERATING', 0.1, 'AAPL,MSFT', 30)
    """)
    cursor.execute("""
        INSERT INTO rebalance_history (ticker, action) VALUES ('AAPL', 'BUY')
    """)
    cursor.execute("""
        INSERT INTO extraction_log (source_type, status) VALUES ('senate', 'success')
    """)
    cursor.execute("""
        INSERT INTO extraction_log (source_type, status) VALUES ('house', 'success')
    """)

    # Second alpha signal for richer test data
    cursor.execute("""
        INSERT INTO alpha_signals (trade_id, ticker, politician_name, chamber,
                                    transaction_type, direction, signal_strength, confidence,
                                    sqs_score, sqs_grade, transaction_date, created_at)
        VALUES (2, 'MSFT', 'Jane Smith', 'House', 'Sale', 'LONG', 0.55, 0.60,
                42.0, 'Silver', '2026-01-20', '2026-02-10')
    """)

    # Second performance row
    cursor.execute("""
        INSERT INTO signal_performance (signal_id, ticker, direction, signal_date,
                                         actual_alpha_5d, hit_5d, signal_strength, confidence)
        VALUES (2, 'MSFT', 'LONG', '2026-01-20', -0.008, 0, 0.55, 0.60)
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
        assert data["total"] >= 1

    def test_list_signals_with_ticker(self, client):
        r = client.get("/api/signals?ticker=AAPL")
        assert r.status_code == 200
        data = r.json()
        assert all(s["ticker"] == "AAPL" for s in data["data"])

    def test_list_signals_pagination(self, client):
        r = client.get("/api/signals?limit=1&offset=0")
        assert r.status_code == 200
        data = r.json()
        assert len(data["data"]) <= 1

    def test_list_signals_nonexistent_ticker(self, client):
        r = client.get("/api/signals?ticker=ZZZZ")
        assert r.status_code == 200
        assert r.json()["total"] == 0

    def test_get_single_signal(self, client):
        r = client.get("/api/signals/1")
        assert r.status_code == 200
        assert r.json()["data"]["ticker"] == "AAPL"

    def test_get_signal_not_found(self, client):
        r = client.get("/api/signals/99999")
        assert r.status_code == 404

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

    def test_convergence_signals(self, client):
        r = client.get("/api/convergence")
        assert r.status_code == 200
        data = r.json()
        assert "data" in data
        assert data["total"] >= 1


class TestTradeEndpoints:
    def test_list_trades(self, client):
        r = client.get("/api/trades")
        assert r.status_code == 200
        data = r.json()
        assert "data" in data
        assert data["total"] >= 1

    def test_list_trades_pagination(self, client):
        r = client.get("/api/trades?limit=1&offset=0")
        assert r.status_code == 200
        data = r.json()
        assert len(data["data"]) <= 1

    def test_list_trades_by_chamber(self, client):
        r = client.get("/api/trades?chamber=Senate")
        assert r.status_code == 200

    def test_insider_trades(self, client):
        r = client.get("/api/insider")
        assert r.status_code == 200
        data = r.json()
        assert "data" in data

    def test_cross_reference(self, client):
        r = client.get("/api/cross-ref")
        assert r.status_code == 200

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

    def test_weekly_flow_custom_weeks(self, client):
        r = client.get("/api/flow/weekly?weeks=8")
        assert r.status_code == 200

    def test_chamber_comparison(self, client):
        r = client.get("/api/chambers/comparison")
        assert r.status_code == 200
        data = r.json()
        assert "senate" in data
        assert "house" in data
        assert "politicians" in data["senate"]
        assert "politicians" in data["house"]


class TestPoliticianEndpoints:
    def test_list_politicians(self, client):
        r = client.get("/api/politicians")
        assert r.status_code == 200
        data = r.json()
        assert "data" in data
        assert data["total"] >= 1

    def test_politician_trades(self, client):
        r = client.get("/api/politicians/John%20Doe/trades")
        assert r.status_code == 200
        data = r.json()
        assert "data" in data

    def test_politician_trades_not_found(self, client):
        r = client.get("/api/politicians/Nobody/trades")
        assert r.status_code in (200, 404)

    def test_top_performers(self, client):
        r = client.get("/api/top-performers", params={"min_signals": 1})
        assert r.status_code in (200, 422)

    def test_politician_performance(self, client):
        r = client.get("/api/politicians/performance")
        assert r.status_code == 200


class TestPerformanceEndpoints:
    def test_performance(self, client):
        r = client.get("/api/performance")
        assert r.status_code == 200
        data = r.json()
        assert "data" in data

    def test_performance_summary(self, client):
        r = client.get("/api/performance/summary")
        assert r.status_code == 200
        data = r.json()
        assert "data" in data
        assert "total_evaluated" in data["data"]

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
        data = r.json()
        assert "data" in data
        assert "table_counts" in data["data"]

    def test_daily_briefing(self, client):
        r = client.get("/api/daily-briefing")
        assert r.status_code == 200
        data = r.json()
        assert "date" in data
        assert "top_picks" in data

    def test_pipeline_status(self, client):
        r = client.get("/api/pipeline/status")
        assert r.status_code == 200
        data = r.json()
        assert "stages" in data
        assert "api_version" in data
        assert "congress_trades" in data["stages"]


class TestAlertsEndpoint:
    def test_alerts_preview(self, client):
        r = client.get("/api/alerts?days=7")
        assert r.status_code == 200
        data = r.json()
        assert "total" in data
        assert "alerts" in data

    def test_alerts_default(self, client):
        r = client.get("/api/alerts")
        assert r.status_code == 200


class TestTimelineAndLeaderboard:
    def test_signal_timeline(self, client):
        r = client.get("/api/signals/timeline?days=30")
        assert r.status_code == 200
        data = r.json()
        assert "timeline" in data
        assert "total_signals" in data

    def test_signal_timeline_default(self, client):
        r = client.get("/api/signals/timeline")
        assert r.status_code == 200

    def test_politician_leaderboard(self, client):
        r = client.get("/api/politicians/leaderboard")
        assert r.status_code == 200
        data = r.json()
        assert "data" in data


class TestEdgeCases:
    """Edge cases and validation tests."""

    def test_invalid_limit(self, client):
        r = client.get("/api/signals?limit=-1")
        assert r.status_code == 422

    def test_large_limit_clamped(self, client):
        r = client.get("/api/signals?limit=9999")
        # Should either clamp or return 422
        assert r.status_code in (200, 422)

    def test_negative_offset(self, client):
        r = client.get("/api/signals?offset=-5")
        assert r.status_code == 422

    def test_nonexistent_endpoint(self, client):
        r = client.get("/api/nonexistent")
        assert r.status_code == 404

    def test_health_no_auth_required(self, client):
        """Health endpoints should work without API key."""
        r = client.get("/api/health")
        assert r.status_code == 200

    def test_signals_response_structure(self, client):
        """Verify standard paginated response structure."""
        r = client.get("/api/signals")
        data = r.json()
        assert isinstance(data["data"], list)
        assert isinstance(data["total"], int)
        assert "limit" in data
        assert "offset" in data

    def test_enhanced_signals_party_field(self, client):
        """Verify party field is returned in enhanced signals."""
        r = client.get("/api/enhanced-signals")
        data = r.json()
        if data["data"]:
            assert "party" in data["data"][0]

    def test_social_mentions_limit(self, client):
        r = client.get("/api/social/ticker-mentions?limit=5")
        assert r.status_code == 200

    def test_weekly_flow_min_weeks(self, client):
        r = client.get("/api/flow/weekly?weeks=4")
        assert r.status_code == 200

    def test_concentration_min_days(self, client):
        r = client.get("/api/tickers/concentration?days=30")
        assert r.status_code == 200
