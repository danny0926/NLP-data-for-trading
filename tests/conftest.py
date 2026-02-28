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
