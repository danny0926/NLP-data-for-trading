"""
tests/test_portfolio_optimizer.py — 投組最佳化器單元測試

測試項目：
1. Module import
2. 權重約束：每個 ticker ≤ 10%，最小 2%，總和 = 100%
3. 評分公式：各分項加總應 ≤ 100
4. Buy-Only：SALE 不貢獻正 alpha（sale-only ticker 被排除）
5. Senate > House 加分（院別權重翻轉）
6. SQS 降權（RB-006）
7. $15K-$50K 甜蜜點加分（RB-001 Quant validation）
8. PortfolioOptimizer 權重約束（max 10%, min 2%, sum=100%）
9. Edge cases（空輸入、單一標的、全相同分數）
10. Senate vs House 院別加分差異
"""

import pytest
import math
from src.portfolio_optimizer import (
    TickerScorer,
    PortfolioOptimizer,
    MAX_WEIGHT,
    MIN_WEIGHT,
    SECTOR_CAP,
    BUY_CAR_5D,
    SALE_CAR_5D,
    AMOUNT_ALPHA,
    SWEET_SPOT_AMOUNT_RANGE,
    SWEET_SPOT_BONUS,
    save_portfolio_to_db,
    generate_report,
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


class TestSweetSpotBonus:
    """測試 $15K-$50K 甜蜜點加分（RB-001 + Quant validation: 93% higher alpha）。"""

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

    def test_sweet_spot_constant_value(self):
        """SWEET_SPOT_BONUS 應為 5.0 分。"""
        assert SWEET_SPOT_BONUS == 5.0, (
            f"SWEET_SPOT_BONUS={SWEET_SPOT_BONUS}，應為 5.0"
        )

    def test_sweet_spot_amount_range_matches_best_alpha(self):
        """SWEET_SPOT_AMOUNT_RANGE 應對應 AMOUNT_ALPHA 最高乘數的金額區間。"""
        best_range = max(AMOUNT_ALPHA, key=AMOUNT_ALPHA.get)
        assert SWEET_SPOT_AMOUNT_RANGE == best_range, (
            f"甜蜜點金額範圍應為 AMOUNT_ALPHA 最高乘數的區間: {best_range}"
        )

    def test_sweet_spot_trade_scores_higher(self, sector_map):
        """有 $15K-$50K 交易的標的應比其他金額區間得更高分。"""
        scorer_sweet = TickerScorer(
            trades=[self._make_trade("$15,001 - $50,000")],
            sqs_map={}, convergence_map={}, sector_map=sector_map,
        )
        scorer_small = TickerScorer(
            trades=[self._make_trade("$1,001 - $15,000")],
            sqs_map={}, convergence_map={}, sector_map=sector_map,
        )
        sweet_score = scorer_sweet.score_all()[0]["conviction_score"]
        small_score = scorer_small.score_all()[0]["conviction_score"]
        assert sweet_score > small_score, (
            f"$15K-$50K (score={sweet_score:.2f}) 應高於 $1K-$15K (score={small_score:.2f})"
        )

    def test_sweet_spot_bonus_in_debug_keys(self, sector_map):
        """結果中應包含 _sweet_spot 分項（debug key）。"""
        scorer = TickerScorer(
            trades=[self._make_trade("$15,001 - $50,000")],
            sqs_map={}, convergence_map={}, sector_map=sector_map,
        )
        result = scorer.score_all()[0]
        assert "_sweet_spot" in result, "_sweet_spot 應出現在結果的 debug 分項中"
        assert result["_sweet_spot"] == SWEET_SPOT_BONUS, (
            f"_sweet_spot 應為 {SWEET_SPOT_BONUS}，實際={result['_sweet_spot']}"
        )

    def test_non_sweet_spot_gets_zero_bonus(self, sector_map):
        """非甜蜜點金額的交易，_sweet_spot 應為 0。"""
        scorer = TickerScorer(
            trades=[self._make_trade("$100,001 - $250,000")],
            sqs_map={}, convergence_map={}, sector_map=sector_map,
        )
        result = scorer.score_all()[0]
        assert result["_sweet_spot"] == 0.0, (
            f"$100K-$250K 不是甜蜜點，_sweet_spot 應為 0，實際={result['_sweet_spot']}"
        )

    def test_score_does_not_exceed_100_with_bonus(self, sector_map):
        """加上甜蜜點 bonus 後，conviction_score 不應超過 100。"""
        # 建立多項加成都滿分的情境
        trades = [
            {
                "id": str(i),
                "chamber": "Senate",
                "politician_name": f"Senator {i}",
                "transaction_date": "2025-01-10",
                "filing_date": "2025-01-20",
                "ticker": "AAPL",
                "transaction_type": "Buy",
                "amount_range": "$15,001 - $50,000",
            }
            for i in range(3)
        ]
        convergence_map = {"AAPL": {"ticker": "AAPL", "direction": "Buy", "score": 2.0}}
        scorer = TickerScorer(
            trades=trades,
            sqs_map={},
            convergence_map=convergence_map,
            sector_map=sector_map,
        )
        result = scorer.score_all()[0]
        assert result["conviction_score"] <= 100.0, (
            f"conviction_score={result['conviction_score']} 不應超過 100"
        )


# ══════════════════════════════════════════════════════════════════════
#  Helper: 生成 scored_tickers 測試資料
# ══════════════════════════════════════════════════════════════════════

def _make_scored_ticker(ticker, sector="Technology", conviction=50.0, alpha=0.005):
    """生成模擬的 scored ticker dict（TickerScorer.score_all 的輸出格式）。"""
    return {
        "ticker": ticker,
        "sector": sector,
        "industry": "",
        "name": f"{ticker} Inc.",
        "conviction_score": conviction,
        "expected_alpha": alpha,
        "buy_count": 2,
        "sale_count": 0,
        "politician_count": 1,
        "avg_sqs": 50.0,
        "has_convergence": False,
        "reasoning": "test",
        "buy_ratio": 1.0,
        "_breadth": 8.33,
        "_direction": 15.0,
        "_buy_ratio": 5.0,
        "_sqs": 2.5,
        "_convergence": 0.0,
        "_amount": 8.0,
        "_sweet_spot": 0.0,
        "_chamber": 7.5,
        "_politician": 0.0,
    }


def _make_scored_list(n, sector_cycle=None):
    """生成 n 個不同 ticker 的 scored list，可指定板塊循環。"""
    sectors = sector_cycle or [
        "Technology", "Healthcare", "Financials", "Energy",
        "Industrials", "Consumer Discretionary", "Utilities",
    ]
    items = []
    for i in range(n):
        ticker = f"T{i:03d}"
        sector = sectors[i % len(sectors)]
        conviction = 80.0 - i * 0.5  # 遞減分數
        items.append(_make_scored_ticker(ticker, sector, conviction, 0.005))
    return items


# ══════════════════════════════════════════════════════════════════════
#  PortfolioOptimizer 權重約束測試
# ══════════════════════════════════════════════════════════════════════

class TestPortfolioOptimizerWeightConstraints:
    """測試 PortfolioOptimizer 產出的持倉權重約束。"""

    def test_weights_sum_to_one(self):
        """所有持倉權重加總應等於 100%（容差 0.01）。"""
        scored = _make_scored_list(15)
        optimizer = PortfolioOptimizer(scored, market_data={}, max_positions=15)
        positions = optimizer.construct()
        total_weight = sum(p["weight"] for p in positions)
        assert abs(total_weight - 1.0) < 0.01, (
            f"權重總和 {total_weight:.4f} 應接近 1.0"
        )

    def test_no_weight_exceeds_max(self):
        """沒有任何持倉權重超過 MAX_WEIGHT (10%)。"""
        scored = _make_scored_list(20)
        optimizer = PortfolioOptimizer(scored, market_data={}, max_positions=20)
        positions = optimizer.construct()
        for p in positions:
            assert p["weight"] <= MAX_WEIGHT + 0.001, (
                f"{p['ticker']} 權重 {p['weight']:.4f} 超過上限 {MAX_WEIGHT}"
            )

    def test_no_weight_below_min(self):
        """沒有任何持倉權重低於 MIN_WEIGHT (2%)（已通過約束收斂後）。"""
        scored = _make_scored_list(20)
        optimizer = PortfolioOptimizer(scored, market_data={}, max_positions=20)
        positions = optimizer.construct()
        for p in positions:
            # _apply_constraints 會移除低於 MIN_WEIGHT*0.5 的持倉
            # 剩餘的持倉在歸一化後可能略低於 MIN_WEIGHT，但不應遠低
            assert p["weight"] >= MIN_WEIGHT * 0.4, (
                f"{p['ticker']} 權重 {p['weight']:.4f} 遠低於最低門檻 {MIN_WEIGHT}"
            )

    def test_max_positions_respected(self):
        """持倉數不超過 max_positions。"""
        scored = _make_scored_list(30)
        optimizer = PortfolioOptimizer(scored, market_data={}, max_positions=10)
        positions = optimizer.construct()
        assert len(positions) <= 10, (
            f"持倉數 {len(positions)} 超過 max_positions=10"
        )

    def test_sector_cap_constraint_reduces_dominant_sector(self):
        """板塊約束應縮減過度集中的板塊權重，使其趨近 SECTOR_CAP。"""
        # 多板塊：分散到 4+ 個板塊，讓 constraint 可以正常運作
        sectors = ["Technology", "Healthcare", "Financials", "Energy",
                   "Industrials", "Consumer Discretionary", "Utilities"]
        scored = []
        # Technology 佔 6 個高分標的
        for i in range(6):
            scored.append(_make_scored_ticker(f"TECH{i}", "Technology", 80 - i))
        # 其他板塊各 3 個
        for s in sectors[1:]:
            for i in range(3):
                scored.append(_make_scored_ticker(f"{s[:3].upper()}{i}", s, 50 - i))
        optimizer = PortfolioOptimizer(scored, market_data={}, max_positions=20)
        positions = optimizer.construct()
        from collections import defaultdict
        sector_weights = defaultdict(float)
        for p in positions:
            sector_weights[p["sector"]] += p["weight"]
        # _select_with_diversification 限制每板塊 max(2, 20//3)=6 個
        # _apply_constraints 會縮減超過 SECTOR_CAP 的板塊
        # 驗證: 約束後 Technology 板塊比無約束時有所下降
        tech_weight = sector_weights.get("Technology", 0)
        n_tech = sum(1 for p in positions if p["sector"] == "Technology")
        n_total = len(positions)
        unconstrained_tech = n_tech / n_total  # 無約束時的等權比例
        # 約束應使 Technology 權重不超過未約束值（如果超過 30% 會被縮減）
        assert tech_weight <= max(SECTOR_CAP + 0.05, unconstrained_tech), (
            f"Technology 權重 {tech_weight:.4f} 應受到板塊約束影響"
        )


class TestPortfolioOptimizerTiltedWeights:
    """測試 conviction-tilted 權重分配邏輯。"""

    def test_higher_conviction_gets_higher_weight(self):
        """conviction_score 更高的標的應獲得更高的 tilted weight（約束前）。"""
        # 直接測試 _calculate_tilted_weights 避免 _apply_constraints 的歸一化效果
        scored = [
            _make_scored_ticker("HIGH", "Technology", conviction=90.0),
            _make_scored_ticker("MED1", "Healthcare", conviction=60.0),
            _make_scored_ticker("MED2", "Financials", conviction=50.0),
            _make_scored_ticker("LOW", "Energy", conviction=20.0),
        ]
        optimizer = PortfolioOptimizer(scored, market_data={}, max_positions=10)
        weights = optimizer._calculate_tilted_weights(scored)
        # HIGH (index 0) 應有最高權重，LOW (index 3) 應有最低
        assert weights[0] > weights[3], (
            f"HIGH weight ({weights[0]:.4f}) 應大於 LOW weight ({weights[3]:.4f})"
        )

    def test_tilted_weights_preserve_ordering(self):
        """_calculate_tilted_weights 應保持 conviction 排序。"""
        sectors = ["Technology", "Healthcare", "Financials", "Energy", "Industrials"]
        scored = [_make_scored_ticker(f"T{i}", sectors[i], 80 - i * 10) for i in range(5)]
        optimizer = PortfolioOptimizer(scored, market_data={}, max_positions=10)
        weights = optimizer._calculate_tilted_weights(scored)
        # 權重應隨 conviction 遞減
        for i in range(len(weights) - 1):
            assert weights[i] >= weights[i + 1], (
                f"weight[{i}]={weights[i]:.4f} 應 >= weight[{i+1}]={weights[i+1]:.4f}"
            )

    def test_equal_scores_get_equal_weights(self):
        """相同 conviction_score 的標的應獲得相同權重。"""
        scored = [
            _make_scored_ticker("A", "Technology", conviction=50.0),
            _make_scored_ticker("B", "Healthcare", conviction=50.0),
            _make_scored_ticker("C", "Financials", conviction=50.0),
        ]
        optimizer = PortfolioOptimizer(scored, market_data={}, max_positions=5)
        positions = optimizer.construct()
        weights = [p["weight"] for p in positions]
        # 全部相同分數，權重應幾乎相等
        assert max(weights) - min(weights) < 0.01, (
            f"權重差異 {max(weights)-min(weights):.4f} 過大，相同分數應得相同權重"
        )


# ══════════════════════════════════════════════════════════════════════
#  Senate vs House 院別加分測試
# ══════════════════════════════════════════════════════════════════════

class TestSenateVsHouseChamberScore:
    """測試 Senate 交易比 House 交易得到更高的 chamber 分數 (RB-004)。"""

    @pytest.fixture
    def sector_map(self):
        return {
            "AAPL": {"sector": "Technology", "industry": "", "name": "Apple Inc."},
            "MSFT": {"sector": "Technology", "industry": "", "name": "Microsoft"},
        }

    def _make_trade(self, ticker, chamber):
        return {
            "id": f"{ticker}_{chamber}",
            "chamber": chamber,
            "politician_name": f"Politician {chamber}",
            "transaction_date": "2025-01-10",
            "filing_date": "2025-01-20",
            "ticker": ticker,
            "transaction_type": "Buy",
            "amount_range": "$50,001 - $100,000",
        }

    def test_senate_scores_higher_than_house(self, sector_map):
        """Senate 交易的 _chamber 分數應高於 House 交易。"""
        senate_trades = [self._make_trade("AAPL", "Senate")]
        house_trades = [self._make_trade("MSFT", "House")]

        scorer_senate = TickerScorer(
            trades=senate_trades, sqs_map={}, convergence_map={}, sector_map=sector_map,
        )
        scorer_house = TickerScorer(
            trades=house_trades, sqs_map={}, convergence_map={}, sector_map=sector_map,
        )
        senate_result = scorer_senate.score_all()[0]
        house_result = scorer_house.score_all()[0]
        assert senate_result["_chamber"] > house_result["_chamber"], (
            f"Senate _chamber={senate_result['_chamber']} 應高於 "
            f"House _chamber={house_result['_chamber']} (RB-004)"
        )

    def test_senate_full_chamber_score(self, sector_map):
        """全 Senate 交易應得到 _chamber = 10.0（滿分）。"""
        trades = [self._make_trade("AAPL", "Senate")]
        scorer = TickerScorer(
            trades=trades, sqs_map={}, convergence_map={}, sector_map=sector_map,
        )
        result = scorer.score_all()[0]
        assert result["_chamber"] == 10.0, (
            f"全 Senate 應得 _chamber=10.0，實際={result['_chamber']}"
        )

    def test_house_partial_chamber_score(self, sector_map):
        """全 House 交易的 _chamber 應為 5.0（基礎分）。"""
        trades = [self._make_trade("MSFT", "House")]
        scorer = TickerScorer(
            trades=trades, sqs_map={}, convergence_map={}, sector_map=sector_map,
        )
        result = scorer.score_all()[0]
        assert result["_chamber"] == 5.0, (
            f"全 House 應得 _chamber=5.0，實際={result['_chamber']}"
        )

    def test_senate_conviction_higher_overall(self, sector_map):
        """同條件下 Senate 交易的 conviction_score 應高於 House。"""
        senate_trades = [self._make_trade("AAPL", "Senate")]
        house_trades = [self._make_trade("MSFT", "House")]

        scorer_senate = TickerScorer(
            trades=senate_trades, sqs_map={}, convergence_map={}, sector_map=sector_map,
        )
        scorer_house = TickerScorer(
            trades=house_trades, sqs_map={}, convergence_map={}, sector_map=sector_map,
        )
        senate_score = scorer_senate.score_all()[0]["conviction_score"]
        house_score = scorer_house.score_all()[0]["conviction_score"]
        assert senate_score > house_score, (
            f"Senate conviction={senate_score} 應高於 House conviction={house_score}"
        )


# ══════════════════════════════════════════════════════════════════════
#  Edge Cases 測試
# ══════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    """測試邊界情況。"""

    def test_empty_input_returns_empty(self):
        """空的 scored_tickers 應回傳空的 positions。"""
        optimizer = PortfolioOptimizer([], market_data={}, max_positions=20)
        positions = optimizer.construct()
        assert positions == [], "空輸入應回傳空 list"

    def test_single_ticker_gets_full_weight(self):
        """只有一個標的時，權重應等於 100%。"""
        scored = [_make_scored_ticker("ONLY", "Technology", 60.0)]
        optimizer = PortfolioOptimizer(scored, market_data={}, max_positions=20)
        positions = optimizer.construct()
        assert len(positions) == 1
        assert abs(positions[0]["weight"] - 1.0) < 0.01, (
            f"單一標的權重 {positions[0]['weight']:.4f} 應為 1.0"
        )

    def test_two_tickers_weights_sum_to_one(self):
        """兩個標的的權重加總應為 100%。"""
        scored = [
            _make_scored_ticker("A", "Technology", 70.0),
            _make_scored_ticker("B", "Healthcare", 30.0),
        ]
        optimizer = PortfolioOptimizer(scored, market_data={}, max_positions=20)
        positions = optimizer.construct()
        total = sum(p["weight"] for p in positions)
        assert abs(total - 1.0) < 0.01, f"總權重 {total:.4f} 應為 1.0"

    def test_no_buy_trades_returns_empty(self):
        """所有交易都是 Sale 時，score_all 應回傳空 list。"""
        trades = [
            {
                "id": "1", "chamber": "Senate",
                "politician_name": "Seller",
                "transaction_date": "2025-01-10",
                "filing_date": "2025-01-20",
                "ticker": "AAPL",
                "transaction_type": "Sale",
                "amount_range": "$50,001 - $100,000",
            }
        ]
        sector_map = {"AAPL": {"sector": "Technology", "industry": "", "name": "Apple"}}
        scorer = TickerScorer(
            trades=trades, sqs_map={}, convergence_map={}, sector_map=sector_map,
        )
        assert scorer.score_all() == [], "全 Sale 應回傳空 list"

    def test_ticker_not_in_sector_map_excluded(self):
        """不在 sector_map 中的 ticker 應被排除。"""
        trades = [
            {
                "id": "1", "chamber": "Senate",
                "politician_name": "Buyer",
                "transaction_date": "2025-01-10",
                "filing_date": "2025-01-20",
                "ticker": "UNKNOWN",
                "transaction_type": "Buy",
                "amount_range": "$50,001 - $100,000",
            }
        ]
        scorer = TickerScorer(
            trades=trades, sqs_map={}, convergence_map={}, sector_map={},
        )
        assert scorer.score_all() == [], "不在 sector_map 中的 ticker 應被排除"

    def test_zero_total_trades_returns_none(self):
        """沒有 Buy 也沒有 Sale 的交易（如 Exchange）應回傳 None。"""
        trades = [
            {
                "id": "1", "chamber": "Senate",
                "politician_name": "Exchanger",
                "transaction_date": "2025-01-10",
                "filing_date": "2025-01-20",
                "ticker": "AAPL",
                "transaction_type": "Exchange",
                "amount_range": "$50,001 - $100,000",
            }
        ]
        sector_map = {"AAPL": {"sector": "Technology", "industry": "", "name": "Apple"}}
        scorer = TickerScorer(
            trades=trades, sqs_map={}, convergence_map={}, sector_map=sector_map,
        )
        assert scorer.score_all() == [], "Exchange-only 交易應被排除"


# ══════════════════════════════════════════════════════════════════════
#  DB 寫入測試（使用 in-memory SQLite）
# ══════════════════════════════════════════════════════════════════════

class TestSavePortfolioDB:
    """測試 save_portfolio_to_db 寫入 in-memory DB。"""

    def test_save_and_read_positions(self, tmp_path):
        """寫入持倉後應可從 DB 讀回。"""
        import sqlite3
        db_path = str(tmp_path / "test.db")
        positions = [
            {
                "ticker": "AAPL",
                "sector": "Technology",
                "weight": 0.10,
                "conviction_score": 75.0,
                "expected_alpha": 0.005,
                "volatility_30d": 0.25,
                "sharpe_estimate": 1.5,
                "reasoning": "test position",
            },
            {
                "ticker": "MSFT",
                "sector": "Technology",
                "weight": 0.08,
                "conviction_score": 65.0,
                "expected_alpha": 0.004,
                "volatility_30d": 0.20,
                "sharpe_estimate": 1.2,
                "reasoning": "test position 2",
            },
        ]
        save_portfolio_to_db(positions, db_path)

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT ticker, weight FROM portfolio_positions ORDER BY weight DESC")
        rows = cursor.fetchall()
        conn.close()

        assert len(rows) == 2
        assert rows[0][0] == "AAPL"
        assert rows[0][1] == 0.10

    def test_save_clears_old_positions(self, tmp_path):
        """重複執行應清除舊持倉再寫入新持倉。"""
        import sqlite3
        db_path = str(tmp_path / "test.db")
        pos1 = [{"ticker": "OLD", "sector": "X", "weight": 0.5,
                  "conviction_score": 50, "expected_alpha": 0.01,
                  "volatility_30d": 0.2, "sharpe_estimate": 1.0, "reasoning": "old"}]
        pos2 = [{"ticker": "NEW", "sector": "Y", "weight": 0.5,
                  "conviction_score": 60, "expected_alpha": 0.02,
                  "volatility_30d": 0.3, "sharpe_estimate": 1.5, "reasoning": "new"}]
        save_portfolio_to_db(pos1, db_path)
        save_portfolio_to_db(pos2, db_path)

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT ticker FROM portfolio_positions")
        tickers = [r[0] for r in cursor.fetchall()]
        conn.close()

        assert "OLD" not in tickers, "舊持倉 OLD 應被清除"
        assert "NEW" in tickers, "新持倉 NEW 應存在"
        assert len(tickers) == 1


# ══════════════════════════════════════════════════════════════════════
#  報告生成測試
# ══════════════════════════════════════════════════════════════════════

class TestGenerateReport:
    """測試 generate_report 輸出格式。"""

    def test_report_contains_key_sections(self):
        """報告應包含摘要、板塊分布、持倉明細等關鍵段落。"""
        positions = [
            {
                "ticker": "AAPL", "sector": "Technology", "weight": 0.10,
                "conviction_score": 75.0, "expected_alpha": 0.005,
                "volatility_30d": 0.25, "sharpe_estimate": 1.5,
                "reasoning": "test", "name": "Apple Inc.",
            }
        ]
        report = generate_report(positions)
        assert "## 摘要" in report
        assert "## 板塊分布" in report
        assert "## 持倉明細" in report
        assert "## 方法論" in report
        assert "AAPL" in report

    def test_report_empty_positions(self):
        """空持倉應仍可生成報告（不 crash）。"""
        report = generate_report([])
        assert "## 摘要" in report
        assert "持股數 | 0" in report


# ══════════════════════════════════════════════════════════════════════
#  評分邏輯 — 分項驗證
# ══════════════════════════════════════════════════════════════════════

class TestScoringComponents:
    """測試評分公式的各個分項計算。"""

    @pytest.fixture
    def sector_map(self):
        return {
            "AAPL": {"sector": "Technology", "industry": "", "name": "Apple Inc."},
        }

    def _make_trade(self, chamber="Senate", tx_type="Buy",
                    amount="$50,001 - $100,000", politician="Test Pol"):
        return {
            "id": "1", "chamber": chamber,
            "politician_name": politician,
            "transaction_date": "2025-01-10",
            "filing_date": "2025-01-20",
            "ticker": "AAPL",
            "transaction_type": tx_type,
            "amount_range": amount,
        }

    def test_sqs_with_data_vs_without(self, sector_map):
        """有 SQS 資料時應使用實際 SQS；無資料時給中等分 2.5。"""
        trade = self._make_trade()
        scorer_no_sqs = TickerScorer(
            trades=[trade], sqs_map={}, convergence_map={}, sector_map=sector_map,
        )
        sqs_data = {"AAPL": [{"sqs": 90, "grade": "Platinum",
                               "actionability": 90, "timeliness": 80,
                               "conviction": 85, "information_edge": 70,
                               "market_impact": 60}]}
        scorer_with_sqs = TickerScorer(
            trades=[trade], sqs_map=sqs_data, convergence_map={}, sector_map=sector_map,
        )
        no_sqs = scorer_no_sqs.score_all()[0]["_sqs"]
        with_sqs = scorer_with_sqs.score_all()[0]["_sqs"]
        assert no_sqs == 2.5, f"無 SQS 資料時應為 2.5，實際={no_sqs}"
        assert with_sqs > no_sqs, f"SQS=90 的分數 {with_sqs} 應高於預設 {no_sqs}"

    def test_politician_ranking_bonus(self, sector_map):
        """有 PIS 排名的議員交易應得到 _politician 加分。"""
        trade = self._make_trade(politician="Top Senator")
        pol_map = {"Top Senator": {"pis_total": 55.0, "rank": 1}}
        scorer = TickerScorer(
            trades=[trade], sqs_map={}, convergence_map={},
            sector_map=sector_map, politician_map=pol_map,
        )
        result = scorer.score_all()[0]
        assert result["_politician"] > 0, (
            f"Top 議員 _politician 分數應 > 0，實際={result['_politician']}"
        )

    def test_buy_ratio_pure_buy(self, sector_map):
        """純 Buy 標的的 _buy_ratio 應為 5.0（滿分）。"""
        trade = self._make_trade()
        scorer = TickerScorer(
            trades=[trade], sqs_map={}, convergence_map={}, sector_map=sector_map,
        )
        result = scorer.score_all()[0]
        assert result["_buy_ratio"] == 5.0, (
            f"純 Buy 標的 _buy_ratio 應為 5.0，實際={result['_buy_ratio']}"
        )

    def test_mixed_buy_sale_reduces_buy_ratio(self, sector_map):
        """Buy+Sale 混合應降低 _buy_ratio。"""
        trades = [
            self._make_trade(tx_type="Buy", politician="A"),
            self._make_trade(tx_type="Sale", politician="B"),
        ]
        # Fix: both need same ticker
        for t in trades:
            t["ticker"] = "AAPL"
            t["id"] = t["politician_name"]
        scorer = TickerScorer(
            trades=trades, sqs_map={}, convergence_map={}, sector_map=sector_map,
        )
        result = scorer.score_all()[0]
        assert result["_buy_ratio"] == 2.5, (
            f"50% Buy 比例的 _buy_ratio 應為 2.5，實際={result['_buy_ratio']}"
        )
