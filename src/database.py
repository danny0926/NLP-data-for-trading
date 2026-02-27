import sqlite3
import hashlib
from datetime import datetime
import os

from src.config import DB_PATH

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Table: senate_trades
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS senate_trades (
        id TEXT PRIMARY KEY,
        filing_date DATE NOT NULL,
        transaction_date DATE NOT NULL,
        politician_name VARCHAR(255) NOT NULL,
        ticker VARCHAR(10),
        asset_type VARCHAR(50) NOT NULL,
        transaction_type VARCHAR(50) NOT NULL,
        amount_range VARCHAR(100) NOT NULL,
        ptr_link TEXT NOT NULL,
        is_paper BOOLEAN NOT NULL,
        created_at TIMESTAMP NOT NULL,
        updated_at TIMESTAMP NOT NULL,
        data_hash VARCHAR(64) UNIQUE NOT NULL
    )
    ''')
    
    # Indices
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_senate_politician_date ON senate_trades (politician_name, transaction_date, ticker)')
    
    # Table: house_trades (Simplified for now, as per spec 4.2)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS house_trades (
        id TEXT PRIMARY KEY,
        filing_date DATE NOT NULL,
        transaction_date DATE,
        politician_name VARCHAR(255) NOT NULL,
        ticker VARCHAR(10),
        asset_type VARCHAR(50),
        transaction_type VARCHAR(50),
        amount_range VARCHAR(100),
        ptr_link TEXT NOT NULL,
        is_paper BOOLEAN NOT NULL,
        document_id VARCHAR(50) NOT NULL,
        chamber VARCHAR(20) DEFAULT 'House',
        created_at TIMESTAMP NOT NULL,
        updated_at TIMESTAMP NOT NULL,
        data_hash VARCHAR(64) UNIQUE NOT NULL
    )
    ''')

    # Table: institutional_holdings
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS institutional_holdings (
        id TEXT PRIMARY KEY,
        report_period DATE NOT NULL,
        institution_name VARCHAR(255) NOT NULL,
        cik VARCHAR(20) NOT NULL,
        ticker VARCHAR(10) NOT NULL,
        shares BIGINT,
        value DECIMAL(18,2),
        change_from_prev DECIMAL(18,2),
        filing_link TEXT,
        created_at TIMESTAMP NOT NULL,
        UNIQUE(report_period, cik, ticker)
    )
    ''')

    # Table: ocr_queue
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS ocr_queue (
        id TEXT PRIMARY KEY,
        filing_id TEXT NOT NULL,
        pdf_url TEXT NOT NULL,
        status VARCHAR(20) NOT NULL,
        error_message TEXT,
        created_at TIMESTAMP NOT NULL,
        processed_at TIMESTAMP
    )
    ''')

    # Table: congress_trades (ETL Pipeline 統一表)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS congress_trades (
        id TEXT PRIMARY KEY,
        chamber TEXT NOT NULL,
        politician_name TEXT NOT NULL,
        transaction_date DATE,
        filing_date DATE,
        ticker TEXT,
        asset_name TEXT,
        asset_type TEXT DEFAULT 'Stock',
        transaction_type TEXT,
        amount_range TEXT,
        owner TEXT,
        comment TEXT,
        source_url TEXT,
        source_format TEXT,
        extraction_confidence REAL,
        data_hash TEXT UNIQUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_congress_politician ON congress_trades(politician_name)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_congress_ticker ON congress_trades(ticker)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_congress_date ON congress_trades(transaction_date)')

    # Table: sec_form4_trades (SEC Form 4 Insider Trading)
    # data_hash 去重: accession_number + transaction_date + transaction_type + shares
    # 因為一個 filing (accession) 可能含多筆交易
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS sec_form4_trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        accession_number TEXT,
        filer_name TEXT NOT NULL,
        filer_title TEXT,
        issuer_name TEXT,
        ticker TEXT,
        transaction_type TEXT,
        transaction_date TEXT,
        shares REAL,
        price_per_share REAL,
        total_value REAL,
        ownership_type TEXT,
        source_url TEXT,
        data_hash TEXT UNIQUE,
        created_at TEXT DEFAULT (datetime('now'))
    )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_form4_ticker ON sec_form4_trades(ticker)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_form4_date ON sec_form4_trades(transaction_date)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_form4_filer ON sec_form4_trades(filer_name)')

    # Table: extraction_log (ETL Pipeline 萃取紀錄)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS extraction_log (
        id TEXT PRIMARY KEY,
        source_type TEXT NOT NULL,
        source_url TEXT,
        confidence REAL,
        raw_record_count INTEGER,
        extracted_count INTEGER,
        status TEXT DEFAULT 'success',
        error_message TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # Table: anomaly_detections (異常偵測結果)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS anomaly_detections (
        id TEXT PRIMARY KEY,
        politician_name TEXT NOT NULL,
        ticker TEXT,
        anomaly_type TEXT NOT NULL,
        severity TEXT NOT NULL,
        score REAL NOT NULL,
        description TEXT,
        transaction_date TEXT,
        related_trades_count INTEGER DEFAULT 0,
        detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_anomaly_politician ON anomaly_detections(politician_name)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_anomaly_type ON anomaly_detections(anomaly_type)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_anomaly_severity ON anomaly_detections(severity)')

    conn.commit()
    conn.close()

def generate_hash(data_tuple):
    data_str = "|".join(map(str, data_tuple))
    return hashlib.sha256(data_str.encode()).hexdigest()

if __name__ == "__main__":
    init_db()
    print(f"Database initialized at {DB_PATH}")
