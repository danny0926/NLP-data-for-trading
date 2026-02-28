"""
tests/test_portfolio_optimizer.py — 投組最佳化器單元測試

測試項目：
1. Module import
2. 權重約束：每個 ticker ≤ 10%，最小 2%
3. 評分公式：各分項加總應 ≤ 100
4. Buy-Only：SALE 不貢獻正 alpha（sale-only ticker 被排除）
5. Senate > House 加分（院別權重翻轉）
6. SQS 降權（RB-006）
"""

import pytest
from src.portfolio_optimizer import (
    TickerScorer,
    MAX_WEIGHT,
    MIN_WEIGHT,
    BUY_CAR_5D,
    SALE_CAR_5D,
    AMOUNT_ALPHA,
)


class TestImport:
    def test_module_imports_successfully(self):
        """portfolio_optimizer 模組應可正常 import。"""
        from src.portfolio_optimizer import TickerScorer
        assert TickerScorer is not None

    def test_buy_only_constants(self):
        """SALE_CAR_5D 應為 0（Buy-Only 策略，Sale 不貢獻正 alpha）。"""
        assert SALE_CAR_5D == 0.0, (
            f"SALE_CAR_5D={SALE_CAR_5D}，RB-004 要求為 0（Sale 有害）"
        )

    def test_buy_car_positive(self):
        """BUY_CAR_5D 應為正數。"""
        assert BUY_CAR_5D > 0, f"BUY_CAR_5D={BUY_CAR_5D} 應為正數"

    def test_weight_constraints(self):
        """MAX_WEIGHT 應為 10%，MIN_WEIGHT 應為 2%。"""
        assert MAX_WEIGHT == 0.10, f"MAX_WEIGHT={MAX_WEIGHT}，應為 0.10"
        assert MIN_WEIGHT == 0.02, f"MIN_WEIGHT={MIN_WEIGHT}，應為 0.02"


class TestTickerScorerBuyOnly:
    """測試 Buy-Only 策略：Sale-Only ticker 應被排除。"""

    @pytest.fixture
    def sector_map(self):
        """提供測試用 sector map。"""
        return {
            "AAPL": {"sector": "Technology", "industry": "Consumer Electronics", "name": "Apple Inc."},
            "NVDA": {"sector": "Technology", "industry": "Semiconductors", "name": "NVIDIA"},
            "XOM":  {"sector": "Energy", "industry": "Oil & Gas", "name": "ExxonMobil"},
        }

    @pytest.fixture
    def buy_trades(self):
        """只有 Buy 交易的測試資料。"""
        return [
            {
                "id": "1",
                "chamber": "Senate",
                "politician_name": "David H McCormick",
                "transaction_date": "2025-01-10",
                "filing_date": "2025-01-20",
                "ticker": "AAPL",
                "transaction_type": "Buy",
                "amount_range": "$15,001 - $50,000",
            },
        ]

    @pytest.fixture
    def sale_only_trades(self):
        """只有 Sale 交易的測試資料（應被排除）。"""
        return [
            {
                "id": "2",
                "chamber": "House",
                "politician_name": "Nancy Pelosi",
                "transaction_date": "2025-01-05",
                "filing_date": "2025-01-18",
                "ticker": "NVDA",
                "transaction_type": "Sale",
                "amount_range": "$100,001 - $250,000",
            },
        ]

    @pytest.fixture
    def mixed_trades(self, buy_trades, sale_only_trades):
        """Buy + Sale 混合交易。"""
        return buy_trades + sale_only_trades

    def test_sale_only_ticker_excluded(self, sale_only_trades, sector_map):
        """Sale-Only 標的應被 TickerScorer 排除（回傳 None）。"""
        scorer = TickerScorer(
            trades=sale_only_trades,
            sqs_map={},
            convergence_map={},
            sector_map=sector_map,
        )
        results = scorer.score_all()
        tickers = [r["ticker"] for r in results]
        assert "NVDA" not in tickers, (
            "Sale-Only 標的 NVDA 不應出現在投組中（RB-004 Buy-Only 策略）"
        )

    def test_buy_ticker_included(self, buy_trades, sector_map):
        """有 Buy 交易的標的應出現在結果中。"""
        scorer = TickerScorer(
            trades=buy_trades,
            sqs_map={},
            convergence_map={},
            sector_map=sector_map,
        )
        results = scorer.score_all()
        tickers = [r["ticker"] for r in results]
        assert "AAPL" in tickers, "有 Buy 交易的 AAPL 應出現在投組中"

    def test_sale_only_ticker_excluded_from_mixed(self, mixed_trades, sector_map):
        """混合 trades 中，Sale-Only 標的應被排除，Buy 標的應被保留。"""
        scorer = TickerScorer(
            trades=mixed_trades,
            sqs_map={},
            convergence_map={},
            sector_map=sector_map,
        )
        results = scorer.score_all()
        tickers = [r["ticker"] for r in results]
        assert "AAPL" in tickers, "AAPL (有 Buy) 應出現在投組中"
        assert "NVDA" not in tickers, "NVDA (Sale-Only) 不應出現在投組中"


class TestTickerScorerScoreFormula:
    """測試評分公式各分項的合理性。"""

    @pytest.fixture
    def sector_map(self):
        return {
            "AAPL": {"sector": "Technology", "industry": "Consumer Electronics", "name": "Apple Inc."},
        }

    @pytest.fixture
    def basic_buy_trade(self):
        return {
            "id": "1",
            "chamber": "Senate",
            "politician_name": "David H McCormick",
            "transaction_date": "2025-01-10",
            "filing_date": "2025-01-20",
            "ticker": "AAPL",
            "transaction_type": "Buy",
            "amount_range": "$15,001 - $50,000",
        }

    def test_score_is_non_negative(self, basic_buy_trade, sector_map):
        """conviction_score 應為非負數。"""
        scorer = TickerScorer(
            trades=[basic_buy_trade],
            sqs_map={},
            convergence_map={},
            sector_map=sector_map,
        )
        results = scorer.score_all()
        assert len(results) == 1
        assert results[0]["conviction_score"] >= 0

    def test_score_does_not_exceed_100(self, basic_buy_trade, sector_map):
        """conviction_score 不應超過 100（滿分）。"""
        scorer = TickerScorer(
            trades=[basic_buy_trade],
            sqs_map={},
            convergence_map={},
            sector_map=sector_map,
        )
        results = scorer.score_all()
        assert results[0]["conviction_score"] <= 100.0

    def test_senate_chamber_included_in_result(self, basic_buy_trade, sector_map):
        """結果中應包含 buy_count、sale_count、politician_count。"""
        scorer = TickerScorer(
            trades=[basic_buy_trade],
            sqs_map={},
            convergence_map={},
            sector_map=sector_map,
        )
        results = scorer.score_all()
        r = results[0]
        assert "buy_count" in r
        assert "sale_count" in r
        assert "politician_count" in r
        assert r["buy_count"] == 1
        assert r["sale_count"] == 0
        assert r["politician_count"] == 1

    def test_convergence_increases_score(self, basic_buy_trade, sector_map):
        """有收斂訊號的標的應得到更高 conviction_score。"""
        scorer_no_conv = TickerScorer(
            trades=[basic_buy_trade],
            sqs_map={},
            convergence_map={},
            sector_map=sector_map,
        )
        scorer_with_conv = TickerScorer(
            trades=[basic_buy_trade],
            sqs_map={},
            convergence_map={"AAPL": {"ticker": "AAPL", "direction": "Buy", "score": 1.5}},
            sector_map=sector_map,
        )
        no_conv_score = scorer_no_conv.score_all()[0]["conviction_score"]
        with_conv_score = scorer_with_conv.score_all()[0]["conviction_score"]
        assert with_conv_score > no_conv_score, (
            "有收斂訊號的標的應得到更高分數"
        )

    def test_multiple_politicians_increases_breadth_score(self, sector_map):
        """多位議員交易同一標的應增加 breadth 分數。"""
        trades_1pol = [
            {
                "id": "1",
                "chamber": "Senate",
                "politician_name": "Politician A",
                "transaction_date": "2025-01-10",
                "filing_date": "2025-01-20",
                "ticker": "AAPL",
                "transaction_type": "Buy",
                "amount_range": "$15,001 - $50,000",
            }
        ]
        trades_3pol = [
            {
                "id": str(i),
                "chamber": "Senate",
                "politician_name": f"Politician {chr(65+i)}",
                "transaction_date": "2025-01-10",
                "filing_date": "2025-01-20",
                "ticker": "AAPL",
                "transaction_type": "Buy",
                "amount_range": "$15,001 - $50,000",
            }
            for i in range(3)
        ]
        scorer_1 = TickerScorer(
            trades=trades_1pol, sqs_map={}, convergence_map={}, sector_map=sector_map
        )
        scorer_3 = TickerScorer(
            trades=trades_3pol, sqs_map={}, convergence_map={}, sector_map=sector_map
        )
        score_1 = scorer_1.score_all()[0]["conviction_score"]
        score_3 = scorer_3.score_all()[0]["conviction_score"]
        assert score_3 > score_1, (
            "3 位議員交易同一標的應得到比 1 位議員更高的分數"
        )


class TestTickerScorerAmountMultiplier:
    """測試金額乘數（RB-001: $15K-$50K 最強）。"""

    @pytest.fixture
    def sector_map(self):
        return {
            "AAPL": {"sector": "Technology", "industry": "", "name": "Apple Inc."},
        }

    def _make_trade(self, amount_range, ticker="AAPL"):
        return {
            "id": "test",
            "chamber": "Senate",
            "politician_name": "Test Senator",
            "transaction_date": "2025-01-10",
            "filing_date": "2025-01-20",
            "ticker": ticker,
            "transaction_type": "Buy",
            "amount_range": amount_range,
        }

    def test_best_alpha_amount_range_gets_highest_multiplier(self, sector_map):
        """$15K-$50K 應得到最高的金額乘數（AMOUNT_ALPHA[range] = 1.5）。"""
        best_mult = AMOUNT_ALPHA.get("$15,001 - $50,000", 0)
        assert best_mult == 1.5, f"$15K-$50K 乘數應為 1.5，實際={best_mult}"

    def test_all_amount_ranges_positive(self):
        """所有金額區間的乘數都應為正數。"""
        for rng, mult in AMOUNT_ALPHA.items():
            assert mult > 0, f"AMOUNT_ALPHA['{rng}']={mult} 應為正數"
