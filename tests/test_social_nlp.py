"""test_social_nlp -- cashtag extraction, sarcasm detection, routing logic"""
import pytest
from src.social_nlp import extract_cashtags, has_sarcasm_signal, needs_deep_analysis, GEMINI_THRESHOLD, CRYPTO_TICKERS

class TestExtractCashtags:
    def test_single(self):
        assert extract_cashtags("Buy $AAPL now") == ["AAPL"]
    def test_multiple(self):
        r = extract_cashtags("$AAPL and $MSFT are hot")
        assert "AAPL" in r and "MSFT" in r
    def test_no_cashtag(self):
        assert extract_cashtags("No tickers here") == []
    def test_crypto_excluded(self):
        assert extract_cashtags("$BTC to the moon") == []
    def test_eth_excluded(self):
        assert extract_cashtags("$ETH pumping") == []
    def test_mixed_crypto_stock(self):
        r = extract_cashtags("$AAPL and $BTC")
        assert r == ["AAPL"]
    def test_lowercase_converted(self):
        assert extract_cashtags("$aapl lowercase") == ["AAPL"]
    def test_empty_string(self):
        assert extract_cashtags("") == []

class TestSarcasmDetection:
    def test_air_quotes(self):
        assert has_sarcasm_signal('This is "great" news')
    def test_reddit_s(self):
        assert has_sarcasm_signal("Totally going to moon /s")
    def test_no_sarcasm(self):
        assert not has_sarcasm_signal("Apple reports strong earnings")
    def test_sarcasm_combo(self):
        assert has_sarcasm_signal("Sure this totally will not crash")

class TestNeedsDeepAnalysis:
    def test_low_confidence_triggers(self):
        assert needs_deep_analysis({"label":"Bullish","score":0.5}, "some text")
    def test_high_confidence_no_trigger(self):
        assert not needs_deep_analysis({"label":"Bullish","score":0.9}, "$AAPL up")
    def test_sarcasm_triggers(self):
        assert needs_deep_analysis({"label":"Bullish","score":0.9}, 'This is "great" for stocks')
    def test_no_cashtag_long_text(self):
        text = "The market is experiencing unprecedented volatility and many analysts are concerned about the upcoming earnings season"
        assert needs_deep_analysis({"label":"Neutral","score":0.85}, text)
    def test_short_with_cashtag(self):
        assert not needs_deep_analysis({"label":"Bullish","score":0.9}, "$AAPL buy")
    def test_threshold_value(self):
        assert GEMINI_THRESHOLD == 0.75

class TestCryptoTickers:
    def test_btc(self): assert "BTC" in CRYPTO_TICKERS
    def test_eth(self): assert "ETH" in CRYPTO_TICKERS
    def test_doge(self): assert "DOGE" in CRYPTO_TICKERS
    def test_aapl_not(self): assert "AAPL" not in CRYPTO_TICKERS
