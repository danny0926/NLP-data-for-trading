"""
tests/test_alpha_signal_generator.py — Alpha 信號生成器單元測試

測試項目：
1. Module import
2. direction 映射：Buy→LONG, Sale→LONG (contrarian)
3. multiplier 計算（chamber / amount / filing_lag / politician_grade）
4. signal_strength 輸出範圍 [0, ∞)（實際值由 alpha × confidence 決定）
5. confidence 輸出範圍 [0, 1]
6. Exchange/未知交易類型回傳 None
7. generate_signal() 回傳 dict 結構
"""

import pytest
from src.alpha_signal_generator import (
    AlphaSignalGenerator,
    BASE_ALPHA,
    CHAMBER_MULTIPLIER,
    AMOUNT_MULTIPLIER,
    FILING_LAG_MULTIPLIER,
    POLITICIAN_GRADE_MULTIPLIER,
    _normalize_direction,
    _get_amount_multiplier,
    _get_filing_lag_multiplier,
    _pis_to_grade,
    _calc_filing_lag,
)


class TestImport:
    def test_module_imports_successfully(self):
        """alpha_signal_generator 模組應可正常 import。"""
        from src.alpha_signal_generator import AlphaSignalGenerator
        assert AlphaSignalGenerator is not None

    def test_base_alpha_constants_positive(self):
        """BASE_ALPHA 的所有數值應為正數（Buy 和 Sale 反向 alpha 均應 > 0）。"""
        for tx_type, alphas in BASE_ALPHA.items():
            for horizon, val in alphas.items():
                assert val > 0, f"BASE_ALPHA[{tx_type}][{horizon}]={val} 應為正數"


class TestDirectionNormalization:
    """測試 _normalize_direction() — 交易類型正規化。"""

    @pytest.mark.parametrize("tx_type,expected", [
        ("Buy",      "Buy"),
        ("Purchase", "Buy"),
        ("purchase", "Buy"),
        ("Sale",     "Sale"),
        ("Sale (Full)", "Sale"),
        ("Sell",     "Sale"),
        ("sell",     "Sale"),
    ])
    def test_known_types_normalized(self, tx_type, expected):
        """已知交易類型應正規化為 Buy 或 Sale。"""
        result = _normalize_direction(tx_type)
        assert result == expected, f"'{tx_type}' 應正規化為 '{expected}'，實際='{result}'"

    @pytest.mark.parametrize("tx_type", ["Exchange", "Gift", "", None])
    def test_unknown_types_return_none(self, tx_type):
        """未知交易類型應回傳 None（不生成訊號）。"""
        result = _normalize_direction(tx_type)
        assert result is None, f"'{tx_type}' 應回傳 None，實際='{result}'"


class TestAmountMultiplier:
    """測試 _get_amount_multiplier() — 金額區間乘數。"""

    def test_best_alpha_range_returns_highest_multiplier(self):
        """$15K-$50K 是研究驗證的最強 alpha 區間，應得最高乘數 1.5。"""
        mult = _get_amount_multiplier("$15,001 - $50,000")
        assert mult == 1.5, f"$15K-$50K 應得 1.5x，實際={mult}"

    def test_empty_amount_returns_default(self):
        """空字串應回傳預設乘數 1.0。"""
        assert _get_amount_multiplier("") == 1.0

    def test_none_amount_returns_default(self):
        """None 應回傳預設乘數 1.0。"""
        assert _get_amount_multiplier(None) == 1.0

    def test_all_known_ranges_return_positive_multiplier(self):
        """所有已知金額區間都應回傳正數乘數。"""
        for range_str in AMOUNT_MULTIPLIER:
            mult = _get_amount_multiplier(range_str)
            assert mult > 0, f"金額區間 '{range_str}' 乘數應 > 0，實際={mult}"


class TestFilingLagMultiplier:
    """測試 _get_filing_lag_multiplier() — 申報時效乘數。"""

    @pytest.mark.parametrize("lag_days,expected_mult", [
        (0,   FILING_LAG_MULTIPLIER["fast"]),    # < 15 天 → fast
        (14,  FILING_LAG_MULTIPLIER["fast"]),
        (15,  FILING_LAG_MULTIPLIER["normal"]),  # 15-44 天 → normal
        (30,  FILING_LAG_MULTIPLIER["normal"]),
        (44,  FILING_LAG_MULTIPLIER["normal"]),
        (45,  FILING_LAG_MULTIPLIER["slow"]),    # >= 45 天 → slow
        (100, FILING_LAG_MULTIPLIER["slow"]),
    ])
    def test_filing_lag_buckets(self, lag_days, expected_mult):
        """各 filing lag 天數應對應正確乘數。"""
        result = _get_filing_lag_multiplier(lag_days)
        assert result == expected_mult, (
            f"lag={lag_days}天 應得 {expected_mult}x，實際={result}"
        )

    def test_none_lag_returns_normal_multiplier(self):
        """缺少 lag 資料應回傳 normal 乘數。"""
        result = _get_filing_lag_multiplier(None)
        assert result == FILING_LAG_MULTIPLIER["normal"]


class TestPISGrade:
    """測試 _pis_to_grade() — PIS 分數等級分配。"""

    @pytest.mark.parametrize("pis,expected_grade", [
        (100.0, "A"),
        (75.0,  "A"),
        (74.9,  "B"),
        (50.0,  "B"),
        (49.9,  "C"),
        (25.0,  "C"),
        (24.9,  "D"),
        (0.0,   "D"),
        (None,  "unknown"),
    ])
    def test_pis_grade_thresholds(self, pis, expected_grade):
        """PIS 分數應對應正確等級。"""
        result = _pis_to_grade(pis)
        assert result == expected_grade, (
            f"PIS={pis} 應為 '{expected_grade}'，實際='{result}'"
        )


class TestFilingLagCalculation:
    def test_normal_lag_calculation(self):
        """正常情況：filing_date - transaction_date 應為正整數。"""
        lag = _calc_filing_lag("2025-01-01", "2025-01-15")
        assert lag == 14

    def test_same_day_returns_zero(self):
        """同一天申報應回傳 0。"""
        lag = _calc_filing_lag("2025-01-15", "2025-01-15")
        assert lag == 0

    def test_negative_lag_clamped_to_zero(self):
        """申報日早於交易日（資料錯誤）應回傳 0，不回傳負數。"""
        lag = _calc_filing_lag("2025-01-15", "2025-01-10")
        assert lag == 0

    def test_invalid_date_returns_none(self):
        """非法日期應回傳 None，不拋出例外。"""
        lag = _calc_filing_lag("not-a-date", "2025-01-15")
        assert lag is None


class TestGenerateSignal:
    """測試 generate_signal() — 核心訊號生成。"""

    @pytest.fixture
    def generator(self):
        return AlphaSignalGenerator.__new__(AlphaSignalGenerator)

    def test_buy_signal_direction_is_long(self, generator, sample_buy_trade):
        """Buy 交易應產生 LONG 方向訊號。"""
        signal = generator.generate_signal(
            trade=sample_buy_trade,
            sqs_data=None,
            convergence_data=None,
            politician_grade="unknown",
        )
        assert signal is not None
        assert signal["direction"] == "LONG"

    def test_sale_signal_direction_is_long(self, generator, sample_sale_trade):
        """Sale 交易（反向 alpha）也應產生 LONG 方向訊號。"""
        signal = generator.generate_signal(
            trade=sample_sale_trade,
            sqs_data=None,
            convergence_data=None,
            politician_grade="unknown",
        )
        assert signal is not None
        assert signal["direction"] == "LONG", (
            "Sale 反向 alpha 訊號方向應為 LONG（回測：國會賣出後股價上漲）"
        )

    def test_exchange_trade_returns_none(self, generator):
        """Exchange 交易類型應回傳 None（無法辨識方向）。"""
        trade = {
            "id": "test-003",
            "ticker": "AAPL",
            "transaction_type": "Exchange",
            "transaction_date": "2025-01-10",
            "filing_date": "2025-01-20",
            "chamber": "House",
            "amount_range": "$15,001 - $50,000",
            "politician_name": "Unknown",
            "asset_name": "",
        }
        signal = generator.generate_signal(
            trade=trade,
            sqs_data=None,
            convergence_data=None,
            politician_grade="unknown",
        )
        assert signal is None

    def test_signal_confidence_in_range(self, generator, sample_buy_trade):
        """confidence 應在 [0, 1] 之間。"""
        signal = generator.generate_signal(
            trade=sample_buy_trade,
            sqs_data=None,
            convergence_data=None,
            politician_grade="B",
        )
        assert signal is not None
        assert 0.0 <= signal["confidence"] <= 1.0, (
            f"confidence={signal['confidence']} 超出 [0,1] 範圍"
        )

    def test_signal_strength_is_non_negative(self, generator, sample_buy_trade):
        """signal_strength 應為非負數。"""
        signal = generator.generate_signal(
            trade=sample_buy_trade,
            sqs_data=None,
            convergence_data=None,
            politician_grade="A",
        )
        assert signal is not None
        assert signal["signal_strength"] >= 0.0, (
            f"signal_strength={signal['signal_strength']} 不應為負數"
        )

    def test_signal_has_required_fields(self, generator, sample_buy_trade):
        """generate_signal() 回傳的 dict 應包含所有必要欄位。"""
        signal = generator.generate_signal(
            trade=sample_buy_trade,
            sqs_data=None,
            convergence_data=None,
            politician_grade="unknown",
        )
        assert signal is not None
        required_fields = [
            "trade_id", "ticker", "direction", "expected_alpha_5d",
            "expected_alpha_20d", "confidence", "signal_strength",
            "combined_multiplier", "has_convergence", "politician_grade",
        ]
        for field in required_fields:
            assert field in signal, f"signal 缺少欄位 '{field}'"

    def test_convergence_bonus_increases_alpha(self, generator, sample_buy_trade):
        """有匯聚訊號加成時，expected_alpha 應高於無匯聚時。"""
        no_conv = generator.generate_signal(
            trade=sample_buy_trade,
            sqs_data=None,
            convergence_data=None,
            politician_grade="unknown",
        )
        with_conv = generator.generate_signal(
            trade=sample_buy_trade,
            sqs_data=None,
            convergence_data={"ticker": "AAPL", "direction": "Buy", "score": 1.5},
            politician_grade="unknown",
        )
        assert with_conv["expected_alpha_5d"] > no_conv["expected_alpha_5d"], (
            "匯聚加分後 expected_alpha_5d 應增加"
        )
        assert with_conv["has_convergence"] is True

    def test_grade_a_multiplier_boosts_alpha(self, generator, sample_buy_trade):
        """Grade A 議員的 expected_alpha 應高於 Grade D。"""
        sig_a = generator.generate_signal(
            trade=sample_buy_trade,
            sqs_data=None,
            convergence_data=None,
            politician_grade="A",
        )
        sig_d = generator.generate_signal(
            trade=sample_buy_trade,
            sqs_data=None,
            convergence_data=None,
            politician_grade="D",
        )
        assert sig_a["expected_alpha_5d"] > sig_d["expected_alpha_5d"], (
            "Grade A 議員的 expected_alpha 應高於 Grade D"
        )
