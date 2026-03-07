"""Tests for signal_enhancer module — VIX regime, PACS scoring, confidence v2."""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.signal_enhancer import (
    VIXRegimeDetector,
    SignalEnhancer,
    VIX_ZONES,
    PACS_WEIGHT_SIGNAL_STRENGTH,
    PACS_WEIGHT_FILING_LAG_INV,
    PACS_WEIGHT_OPTIONS_SENTIMENT,
    PACS_WEIGHT_CONVERGENCE,
    CONFIDENCE_V2_WEIGHTS,
)


# ─────────────────────────────────────────
# VIX Regime Tests
# ─────────────────────────────────────────

class TestVIXRegimeDetector:

    def test_classify_ultra_low(self):
        detector = VIXRegimeDetector()
        result = detector.classify_regime(vix_value=12.0)
        assert result["zone"] == "ultra_low"
        assert result["multiplier"] == 0.6

    def test_classify_goldilocks(self):
        detector = VIXRegimeDetector()
        result = detector.classify_regime(vix_value=15.0)
        assert result["zone"] == "goldilocks"
        assert result["multiplier"] == 1.3

    def test_classify_moderate(self):
        detector = VIXRegimeDetector()
        result = detector.classify_regime(vix_value=18.0)
        assert result["zone"] == "moderate"
        assert result["multiplier"] == 0.8

    def test_classify_high(self):
        detector = VIXRegimeDetector()
        result = detector.classify_regime(vix_value=25.0)
        assert result["zone"] == "high"
        assert result["multiplier"] == 0.5

    def test_classify_extreme(self):
        detector = VIXRegimeDetector()
        result = detector.classify_regime(vix_value=35.0)
        assert result["zone"] == "extreme"
        assert result["multiplier"] == 0.3

    def test_classify_boundary_14(self):
        """VIX=14 should be goldilocks (14 <= vix < 16)."""
        detector = VIXRegimeDetector()
        result = detector.classify_regime(vix_value=14.0)
        assert result["zone"] == "goldilocks"

    def test_classify_boundary_16(self):
        """VIX=16 should be moderate (16 <= vix < 20)."""
        detector = VIXRegimeDetector()
        result = detector.classify_regime(vix_value=16.0)
        assert result["zone"] == "moderate"

    def test_classify_none_with_mock(self):
        """When VIX fetch fails, should return unknown."""
        from unittest.mock import patch
        detector = VIXRegimeDetector()
        with patch.object(detector, 'get_current_vix', return_value=None):
            result = detector.classify_regime(vix_value=None)
            assert result["zone"] == "unknown"
            assert result["multiplier"] == 1.0

    def test_classify_very_high_vix(self):
        detector = VIXRegimeDetector()
        result = detector.classify_regime(vix_value=80.0)
        assert result["zone"] == "extreme"

    def test_result_structure(self):
        detector = VIXRegimeDetector()
        result = detector.classify_regime(vix_value=15.0)
        assert "zone" in result
        assert "vix" in result
        assert "multiplier" in result
        assert "label" in result


# ─────────────────────────────────────────
# PACS Score Tests
# ─────────────────────────────────────────

class TestPACSScore:

    def _make_enhancer(self):
        return SignalEnhancer(db_path=":memory:")

    def test_pacs_basic_calculation(self):
        enhancer = self._make_enhancer()
        signal = {"signal_strength": 0.8, "filing_lag_days": 10}
        pacs, components = enhancer._calc_pacs_score(signal, None, None)
        assert 0 < pacs <= 1.0

    def test_pacs_higher_strength_gives_higher_score(self):
        enhancer = self._make_enhancer()
        sig_weak = {"signal_strength": 0.3, "filing_lag_days": 15}
        sig_strong = {"signal_strength": 1.2, "filing_lag_days": 15}
        pacs_weak, _ = enhancer._calc_pacs_score(sig_weak, None, None)
        pacs_strong, _ = enhancer._calc_pacs_score(sig_strong, None, None)
        assert pacs_strong > pacs_weak

    def test_pacs_lower_filing_lag_gives_higher_score(self):
        """PACS v3: binary filing_lag — ≤45d gets 1.0, >45d gets 0.7."""
        enhancer = self._make_enhancer()
        sig_fast = {"signal_strength": 0.8, "filing_lag_days": 3}
        sig_slow = {"signal_strength": 0.8, "filing_lag_days": 60}
        pacs_fast, _ = enhancer._calc_pacs_score(sig_fast, None, None)
        pacs_slow, _ = enhancer._calc_pacs_score(sig_slow, None, None)
        assert pacs_fast > pacs_slow

    def test_pacs_convergence_bonus(self):
        enhancer = self._make_enhancer()
        signal = {"signal_strength": 0.8, "filing_lag_days": 15}
        pacs_no_conv, _ = enhancer._calc_pacs_score(signal, None, None)
        pacs_with_conv, _ = enhancer._calc_pacs_score(signal, None, {"score": 3.0})
        assert pacs_with_conv > pacs_no_conv

    def test_pacs_strength_norm_capped_at_1(self):
        enhancer = self._make_enhancer()
        signal = {"signal_strength": 5.0, "filing_lag_days": 15}
        _, components = enhancer._calc_pacs_score(signal, None, None)
        assert components["signal_strength_norm"] <= 1.0

    def test_pacs_zero_lag_gives_max_lag_score(self):
        enhancer = self._make_enhancer()
        signal = {"signal_strength": 0.8, "filing_lag_days": 0}
        _, components = enhancer._calc_pacs_score(signal, None, None)
        assert components["filing_lag_inv"] == pytest.approx(1.0, abs=0.01)

    def test_pacs_none_lag_gives_midpoint(self):
        enhancer = self._make_enhancer()
        signal = {"signal_strength": 0.8, "filing_lag_days": None}
        _, components = enhancer._calc_pacs_score(signal, None, None)
        assert components["filing_lag_inv"] == pytest.approx(0.5, abs=0.01)

    def test_pacs_components_present(self):
        enhancer = self._make_enhancer()
        signal = {"signal_strength": 0.8, "filing_lag_days": 15}
        _, components = enhancer._calc_pacs_score(signal, None, None)
        assert "signal_strength_norm" in components
        assert "filing_lag_inv" in components
        assert "options_sentiment_norm" in components
        assert "convergence_norm" in components

    def test_pacs_contract_bonus_large(self):
        enhancer = self._make_enhancer()
        signal = {"signal_strength": 0.8, "filing_lag_days": 15}
        pacs_no, _ = enhancer._calc_pacs_score(signal, None, None, None)
        pacs_with, comps = enhancer._calc_pacs_score(
            signal, None, None, {"max_amount": 200_000_000}
        )
        assert comps["contract_bonus"] == 0.2
        assert pacs_with > pacs_no

    def test_pacs_options_bullish(self):
        enhancer = self._make_enhancer()
        signal = {"signal_strength": 0.8, "filing_lag_days": 15}
        pacs_neutral, _ = enhancer._calc_pacs_score(signal, None, None)
        pacs_bullish, _ = enhancer._calc_pacs_score(
            signal, {"sentiment": 0.8}, None
        )
        assert pacs_bullish > pacs_neutral


# ─────────────────────────────────────────
# PACS Weights Validation
# ─────────────────────────────────────────

class TestPACSWeights:

    def test_weights_sum_to_one(self):
        total = (
            PACS_WEIGHT_SIGNAL_STRENGTH
            + PACS_WEIGHT_FILING_LAG_INV
            + PACS_WEIGHT_OPTIONS_SENTIMENT
            + PACS_WEIGHT_CONVERGENCE
        )
        assert total == pytest.approx(1.0, abs=1e-6)

    def test_signal_strength_is_dominant(self):
        assert PACS_WEIGHT_SIGNAL_STRENGTH >= 0.5

    def test_confidence_v2_weights_sum_to_one(self):
        total = sum(CONFIDENCE_V2_WEIGHTS.values())
        assert total == pytest.approx(1.0, abs=1e-6)

    def test_sqs_weight_reduced(self):
        assert CONFIDENCE_V2_WEIGHTS["sqs_total"] <= 0.15


# ─────────────────────────────────────────
# VIX Zone Constants Validation
# ─────────────────────────────────────────

class TestVIXZones:

    def test_goldilocks_is_best_multiplier(self):
        assert VIX_ZONES["goldilocks"]["multiplier"] == 1.3
        for name, zone in VIX_ZONES.items():
            if name != "goldilocks":
                assert zone["multiplier"] < VIX_ZONES["goldilocks"]["multiplier"]

    def test_extreme_is_worst_multiplier(self):
        assert VIX_ZONES["extreme"]["multiplier"] == 0.3
        for name, zone in VIX_ZONES.items():
            assert zone["multiplier"] >= VIX_ZONES["extreme"]["multiplier"]

    def test_zones_cover_0_to_100(self):
        """All VIX values 0-100 should map to a zone."""
        detector = VIXRegimeDetector()
        for vix in [0, 5, 10, 13, 14, 15, 16, 19, 20, 29, 30, 50, 99]:
            result = detector.classify_regime(vix_value=vix)
            assert result["zone"] != "unknown"


# ─────────────────────────────────────────
# Ticker Familiarity Tests (RB-021)
# ─────────────────────────────────────────

class TestTickerFamiliarity:
    """Tests for ticker familiarity bonus in PACS scoring (RB-021).

    RB-021: repeat trades 3+ on same ticker show +0.70% vs -1.04% (p=0.045).
    Bonus tiers: 0-2 → 0, 3-4 → 0.05, 5+ → 0.08.
    """

    def _make_enhancer(self):
        return SignalEnhancer(db_path=":memory:")

    def _base_signal(self):
        return {"signal_strength": 0.8, "filing_lag_days": 15}

    def test_familiarity_bonus_zero(self):
        """ticker_trade_count=0 → bonus=0."""
        enhancer = self._make_enhancer()
        _, components = enhancer._calc_pacs_score(
            self._base_signal(), None, None, None, ticker_trade_count=0
        )
        assert components["ticker_familiarity_bonus"] == 0.0
        assert components["ticker_trade_count"] == 0

    def test_familiarity_bonus_one(self):
        """ticker_trade_count=1 → bonus=0."""
        enhancer = self._make_enhancer()
        _, components = enhancer._calc_pacs_score(
            self._base_signal(), None, None, None, ticker_trade_count=1
        )
        assert components["ticker_familiarity_bonus"] == 0.0

    def test_familiarity_bonus_two(self):
        """ticker_trade_count=2 → bonus=0."""
        enhancer = self._make_enhancer()
        _, components = enhancer._calc_pacs_score(
            self._base_signal(), None, None, None, ticker_trade_count=2
        )
        assert components["ticker_familiarity_bonus"] == 0.0

    def test_familiarity_bonus_three(self):
        """ticker_trade_count=3 → bonus=0.05."""
        enhancer = self._make_enhancer()
        _, components = enhancer._calc_pacs_score(
            self._base_signal(), None, None, None, ticker_trade_count=3
        )
        assert components["ticker_familiarity_bonus"] == 0.05

    def test_familiarity_bonus_four(self):
        """ticker_trade_count=4 → bonus=0.05."""
        enhancer = self._make_enhancer()
        _, components = enhancer._calc_pacs_score(
            self._base_signal(), None, None, None, ticker_trade_count=4
        )
        assert components["ticker_familiarity_bonus"] == 0.05

    def test_familiarity_bonus_five(self):
        """ticker_trade_count=5 → bonus=0.08."""
        enhancer = self._make_enhancer()
        _, components = enhancer._calc_pacs_score(
            self._base_signal(), None, None, None, ticker_trade_count=5
        )
        assert components["ticker_familiarity_bonus"] == 0.08

    def test_familiarity_bonus_ten(self):
        """ticker_trade_count=10 → bonus=0.08 (same as 5+)."""
        enhancer = self._make_enhancer()
        _, components = enhancer._calc_pacs_score(
            self._base_signal(), None, None, None, ticker_trade_count=10
        )
        assert components["ticker_familiarity_bonus"] == 0.08

    def test_pacs_cap_with_bonus(self):
        """High PACS base + familiarity bonus must not exceed 1.0."""
        enhancer = self._make_enhancer()
        # Max out everything: high strength, low lag, options, convergence, contract, familiarity
        signal = {"signal_strength": 5.0, "filing_lag_days": 0}
        pacs, components = enhancer._calc_pacs_score(
            signal,
            {"sentiment": 1.0},          # max options
            {"score": 5.0},              # max convergence
            {"max_amount": 200_000_000}, # max contract bonus (0.2)
            ticker_trade_count=10,       # max familiarity bonus (0.08)
        )
        assert pacs <= 1.0

    def test_familiarity_bonus_additive(self):
        """Familiarity bonus is additive, not multiplicative."""
        enhancer = self._make_enhancer()
        sig = self._base_signal()
        pacs_no_fam, _ = enhancer._calc_pacs_score(
            sig, None, None, None, ticker_trade_count=0
        )
        pacs_with_fam, _ = enhancer._calc_pacs_score(
            sig, None, None, None, ticker_trade_count=5
        )
        # Difference should be exactly the bonus value (0.08), not scaled
        assert pacs_with_fam - pacs_no_fam == pytest.approx(0.08, abs=1e-4)
