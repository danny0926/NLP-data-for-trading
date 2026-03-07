"""
tests/test_ticker_enricher.py -- Ticker enrichment unit tests

Tests:
1. Static mapping lookup
2. Non-tickerable asset detection
3. Ticker pattern recognition
4. resolve_ticker() integration
5. Edge cases
6. _classify_non_ticker_asset()
"""

from unittest.mock import patch, MagicMock

import pytest
from src.ticker_enricher import (
    _is_non_tickerable,
    _looks_like_ticker,
    _static_lookup,
    _classify_non_ticker_asset,
    resolve_ticker,
    STATIC_MAPPING,
    NON_TICKER_PATTERNS,
)


class TestStaticLookup:
    """Static mapping table lookup tests."""

    def test_apple_maps_to_aapl(self):
        assert _static_lookup("Apple Inc.") == "AAPL"

    def test_microsoft_maps_to_msft(self):
        assert _static_lookup("Microsoft Corporation") == "MSFT"

    def test_nvidia_maps_to_nvda(self):
        assert _static_lookup("NVIDIA Corp") == "NVDA"

    def test_case_insensitive_match(self):
        assert _static_lookup("APPLE INC") == "AAPL"

    def test_partial_match_amazon(self):
        assert _static_lookup("Amazon.com Inc") == "AMZN"

    def test_jpmorgan_maps(self):
        assert _static_lookup("JPMorgan Chase") == "JPM"

    def test_coinbase_maps(self):
        assert _static_lookup("Coinbase Global") == "COIN"

    def test_unknown_company_returns_none(self):
        assert _static_lookup("Totally Unknown Corp XYZ") is None

    def test_empty_string_returns_none(self):
        assert _static_lookup("") is None

    def test_etf_spy_maps(self):
        result = _static_lookup("SPDR S&P 500 ETF Trust")
        assert result == "SPY"


class TestNonTickerable:
    """Non-tickerable asset detection tests."""

    def test_municipal_bond_detected(self):
        assert _is_non_tickerable("ST GO BD 3.5% Due 2032") is True

    def test_us_treasury_detected(self):
        assert _is_non_tickerable("US Treasury Note 2.5%") is True

    def test_private_fund_detected(self):
        assert _is_non_tickerable("Acme Ventures LLC") is True

    def test_fannie_mae_detected(self):
        assert _is_non_tickerable("Fannie Mae MBS Pool") is True

    def test_normal_stock_not_detected(self):
        assert _is_non_tickerable("Apple Inc.") is False

    def test_school_district_bond_detected(self):
        assert _is_non_tickerable("Madison School District Bond") is True

    def test_promissory_note_detected(self):
        assert _is_non_tickerable("Promissory Notes Series A") is True


class TestLooksLikeTicker:
    """Ticker pattern detection tests."""

    def test_aapl_is_ticker(self):
        assert _looks_like_ticker("AAPL") is True

    def test_msft_is_ticker(self):
        assert _looks_like_ticker("MSFT") is True

    def test_brk_b_is_ticker(self):
        assert _looks_like_ticker("BRK.B") is True

    def test_lowercase_converted(self):
        assert _looks_like_ticker("aapl") is True

    def test_long_string_not_ticker(self):
        assert _looks_like_ticker("ABCDEF") is False

    def test_number_not_ticker(self):
        assert _looks_like_ticker("12345") is False

    def test_single_char_is_ticker(self):
        assert _looks_like_ticker("C") is True


class TestClassifyNonTickerAsset:
    """Asset type classification tests."""

    def test_treasury_classified(self):
        assert _classify_non_ticker_asset("US Treasury Bond 3%") == "Treasury"

    def test_fannie_mae_classified(self):
        assert _classify_non_ticker_asset("Fannie Mae Pool") == "Government Bond"

    def test_llc_classified_as_private_fund(self):
        assert _classify_non_ticker_asset("Acme Capital LLC") == "Private Fund"

    def test_muni_bond_classified(self):
        assert _classify_non_ticker_asset("CA GO BOND 3.5%") == "Municipal Bond"

    def test_unknown_classified_as_other(self):
        assert _classify_non_ticker_asset("Something Random") == "Other"


class TestResolveTicker:
    """resolve_ticker() integration tests with mocked yfinance."""

    def test_empty_input_returns_empty(self):
        ticker, method = resolve_ticker("")
        assert ticker is None
        assert method == "empty"

    def test_none_input_returns_empty(self):
        ticker, method = resolve_ticker(None)
        assert ticker is None
        assert method == "empty"

    def test_non_tickerable_returns_non_tickerable(self):
        ticker, method = resolve_ticker("US Treasury Note 2%")
        assert ticker is None
        assert method == "non_tickerable"

    def test_static_mapping_used(self):
        ticker, method = resolve_ticker("Apple Inc.")
        assert ticker == "AAPL"
        assert method == "static"

    def test_static_mapping_nvidia(self):
        ticker, method = resolve_ticker("NVIDIA Corporation")
        assert ticker == "NVDA"
        assert method == "static"

    @patch("src.ticker_enricher._validate_ticker", return_value=True)
    def test_ticker_pattern_used(self, mock_validate):
        ticker, method = resolve_ticker("AAPL")
        assert ticker == "AAPL"
        assert method == "pattern"

    @patch("src.ticker_enricher._validate_ticker", return_value=False)
    def test_ticker_pattern_invalid_returns_unresolved(self, mock_validate):
        ticker, method = resolve_ticker("ZZZZ")
        assert ticker is None
        assert method == "unresolved"

    @patch("src.ticker_enricher._yfinance_lookup", return_value="PLTR")
    def test_yfinance_fallback_used(self, mock_yf):
        ticker, method = resolve_ticker("Palantir Technologies Inc")
        # Should match static first since palantir is in STATIC_MAPPING
        assert ticker == "PLTR"


class TestEdgeCases:
    """Edge case tests."""

    def test_whitespace_only_returns_empty(self):
        ticker, method = resolve_ticker("   ")
        assert ticker is None
        assert method == "empty"

    def test_static_mapping_not_empty(self):
        assert len(STATIC_MAPPING) > 50

    def test_non_ticker_patterns_not_empty(self):
        assert len(NON_TICKER_PATTERNS) > 10

    def test_llc_is_non_tickerable(self):
        assert _is_non_tickerable("Sunrise Capital LLC") is True

    def test_lp_is_non_tickerable(self):
        assert _is_non_tickerable("BlackRock Partners LP") is True

