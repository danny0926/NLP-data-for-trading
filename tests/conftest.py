"""
tests/conftest.py — 共用 fixtures

所有測試模組共享的 pytest fixtures：
- db_conn: read-only connection to data/data.db
- sample_trade: 標準測試用交易 dict
- sample_buy_trade / sample_sale_trade: 方向明確的交易
"""

import sqlite3
from pathlib import Path

import pytest

# 專案根目錄（tests/ 的父層）
PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = str(PROJECT_ROOT / "data" / "data.db")


@pytest.fixture(scope="session")
def db_path():
    """回傳 data/data.db 的絕對路徑字串。"""
    return DB_PATH


@pytest.fixture(scope="session")
def db_conn():
    """提供 read-only SQLite 連線（session 範圍，整個測試 session 共用一個連線）。"""
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


@pytest.fixture
def sample_buy_trade():
    """標準 Senate Buy 交易，所有必要欄位完整。"""
    return {
        "id": "test-001",
        "chamber": "Senate",
        "politician_name": "David H McCormick",
        "transaction_date": "2025-01-10",
        "filing_date": "2025-01-20",
        "ticker": "AAPL",
        "asset_name": "Apple Inc.",
        "asset_type": "Stock",
        "transaction_type": "Buy",
        "amount_range": "$15,001 - $50,000",
        "owner": "Self",
        "comment": None,
        "source_url": "https://example.com",
        "source_format": "html",
        "extraction_confidence": 0.95,
    }


@pytest.fixture
def sample_sale_trade():
    """標準 House Sale 交易。"""
    return {
        "id": "test-002",
        "chamber": "House",
        "politician_name": "Nancy Pelosi",
        "transaction_date": "2025-01-05",
        "filing_date": "2025-01-18",
        "ticker": "NVDA",
        "asset_name": "NVIDIA Corporation",
        "asset_type": "Stock",
        "transaction_type": "Sale",
        "amount_range": "$100,001 - $250,000",
        "owner": "Spouse",
        "comment": None,
        "source_url": "https://example.com",
        "source_format": "pdf",
        "extraction_confidence": 0.85,
    }


@pytest.fixture
def sample_trade(sample_buy_trade):
    """預設 sample trade（等同 sample_buy_trade）。"""
    return sample_buy_trade


# ============================================================================
# Isolated temp DB fixtures (unit tests - no data/data.db access)
# ============================================================================

@pytest.fixture
def tmp_db_path(tmp_path):
    """Temp directory SQLite DB path (per-test isolated)."""
    return str(tmp_path / "test.db")


@pytest.fixture
def tmp_db(tmp_db_path):
    """Temp SQLite with core tables."""
    conn = sqlite3.connect(tmp_db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    for sql in _CORE_TABLE_SQLS:
        c.execute(sql)
    conn.commit()
    yield conn
    conn.close()


_CORE_TABLE_SQLS = [
    "CREATE TABLE IF NOT EXISTS congress_trades (id TEXT PRIMARY KEY, chamber TEXT NOT NULL, politician_name TEXT NOT NULL, transaction_date DATE, filing_date DATE, ticker TEXT, asset_name TEXT, asset_type TEXT, transaction_type TEXT, amount_range TEXT, owner TEXT, comment TEXT, source_url TEXT, source_format TEXT, extraction_confidence REAL, data_hash TEXT UNIQUE, created_at TIMESTAMP)",
    "CREATE TABLE IF NOT EXISTS signal_quality_scores (id INTEGER PRIMARY KEY AUTOINCREMENT, trade_id TEXT NOT NULL UNIQUE, politician_name TEXT, ticker TEXT, sqs REAL NOT NULL, grade TEXT NOT NULL, action TEXT, actionability REAL, timeliness REAL, conviction REAL, information_edge REAL, market_impact REAL, scored_at TIMESTAMP)",
    "CREATE TABLE IF NOT EXISTS convergence_signals (id TEXT PRIMARY KEY, ticker TEXT NOT NULL, direction TEXT NOT NULL, politician_count INTEGER NOT NULL, politicians TEXT NOT NULL, chambers TEXT NOT NULL, window_start DATE NOT NULL, window_end DATE NOT NULL, span_days INTEGER NOT NULL, score REAL NOT NULL, score_base REAL, score_cross_chamber REAL, score_time_density REAL, score_amount_weight REAL, score_contract REAL DEFAULT 0, detected_at TIMESTAMP, UNIQUE(ticker, direction, window_start, window_end))",
    "CREATE TABLE IF NOT EXISTS politician_rankings (politician_name TEXT PRIMARY KEY, chamber TEXT, total_trades INTEGER, avg_trade_size REAL, trades_per_month REAL, unique_tickers INTEGER, buy_count INTEGER, sale_count INTEGER, pis_activity REAL, pis_conviction REAL, pis_diversification REAL, pis_timing REAL, pis_total REAL, rank INTEGER, updated_at TIMESTAMP)",
    "CREATE TABLE IF NOT EXISTS sec_form4_trades (id INTEGER PRIMARY KEY AUTOINCREMENT, accession_number TEXT, filer_name TEXT NOT NULL, filer_title TEXT, issuer_name TEXT, ticker TEXT, transaction_type TEXT, transaction_date TEXT, shares REAL, price_per_share REAL, total_value REAL, ownership_type TEXT, source_url TEXT, data_hash TEXT UNIQUE, created_at TEXT)",
    "CREATE TABLE IF NOT EXISTS alpha_signals (id TEXT PRIMARY KEY, trade_id TEXT NOT NULL UNIQUE, ticker TEXT NOT NULL, asset_name TEXT, politician_name TEXT, chamber TEXT, transaction_type TEXT, transaction_date DATE, filing_date DATE, amount_range TEXT, direction TEXT NOT NULL, expected_alpha_5d REAL NOT NULL, expected_alpha_20d REAL NOT NULL, confidence REAL NOT NULL, signal_strength REAL NOT NULL, combined_multiplier REAL, convergence_bonus REAL, has_convergence BOOLEAN, politician_grade TEXT, filing_lag_days INTEGER, sqs_score REAL, sqs_grade TEXT, insider_overlap_count INTEGER DEFAULT 0, insider_convergence_bonus REAL DEFAULT 0.0, reasoning TEXT, created_at TIMESTAMP)",
]


@pytest.fixture
def populated_tmp_db(tmp_db, tmp_db_path):
    """Temp DB pre-filled with sample congress_trades."""
    c = tmp_db.cursor()
    trades = [
        ('t-001', 'Senate', 'Alice Senator', '2025-01-10', '2025-01-17', 'AAPL', 'Apple Inc.', 'Stock', 'Buy', '$15,001 - $50,000', 'Self', '', 'https://example.com', 'html', 0.95, 'hash001'),
        ('t-002', 'House', 'Bob Representative', '2025-01-12', '2025-01-20', 'AAPL', 'Apple Inc.', 'Stock', 'Buy', '$50,001 - $100,000', 'Self', '', 'https://example.com', 'html', 0.9, 'hash002'),
        ('t-003', 'Senate', 'Charlie Senator', '2025-01-14', '2025-01-25', 'AAPL', 'Apple Inc.', 'Stock', 'Buy', '$100,001 - $250,000', 'Spouse', '', 'https://example.com', 'html', 0.88, 'hash003'),
        ('t-004', 'House', 'Diana Representative', '2025-01-15', '2025-01-30', 'MSFT', 'Microsoft Corp.', 'Stock', 'Sale', '$250,001 - $500,000', 'Self', '', 'https://example.com', 'pdf', 0.92, 'hash004'),
        ('t-005', 'Senate', 'Alice Senator', '2025-01-18', '2025-02-01', 'NVDA', 'NVIDIA Corporation', 'Stock', 'Buy', '$1,001 - $15,000', 'Self', '', 'https://example.com', 'html', 0.85, 'hash005'),
    ]
    c.executemany(
        "INSERT INTO congress_trades (id, chamber, politician_name, transaction_date, filing_date, ticker, asset_name, asset_type, transaction_type, amount_range, owner, comment, source_url, source_format, extraction_confidence, data_hash) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        trades)
    tmp_db.commit()
    return tmp_db
