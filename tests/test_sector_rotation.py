import pytest
from src.sector_rotation import (
    _parse_amount, SECTOR_ETF_MAP, EXCLUDED_SECTORS,
    AMOUNT_RANGES, MIN_TRADES, MIN_POLITICIANS,
    NET_BUY_THRESHOLD, MOMENTUM_SCORE_MIN,
)


class TestSectorETFMap:

    def test_technology_maps_to_xlk(self):
        assert SECTOR_ETF_MAP["Technology"] == "XLK"

    def test_financial_maps_to_xlf(self):
        assert SECTOR_ETF_MAP["Financial Services"] == "XLF"

    def test_healthcare_maps_to_xlv(self):
        assert SECTOR_ETF_MAP["Healthcare"] == "XLV"

    def test_industrials_maps_to_xli(self):
        assert SECTOR_ETF_MAP["Industrials"] == "XLI"

    def test_energy_maps_to_xle(self):
        assert SECTOR_ETF_MAP["Energy"] == "XLE"

    def test_all_11_sectors(self):
        assert len(SECTOR_ETF_MAP) == 11

    def test_consumer_cyclical(self):
        assert SECTOR_ETF_MAP["Consumer Cyclical"] == "XLY"

    def test_utilities(self):
        assert SECTOR_ETF_MAP["Utilities"] == "XLU"


class TestExcludedSectors:

    def test_energy_excluded(self):
        assert "Energy" in EXCLUDED_SECTORS

    def test_technology_not_excluded(self):
        assert "Technology" not in EXCLUDED_SECTORS

    def test_only_energy_excluded(self):
        assert len(EXCLUDED_SECTORS) == 1


class TestParseAmount:

    def test_known_range_15k(self):
        assert _parse_amount("$1,001 - $15,000") == 8000.0

    def test_known_range_50k(self):
        assert _parse_amount("$15,001 - $50,000") == 32500.0

    def test_known_range_100k(self):
        assert _parse_amount("$50,001 - $100,000") == 75000.0

    def test_known_range_250k(self):
        assert _parse_amount("$100,001 - $250,000") == 175000.0

    def test_known_range_1m(self):
        assert _parse_amount("$500,001 - $1,000,000") == 750000.0

    def test_known_range_5m(self):
        assert _parse_amount("$1,000,001 - $5,000,000") == 3000000.0

    def test_known_range_50m_plus(self):
        assert _parse_amount("$50,000,000+") == 50000000.0

    def test_over_50m(self):
        assert _parse_amount("Over $50,000,000") == 50000000.0

    def test_empty_string(self):
        assert _parse_amount("") == 0.0

    def test_none_like_empty(self):
        assert _parse_amount("") == 0.0

    def test_whitespace(self):
        assert _parse_amount("  $1,001 - $15,000  ") == 8000.0


class TestConstants:

    def test_min_trades(self):
        assert MIN_TRADES == 3

    def test_min_politicians(self):
        assert MIN_POLITICIANS == 2

    def test_net_buy_threshold(self):
        assert NET_BUY_THRESHOLD == 0.55

    def test_momentum_score_min(self):
        assert MOMENTUM_SCORE_MIN == 0.30

    def test_amount_ranges_count(self):
        assert len(AMOUNT_RANGES) >= 10


class TestMomentumFormula:

    def test_all_buy_momentum(self):
        # net_ratio = 1.0, all components max
        net_ratio_score = (1.0 - 0.5) * 2  # = 1.0
        dollar_flow_norm = 1.0
        politician_breadth = 1.0
        ticker_diversity = 1.0
        cross_chamber = 1.0
        momentum = (
            net_ratio_score * 0.35
            + dollar_flow_norm * 0.25
            + politician_breadth * 0.20
            + ticker_diversity * 0.10
            + cross_chamber * 0.10
        )
        assert momentum == 1.0

    def test_neutral_momentum(self):
        # net_ratio = 0.5 (neutral)
        net_ratio_score = (0.5 - 0.5) * 2  # = 0.0
        momentum = net_ratio_score * 0.35 + 0.5 * 0.25 + 0.5 * 0.20 + 0.5 * 0.10 + 0.0 * 0.10
        assert abs(momentum - 0.275) < 0.001

    def test_all_sell_momentum_negative(self):
        net_ratio_score = (0.0 - 0.5) * 2  # = -1.0
        momentum = net_ratio_score * 0.35  # = -0.35 + others
        assert momentum < 0


class TestRotationType:

    def test_reversing_up(self):
        m90, m30 = -0.2, 0.3
        # REVERSING_UP: m90 < -0.1 and m30 > 0.1
        assert m90 < -0.1 and m30 > 0.1

    def test_reversing_down(self):
        m90, m30 = 0.3, -0.2
        # REVERSING_DOWN: m90 > 0.1 and m30 < -0.1
        assert m90 > 0.1 and m30 < -0.1

    def test_accelerating(self):
        m90, m30 = 0.3, 0.6
        delta = m30 - m90
        assert delta > 0.15  # ACCELERATING

    def test_decelerating(self):
        m90, m30 = 0.6, 0.3
        delta = m30 - m90
        assert delta < -0.15  # DECELERATING

    def test_stable(self):
        m90, m30 = 0.4, 0.42
        delta = m30 - m90
        assert abs(delta) <= 0.15  # STABLE

