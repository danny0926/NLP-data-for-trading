"""
投資組合最佳化器 — 基於國會交易訊號的 Modern Portfolio Theory 配置

根據 congress_trades、signal_quality_scores、convergence_signals 三張表，
以及歷史回測結果（Buy +0.77% CAR_5d, Buy +1.10% CAR_20d 59.2% WR,
Sale -3.21% CAR_20d → Buy-Only 策略），對每支股票評分並產生最佳投資組合配置。

RB-004 核心發現: Buy-Only strategy 遠優於 Buy+Sale，Sale 信號有負 alpha。
因此本模組採用 Buy-Only 過濾: Sale-Only 標的自動排除，Sale 交易不貢獻正 alpha。

用法:
    python -m src.portfolio_optimizer                    # 產生投資組合
    python -m src.portfolio_optimizer --budget 100000    # 帶美金金額
    python -m src.portfolio_optimizer --max-positions 15 # 限制持股數
"""

import argparse
import json
import logging
import math
import os
import sqlite3
import uuid
from collections import defaultdict
from datetime import datetime, date
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from src.config import DB_PATH, PROJECT_ROOT

# ── 常數 ──
MAX_WEIGHT = 0.10          # 單一標的最大權重 10%
MIN_WEIGHT = 0.02          # 單一標的最小權重 2%
SECTOR_CAP = 0.30          # 單一板塊最大權重 30%
DEFAULT_MAX_POSITIONS = 20 # 預設最大持股數
DEFAULT_BUDGET = 0         # 0 表示僅顯示百分比

# 回測結果: 金額區間的 alpha 乘數（來自歷史回測）
AMOUNT_ALPHA = {
    "$15,001 - $50,000":      1.5,   # 最強訊號
    "$50,001 - $100,000":     1.3,
    "$100,001 - $250,000":    1.2,
    "$250,001 - $500,000":    1.1,
    "$500,001 - $1,000,000":  1.0,
    "$1,000,001 - $5,000,000": 1.0,
    "$5,000,001 - $25,000,000": 0.9,
    "$1,001 - $15,000":       0.8,   # 最低金額，訊號較弱
}

# 回測結果常數 (RB-004 validated)
BUY_CAR_5D = 0.0077    # Buy 方向 5 日 CAR (p<0.001)
BUY_CAR_20D = 0.0110   # Buy 方向 20 日 CAR (59.2% WR)
SALE_CAR_5D = 0.0       # Sale: 不給正 alpha (RB-004: -3.21% 20d, 有害)
# 歷史值: SALE_CAR_5D = 0.0050 (contrarian hypothesis, 已被 RB-004 否定)

logger = logging.getLogger("PortfolioOptimizer")


# ══════════════════════════════════════════════════════════════════════
#  資料讀取層
# ══════════════════════════════════════════════════════════════════════

def load_sector_map(path: Optional[str] = None) -> Dict[str, dict]:
    """讀取 ticker_sectors.json，回傳 {ticker: {sector, industry, name}}"""
    if path is None:
        path = str(PROJECT_ROOT / "data" / "ticker_sectors.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("sector_map", {})
    except FileNotFoundError:
        logger.warning("找不到 ticker_sectors.json，板塊資訊將為空")
        return {}


def load_congress_trades(db_path: str = None, days: int = 90) -> List[dict]:
    """讀取最近 N 天有 ticker 的國會交易紀錄"""
    if db_path is None:
        db_path = DB_PATH
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT ct.id, ct.chamber, ct.politician_name, ct.transaction_date,
               ct.filing_date, ct.ticker, ct.asset_name, ct.transaction_type,
               ct.amount_range, ct.owner
        FROM congress_trades ct
        WHERE ct.ticker IS NOT NULL
          AND ct.transaction_date >= date('now', ?)
        ORDER BY ct.transaction_date DESC
    """, (f"-{days} days",))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def load_sqs_scores(db_path: str = None) -> Dict[str, List[dict]]:
    """讀取 signal_quality_scores，以 ticker 為 key 分組"""
    if db_path is None:
        db_path = DB_PATH
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT ticker, sqs, grade, actionability, timeliness,
               conviction, information_edge, market_impact
        FROM signal_quality_scores
        WHERE ticker IS NOT NULL AND grade != 'Discard'
    """)
    result: Dict[str, List[dict]] = defaultdict(list)
    for row in cursor.fetchall():
        result[row["ticker"]].append(dict(row))
    conn.close()
    return result


def load_convergence_signals(db_path: str = None) -> Dict[str, dict]:
    """讀取 convergence_signals，以 ticker 為 key"""
    if db_path is None:
        db_path = DB_PATH
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT ticker, direction, politician_count, politicians,
               chambers, score
        FROM convergence_signals
    """)
    result = {}
    for row in cursor.fetchall():
        result[row["ticker"]] = dict(row)
    conn.close()
    return result


# ══════════════════════════════════════════════════════════════════════
#  市場數據（yfinance）
# ══════════════════════════════════════════════════════════════════════

def fetch_market_data(tickers: List[str]) -> Dict[str, dict]:
    """
    透過 yfinance 取得每支股票的最新價格和 30 日年化波動率。
    回傳 {ticker: {price, volatility_30d, name}}
    """
    try:
        import yfinance as yf
    except ImportError:
        logger.warning("yfinance 未安裝，跳過市場數據抓取")
        return {}

    market_data: Dict[str, dict] = {}
    # 分批處理以避免 API 限制
    batch_size = 20
    for i in range(0, len(tickers), batch_size):
        batch = tickers[i:i + batch_size]
        ticker_str = " ".join(batch)
        try:
            data = yf.download(ticker_str, period="35d", interval="1d",
                               progress=False, threads=True)
            if data.empty:
                continue

            for t in batch:
                try:
                    # yfinance 多標的回傳 MultiIndex columns
                    if len(batch) > 1 and isinstance(data.columns, type(data.columns)):
                        try:
                            close = data["Close"][t].dropna()
                        except (KeyError, TypeError):
                            close = data["Close"].dropna()
                    else:
                        close = data["Close"].dropna()
                        # 如果是 DataFrame 要 squeeze
                        if hasattr(close, "columns"):
                            close = close.squeeze()

                    if len(close) < 5:
                        continue

                    price = float(close.iloc[-1])
                    # 30 日年化波動率
                    returns = close.pct_change().dropna()
                    if len(returns) >= 5:
                        vol_30d = float(returns.std() * math.sqrt(252))
                    else:
                        vol_30d = 0.0

                    market_data[t] = {
                        "price": round(price, 2),
                        "volatility_30d": round(vol_30d, 4),
                    }
                except Exception as e:
                    logger.debug(f"處理 {t} 市場數據失敗: {e}")
        except Exception as e:
            logger.warning(f"yfinance 下載批次失敗: {e}")

    return market_data


# ══════════════════════════════════════════════════════════════════════
#  評分引擎
# ══════════════════════════════════════════════════════════════════════

class TickerScorer:
    """為每支股票計算 conviction score（綜合信念分數）"""

    def __init__(
        self,
        trades: List[dict],
        sqs_map: Dict[str, List[dict]],
        convergence_map: Dict[str, dict],
        sector_map: Dict[str, dict],
    ):
        self.trades = trades
        self.sqs_map = sqs_map
        self.convergence_map = convergence_map
        self.sector_map = sector_map

        # 按 ticker 分組交易
        self.ticker_trades: Dict[str, List[dict]] = defaultdict(list)
        for t in trades:
            self.ticker_trades[t["ticker"]].append(t)

    def score_all(self) -> List[dict]:
        """對所有有效 ticker 評分，回傳排序後的清單"""
        scored = []
        for ticker, ticker_trades in self.ticker_trades.items():
            # 跳過沒有板塊資訊的標的（ETF、OTC 等）
            if ticker not in self.sector_map:
                continue

            score_detail = self._score_ticker(ticker, ticker_trades)
            if score_detail is not None:
                scored.append(score_detail)

        # 按 conviction_score 降冪排序
        scored.sort(key=lambda x: x["conviction_score"], reverse=True)
        return scored

    def _score_ticker(self, ticker: str, trades: List[dict]) -> Optional[dict]:
        """計算單一 ticker 的綜合分數 (Buy-Only 策略, RB-004)"""
        # ── 1. 信念廣度分數 (breadth): 多少議員在交易 ──
        politicians = set(t["politician_name"] for t in trades)
        breadth_score = min(len(politicians) / 3.0, 1.0) * 25.0  # 3 位議員得滿分

        # ── 2. 方向分數 (direction): Buy-Only 策略 (RB-004) ──
        buy_count = sum(1 for t in trades if t["transaction_type"] == "Buy")
        sale_count = sum(1 for t in trades if t["transaction_type"] == "Sale")
        total = buy_count + sale_count
        if total == 0:
            return None

        # RB-004: Sale-Only 標的排除 — Sale 信號有 -3.21% 20d alpha
        if buy_count == 0:
            return None

        # Buy-Only alpha: Sale 不貢獻正 alpha (SALE_CAR_5D = 0)
        buy_alpha = buy_count * BUY_CAR_5D
        direction_weight = buy_alpha / total
        direction_score = min(direction_weight / 0.008, 1.0) * 15.0

        # ── 2b. Buy 比例加分 (RB-004): 純 Buy 標的加分 ──
        buy_ratio = buy_count / total
        buy_ratio_score = buy_ratio * 5.0  # 純 Buy 標的得滿分 5 分

        # ── 3. SQS 分數 (降權, RB-006: SQS 與實際 alpha r=-0.50) ──
        # RB-006 發現 SQS conviction 與實際 alpha 負相關
        # 保留作為品質過濾（淘汰 Discard），但權重從 20 降至 5
        sqs_records = self.sqs_map.get(ticker, [])
        if sqs_records:
            avg_sqs = sum(r["sqs"] for r in sqs_records) / len(sqs_records)
            sqs_score = (avg_sqs / 100.0) * 5.0  # SQS 0-100 → 0-5 (降權)
        else:
            sqs_score = 2.5  # 無 SQS 資料給中等分

        # ── 4. 收斂訊號加分 (提權: 15→20, RB-006 validated) ──
        convergence = self.convergence_map.get(ticker)
        if convergence:
            conv_score = min(convergence["score"] / 2.0, 1.0) * 20.0
        else:
            conv_score = 0.0

        # ── 5. 金額加權: $15K-$50K 最強 (提權: 10→15, RB-001) ──
        amount_multipliers = []
        for t in trades:
            amt = t.get("amount_range", "")
            mult = AMOUNT_ALPHA.get(amt, 0.8)
            amount_multipliers.append(mult)
        avg_amount_mult = sum(amount_multipliers) / len(amount_multipliers)
        amount_score = (avg_amount_mult / 1.5) * 15.0  # 1.5 為最大倍率

        # ── 6. 院別加權: Senate >> House (RB-004) ──
        # RB-004: Senate 20d +1.39% (69.2% WR) vs House -1.27%
        senate_count = sum(1 for t in trades if t["chamber"] == "Senate")
        senate_ratio = senate_count / len(trades)
        house_count = sum(1 for t in trades if t["chamber"] == "House")
        house_ratio = house_count / len(trades)
        chamber_score = (0.5 + 0.5 * senate_ratio) * 10.0  # Senate 有加分

        # ── 綜合分數 (滿分 100) ──
        conviction = (breadth_score + direction_score + buy_ratio_score
                      + sqs_score + conv_score + amount_score + chamber_score)

        # 預期 alpha 估算 (Buy-Only, RB-004)
        base_alpha = buy_alpha / total  # Sale 不貢獻正 alpha
        expected_alpha = base_alpha * avg_amount_mult * (1.0 + conv_score / 30.0)

        sector_info = self.sector_map.get(ticker, {})
        sector = sector_info.get("sector", "Unknown")

        # 構建推理說明
        reasons = []
        if len(politicians) > 1:
            reasons.append(f"{len(politicians)} 位議員交易")
        if buy_count > 0:
            reasons.append(f"{buy_count} 筆買入")
        if sale_count > 0:
            reasons.append(f"{sale_count} 筆賣出(不計 alpha)")
        if buy_ratio >= 0.8:
            reasons.append("強力買入信號")
        elif buy_ratio >= 0.5:
            reasons.append("買入為主")
        if convergence:
            reasons.append(f"收斂訊號(分數{convergence['score']:.2f})")
        if avg_amount_mult > 1.0:
            reasons.append("高金額交易")
        if senate_ratio > 0.5:
            reasons.append("Senate 為主(RB-004)")
        elif house_ratio > 0.5:
            reasons.append("House 為主")

        return {
            "ticker": ticker,
            "sector": sector,
            "industry": sector_info.get("industry", ""),
            "name": sector_info.get("name", ""),
            "conviction_score": round(conviction, 2),
            "expected_alpha": round(expected_alpha, 4),
            "buy_count": buy_count,
            "sale_count": sale_count,
            "politician_count": len(politicians),
            "avg_sqs": round(avg_sqs if sqs_records else 0, 2),
            "has_convergence": convergence is not None,
            "reasoning": "; ".join(reasons),
            "buy_ratio": round(buy_ratio, 2),
            # 分項 (debug 用)
            "_breadth": round(breadth_score, 2),
            "_direction": round(direction_score, 2),
            "_buy_ratio": round(buy_ratio_score, 2),
            "_sqs": round(sqs_score, 2),
            "_convergence": round(conv_score, 2),
            "_amount": round(amount_score, 2),
            "_chamber": round(chamber_score, 2),
        }


# ══════════════════════════════════════════════════════════════════════
#  投資組合配置引擎
# ══════════════════════════════════════════════════════════════════════

class PortfolioOptimizer:
    """
    Modern Portfolio Theory 風格的投資組合配置器。
    在等權重基礎上依 conviction score 傾斜，
    並套用最大/最小持倉限制和板塊上限。
    """

    def __init__(
        self,
        scored_tickers: List[dict],
        market_data: Dict[str, dict],
        max_positions: int = DEFAULT_MAX_POSITIONS,
        budget: float = DEFAULT_BUDGET,
    ):
        self.scored_tickers = scored_tickers
        self.market_data = market_data
        self.max_positions = max_positions
        self.budget = budget

    def construct(self) -> List[dict]:
        """建構最佳投資組合，回傳持倉清單"""
        # 步驟 1: 選擇 top N 標的
        candidates = self.scored_tickers[:self.max_positions * 2]  # 先取 2 倍候選

        # 步驟 2: 考慮板塊多樣性，最終選出 max_positions 個
        selected = self._select_with_diversification(candidates)

        if not selected:
            logger.warning("沒有可配置的標的")
            return []

        # 步驟 3: 初始等權重 + conviction 傾斜
        weights = self._calculate_tilted_weights(selected)

        # 步驟 4: 套用約束條件（迭代收斂）
        weights = self._apply_constraints(selected, weights)

        # 步驟 5: 組裝最終持倉資訊
        positions = []
        for i, item in enumerate(selected):
            ticker = item["ticker"]
            mkt = self.market_data.get(ticker, {})
            vol = mkt.get("volatility_30d", 0.0)
            price = mkt.get("price", 0.0)

            # Sharpe 估算: expected_alpha / volatility（簡化版）
            if vol > 0:
                # 年化 alpha 估算: 5 日 CAR * 52 週
                annual_alpha = item["expected_alpha"] * 52
                sharpe = round(annual_alpha / vol, 2)
            else:
                sharpe = 0.0

            pos = {
                "ticker": ticker,
                "sector": item["sector"],
                "industry": item.get("industry", ""),
                "name": item.get("name", ""),
                "weight": round(weights[i], 4),
                "conviction_score": item["conviction_score"],
                "expected_alpha": item["expected_alpha"],
                "volatility_30d": vol,
                "sharpe_estimate": sharpe,
                "reasoning": item["reasoning"],
                "price": price,
                "buy_count": item["buy_count"],
                "sale_count": item["sale_count"],
                "politician_count": item["politician_count"],
            }
            if self.budget > 0:
                pos["dollar_amount"] = round(self.budget * weights[i], 2)
                if price > 0:
                    pos["shares"] = int(pos["dollar_amount"] / price)

            positions.append(pos)

        # 按權重降冪排序
        positions.sort(key=lambda x: x["weight"], reverse=True)
        return positions

    def _select_with_diversification(self, candidates: List[dict]) -> List[dict]:
        """帶板塊多樣性限制的標的篩選"""
        selected = []
        sector_count: Dict[str, int] = defaultdict(int)
        max_per_sector = max(2, self.max_positions // 3)  # 每板塊至少 2 個，但不超過 1/3

        for item in candidates:
            if len(selected) >= self.max_positions:
                break
            sector = item["sector"]
            # 板塊配額檢查
            if sector_count[sector] >= max_per_sector:
                continue
            selected.append(item)
            sector_count[sector] += 1

        return selected

    def _calculate_tilted_weights(self, selected: List[dict]) -> List[float]:
        """等權重基礎上按 conviction score 傾斜"""
        n = len(selected)
        if n == 0:
            return []

        # 等權重基礎
        equal_w = 1.0 / n

        # conviction 傾斜: 分數越高，權重越大
        scores = [item["conviction_score"] for item in selected]
        total_score = sum(scores)
        if total_score == 0:
            return [equal_w] * n

        # 50% 等權重 + 50% 分數加權
        weights = []
        for s in scores:
            conviction_w = s / total_score
            w = 0.5 * equal_w + 0.5 * conviction_w
            weights.append(w)

        # 歸一化
        w_sum = sum(weights)
        weights = [w / w_sum for w in weights]
        return weights

    def _apply_constraints(self, selected: List[dict], weights: List[float]) -> List[float]:
        """
        迭代套用約束條件:
        1. 單一標的最大 10%、最小 2%
        2. 單一板塊最大 30%
        3. 總和 = 100%
        最多迭代 50 次收斂
        """
        for iteration in range(50):
            changed = False

            # ── 個股約束 ──
            excess = 0.0
            deficit_indices = []
            for i in range(len(weights)):
                if weights[i] > MAX_WEIGHT:
                    excess += weights[i] - MAX_WEIGHT
                    weights[i] = MAX_WEIGHT
                    changed = True
                elif weights[i] < MIN_WEIGHT:
                    deficit_indices.append(i)

            # 分配超額給低於最低門檻的
            if excess > 0 and deficit_indices:
                share = excess / len(deficit_indices)
                for idx in deficit_indices:
                    weights[idx] += share
                    changed = True

            # 移除仍低於最低門檻的
            valid = [(i, w) for i, w in enumerate(weights) if w >= MIN_WEIGHT * 0.5]
            if len(valid) < len(weights):
                # 重建
                new_selected = [selected[i] for i, _ in valid]
                new_weights = [w for _, w in valid]
                w_sum = sum(new_weights)
                if w_sum > 0:
                    new_weights = [w / w_sum for w in new_weights]
                selected.clear()
                selected.extend(new_selected)
                weights = new_weights
                changed = True

            # ── 板塊約束 ──
            sector_weights: Dict[str, float] = defaultdict(float)
            sector_indices: Dict[str, List[int]] = defaultdict(list)
            for i, item in enumerate(selected):
                sector_weights[item["sector"]] += weights[i]
                sector_indices[item["sector"]].append(i)

            for sector, sw in sector_weights.items():
                if sw > SECTOR_CAP:
                    # 按比例縮減該板塊所有標的
                    scale = SECTOR_CAP / sw
                    released = 0.0
                    for idx in sector_indices[sector]:
                        old_w = weights[idx]
                        weights[idx] = old_w * scale
                        released += old_w - weights[idx]
                    # 釋放的權重分配給其他板塊
                    other_indices = [i for i in range(len(weights))
                                     if selected[i]["sector"] != sector]
                    if other_indices:
                        share = released / len(other_indices)
                        for idx in other_indices:
                            weights[idx] += share
                    changed = True

            # 歸一化
            w_sum = sum(weights)
            if w_sum > 0:
                weights = [w / w_sum for w in weights]

            if not changed:
                break

        return weights


# ══════════════════════════════════════════════════════════════════════
#  資料庫寫入
# ══════════════════════════════════════════════════════════════════════

def save_portfolio_to_db(positions: List[dict], db_path: str = None):
    """將投資組合寫入 portfolio_positions 表"""
    if db_path is None:
        db_path = DB_PATH
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 建表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS portfolio_positions (
            id TEXT PRIMARY KEY,
            ticker TEXT NOT NULL,
            sector TEXT,
            weight REAL NOT NULL,
            conviction_score REAL,
            expected_alpha REAL,
            volatility_30d REAL,
            sharpe_estimate REAL,
            reasoning TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_portfolio_ticker
        ON portfolio_positions(ticker)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_portfolio_date
        ON portfolio_positions(created_at)
    """)

    # 清除舊的持倉資料，避免重複執行時產生重複 ticker
    cursor.execute("DELETE FROM portfolio_positions")
    logger.info("已清除舊持倉資料，準備寫入新的投資組合")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for pos in positions:
        cursor.execute("""
            INSERT INTO portfolio_positions
            (id, ticker, sector, weight, conviction_score, expected_alpha,
             volatility_30d, sharpe_estimate, reasoning, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            str(uuid.uuid4()),
            pos["ticker"],
            pos["sector"],
            pos["weight"],
            pos["conviction_score"],
            pos["expected_alpha"],
            pos["volatility_30d"],
            pos["sharpe_estimate"],
            pos["reasoning"],
            now,
        ))

    conn.commit()
    conn.close()
    logger.info(f"已寫入 {len(positions)} 筆持倉到 portfolio_positions 表")


# ══════════════════════════════════════════════════════════════════════
#  報告生成
# ══════════════════════════════════════════════════════════════════════

def generate_report(positions: List[dict], budget: float = 0) -> str:
    """產生 Markdown 格式的投資組合報告"""
    today_str = date.today().strftime("%Y-%m-%d")
    lines = []
    lines.append(f"# 國會交易投資組合配置報告")
    lines.append(f"日期: {today_str}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # ── 摘要 ──
    lines.append("## 摘要")
    lines.append("")
    total_positions = len(positions)
    total_weight = sum(p["weight"] for p in positions)
    avg_conviction = sum(p["conviction_score"] for p in positions) / total_positions if total_positions else 0
    avg_alpha = sum(p["expected_alpha"] for p in positions) / total_positions if total_positions else 0
    weighted_alpha = sum(p["expected_alpha"] * p["weight"] for p in positions)
    vols = [p["volatility_30d"] for p in positions if p["volatility_30d"] > 0]
    avg_vol = sum(vols) / len(vols) if vols else 0
    sharpes = [p["sharpe_estimate"] for p in positions if p["sharpe_estimate"] != 0]
    avg_sharpe = sum(sharpes) / len(sharpes) if sharpes else 0

    lines.append(f"| 指標 | 數值 |")
    lines.append(f"|------|------|")
    lines.append(f"| 持股數 | {total_positions} |")
    lines.append(f"| 總權重 | {total_weight:.2%} |")
    if budget > 0:
        lines.append(f"| 投資預算 | ${budget:,.0f} |")
    lines.append(f"| 平均信念分數 | {avg_conviction:.1f}/100 |")
    lines.append(f"| 加權預期 Alpha (5日) | {weighted_alpha:.4%} |")
    lines.append(f"| 年化預期 Alpha | {weighted_alpha * 52:.2%} |")
    lines.append(f"| 平均 30 日波動率 | {avg_vol:.2%} |")
    lines.append(f"| 平均 Sharpe 估算 | {avg_sharpe:.2f} |")
    lines.append("")

    # ── 板塊分布 ──
    lines.append("## 板塊分布")
    lines.append("")
    sector_weights: Dict[str, float] = defaultdict(float)
    sector_counts: Dict[str, int] = defaultdict(int)
    for p in positions:
        sector_weights[p["sector"]] += p["weight"]
        sector_counts[p["sector"]] += 1

    lines.append("| 板塊 | 權重 | 持股數 |")
    lines.append("|------|------|--------|")
    for sector in sorted(sector_weights, key=sector_weights.get, reverse=True):
        lines.append(f"| {sector} | {sector_weights[sector]:.2%} | {sector_counts[sector]} |")
    lines.append("")

    # 多樣性分數: Herfindahl-Hirschman Index 的反指標
    hhi = sum(w ** 2 for w in sector_weights.values())
    diversification = round(1.0 - hhi, 4) if hhi < 1 else 0
    lines.append(f"**多樣性分數**: {diversification:.4f} (1.0=完全分散, 0.0=集中)")
    lines.append("")

    # ── 持倉明細 ──
    lines.append("## 持倉明細")
    lines.append("")

    if budget > 0:
        lines.append("| # | Ticker | 名稱 | 板塊 | 權重 | 金額 | 股數 | 信念分數 | Alpha(5d) | 波動率 | Sharpe | 理由 |")
        lines.append("|---|--------|------|------|------|------|------|---------|-----------|--------|--------|------|")
        for i, p in enumerate(positions, 1):
            dollar = p.get("dollar_amount", 0)
            shares = p.get("shares", 0)
            name_short = p.get("name", "")[:20]
            lines.append(
                f"| {i} | **{p['ticker']}** | {name_short} | {p['sector']} | "
                f"{p['weight']:.2%} | ${dollar:,.0f} | {shares} | "
                f"{p['conviction_score']:.1f} | {p['expected_alpha']:.4%} | "
                f"{p['volatility_30d']:.2%} | {p['sharpe_estimate']:.2f} | "
                f"{p['reasoning']} |"
            )
    else:
        lines.append("| # | Ticker | 名稱 | 板塊 | 權重 | 信念分數 | Alpha(5d) | 波動率 | Sharpe | 理由 |")
        lines.append("|---|--------|------|------|------|---------|-----------|--------|--------|------|")
        for i, p in enumerate(positions, 1):
            name_short = p.get("name", "")[:20]
            lines.append(
                f"| {i} | **{p['ticker']}** | {name_short} | {p['sector']} | "
                f"{p['weight']:.2%} | {p['conviction_score']:.1f} | "
                f"{p['expected_alpha']:.4%} | {p['volatility_30d']:.2%} | "
                f"{p['sharpe_estimate']:.2f} | {p['reasoning']} |"
            )

    lines.append("")

    # ── 方法論 ──
    lines.append("## 方法論")
    lines.append("")
    lines.append("### 評分模型 (Research-Aligned, RB-001~RB-006)")
    lines.append("")
    lines.append("| 因子 | 權重 | 說明 | 研究依據 |")
    lines.append("|------|------|------|----------|")
    lines.append("| 信念廣度 | 25 | 交易該標的的議員人數 (3 人得滿分) | RB-001 |")
    lines.append("| Buy 方向 | 15 | Buy +0.77% CAR_5d (Sale 不計正 alpha) | RB-004 |")
    lines.append("| Buy 比例 | 5 | 純 Buy 標的加分 (Sale -3.21% 20d) | RB-004 |")
    lines.append("| SQS 品質 | 5 | 降權: SQS conviction 與 alpha r=-0.50 | RB-006 |")
    lines.append("| 收斂訊號 | 20 | 多位議員同方向交易加分 (提權) | RB-006 |")
    lines.append("| 金額權重 | 15 | $15K-$50K 最強訊號 (提權) | RB-001 |")
    lines.append("| 院別加權 | 10 | Senate 20d +1.39% >> House -1.27% | RB-004 |")
    lines.append("")
    lines.append("### 配置限制")
    lines.append("")
    lines.append(f"- 單一標的最大權重: {MAX_WEIGHT:.0%}")
    lines.append(f"- 單一標的最小權重: {MIN_WEIGHT:.0%}")
    lines.append(f"- 單一板塊上限: {SECTOR_CAP:.0%}")
    lines.append("- 基礎配置: 50% 等權重 + 50% conviction 加權")
    lines.append("")
    lines.append("### 風險提示")
    lines.append("")
    lines.append("- 本報告僅供研究參考，不構成投資建議")
    lines.append("- 國會交易揭露存在延遲 (中位數 28 天)")
    lines.append("- 過去績效不保證未來表現")
    lines.append("- Sharpe 估算基於簡化假設 (5 日 CAR * 52 週年化)")
    lines.append("- Buy-Only 策略 (RB-004): Sale-Only 標的已排除")
    lines.append("")

    return "\n".join(lines)


def print_portfolio(positions: List[dict], budget: float = 0):
    """格式化輸出投資組合到終端"""
    print()
    print("=" * 80)
    print("   國會交易投資組合配置 — Political Alpha Monitor")
    print(f"   日期: {date.today().strftime('%Y-%m-%d')}")
    if budget > 0:
        print(f"   預算: ${budget:,.0f}")
    print("=" * 80)
    print()

    # 板塊摘要
    sector_weights: Dict[str, float] = defaultdict(float)
    for p in positions:
        sector_weights[p["sector"]] += p["weight"]

    print("  [板塊分布]")
    for sector in sorted(sector_weights, key=sector_weights.get, reverse=True):
        bar_len = int(sector_weights[sector] * 50)
        bar = "#" * bar_len
        print(f"    {sector:<25s} {sector_weights[sector]:6.2%}  {bar}")
    print()

    # 持倉明細
    print("  [持倉明細]")
    print(f"  {'#':>3s}  {'Ticker':<8s} {'板塊':<22s} {'權重':>6s}  {'信念':>5s}  {'Alpha':>8s}  {'波動率':>6s}  {'Sharpe':>6s}")
    print("  " + "-" * 76)

    for i, p in enumerate(positions, 1):
        alpha_str = f"{p['expected_alpha']:.4%}"
        vol_str = f"{p['volatility_30d']:.2%}" if p['volatility_30d'] > 0 else "  N/A "
        sharpe_str = f"{p['sharpe_estimate']:.2f}" if p['sharpe_estimate'] != 0 else " N/A "
        print(f"  {i:3d}  {p['ticker']:<8s} {p['sector']:<22s} {p['weight']:6.2%}  {p['conviction_score']:5.1f}  {alpha_str:>8s}  {vol_str:>6s}  {sharpe_str:>6s}")

        if budget > 0 and "dollar_amount" in p:
            shares_str = f"  ({p.get('shares', 0)} 股)" if p.get("price", 0) > 0 else ""
            print(f"       --> ${p['dollar_amount']:,.0f}{shares_str}")

    print()

    # 摘要統計
    total_positions = len(positions)
    weighted_alpha = sum(p["expected_alpha"] * p["weight"] for p in positions)
    vols = [p["volatility_30d"] for p in positions if p["volatility_30d"] > 0]
    avg_vol = sum(vols) / len(vols) if vols else 0
    hhi = sum(w ** 2 for w in sector_weights.values())
    diversification = 1.0 - hhi if hhi < 1 else 0

    print("  [組合統計]")
    print(f"    持股數:             {total_positions}")
    print(f"    加權預期 Alpha(5d): {weighted_alpha:.4%}")
    print(f"    年化預期 Alpha:     {weighted_alpha * 52:.2%}")
    print(f"    平均 30 日波動率:   {avg_vol:.2%}")
    print(f"    板塊多樣性分數:     {diversification:.4f}")
    print()


# ══════════════════════════════════════════════════════════════════════
#  主流程
# ══════════════════════════════════════════════════════════════════════

def run_portfolio_optimization(
    max_positions: int = DEFAULT_MAX_POSITIONS,
    budget: float = DEFAULT_BUDGET,
    days: int = 90,
    db_path: str = None,
) -> List[dict]:
    """
    完整的投資組合最佳化流程:
    1. 讀取資料
    2. 評分
    3. 配置
    4. 取得市場數據
    5. 寫入 DB
    6. 輸出報告
    """
    if db_path is None:
        db_path = DB_PATH

    print("\n[1/6] 讀取國會交易資料...")
    trades = load_congress_trades(db_path, days=days)
    print(f"      讀取到 {len(trades)} 筆交易 (過去 {days} 天，有 ticker)")

    print("[2/6] 讀取品質分數與收斂訊號...")
    sqs_map = load_sqs_scores(db_path)
    convergence_map = load_convergence_signals(db_path)
    sector_map = load_sector_map()
    print(f"      SQS: {sum(len(v) for v in sqs_map.values())} 筆, "
          f"收斂訊號: {len(convergence_map)} 個, "
          f"板塊映射: {len(sector_map)} 支")

    print("[3/6] 計算標的信念分數...")
    scorer = TickerScorer(trades, sqs_map, convergence_map, sector_map)
    scored = scorer.score_all()
    print(f"      {len(scored)} 支有效標的已評分 (最高: {scored[0]['conviction_score']:.1f}, "
          f"最低: {scored[-1]['conviction_score']:.1f})" if scored else "      無有效標的")

    if not scored:
        print("\n[錯誤] 沒有可配置的標的，請先執行 ETL pipeline 抓取資料")
        return []

    print("[4/6] 取得市場數據 (yfinance)...")
    top_tickers = [s["ticker"] for s in scored[:max_positions * 2]]
    market_data = fetch_market_data(top_tickers)
    print(f"      成功取得 {len(market_data)}/{len(top_tickers)} 支股票的市場數據")

    print("[5/6] 建構最佳投資組合...")
    optimizer = PortfolioOptimizer(
        scored_tickers=scored,
        market_data=market_data,
        max_positions=max_positions,
        budget=budget,
    )
    positions = optimizer.construct()
    print(f"      最終持倉: {len(positions)} 支")

    # 合併市場數據到持倉
    # (已在 construct() 中完成)

    # 輸出到終端
    print_portfolio(positions, budget)

    # 寫入 DB
    print("[6/6] 儲存結果...")
    save_portfolio_to_db(positions, db_path)

    # 生成報告
    report_dir = PROJECT_ROOT / "docs" / "reports"
    os.makedirs(str(report_dir), exist_ok=True)
    today_str = date.today().strftime("%Y-%m-%d")
    report_path = report_dir / f"Portfolio_Allocation_{today_str}.md"
    report_content = generate_report(positions, budget)
    with open(str(report_path), "w", encoding="utf-8") as f:
        f.write(report_content)
    print(f"      報告已儲存: {report_path}")
    print(f"      DB 持倉已寫入: portfolio_positions 表 ({len(positions)} 筆)")
    print()

    return positions


# ══════════════════════════════════════════════════════════════════════
#  CLI 入口
# ══════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="國會交易投資組合最佳化器 — Political Alpha Monitor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
範例:
  python -m src.portfolio_optimizer                      # 產生投資組合
  python -m src.portfolio_optimizer --budget 100000      # 帶美金金額
  python -m src.portfolio_optimizer --max-positions 15   # 限制持股數
  python -m src.portfolio_optimizer --days 30            # 僅看最近 30 天
        """
    )
    parser.add_argument("--budget", type=float, default=0,
                        help="投資預算 (美金)，0 表示僅顯示百分比")
    parser.add_argument("--max-positions", type=int, default=DEFAULT_MAX_POSITIONS,
                        help=f"最大持股數 (預設 {DEFAULT_MAX_POSITIONS})")
    parser.add_argument("--days", type=int, default=90,
                        help="僅考慮最近 N 天的交易 (預設 90)")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    run_portfolio_optimization(
        max_positions=args.max_positions,
        budget=args.budget,
        days=args.days,
    )


if __name__ == "__main__":
    main()
