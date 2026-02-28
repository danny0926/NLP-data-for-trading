"""
tests/test_convergence_detector.py — ConvergenceDetector._calc_score 測試

測試範圍：
- _calc_score: 基礎分、跨院加分、時間密度、金額加權
- burst_bonus: 7 天內密集收斂加分 (Task #5 新功能)
- _parse_amount: 金額字串解析
- _map_direction: 交易方向映射
- detect(): 端對端 DB 整合測試（用 tmp_path）
"""

import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

# 加入專案根目錄到 path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.convergence_detector import (
    BURST_BONUS,
    BURST_WINDOW_DAYS,
    CONVERGENCE_WINDOW_DAYS,
    MAX_AMOUNT,
    ConvergenceDetector,
    _map_direction,
    _parse_amount,
)


# ─────────────────────────────────────────
# Helper: 建立測試用 DB
# ─────────────────────────────────────────

def make_test_db(tmp_path, trades):
    """建立有 congress_trades 表的臨時 DB，插入指定交易資料。"""
    db = tmp_path / "test.db"
    conn = sqlite3.connect(str(db))
    cur = conn.cursor()
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
# _parse_amount 測試
# ─────────────────────────────────────────

class TestParseAmount:

    def test_parse_known_range_small(self):
        """已知區間 $1,001 - $15,000 → 8000。"""
        assert _parse_amount("$1,001 - $15,000") == 8_000.0

    def test_parse_known_range_medium(self):
        """已知區間 $15,001 - $50,000 → 32500。"""
        assert _parse_amount("$15,001 - $50,000") == 32_500.0

    def test_parse_known_range_large(self):
        """已知區間 $1,000,001 - $5,000,000 → 3000000。"""
        assert _parse_amount("$1,000,001 - $5,000,000") == 3_000_000.0

    def test_parse_empty_string_returns_zero(self):
        """空字串 → 0.0。"""
        assert _parse_amount("") == 0.0

    def test_parse_none_returns_zero(self):
        """None → 0.0。"""
        assert _parse_amount(None) == 0.0

    def test_parse_unknown_string_fuzzy(self):
        """未知格式但含數字 → 模糊解析取平均。"""
        result = _parse_amount("$100,000 - $200,000")
        assert result == pytest.approx(150_000.0, abs=1.0)


# ─────────────────────────────────────────
# _map_direction 測試
# ─────────────────────────────────────────

class TestMapDirection:

    def test_buy_maps_to_buy(self):
        assert _map_direction("Buy") == "Buy"

    def test_purchase_maps_to_buy(self):
        assert _map_direction("Purchase") == "Buy"

    def test_sale_maps_to_sale(self):
        assert _map_direction("Sale") == "Sale"

    def test_sale_full_maps_to_sale(self):
        assert _map_direction("Sale (Full)") == "Sale"

    def test_unknown_returns_none(self):
        assert _map_direction("Exchange") is None

    def test_empty_returns_none(self):
        assert _map_direction("") is None

    def test_none_returns_none(self):
        assert _map_direction(None) is None


# ─────────────────────────────────────────
# _calc_score 單元測試
# ─────────────────────────────────────────

class TestCalcScore:
    """直接測試 _calc_score 方法。"""

    def _make_detector(self):
        """建立 ConvergenceDetector（不需要真實 DB）。"""
        return ConvergenceDetector(db_path=":memory:")

    def _make_trades(self, n, amount_range="$15,001 - $50,000"):
        """建立 n 筆測試交易 dict。"""
        return [{"amount_range": amount_range, "chamber": "Senate"} for _ in range(n)]

    # ── 基礎分 ──

    def test_base_score_two_politicians(self):
        """2 位議員 → 基礎分 = 0.5 * (2-1) = 0.5。"""
        d = self._make_detector()
        trades = self._make_trades(2)
        score, breakdown = d._calc_score(
            politician_count=2, chambers=["Senate"], span_days=15, trades=trades
        )
        assert breakdown["base"] == pytest.approx(0.5, abs=1e-3)

    def test_base_score_three_politicians(self):
        """3 位議員 → 基礎分 = 0.5 * (3-1) = 1.0。"""
        d = self._make_detector()
        trades = self._make_trades(3)
        score, breakdown = d._calc_score(
            politician_count=3, chambers=["Senate"], span_days=15, trades=trades
        )
        assert breakdown["base"] == pytest.approx(1.0, abs=1e-3)

    def test_base_score_four_politicians(self):
        """4 位議員 → 基礎分 = 0.5 * (4-1) = 1.5。"""
        d = self._make_detector()
        trades = self._make_trades(4)
        score, breakdown = d._calc_score(
            politician_count=4, chambers=["Senate"], span_days=15, trades=trades
        )
        assert breakdown["base"] == pytest.approx(1.5, abs=1e-3)

    # ── 跨院加分 ──

    def test_cross_chamber_bonus_applied(self):
        """House + Senate 兩院 → cross_chamber = 0.5。"""
        d = self._make_detector()
        trades = self._make_trades(2)
        score, breakdown = d._calc_score(
            politician_count=2, chambers=["House", "Senate"], span_days=10, trades=trades
        )
        assert breakdown["cross_chamber"] == pytest.approx(0.5, abs=1e-3)

    def test_cross_chamber_no_bonus_single_chamber(self):
        """只有 Senate → cross_chamber = 0.0。"""
        d = self._make_detector()
        trades = self._make_trades(2)
        score, breakdown = d._calc_score(
            politician_count=2, chambers=["Senate"], span_days=10, trades=trades
        )
        assert breakdown["cross_chamber"] == pytest.approx(0.0, abs=1e-3)

    # ── 時間密度 ──

    def test_time_density_same_day(self):
        """同一天 (span_days=0) → time_density = 1.0。"""
        d = self._make_detector()
        trades = self._make_trades(2)
        score, breakdown = d._calc_score(
            politician_count=2, chambers=["Senate"], span_days=0, trades=trades
        )
        assert breakdown["time_density"] == pytest.approx(1.0, abs=1e-3)

    def test_time_density_full_window(self):
        """span_days = 30 (整個視窗) → time_density = 0.0。"""
        d = self._make_detector()
        trades = self._make_trades(2)
        score, breakdown = d._calc_score(
            politician_count=2, chambers=["Senate"],
            span_days=CONVERGENCE_WINDOW_DAYS, trades=trades
        )
        assert breakdown["time_density"] == pytest.approx(0.0, abs=1e-3)

    def test_time_density_midpoint(self):
        """span_days = 15 (視窗一半) → time_density = 0.5。"""
        d = self._make_detector()
        trades = self._make_trades(2)
        score, breakdown = d._calc_score(
            politician_count=2, chambers=["Senate"], span_days=15, trades=trades
        )
        assert breakdown["time_density"] == pytest.approx(0.5, abs=1e-3)

    # ── 金額加權 ──

    def test_amount_weight_max_capped_at_one(self):
        """超大金額 → amount_weight 上限 1.0。"""
        d = self._make_detector()
        trades = self._make_trades(2, amount_range="$50,000,000+")
        score, breakdown = d._calc_score(
            politician_count=2, chambers=["Senate"], span_days=10, trades=trades
        )
        assert breakdown["amount_weight"] == pytest.approx(1.0, abs=1e-3)

    def test_amount_weight_zero_for_unknown(self):
        """未知金額區間 → amount_weight = 0.0。"""
        d = self._make_detector()
        trades = [{"amount_range": None, "chamber": "Senate"} for _ in range(2)]
        score, breakdown = d._calc_score(
            politician_count=2, chambers=["Senate"], span_days=10, trades=trades
        )
        assert breakdown["amount_weight"] == pytest.approx(0.0, abs=1e-3)

    # ── Burst Bonus (Task #5 新功能) ──

    def test_burst_bonus_applied_within_7_days(self):
        """span_days <= 7 → burst_bonus = BURST_BONUS (0.5)。"""
        d = self._make_detector()
        trades = self._make_trades(2)
        score, breakdown = d._calc_score(
            politician_count=2, chambers=["Senate"],
            span_days=BURST_WINDOW_DAYS, trades=trades
        )
        assert breakdown["burst_bonus"] == pytest.approx(BURST_BONUS, abs=1e-3)

    def test_burst_bonus_applied_same_day(self):
        """span_days = 0 (同一天) → burst_bonus = BURST_BONUS。"""
        d = self._make_detector()
        trades = self._make_trades(2)
        score, breakdown = d._calc_score(
            politician_count=2, chambers=["Senate"], span_days=0, trades=trades
        )
        assert breakdown["burst_bonus"] == pytest.approx(BURST_BONUS, abs=1e-3)

    def test_burst_bonus_not_applied_after_7_days(self):
        """span_days = 8 (超過 burst 視窗) → burst_bonus = 0.0。"""
        d = self._make_detector()
        trades = self._make_trades(2)
        score, breakdown = d._calc_score(
            politician_count=2, chambers=["Senate"],
            span_days=BURST_WINDOW_DAYS + 1, trades=trades
        )
        assert breakdown["burst_bonus"] == pytest.approx(0.0, abs=1e-3)

    def test_burst_bonus_not_applied_at_15_days(self):
        """span_days = 15 → burst_bonus = 0.0。"""
        d = self._make_detector()
        trades = self._make_trades(2)
        score, breakdown = d._calc_score(
            politician_count=2, chambers=["Senate"], span_days=15, trades=trades
        )
        assert breakdown["burst_bonus"] == pytest.approx(0.0, abs=1e-3)

    def test_burst_bonus_boundary_exactly_7_days(self):
        """span_days = 7 (邊界值) → burst_bonus = BURST_BONUS。"""
        d = self._make_detector()
        trades = self._make_trades(2)
        score, breakdown = d._calc_score(
            politician_count=2, chambers=["Senate"],
            span_days=7, trades=trades
        )
        assert breakdown["burst_bonus"] == pytest.approx(BURST_BONUS, abs=1e-3)

    def test_burst_bonus_increases_total_score(self):
        """burst 條件下，總分應高於非 burst 相同條件。"""
        d = self._make_detector()
        trades = self._make_trades(3)
        score_burst, _ = d._calc_score(
            politician_count=3, chambers=["Senate"], span_days=5, trades=trades
        )
        score_no_burst, _ = d._calc_score(
            politician_count=3, chambers=["Senate"], span_days=20, trades=trades
        )
        assert score_burst > score_no_burst

    def test_burst_bonus_value_is_0_5(self):
        """確認 BURST_BONUS 常數值為 0.5（研究驗證值）。"""
        assert BURST_BONUS == pytest.approx(0.5, abs=1e-6)

    def test_burst_window_is_7_days(self):
        """確認 BURST_WINDOW_DAYS 常數值為 7。"""
        assert BURST_WINDOW_DAYS == 7

    # ── 完整評分公式驗證 ──

    def test_total_score_formula(self):
        """驗證總分 = base + cross_chamber + time_density*0.5 + amount_weight*0.5 + burst_bonus。"""
        d = self._make_detector()
        trades = self._make_trades(2, amount_range="$15,001 - $50,000")
        score, breakdown = d._calc_score(
            politician_count=2, chambers=["House", "Senate"], span_days=3, trades=trades
        )
        expected = (
            breakdown["base"]
            + breakdown["cross_chamber"]
            + breakdown["time_density"] * 0.5
            + breakdown["amount_weight"] * 0.5
            + breakdown["burst_bonus"]
        )
        assert score == pytest.approx(expected, abs=1e-3)

    def test_breakdown_keys_complete(self):
        """breakdown 包含所有必要 key (含 burst_bonus)。"""
        d = self._make_detector()
        trades = self._make_trades(2)
        _, breakdown = d._calc_score(
            politician_count=2, chambers=["Senate"], span_days=5, trades=trades
        )
        required_keys = ["base", "cross_chamber", "time_density", "amount_weight", "burst_bonus"]
        for key in required_keys:
            assert key in breakdown, f"Missing key: {key}"


# ─────────────────────────────────────────
# detect() 端對端整合測試
# ─────────────────────────────────────────

class TestDetectIntegration:
    """使用 tmp_path 建立臨時 DB，測試 detect() 完整流程。"""

    def test_detect_finds_basic_convergence(self, tmp_path):
        """兩位議員在 30 天內同向交易同一 ticker → 偵測到 1 個收斂事件。"""
        trades = [
            {
                "id": "t1", "politician_name": "Alice Smith", "chamber": "Senate",
                "ticker": "AAPL", "transaction_type": "Buy",
                "transaction_date": "2025-01-10", "filing_date": "2025-01-15",
                "amount_range": "$15,001 - $50,000", "data_hash": "h1",
            },
            {
                "id": "t2", "politician_name": "Bob Jones", "chamber": "House",
                "ticker": "AAPL", "transaction_type": "Buy",
                "transaction_date": "2025-01-15", "filing_date": "2025-01-20",
                "amount_range": "$15,001 - $50,000", "data_hash": "h2",
            },
        ]
        db = make_test_db(tmp_path, trades)
        detector = ConvergenceDetector(db_path=db)
        events = detector.detect()
        assert len(events) >= 1
        event = events[0]
        assert event["ticker"] == "AAPL"
        assert event["direction"] == "Buy"
        assert event["politician_count"] == 2

    def test_detect_burst_convergence_has_bonus(self, tmp_path):
        """兩位議員在 7 天內同向交易 → score_breakdown 含 burst_bonus = 0.5。"""
        base_date = date(2025, 2, 1)
        trades = [
            {
                "id": "t1", "politician_name": "Alice Smith", "chamber": "Senate",
                "ticker": "NVDA", "transaction_type": "Buy",
                "transaction_date": str(base_date),
                "filing_date": str(base_date + timedelta(days=5)),
                "amount_range": "$50,001 - $100,000", "data_hash": "h1",
            },
            {
                "id": "t2", "politician_name": "Bob Jones", "chamber": "House",
                "ticker": "NVDA", "transaction_type": "Buy",
                "transaction_date": str(base_date + timedelta(days=5)),
                "filing_date": str(base_date + timedelta(days=10)),
                "amount_range": "$50,001 - $100,000", "data_hash": "h2",
            },
        ]
        db = make_test_db(tmp_path, trades)
        detector = ConvergenceDetector(db_path=db)
        events = detector.detect()
        assert len(events) >= 1
        event = events[0]
        assert event["score_breakdown"]["burst_bonus"] == pytest.approx(BURST_BONUS, abs=1e-3)

    def test_detect_no_burst_bonus_for_old_span(self, tmp_path):
        """兩位議員 span_days > 7 → burst_bonus = 0.0。"""
        base_date = date(2025, 2, 1)
        trades = [
            {
                "id": "t1", "politician_name": "Alice Smith", "chamber": "Senate",
                "ticker": "MSFT", "transaction_type": "Buy",
                "transaction_date": str(base_date),
                "filing_date": str(base_date + timedelta(days=5)),
                "amount_range": "$15,001 - $50,000", "data_hash": "h1",
            },
            {
                "id": "t2", "politician_name": "Bob Jones", "chamber": "Senate",
                "ticker": "MSFT", "transaction_type": "Buy",
                "transaction_date": str(base_date + timedelta(days=20)),
                "filing_date": str(base_date + timedelta(days=25)),
                "amount_range": "$15,001 - $50,000", "data_hash": "h2",
            },
        ]
        db = make_test_db(tmp_path, trades)
        detector = ConvergenceDetector(db_path=db)
        events = detector.detect()
        assert len(events) >= 1
        assert events[0]["score_breakdown"]["burst_bonus"] == pytest.approx(0.0, abs=1e-3)

    def test_detect_no_convergence_for_opposite_directions(self, tmp_path):
        """一人 Buy 一人 Sale → 不同方向，不算收斂。"""
        trades = [
            {
                "id": "t1", "politician_name": "Alice Smith", "chamber": "Senate",
                "ticker": "TSLA", "transaction_type": "Buy",
                "transaction_date": "2025-01-10", "filing_date": "2025-01-15",
                "amount_range": "$15,001 - $50,000", "data_hash": "h1",
            },
            {
                "id": "t2", "politician_name": "Bob Jones", "chamber": "Senate",
                "ticker": "TSLA", "transaction_type": "Sale",
                "transaction_date": "2025-01-12", "filing_date": "2025-01-18",
                "amount_range": "$15,001 - $50,000", "data_hash": "h2",
            },
        ]
        db = make_test_db(tmp_path, trades)
        detector = ConvergenceDetector(db_path=db)
        events = detector.detect()
        # TSLA 收斂不應存在（不同方向）
        tsla_events = [e for e in events if e["ticker"] == "TSLA"]
        assert len(tsla_events) == 0

    def test_detect_no_convergence_single_politician(self, tmp_path):
        """同一議員多次交易 → 不算收斂（需要 2+ 不同議員）。"""
        trades = [
            {
                "id": "t1", "politician_name": "Alice Smith", "chamber": "Senate",
                "ticker": "AMZN", "transaction_type": "Buy",
                "transaction_date": "2025-01-10", "filing_date": "2025-01-15",
                "amount_range": "$15,001 - $50,000", "data_hash": "h1",
            },
            {
                "id": "t2", "politician_name": "Alice Smith", "chamber": "Senate",
                "ticker": "AMZN", "transaction_type": "Buy",
                "transaction_date": "2025-01-12", "filing_date": "2025-01-18",
                "amount_range": "$50,001 - $100,000", "data_hash": "h2",
            },
        ]
        db = make_test_db(tmp_path, trades)
        detector = ConvergenceDetector(db_path=db)
        events = detector.detect()
        amzn_events = [e for e in events if e["ticker"] == "AMZN"]
        assert len(amzn_events) == 0

    def test_detect_empty_db_returns_empty_list(self, tmp_path):
        """空 DB → 回傳空 list。"""
        db = make_test_db(tmp_path, [])
        detector = ConvergenceDetector(db_path=db)
        events = detector.detect()
        assert events == []

    def test_detect_cross_chamber_bonus_in_event(self, tmp_path):
        """House + Senate 同向交易 → cross_chamber = 0.5。"""
        trades = [
            {
                "id": "t1", "politician_name": "Alice Smith", "chamber": "Senate",
                "ticker": "META", "transaction_type": "Buy",
                "transaction_date": "2025-01-10", "filing_date": "2025-01-15",
                "amount_range": "$15,001 - $50,000", "data_hash": "h1",
            },
            {
                "id": "t2", "politician_name": "Bob Jones", "chamber": "House",
                "ticker": "META", "transaction_type": "Buy",
                "transaction_date": "2025-01-12", "filing_date": "2025-01-18",
                "amount_range": "$15,001 - $50,000", "data_hash": "h2",
            },
        ]
        db = make_test_db(tmp_path, trades)
        detector = ConvergenceDetector(db_path=db)
        events = detector.detect()
        assert len(events) >= 1
        meta_event = next(e for e in events if e["ticker"] == "META")
        assert meta_event["score_breakdown"]["cross_chamber"] == pytest.approx(0.5, abs=1e-3)
