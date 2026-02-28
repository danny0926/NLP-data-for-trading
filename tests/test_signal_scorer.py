"""
tests/test_signal_scorer.py — SQS 信號評分單元測試

測試項目：
1. Module import
2. SQS 計算：已知輸入 → 驗證輸出範圍
3. Grade 分配：Platinum/Gold/Silver/Bronze/Discard
4. Action 映射
5. Actionability 維度計算
6. Timeliness 維度計算（filing lag）
7. Conviction 維度計算
"""

import pytest
from src.signal_scorer import SignalScorer, GRADE_THRESHOLDS, WEIGHTS


class TestSignalScorerImport:
    def test_module_imports_successfully(self):
        """SignalScorer 模組應可正常 import。"""
        from src.signal_scorer import SignalScorer
        assert SignalScorer is not None

    def test_constants_defined(self):
        """關鍵常數應已定義。"""
        from src.signal_scorer import WEIGHTS, GRADE_THRESHOLDS, AMOUNT_RANGES
        assert isinstance(WEIGHTS, dict)
        assert isinstance(GRADE_THRESHOLDS, list)
        assert isinstance(AMOUNT_RANGES, dict)

    def test_weights_sum_to_one(self):
        """SQS 五維度權重加總應為 1.0。"""
        total = sum(WEIGHTS.values())
        assert abs(total - 1.0) < 1e-9, f"權重加總 = {total}，應為 1.0"


class TestGradeClassification:
    """測試 classify_signal() 的等級分配邏輯。"""

    @pytest.fixture
    def scorer(self):
        return SignalScorer.__new__(SignalScorer)

    @pytest.mark.parametrize("sqs,expected_grade", [
        (85.0, "Platinum"),
        (80.0, "Platinum"),
        (79.9, "Gold"),
        (70.0, "Gold"),
        (60.0, "Gold"),
        (59.9, "Silver"),
        (50.0, "Silver"),
        (40.0, "Silver"),
        (39.9, "Bronze"),
        (30.0, "Bronze"),
        (20.0, "Bronze"),
        (19.9, "Discard"),
        (10.0, "Discard"),
        (0.0,  "Discard"),
    ])
    def test_grade_thresholds(self, scorer, sqs, expected_grade):
        """SQS 分數應落入正確等級。"""
        grade, _ = scorer.classify_signal(sqs)
        assert grade == expected_grade, (
            f"SQS={sqs} 應為 {expected_grade}，實際為 {grade}"
        )

    def test_platinum_action_contains_moo(self, scorer):
        """Platinum 等級的 action 應包含 MOO（Market On Open）。"""
        _, action = scorer.classify_signal(90.0)
        assert "MOO" in action, f"Platinum action='{action}' 應包含 MOO"

    def test_gold_action_contains_moc(self, scorer):
        """Gold 等級的 action 應包含 MOC（Market On Close）。"""
        _, action = scorer.classify_signal(70.0)
        assert "MOC" in action, f"Gold action='{action}' 應包含 MOC"

    def test_discard_action(self, scorer):
        """Discard 等級的 action 應包含「淘汰」。"""
        _, action = scorer.classify_signal(5.0)
        assert "淘汰" in action, f"Discard action='{action}' 應包含「淘汰」"


class TestActionabilityDimension:
    """測試 _calc_actionability() — 可操作性維度。"""

    @pytest.fixture
    def scorer(self):
        return SignalScorer.__new__(SignalScorer)

    def test_ticker_and_buy_direction_returns_100(self, scorer):
        """有 ticker + Buy 方向應得 100 分。"""
        trade = {"ticker": "AAPL", "transaction_type": "Buy", "asset_name": ""}
        assert scorer._calc_actionability(trade) == 100.0

    def test_ticker_and_sale_direction_returns_100(self, scorer):
        """有 ticker + Sale 方向應得 100 分。"""
        trade = {"ticker": "NVDA", "transaction_type": "Sale", "asset_name": ""}
        assert scorer._calc_actionability(trade) == 100.0

    def test_ticker_no_direction_returns_70(self, scorer):
        """有 ticker 但方向不明應得 70 分。"""
        trade = {"ticker": "MSFT", "transaction_type": "Unknown", "asset_name": ""}
        assert scorer._calc_actionability(trade) == 70.0

    def test_no_ticker_sector_keyword_returns_30(self, scorer):
        """無 ticker 但 asset_name 含板塊關鍵字應得 30 分。"""
        trade = {"ticker": None, "transaction_type": "Buy", "asset_name": "biotech fund"}
        assert scorer._calc_actionability(trade) == 30.0

    def test_no_ticker_no_keyword_returns_0(self, scorer):
        """無 ticker 且無板塊關鍵字應得 0 分。"""
        trade = {"ticker": None, "transaction_type": "Buy", "asset_name": "Government Bond"}
        assert scorer._calc_actionability(trade) == 0.0

    def test_empty_ticker_string_treated_as_no_ticker(self, scorer):
        """ticker 為空字串應視為無 ticker。"""
        trade = {"ticker": "", "transaction_type": "Buy", "asset_name": ""}
        result = scorer._calc_actionability(trade)
        assert result in (0.0, 30.0), f"空 ticker 不應得 100 或 70 分，實際={result}"


class TestTimelinessDimension:
    """測試 _calc_timeliness() — 時效性維度（filing lag）。"""

    @pytest.fixture
    def scorer(self):
        return SignalScorer.__new__(SignalScorer)

    @pytest.mark.parametrize("lag_days,expected_score", [
        (0,   100.0),
        (7,   100.0),
        (8,    75.0),
        (15,   75.0),
        (16,   50.0),
        (30,   50.0),
        (31,   25.0),
        (45,   25.0),
        (46,    0.0),
        (100,   0.0),
    ])
    def test_timeliness_by_lag(self, scorer, lag_days, expected_score):
        """各 filing lag 天數應對應正確的時效性分數。"""
        from datetime import date, timedelta
        base = date(2025, 1, 1)
        trade = {
            "transaction_date": base.strftime("%Y-%m-%d"),
            "filing_date": (base + timedelta(days=lag_days)).strftime("%Y-%m-%d"),
        }
        result = scorer._calc_timeliness(trade)
        assert result == expected_score, (
            f"lag={lag_days}天 應得 {expected_score}，實際={result}"
        )

    def test_missing_dates_returns_conservative_score(self, scorer):
        """缺少日期時應回傳保守中間分數（25.0）。"""
        trade = {"transaction_date": None, "filing_date": None}
        result = scorer._calc_timeliness(trade)
        assert result == 25.0

    def test_invalid_date_format_returns_25(self, scorer):
        """非法日期格式應回傳 25.0（不應拋出例外）。"""
        trade = {"transaction_date": "not-a-date", "filing_date": "2025-01-20"}
        result = scorer._calc_timeliness(trade)
        assert result == 25.0


class TestConvictionDimension:
    """測試 _calc_conviction() — 確信度維度。"""

    @pytest.fixture
    def scorer(self):
        return SignalScorer.__new__(SignalScorer)

    def test_high_amount_self_owner_high_confidence(self, scorer):
        """大額 + Self owner + 高 extraction confidence 應得高分。"""
        trade = {
            "amount_range": "$500,001 - $1,000,000",
            "owner": "Self",
            "extraction_confidence": 0.95,
            "_multi_same_direction": 0,
        }
        result = scorer._calc_conviction(trade)
        assert result >= 60.0, f"高確信交易應得 >= 60，實際={result}"

    def test_low_amount_no_owner_returns_low_score(self, scorer):
        """小額 + 無 owner + 低 confidence 應得低分。"""
        trade = {
            "amount_range": "$1,001 - $15,000",
            "owner": "",
            "extraction_confidence": 0.5,
            "_multi_same_direction": 0,
        }
        result = scorer._calc_conviction(trade)
        assert result <= 30.0, f"低確信交易應得 <= 30，實際={result}"

    def test_conviction_capped_at_100(self, scorer):
        """確信度最高不超過 100。"""
        trade = {
            "amount_range": "$50,000,000+",
            "owner": "Self",
            "extraction_confidence": 1.0,
            "_multi_same_direction": 5,
        }
        result = scorer._calc_conviction(trade)
        assert result <= 100.0, f"確信度超過 100：{result}"

    def test_multi_same_direction_adds_bonus(self, scorer):
        """多筆同方向交易應增加確信度。"""
        base_trade = {
            "amount_range": "$15,001 - $50,000",
            "owner": "Self",
            "extraction_confidence": 0.8,
            "_multi_same_direction": 0,
        }
        multi_trade = dict(base_trade)
        multi_trade["_multi_same_direction"] = 3

        base_score = scorer._calc_conviction(base_trade)
        multi_score = scorer._calc_conviction(multi_trade)
        assert multi_score > base_score, "多筆同方向應比單筆得分高"


class TestFullSQSCalculation:
    """測試完整的 score_signal() 端到端計算。"""

    @pytest.fixture
    def scorer(self):
        return SignalScorer.__new__(SignalScorer)

    def test_score_signal_returns_required_keys(self, scorer, sample_buy_trade):
        """score_signal() 應回傳所有必要欄位。"""
        result = scorer.score_signal(sample_buy_trade)
        required_keys = ["sqs", "grade", "action", "dimensions", "trade_id", "politician_name", "ticker"]
        for key in required_keys:
            assert key in result, f"score_signal() 回傳值缺少欄位 '{key}'"

    def test_score_signal_sqs_in_valid_range(self, scorer, sample_buy_trade):
        """SQS 分數應在 0~100 之間。"""
        result = scorer.score_signal(sample_buy_trade)
        assert 0.0 <= result["sqs"] <= 100.0, f"SQS={result['sqs']} 超出範圍"

    def test_score_signal_dimensions_all_present(self, scorer, sample_buy_trade):
        """dimensions 字典應包含所有五個維度。"""
        result = scorer.score_signal(sample_buy_trade)
        dims = result["dimensions"]
        expected_dims = ["actionability", "timeliness", "conviction", "information_edge", "market_impact"]
        for dim in expected_dims:
            assert dim in dims, f"dimensions 缺少 '{dim}'"

    def test_score_signal_dimensions_in_range(self, scorer, sample_buy_trade):
        """每個維度分數應在 0~100 之間。"""
        result = scorer.score_signal(sample_buy_trade)
        for dim, val in result["dimensions"].items():
            assert 0.0 <= val <= 100.0, f"維度 '{dim}' = {val} 超出 0-100 範圍"

    def test_full_actionable_trade_gets_high_sqs(self, scorer):
        """完整可操作交易（有 ticker + Buy + 快速申報）應得到合理分數。"""
        trade = {
            "id": "test-full",
            "ticker": "AAPL",
            "transaction_type": "Buy",
            "transaction_date": "2025-01-10",
            "filing_date": "2025-01-12",  # lag = 2 天 → 100 分
            "amount_range": "$15,001 - $50,000",
            "owner": "Self",
            "extraction_confidence": 0.95,
            "politician_name": "Unknown",
            "asset_name": "Apple Inc.",
            "_multi_same_direction": 0,
        }
        result = scorer.score_signal(trade)
        # actionability=100, timeliness=100 → 加權後至少 50
        assert result["sqs"] >= 40.0, f"完整可操作交易 SQS 應 >= 40，實際={result['sqs']}"
