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


# ─────────────────────────────────────────
# Window Boundary 測試
# ─────────────────────────────────────────

class TestWindowBoundary:
    """測試 30 天視窗邊界條件。"""

    def test_trade_exactly_30_days_apart_is_included(self, tmp_path):
        """兩筆交易恰好相差 30 天 → 應被包含在同一視窗（<= window_end）。"""
        base_date = date(2025, 3, 1)
        trades = [
            {
                "id": "t1", "politician_name": "Alice", "chamber": "Senate",
                "ticker": "GOOG", "transaction_type": "Buy",
                "transaction_date": str(base_date),
                "filing_date": str(base_date + timedelta(days=5)),
                "amount_range": "$15,001 - $50,000", "data_hash": "h1",
            },
            {
                "id": "t2", "politician_name": "Bob", "chamber": "Senate",
                "ticker": "GOOG", "transaction_type": "Buy",
                "transaction_date": str(base_date + timedelta(days=CONVERGENCE_WINDOW_DAYS)),
                "filing_date": str(base_date + timedelta(days=35)),
                "amount_range": "$15,001 - $50,000", "data_hash": "h2",
            },
        ]
        db = make_test_db(tmp_path, trades)
        detector = ConvergenceDetector(db_path=db)
        events = detector.detect()
        goog_events = [e for e in events if e["ticker"] == "GOOG"]
        assert len(goog_events) == 1, "Trade exactly 30 days apart should be included"
        assert goog_events[0]["politician_count"] == 2

    def test_trade_31_days_apart_is_excluded(self, tmp_path):
        """兩筆交易相差 31 天 → 超出視窗，不應形成收斂。"""
        base_date = date(2025, 3, 1)
        trades = [
            {
                "id": "t1", "politician_name": "Alice", "chamber": "Senate",
                "ticker": "GOOG", "transaction_type": "Buy",
                "transaction_date": str(base_date),
                "filing_date": str(base_date + timedelta(days=5)),
                "amount_range": "$15,001 - $50,000", "data_hash": "h1",
            },
            {
                "id": "t2", "politician_name": "Bob", "chamber": "Senate",
                "ticker": "GOOG", "transaction_type": "Buy",
                "transaction_date": str(base_date + timedelta(days=CONVERGENCE_WINDOW_DAYS + 1)),
                "filing_date": str(base_date + timedelta(days=36)),
                "amount_range": "$15,001 - $50,000", "data_hash": "h2",
            },
        ]
        db = make_test_db(tmp_path, trades)
        detector = ConvergenceDetector(db_path=db)
        events = detector.detect()
        goog_events = [e for e in events if e["ticker"] == "GOOG"]
        assert len(goog_events) == 0, "Trade 31 days apart should NOT form convergence"

    def test_trade_29_days_apart_is_included(self, tmp_path):
        """兩筆交易相差 29 天 → 在視窗內，應形成收斂。"""
        base_date = date(2025, 3, 1)
        trades = [
            {
                "id": "t1", "politician_name": "Alice", "chamber": "Senate",
                "ticker": "GOOG", "transaction_type": "Sale",
                "transaction_date": str(base_date),
                "filing_date": str(base_date + timedelta(days=5)),
                "amount_range": "$15,001 - $50,000", "data_hash": "h1",
            },
            {
                "id": "t2", "politician_name": "Bob", "chamber": "Senate",
                "ticker": "GOOG", "transaction_type": "Sale",
                "transaction_date": str(base_date + timedelta(days=29)),
                "filing_date": str(base_date + timedelta(days=34)),
                "amount_range": "$15,001 - $50,000", "data_hash": "h2",
            },
        ]
        db = make_test_db(tmp_path, trades)
        detector = ConvergenceDetector(db_path=db)
        events = detector.detect()
        goog_events = [e for e in events if e["ticker"] == "GOOG"]
        assert len(goog_events) == 1


# ─────────────────────────────────────────
# Score Components 驗證
# ─────────────────────────────────────────

class TestScoreComponents:
    """驗證各評分組件的數值計算。"""

    def test_full_score_components_two_senate_same_day_small_amount(self):
        """2 Senate, span=0, $15K-$50K → 驗證每個組件的精確值。"""
        d = ConvergenceDetector(db_path=":memory:")
        trades = [{"amount_range": "$15,001 - $50,000", "chamber": "Senate"} for _ in range(2)]
        score, bd = d._calc_score(
            politician_count=2, chambers=["Senate"], span_days=0, trades=trades
        )
        # base = 0.5*(2-1) = 0.5
        assert bd["base"] == pytest.approx(0.5)
        # cross_chamber = 0 (single chamber)
        assert bd["cross_chamber"] == pytest.approx(0.0)
        # time_density = 1.0 (span=0)
        assert bd["time_density"] == pytest.approx(1.0)
        # amount_weight = round(32500 / 5000000, 3) = 0.006 (rounded in _calc_score)
        assert bd["amount_weight"] == pytest.approx(round(32_500 / MAX_AMOUNT, 3), abs=1e-4)
        # burst_bonus = 0.5 (span=0 <= 7)
        assert bd["burst_bonus"] == pytest.approx(0.5)
        # total uses rounded breakdown values internally but score is computed before rounding
        # Verify total is consistent with the formula
        expected_total = 0.5 + 0.0 + 1.0 * 0.5 + (32_500 / MAX_AMOUNT) * 0.5 + 0.5 + 0.0
        assert score == pytest.approx(expected_total, abs=1e-2)

    def test_full_score_components_cross_chamber_large_amount(self):
        """3 politicians, House+Senate, span=10, $250K-$500K → 驗證精確值。"""
        d = ConvergenceDetector(db_path=":memory:")
        trades = [{"amount_range": "$250,001 - $500,000", "chamber": "Senate"} for _ in range(3)]
        score, bd = d._calc_score(
            politician_count=3, chambers=["House", "Senate"], span_days=10, trades=trades
        )
        # base = 0.5*(3-1) = 1.0
        assert bd["base"] == pytest.approx(1.0)
        # cross_chamber = 0.5
        assert bd["cross_chamber"] == pytest.approx(0.5)
        # time_density = 1.0 - 10/30 = 0.6667
        assert bd["time_density"] == pytest.approx(1.0 - 10.0 / 30.0, abs=1e-3)
        # amount_weight = min(1, 375000/5000000) = 0.075
        assert bd["amount_weight"] == pytest.approx(375_000 / MAX_AMOUNT, abs=1e-4)
        # burst_bonus = 0 (span=10 > 7)
        assert bd["burst_bonus"] == pytest.approx(0.0)

    def test_score_with_contract_proximity(self):
        """合約近接分數加入後影響總分。"""
        d = ConvergenceDetector(db_path=":memory:")
        trades = [{"amount_range": "$15,001 - $50,000", "chamber": "Senate"} for _ in range(2)]
        score_no_contract, _ = d._calc_score(
            politician_count=2, chambers=["Senate"], span_days=15, trades=trades,
            contract_proximity=0.0,
        )
        score_with_contract, bd = d._calc_score(
            politician_count=2, chambers=["Senate"], span_days=15, trades=trades,
            contract_proximity=0.8,
        )
        # score_contract = 0.8 * 0.5 = 0.4
        assert bd["score_contract"] == pytest.approx(0.4, abs=1e-3)
        assert score_with_contract > score_no_contract
        assert score_with_contract - score_no_contract == pytest.approx(0.4, abs=1e-3)


# ─────────────────────────────────────────
# Direction Consistency 測試
# ─────────────────────────────────────────

class TestDirectionConsistency:
    """確認只有同方向的交易才會形成收斂信號。"""

    def test_mixed_directions_no_convergence(self, tmp_path):
        """3 人交易同 ticker: 2 Buy + 1 Sale → Buy 收斂但 Sale 不收斂。"""
        trades = [
            {
                "id": "t1", "politician_name": "Alice", "chamber": "Senate",
                "ticker": "MSFT", "transaction_type": "Buy",
                "transaction_date": "2025-02-01", "filing_date": "2025-02-05",
                "amount_range": "$15,001 - $50,000", "data_hash": "h1",
            },
            {
                "id": "t2", "politician_name": "Bob", "chamber": "Senate",
                "ticker": "MSFT", "transaction_type": "Buy",
                "transaction_date": "2025-02-03", "filing_date": "2025-02-08",
                "amount_range": "$15,001 - $50,000", "data_hash": "h2",
            },
            {
                "id": "t3", "politician_name": "Charlie", "chamber": "House",
                "ticker": "MSFT", "transaction_type": "Sale",
                "transaction_date": "2025-02-05", "filing_date": "2025-02-10",
                "amount_range": "$15,001 - $50,000", "data_hash": "h3",
            },
        ]
        db = make_test_db(tmp_path, trades)
        detector = ConvergenceDetector(db_path=db)
        events = detector.detect()
        buy_events = [e for e in events if e["ticker"] == "MSFT" and e["direction"] == "Buy"]
        sale_events = [e for e in events if e["ticker"] == "MSFT" and e["direction"] == "Sale"]
        assert len(buy_events) == 1, "2 Buy politicians should converge"
        assert len(sale_events) == 0, "Only 1 Sale politician, no convergence"

    def test_both_directions_converge_separately(self, tmp_path):
        """2 Buy + 2 Sale 同 ticker → 應產生 2 個獨立收斂事件。"""
        trades = [
            {
                "id": "t1", "politician_name": "Alice", "chamber": "Senate",
                "ticker": "AMZN", "transaction_type": "Buy",
                "transaction_date": "2025-02-01", "filing_date": "2025-02-05",
                "amount_range": "$15,001 - $50,000", "data_hash": "h1",
            },
            {
                "id": "t2", "politician_name": "Bob", "chamber": "Senate",
                "ticker": "AMZN", "transaction_type": "Buy",
                "transaction_date": "2025-02-03", "filing_date": "2025-02-08",
                "amount_range": "$15,001 - $50,000", "data_hash": "h2",
            },
            {
                "id": "t3", "politician_name": "Charlie", "chamber": "House",
                "ticker": "AMZN", "transaction_type": "Sale",
                "transaction_date": "2025-02-05", "filing_date": "2025-02-10",
                "amount_range": "$15,001 - $50,000", "data_hash": "h3",
            },
            {
                "id": "t4", "politician_name": "Diana", "chamber": "House",
                "ticker": "AMZN", "transaction_type": "Sale (Full)",
                "transaction_date": "2025-02-07", "filing_date": "2025-02-12",
                "amount_range": "$15,001 - $50,000", "data_hash": "h4",
            },
        ]
        db = make_test_db(tmp_path, trades)
        detector = ConvergenceDetector(db_path=db)
        events = detector.detect()
        amzn_buy = [e for e in events if e["ticker"] == "AMZN" and e["direction"] == "Buy"]
        amzn_sale = [e for e in events if e["ticker"] == "AMZN" and e["direction"] == "Sale"]
        assert len(amzn_buy) == 1
        assert len(amzn_sale) == 1


# ─────────────────────────────────────────
# Minimum Politician Count 測試
# ─────────────────────────────────────────

class TestMinimumPoliticianCount:
    """確認需要 2+ 不同議員才能形成收斂。"""

    def test_exactly_two_politicians_converges(self, tmp_path):
        """恰好 2 位不同議員 → 應形成收斂。"""
        trades = [
            {
                "id": "t1", "politician_name": "Pol_A", "chamber": "Senate",
                "ticker": "XOM", "transaction_type": "Buy",
                "transaction_date": "2025-04-01", "filing_date": "2025-04-05",
                "amount_range": "$15,001 - $50,000", "data_hash": "h1",
            },
            {
                "id": "t2", "politician_name": "Pol_B", "chamber": "Senate",
                "ticker": "XOM", "transaction_type": "Buy",
                "transaction_date": "2025-04-02", "filing_date": "2025-04-06",
                "amount_range": "$15,001 - $50,000", "data_hash": "h2",
            },
        ]
        db = make_test_db(tmp_path, trades)
        detector = ConvergenceDetector(db_path=db)
        events = detector.detect()
        assert len([e for e in events if e["ticker"] == "XOM"]) == 1

    def test_one_politician_multiple_trades_no_convergence(self, tmp_path):
        """1 位議員 5 筆交易 → 不算收斂。"""
        trades = [
            {
                "id": f"t{i}", "politician_name": "Solo_Trader", "chamber": "Senate",
                "ticker": "BA", "transaction_type": "Buy",
                "transaction_date": f"2025-04-{10+i:02d}",
                "filing_date": f"2025-04-{15+i:02d}",
                "amount_range": "$15,001 - $50,000", "data_hash": f"h{i}",
            }
            for i in range(5)
        ]
        db = make_test_db(tmp_path, trades)
        detector = ConvergenceDetector(db_path=db)
        events = detector.detect()
        ba_events = [e for e in events if e["ticker"] == "BA"]
        assert len(ba_events) == 0


# ─────────────────────────────────────────
# Empty DB / No Trades 邊緣情況
# ─────────────────────────────────────────

class TestEdgeCases:
    """邊緣情況測試。"""

    def test_no_valid_tickers(self, tmp_path):
        """交易無 ticker → 空結果。"""
        trades = [
            {
                "id": "t1", "politician_name": "Alice", "chamber": "Senate",
                "ticker": "", "transaction_type": "Buy",
                "transaction_date": "2025-01-10", "filing_date": "2025-01-15",
                "amount_range": "$15,001 - $50,000", "data_hash": "h1",
            },
            {
                "id": "t2", "politician_name": "Bob", "chamber": "Senate",
                "ticker": None, "transaction_type": "Buy",
                "transaction_date": "2025-01-12", "filing_date": "2025-01-18",
                "amount_range": "$15,001 - $50,000", "data_hash": "h2",
            },
        ]
        db = make_test_db(tmp_path, trades)
        detector = ConvergenceDetector(db_path=db)
        events = detector.detect()
        assert events == []

    def test_unrecognized_transaction_types(self, tmp_path):
        """無法辨識的 transaction_type (Exchange) → 空結果。"""
        trades = [
            {
                "id": "t1", "politician_name": "Alice", "chamber": "Senate",
                "ticker": "AAPL", "transaction_type": "Exchange",
                "transaction_date": "2025-01-10", "filing_date": "2025-01-15",
                "amount_range": "$15,001 - $50,000", "data_hash": "h1",
            },
            {
                "id": "t2", "politician_name": "Bob", "chamber": "Senate",
                "ticker": "AAPL", "transaction_type": "Exchange",
                "transaction_date": "2025-01-12", "filing_date": "2025-01-18",
                "amount_range": "$15,001 - $50,000", "data_hash": "h2",
            },
        ]
        db = make_test_db(tmp_path, trades)
        detector = ConvergenceDetector(db_path=db)
        events = detector.detect()
        assert events == []

    def test_invalid_dates_are_skipped(self, tmp_path):
        """無效日期的交易應被跳過。"""
        trades = [
            {
                "id": "t1", "politician_name": "Alice", "chamber": "Senate",
                "ticker": "AAPL", "transaction_type": "Buy",
                "transaction_date": "not-a-date", "filing_date": "2025-01-15",
                "amount_range": "$15,001 - $50,000", "data_hash": "h1",
            },
            {
                "id": "t2", "politician_name": "Bob", "chamber": "Senate",
                "ticker": "AAPL", "transaction_type": "Buy",
                "transaction_date": "2025-01-12", "filing_date": "2025-01-18",
                "amount_range": "$15,001 - $50,000", "data_hash": "h2",
            },
        ]
        db = make_test_db(tmp_path, trades)
        detector = ConvergenceDetector(db_path=db)
        events = detector.detect()
        # Only 1 valid trade (Bob), so no convergence possible
        aapl_events = [e for e in events if e["ticker"] == "AAPL"]
        assert len(aapl_events) == 0


# ─────────────────────────────────────────
# 大量收斂（10+ 議員）處理
# ─────────────────────────────────────────

class TestLargeConvergence:
    """測試大量議員同一 ticker 的收斂。"""

    def test_ten_politicians_convergence(self, tmp_path):
        """10 位議員在 7 天內同向買入同一 ticker → 正確偵測 + 高分。"""
        base_date = date(2025, 5, 1)
        trades = [
            {
                "id": f"t{i}", "politician_name": f"Politician_{i}",
                "chamber": "Senate" if i % 2 == 0 else "House",
                "ticker": "NVDA", "transaction_type": "Buy",
                "transaction_date": str(base_date + timedelta(days=i % 7)),
                "filing_date": str(base_date + timedelta(days=10 + i)),
                "amount_range": "$100,001 - $250,000", "data_hash": f"h{i}",
            }
            for i in range(10)
        ]
        db = make_test_db(tmp_path, trades)
        detector = ConvergenceDetector(db_path=db)
        events = detector.detect()
        nvda_events = [e for e in events if e["ticker"] == "NVDA"]
        assert len(nvda_events) >= 1
        top = nvda_events[0]
        assert top["politician_count"] == 10
        # base = 0.5 * (10-1) = 4.5
        assert top["score_breakdown"]["base"] == pytest.approx(4.5)
        # cross_chamber bonus (both House and Senate present)
        assert top["score_breakdown"]["cross_chamber"] == pytest.approx(0.5)
        # burst_bonus should be applied (span <= 7)
        assert top["score_breakdown"]["burst_bonus"] == pytest.approx(BURST_BONUS)

    def test_fifteen_politicians_score_scales(self, tmp_path):
        """15 位議員 → base score = 0.5*(15-1) = 7.0。"""
        base_date = date(2025, 5, 1)
        trades = [
            {
                "id": f"t{i}", "politician_name": f"Pol_{i}",
                "chamber": "Senate",
                "ticker": "TSLA", "transaction_type": "Buy",
                "transaction_date": str(base_date + timedelta(days=i % 5)),
                "filing_date": str(base_date + timedelta(days=10 + i)),
                "amount_range": "$15,001 - $50,000", "data_hash": f"h{i}",
            }
            for i in range(15)
        ]
        db = make_test_db(tmp_path, trades)
        detector = ConvergenceDetector(db_path=db)
        events = detector.detect()
        tsla_events = [e for e in events if e["ticker"] == "TSLA"]
        assert len(tsla_events) >= 1
        assert tsla_events[0]["politician_count"] == 15
        assert tsla_events[0]["score_breakdown"]["base"] == pytest.approx(7.0)


# ─────────────────────────────────────────
# 重複交易去重測試
# ─────────────────────────────────────────

class TestDeduplication:
    """同一議員同一 ticker 多次交易不應被多次計算在 politician_count 中。"""

    def test_same_politician_multiple_trades_counted_once(self, tmp_path):
        """Alice 買 AAPL 3 次 + Bob 買 1 次 → politician_count = 2（非 4）。"""
        trades = [
            {
                "id": "t1", "politician_name": "Alice", "chamber": "Senate",
                "ticker": "AAPL", "transaction_type": "Buy",
                "transaction_date": "2025-06-01", "filing_date": "2025-06-05",
                "amount_range": "$15,001 - $50,000", "data_hash": "h1",
            },
            {
                "id": "t2", "politician_name": "Alice", "chamber": "Senate",
                "ticker": "AAPL", "transaction_type": "Buy",
                "transaction_date": "2025-06-05", "filing_date": "2025-06-10",
                "amount_range": "$50,001 - $100,000", "data_hash": "h2",
            },
            {
                "id": "t3", "politician_name": "Alice", "chamber": "Senate",
                "ticker": "AAPL", "transaction_type": "Buy",
                "transaction_date": "2025-06-10", "filing_date": "2025-06-15",
                "amount_range": "$15,001 - $50,000", "data_hash": "h3",
            },
            {
                "id": "t4", "politician_name": "Bob", "chamber": "House",
                "ticker": "AAPL", "transaction_type": "Buy",
                "transaction_date": "2025-06-08", "filing_date": "2025-06-12",
                "amount_range": "$15,001 - $50,000", "data_hash": "h4",
            },
        ]
        db = make_test_db(tmp_path, trades)
        detector = ConvergenceDetector(db_path=db)
        events = detector.detect()
        aapl_events = [e for e in events if e["ticker"] == "AAPL"]
        assert len(aapl_events) == 1
        event = aapl_events[0]
        assert event["politician_count"] == 2, "Alice should be counted only once"
        # politicians list should have exactly 2 entries
        assert len(event["politicians"]) == 2

    def test_dedup_picks_earliest_trade_per_politician(self, tmp_path):
        """去重時每位議員取最早的交易作為代表。"""
        trades = [
            {
                "id": "t1", "politician_name": "Alice", "chamber": "Senate",
                "ticker": "META", "transaction_type": "Buy",
                "transaction_date": "2025-06-10", "filing_date": "2025-06-15",
                "amount_range": "$50,001 - $100,000", "data_hash": "h1",
            },
            {
                "id": "t2", "politician_name": "Alice", "chamber": "Senate",
                "ticker": "META", "transaction_type": "Buy",
                "transaction_date": "2025-06-01", "filing_date": "2025-06-05",
                "amount_range": "$15,001 - $50,000", "data_hash": "h2",
            },
            {
                "id": "t3", "politician_name": "Bob", "chamber": "House",
                "ticker": "META", "transaction_type": "Buy",
                "transaction_date": "2025-06-05", "filing_date": "2025-06-10",
                "amount_range": "$15,001 - $50,000", "data_hash": "h3",
            },
        ]
        db = make_test_db(tmp_path, trades)
        detector = ConvergenceDetector(db_path=db)
        events = detector.detect()
        meta_events = [e for e in events if e["ticker"] == "META"]
        assert len(meta_events) == 1
        event = meta_events[0]
        # Alice's representative trade should be the earliest (2025-06-01)
        alice_entry = next(p for p in event["politicians"] if p["name"] == "Alice")
        assert alice_entry["date"] == "2025-06-01"


# ─────────────────────────────────────────
# save_signals 測試
# ─────────────────────────────────────────

class TestSaveSignals:
    """測試收斂事件寫入資料庫。"""

    def test_save_and_reload(self, tmp_path):
        """偵測到的事件寫入 DB 後可被查詢回來。"""
        trades = [
            {
                "id": "t1", "politician_name": "Alice", "chamber": "Senate",
                "ticker": "AAPL", "transaction_type": "Buy",
                "transaction_date": "2025-01-10", "filing_date": "2025-01-15",
                "amount_range": "$15,001 - $50,000", "data_hash": "h1",
            },
            {
                "id": "t2", "politician_name": "Bob", "chamber": "House",
                "ticker": "AAPL", "transaction_type": "Buy",
                "transaction_date": "2025-01-12", "filing_date": "2025-01-18",
                "amount_range": "$15,001 - $50,000", "data_hash": "h2",
            },
        ]
        db = make_test_db(tmp_path, trades)
        detector = ConvergenceDetector(db_path=db)
        events = detector.detect()
        result = detector.save_signals(events)
        assert result["inserted"] >= 1
        # Verify data in DB
        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM convergence_signals WHERE ticker='AAPL'").fetchall()
        conn.close()
        assert len(rows) >= 1
        assert rows[0]["direction"] == "Buy"
        assert rows[0]["politician_count"] == 2
