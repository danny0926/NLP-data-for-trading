"""
tests/test_signal_decay.py — Signal Decay 機制測試

測試範圍：
- Signal decay 公式: filing_date + 20d 後線性衰減 (RB-004)
  - day 0-20: decay_factor = 1.0 (無衰減)
  - day 20: decay_factor = 1.0 (臨界點)
  - day 30: decay_factor = 0.5 (半衰減)
  - day 40: decay_factor = 0.0 (完全衰減)
  - day > 40: decay_factor = 0.0 (不低於 0)
- 整合測試: SignalEnhancer.enhance_signals() 的 decay_factor 欄位
- edge cases: 無效日期、None filing_date
"""

import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ─────────────────────────────────────────
# 純公式測試 (不依賴 class)
# ─────────────────────────────────────────

def compute_decay_factor(days_since_filing: int) -> float:
    """複製 signal_enhancer.py 的 decay 公式，便於單元測試。"""
    if days_since_filing > 20:
        return max(0.0, 1.0 - (days_since_filing - 20) / 20.0)
    return 1.0


class TestDecayFormula:
    """直接測試 decay 公式數學正確性。"""

    def test_no_decay_at_day_0(self):
        """filing 當天 → decay_factor = 1.0。"""
        assert compute_decay_factor(0) == pytest.approx(1.0)

    def test_no_decay_at_day_10(self):
        """day 10 → decay_factor = 1.0 (尚在保護期)。"""
        assert compute_decay_factor(10) == pytest.approx(1.0)

    def test_no_decay_at_day_20(self):
        """day 20 (臨界點) → decay_factor = 1.0。"""
        assert compute_decay_factor(20) == pytest.approx(1.0)

    def test_half_decay_at_day_30(self):
        """day 30 → decay_factor = 0.5 (線性衰減中點)。"""
        assert compute_decay_factor(30) == pytest.approx(0.5)

    def test_full_decay_at_day_40(self):
        """day 40 → decay_factor = 0.0 (完全衰減)。"""
        assert compute_decay_factor(40) == pytest.approx(0.0)

    def test_clamped_to_zero_after_day_40(self):
        """day 50 → decay_factor = 0.0 (不低於 0)。"""
        assert compute_decay_factor(50) == pytest.approx(0.0)

    def test_clamped_to_zero_at_day_100(self):
        """day 100 → decay_factor = 0.0。"""
        assert compute_decay_factor(100) == pytest.approx(0.0)

    def test_decay_at_day_21(self):
        """day 21 (剛過臨界點) → decay_factor = 1 - 1/20 = 0.95。"""
        assert compute_decay_factor(21) == pytest.approx(0.95, abs=1e-6)

    def test_decay_at_day_25(self):
        """day 25 → decay_factor = 1 - 5/20 = 0.75。"""
        assert compute_decay_factor(25) == pytest.approx(0.75, abs=1e-6)

    def test_decay_is_linear(self):
        """decay 應為線性: 每天衰減幅度相同 (1/20 = 0.05)。"""
        d1 = compute_decay_factor(25)
        d2 = compute_decay_factor(26)
        d3 = compute_decay_factor(27)
        step1 = round(d1 - d2, 6)
        step2 = round(d2 - d3, 6)
        assert step1 == pytest.approx(step2, abs=1e-6), "Decay 應為等步長線性"
        assert step1 == pytest.approx(0.05, abs=1e-6)

    def test_decay_never_negative(self):
        """各種天數下 decay_factor 不得為負。"""
        for days in range(0, 200, 10):
            assert compute_decay_factor(days) >= 0.0


# ─────────────────────────────────────────
# Helper: 建立測試用 DB
# ─────────────────────────────────────────

def make_test_db_for_enhancer(tmp_path, filing_date_str,
                               signal_strength: float = 0.7) -> str:
    """建立帶有 alpha_signals + signal_quality_scores 表的臨時 DB。"""
    db = tmp_path / "test.db"
    conn = sqlite3.connect(str(db))
    cur = conn.cursor()

    # _load_alpha_signals 需要 LEFT JOIN signal_quality_scores
    cur.execute("""
        CREATE TABLE signal_quality_scores (
            id INTEGER PRIMARY KEY,
            trade_id TEXT UNIQUE,
            politician_name TEXT,
            ticker TEXT,
            sqs REAL,
            grade TEXT,
            action TEXT,
            actionability REAL,
            timeliness REAL,
            conviction REAL,
            information_edge REAL,
            market_impact REAL,
            scored_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE alpha_signals (
            id INTEGER PRIMARY KEY,
            trade_id TEXT,
            ticker TEXT,
            asset_name TEXT,
            politician_name TEXT,
            chamber TEXT,
            transaction_type TEXT,
            transaction_date TEXT,
            filing_date TEXT,
            amount_range TEXT,
            direction TEXT,
            expected_alpha_5d REAL,
            expected_alpha_20d REAL,
            confidence REAL,
            signal_strength REAL,
            combined_multiplier REAL,
            convergence_bonus REAL,
            has_convergence INTEGER,
            politician_grade TEXT,
            filing_lag_days INTEGER,
            sqs_score REAL,
            sqs_grade TEXT,
            reasoning TEXT,
            created_at TEXT
        )
    """)

    cur.execute("""
        INSERT INTO alpha_signals
        (trade_id, ticker, asset_name, politician_name, chamber,
         transaction_type, transaction_date, filing_date, amount_range,
         direction, expected_alpha_5d, expected_alpha_20d, confidence,
         signal_strength, filing_lag_days, sqs_score, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "trade-001", "AAPL", "Apple Inc.", "Alice Smith", "Senate",
        "Buy", "2025-01-01", filing_date_str, "$15,001 - $50,000",
        "LONG", 0.0077, 0.0079, 0.8,
        signal_strength, 5, 65.0,
        "2025-01-05 12:00:00"
    ))

    conn.commit()
    conn.close()
    return str(db)


# ─────────────────────────────────────────
# SignalEnhancer 整合測試 (decay_factor 欄位)
# ─────────────────────────────────────────

class TestSignalEnhancerDecay:
    """透過 SignalEnhancer.enhance_signals() 驗證 decay_factor 欄位。"""

    def _get_enhancer_with_mock_vix(self, db_path: str):
        """建立 SignalEnhancer，mock VIX 為 goldilocks (1.0x) 以隔離 VIX 影響。"""
        from src.signal_enhancer import SignalEnhancer

        enhancer = SignalEnhancer(db_path=db_path)
        enhancer.vix_detector = MagicMock()
        enhancer.vix_detector.classify_regime.return_value = {
            "zone": "goldilocks",
            "label": "Goldilocks",
            "multiplier": 1.0,
            "vix": 15.0,
        }
        return enhancer

    def test_decay_factor_one_for_fresh_signal(self, tmp_path):
        """filing_date = 今天 → decay_factor = 1.0。"""
        today = date.today().strftime("%Y-%m-%d")
        db = make_test_db_for_enhancer(tmp_path, today)
        enhancer = self._get_enhancer_with_mock_vix(db)
        results = enhancer.enhance_signals()
        assert len(results) == 1
        assert results[0]["decay_factor"] == pytest.approx(1.0, abs=1e-4)

    def test_decay_factor_one_at_day_20(self, tmp_path):
        """filing_date = 20 天前 → decay_factor = 1.0 (臨界點)。"""
        filing = (date.today() - timedelta(days=20)).strftime("%Y-%m-%d")
        db = make_test_db_for_enhancer(tmp_path, filing)
        enhancer = self._get_enhancer_with_mock_vix(db)
        results = enhancer.enhance_signals()
        assert len(results) == 1
        assert results[0]["decay_factor"] == pytest.approx(1.0, abs=1e-4)

    def test_decay_factor_half_at_day_30(self, tmp_path):
        """filing_date = 30 天前 → decay_factor = 0.5。"""
        filing = (date.today() - timedelta(days=30)).strftime("%Y-%m-%d")
        db = make_test_db_for_enhancer(tmp_path, filing)
        enhancer = self._get_enhancer_with_mock_vix(db)
        results = enhancer.enhance_signals()
        assert len(results) == 1
        assert results[0]["decay_factor"] == pytest.approx(0.5, abs=1e-4)

    def test_decay_factor_zero_at_day_40(self, tmp_path):
        """filing_date = 40 天前 → decay_factor = 0.0。"""
        filing = (date.today() - timedelta(days=40)).strftime("%Y-%m-%d")
        db = make_test_db_for_enhancer(tmp_path, filing)
        enhancer = self._get_enhancer_with_mock_vix(db)
        results = enhancer.enhance_signals()
        assert len(results) == 1
        assert results[0]["decay_factor"] == pytest.approx(0.0, abs=1e-4)

    def test_decay_factor_zero_at_day_60(self, tmp_path):
        """filing_date = 60 天前 → decay_factor = 0.0 (不低於 0)。"""
        filing = (date.today() - timedelta(days=60)).strftime("%Y-%m-%d")
        db = make_test_db_for_enhancer(tmp_path, filing)
        enhancer = self._get_enhancer_with_mock_vix(db)
        results = enhancer.enhance_signals()
        assert len(results) == 1
        assert results[0]["decay_factor"] == pytest.approx(0.0, abs=1e-4)

    def test_enhanced_strength_reduced_by_decay(self, tmp_path):
        """舊信號 (day 30) 的 enhanced_strength 應低於新信號 (day 0)。"""
        today = date.today().strftime("%Y-%m-%d")
        old_date = (date.today() - timedelta(days=30)).strftime("%Y-%m-%d")

        dir_new = tmp_path / "new"
        dir_old = tmp_path / "old"
        dir_new.mkdir()
        dir_old.mkdir()
        db_new = make_test_db_for_enhancer(dir_new, today, signal_strength=0.7)
        db_old = make_test_db_for_enhancer(dir_old, old_date, signal_strength=0.7)

        enhancer_new = self._get_enhancer_with_mock_vix(db_new)
        enhancer_old = self._get_enhancer_with_mock_vix(db_old)

        results_new = enhancer_new.enhance_signals()
        results_old = enhancer_old.enhance_signals()

        assert len(results_new) == 1 and len(results_old) == 1
        # 舊信號因衰減，enhanced_strength 應更低
        assert results_old[0]["enhanced_strength"] < results_new[0]["enhanced_strength"]

    def test_decay_factor_none_filing_date_no_decay(self, tmp_path):
        """filing_date = None → 不套用衰減，decay_factor = 1.0。"""
        db = make_test_db_for_enhancer(tmp_path, None)
        enhancer = self._get_enhancer_with_mock_vix(db)
        results = enhancer.enhance_signals()
        assert len(results) == 1
        assert results[0]["decay_factor"] == pytest.approx(1.0, abs=1e-4)

    def test_decay_factor_invalid_date_no_decay(self, tmp_path):
        """filing_date = 無效字串 → 解析失敗，不套用衰減，decay_factor = 1.0。"""
        db = make_test_db_for_enhancer(tmp_path, "not-a-date")
        enhancer = self._get_enhancer_with_mock_vix(db)
        results = enhancer.enhance_signals()
        assert len(results) == 1
        assert results[0]["decay_factor"] == pytest.approx(1.0, abs=1e-4)

    def test_decay_factor_in_output_dict(self, tmp_path):
        """output dict 必須包含 decay_factor 欄位。"""
        today = date.today().strftime("%Y-%m-%d")
        db = make_test_db_for_enhancer(tmp_path, today)
        enhancer = self._get_enhancer_with_mock_vix(db)
        results = enhancer.enhance_signals()
        assert len(results) == 1
        assert "decay_factor" in results[0]

    def test_decay_factor_rounded_to_4_decimals(self, tmp_path):
        """decay_factor 四捨五入至 4 位小數。"""
        filing = (date.today() - timedelta(days=25)).strftime("%Y-%m-%d")
        db = make_test_db_for_enhancer(tmp_path, filing)
        enhancer = self._get_enhancer_with_mock_vix(db)
        results = enhancer.enhance_signals()
        factor = results[0]["decay_factor"]
        # 確認不超過 4 位小數
        assert factor == round(factor, 4)
