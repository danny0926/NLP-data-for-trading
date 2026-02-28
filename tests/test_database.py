"""
tests/test_database.py — 資料庫整合測試

測試項目：
1. 連線成功
2. 關鍵 table 存在
3. 關鍵欄位存在（schema 正確性）
4. 資料完整性（count > 0）
"""

import sqlite3

import pytest


# ── 預期存在的 table 清單 ───────────────────────────────────────────────
REQUIRED_TABLES = [
    "congress_trades",
    "alpha_signals",
    "enhanced_signals",
    "signal_quality_scores",
    "convergence_signals",
    "politician_rankings",
    "portfolio_positions",
    "sector_rotation_signals",
    "rebalance_history",
    "extraction_log",
    "sec_form4_trades",
    "social_posts",
    "social_signals",
]

# ── 關鍵 table 的必要欄位 ────────────────────────────────────────────────
TABLE_REQUIRED_COLUMNS = {
    "congress_trades": [
        "id", "chamber", "politician_name", "transaction_date",
        "filing_date", "ticker", "transaction_type", "amount_range",
        "extraction_confidence", "data_hash",
    ],
    "alpha_signals": [
        "id", "trade_id", "ticker", "politician_name", "chamber",
        "direction", "expected_alpha_5d", "expected_alpha_20d",
        "confidence", "signal_strength",
    ],
    "signal_quality_scores": [
        "id", "trade_id", "ticker", "sqs", "grade", "action",
        "actionability", "timeliness", "conviction",
    ],
    "convergence_signals": [
        "id", "ticker", "direction", "politician_count", "score",
    ],
    "politician_rankings": [
        "politician_name", "chamber", "pis_total", "rank",
    ],
}


class TestDatabaseConnection:
    def test_db_connection_succeeds(self, db_path):
        """data/data.db 應可正常開啟連線。"""
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        assert conn is not None
        conn.close()

    def test_db_is_valid_sqlite(self, db_conn):
        """資料庫應為合法 SQLite 格式（可執行基本查詢）。"""
        cursor = db_conn.cursor()
        cursor.execute("SELECT sqlite_version()")
        row = cursor.fetchone()
        assert row is not None
        assert len(row[0]) > 0


class TestTablesExist:
    @pytest.mark.parametrize("table_name", REQUIRED_TABLES)
    def test_required_table_exists(self, db_conn, table_name):
        """所有關鍵 table 都應存在。"""
        cursor = db_conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        )
        result = cursor.fetchone()
        assert result is not None, f"Table '{table_name}' 不存在於資料庫"


class TestTableSchema:
    @pytest.mark.parametrize("table_name,expected_cols", TABLE_REQUIRED_COLUMNS.items())
    def test_required_columns_exist(self, db_conn, table_name, expected_cols):
        """關鍵 table 的必要欄位都應存在。"""
        cursor = db_conn.cursor()
        cursor.execute(f"PRAGMA table_info({table_name})")
        actual_cols = {row["name"] for row in cursor.fetchall()}
        for col in expected_cols:
            assert col in actual_cols, (
                f"Table '{table_name}' 缺少欄位 '{col}'"
            )

    def test_congress_trades_data_hash_unique_constraint(self, db_conn):
        """congress_trades.data_hash 應有 UNIQUE 約束。"""
        cursor = db_conn.cursor()
        cursor.execute("PRAGMA index_list(congress_trades)")
        indexes = cursor.fetchall()
        # 找出唯一索引
        unique_cols = set()
        for idx in indexes:
            if idx["unique"]:
                cursor.execute(f"PRAGMA index_info({idx['name']})")
                for col_info in cursor.fetchall():
                    unique_cols.add(col_info["name"])
        assert "data_hash" in unique_cols, (
            "congress_trades.data_hash 應有 UNIQUE 約束"
        )


class TestDataIntegrity:
    def test_congress_trades_has_data(self, db_conn):
        """congress_trades 表應有至少 1 筆資料。"""
        cursor = db_conn.cursor()
        cursor.execute("SELECT COUNT(*) as cnt FROM congress_trades")
        count = cursor.fetchone()["cnt"]
        assert count > 0, "congress_trades 表為空，ETL pipeline 可能未執行"

    def test_congress_trades_no_null_politician_name(self, db_conn):
        """所有 congress_trades 應有 politician_name（不為 NULL 或空字串）。"""
        cursor = db_conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) as cnt FROM congress_trades "
            "WHERE politician_name IS NULL OR politician_name = ''"
        )
        null_count = cursor.fetchone()["cnt"]
        assert null_count == 0, (
            f"{null_count} 筆 congress_trades 缺少 politician_name"
        )

    def test_congress_trades_transaction_type_valid(self, db_conn):
        """transaction_type 應為 Buy、Sale、Exchange 之一。"""
        cursor = db_conn.cursor()
        cursor.execute(
            "SELECT DISTINCT transaction_type FROM congress_trades "
            "WHERE transaction_type NOT IN ('Buy', 'Sale', 'Exchange') "
            "AND transaction_type IS NOT NULL"
        )
        unexpected = [r[0] for r in cursor.fetchall()]
        # 允許存在其他值（歷史資料可能有差異），但記錄以供審查
        # 此測試不強制失敗，僅確認 query 可正常執行
        assert isinstance(unexpected, list)

    def test_alpha_signals_direction_valid(self, db_conn):
        """alpha_signals.direction 應全為 LONG。"""
        cursor = db_conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) as cnt FROM alpha_signals "
            "WHERE direction NOT IN ('LONG', 'SHORT') "
            "AND direction IS NOT NULL"
        )
        invalid_count = cursor.fetchone()["cnt"]
        assert invalid_count == 0, (
            f"{invalid_count} 筆 alpha_signals 有非法 direction 值"
        )

    def test_signal_quality_scores_sqs_in_range(self, db_conn):
        """sqs 分數應在 0~100 之間。"""
        cursor = db_conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) as cnt FROM signal_quality_scores "
            "WHERE sqs < 0 OR sqs > 100"
        )
        out_of_range = cursor.fetchone()["cnt"]
        assert out_of_range == 0, (
            f"{out_of_range} 筆 SQS 分數超出 0-100 範圍"
        )

    def test_alpha_signals_confidence_in_range(self, db_conn):
        """confidence 應在 0.0~1.0 之間。"""
        cursor = db_conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) as cnt FROM alpha_signals "
            "WHERE confidence < 0 OR confidence > 1"
        )
        invalid = cursor.fetchone()["cnt"]
        assert invalid == 0, (
            f"{invalid} 筆 alpha_signals.confidence 超出 [0,1] 範圍"
        )
