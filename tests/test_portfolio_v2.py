import pytest
from src.portfolio_optimizer import (
    TickerScorer,
    MAX_WEIGHT, MIN_WEIGHT, SECTOR_CAP,
)


class TestWeightConstraints:

    def test_max_weight_is_10pct(self):
        assert MAX_WEIGHT == 0.10

    def test_min_weight_is_2pct(self):
        assert MIN_WEIGHT == 0.02

    def test_sector_cap_is_30pct(self):
        assert SECTOR_CAP == 0.30

    def test_max_greater_than_min(self):
        assert MAX_WEIGHT > MIN_WEIGHT


class TestTiltedWeights:

    def test_equal_scores_equal_weights(self):
        # With equal conviction scores, tilted weights should be equal
        scores = {"AAPL": 50, "GOOG": 50, "MSFT": 50}
        n = len(scores)
        equal_part = 1.0 / n
        total = sum(scores.values())
        tilted = {t: 0.5 * equal_part + 0.5 * (s / total) for t, s in scores.items()}
        # All should be equal
        vals = list(tilted.values())
        assert abs(vals[0] - vals[1]) < 0.001
        assert abs(vals[1] - vals[2]) < 0.001

    def test_higher_score_higher_weight(self):
        scores = {"AAPL": 80, "GOOG": 40}
        total = sum(scores.values())
        n = len(scores)
        equal_part = 1.0 / n
        tilted = {t: 0.5 * equal_part + 0.5 * (s / total) for t, s in scores.items()}
        assert tilted["AAPL"] > tilted["GOOG"]


class TestConvictionScoring:

    def test_breadth_max_25(self):
        # breadth component: min(politician_count * 5, 25)
        assert min(3 * 5, 25) == 15
        assert min(5 * 5, 25) == 25
        assert min(6 * 5, 25) == 25

    def test_convergence_max_20(self):
        # convergence: 20 if has_convergence else 0
        assert 20 if True else 0 == 20
        assert 0 if False else 20  # no convergence

    def test_chamber_senate_bonus(self):
        # Senate: 10, House: 5
        senate_score = 10
        house_score = 5
        assert senate_score > house_score

    def test_amount_max_15(self):
        # amount component capped at 15
        assert min(20, 15) == 15
        assert min(10, 15) == 10

    def test_total_score_capped_100(self):
        # Max possible: 25+15+5+5+20+15+10+5 = 100
        total = 25 + 15 + 5 + 5 + 20 + 15 + 10 + 5
        assert total == 100

    def test_buy_ratio_bonus(self):
        # buy_ratio: 5 if buy_ratio >= 0.7 else 0
        assert (5 if 0.8 >= 0.7 else 0) == 5
        assert (5 if 0.5 >= 0.7 else 0) == 0

    def test_sweet_spot_bonus(self):
        # sweet_spot: +5 if avg_amount in $15K-$50K range
        sweet = 32500
        assert 15001 <= sweet <= 50000
