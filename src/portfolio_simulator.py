"""投資組合回測模擬器 — 歷史績效模擬

根據國會交易訊號、SQS 品質分數、政治人物排名，模擬歷史投資績效。
使用 yfinance 取得歷史股價，套用風險管理規則（停損/停利/最大持倉天數）。

Research Brief: RB-007

用法:
    python run_portfolio_sim.py                           # 預設參數
    python run_portfolio_sim.py --capital 200000          # 起始資金 $200K
    python run_portfolio_sim.py --strategy conviction     # 信念加權
    python run_portfolio_sim.py --start-date 2025-12-01   # 指定起始日期
"""

import logging
import math
import os
import sqlite3
import time
import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from src.config import DB_PATH, PROJECT_ROOT

logger = logging.getLogger("PortfolioSimulator")

# ══════════════════════════════════════════════════════════════════════
#  常數
# ══════════════════════════════════════════════════════════════════════

# 風險規則 (與 risk_manager.py 一致)
STOP_LOSS_PCT = -0.05          # 停損: -5%
TAKE_PROFIT_PCT = 0.15         # 停利: +15%
MAX_HOLDING_DAYS = 60          # 最大持倉天數 (交易日)
MAX_POSITION_PCT = 0.10        # 單一部位最大權重: 10%

# 訊號過濾門檻
MIN_SQS_SCORE = 44.0           # SQS >= 44 (Gold/Silver 等級，排除 Bronze/Discard)
PREFERRED_FILING_LAG = 15      # 偏好 filing_lag < 15 天
PREFERRED_AMOUNT_LOWER = 15001 # 偏好 $15K-$50K
PREFERRED_AMOUNT_UPPER = 50000

# 金額區間 alpha 倍率 (與 portfolio_optimizer.py 一致)
AMOUNT_ALPHA = {
    "$15,001 - $50,000":       1.5,
    "$50,001 - $100,000":      1.3,
    "$100,001 - $250,000":     1.2,
    "$250,001 - $500,000":     1.1,
    "$500,001 - $1,000,000":   1.0,
    "$1,000,001 - $5,000,000": 1.0,
    "$5,000,001 - $25,000,000": 0.9,
    "$1,001 - $15,000":        0.8,
}


# ══════════════════════════════════════════════════════════════════════
#  輔助函數
# ══════════════════════════════════════════════════════════════════════

def _parse_amount_lower(amount_range: str) -> float:
    """解析金額區間取下限。"""
    import re
    if not amount_range or not isinstance(amount_range, str):
        return 0.0
    cleaned = amount_range.replace("$", "").replace(",", "").strip()
    numbers = re.findall(r"[\d]+(?:\.[\d]+)?", cleaned)
    return float(numbers[0]) if numbers else 0.0


def _download_prices_batch(tickers: List[str], start: str, end: str,
                           max_retries: int = 3) -> Dict[str, pd.DataFrame]:
    """批量下載歷史股價，含重試邏輯。回傳 {ticker: DataFrame(Close)}。"""
    try:
        import yfinance as yf
    except ImportError:
        logger.error("yfinance 未安裝")
        return {}

    all_tickers = list(set(tickers + ["SPY"]))
    result = {}

    # 分批下載，每批 30 支
    batch_size = 30
    for batch_idx in range(0, len(all_tickers), batch_size):
        batch = all_tickers[batch_idx:batch_idx + batch_size]
        ticker_str = " ".join(batch)

        for attempt in range(max_retries):
            try:
                data = yf.download(
                    ticker_str,
                    start=start,
                    end=end,
                    auto_adjust=True,
                    progress=False,
                    threads=True,
                )
                if data.empty:
                    break

                for t in batch:
                    try:
                        if len(batch) == 1:
                            close = data[["Close"]].copy()
                            close.columns = ["Close"]
                        else:
                            close = data["Close"][[t]].copy()
                            close.columns = ["Close"]

                        close = close.dropna()
                        if len(close) > 0:
                            result[t] = close
                    except (KeyError, TypeError):
                        pass

                break  # 成功，跳出重試迴圈
            except Exception as e:
                logger.warning(f"下載批次 {batch_idx // batch_size + 1} 失敗 "
                               f"(嘗試 {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 * (attempt + 1))

        # 批次間間隔，避免 rate limit
        if batch_idx + batch_size < len(all_tickers):
            time.sleep(1)

    return result


# ══════════════════════════════════════════════════════════════════════
#  交易紀錄 (Trade) 和持倉 (Position) 資料結構
# ══════════════════════════════════════════════════════════════════════

class SimTrade:
    """模擬交易紀錄。"""
    def __init__(self, ticker: str, direction: str, entry_date: str,
                 entry_price: float, shares: float, signal_score: float,
                 politician: str, reason: str):
        self.ticker = ticker
        self.direction = direction       # "Long" or "Short"
        self.entry_date = entry_date
        self.entry_price = entry_price
        self.shares = shares
        self.signal_score = signal_score
        self.politician = politician
        self.reason = reason

        self.exit_date = None            # type: Optional[str]
        self.exit_price = None           # type: Optional[float]
        self.exit_reason = None          # type: Optional[str]
        self.pnl = 0.0
        self.pnl_pct = 0.0
        self.holding_days = 0


# ══════════════════════════════════════════════════════════════════════
#  PortfolioSimulator 主類別
# ══════════════════════════════════════════════════════════════════════

class PortfolioSimulator:
    """投資組合回測模擬器。

    模擬流程:
      1. 載入交易資料 + SQS + 政治人物排名
      2. 過濾訊號 (SQS >= 60, 偏好低 filing lag、中等金額)
      3. 依 filing_date 排序，逐筆模擬進出場
      4. 套用風險規則 (停損/停利/最大持倉天數)
      5. 計算績效指標
      6. 產生圖表與報告
    """

    def __init__(self, capital: float = 100000.0,
                 strategy: str = "equal",
                 start_date: Optional[str] = None,
                 end_date: Optional[str] = None,
                 db_path: Optional[str] = None):
        self.initial_capital = capital
        self.strategy = strategy          # "equal" 或 "conviction"
        self.start_date = start_date
        self.end_date = end_date
        self.db_path = db_path or DB_PATH

        # 模擬狀態
        self.cash = capital
        self.positions = {}               # type: Dict[str, SimTrade]  ticker -> active trade
        self.closed_trades = []           # type: List[SimTrade]
        self.equity_history = []          # type: List[Tuple[str, float]]  (date, equity)
        self.price_cache = {}             # type: Dict[str, pd.DataFrame]
        self.spy_prices = None            # type: Optional[pd.DataFrame]

        # 原始資料
        self.signals = []                 # type: List[dict]
        self.sqs_map = {}                 # type: Dict[str, float]  ticker -> avg sqs
        self.politician_rank = {}         # type: Dict[str, int]   name -> rank

    # ── 資料載入 ────────────────────────────────────────────────────

    def load_data(self):
        """載入所有必要資料。"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        # 1. 國會交易
        where_clauses = ["ct.ticker IS NOT NULL", "ct.ticker != ''"]
        params = []

        if self.start_date:
            where_clauses.append("ct.filing_date >= ?")
            params.append(self.start_date)
        if self.end_date:
            where_clauses.append("ct.filing_date <= ?")
            params.append(self.end_date)

        where_str = " AND ".join(where_clauses)
        query = f"""
            SELECT ct.id, ct.chamber, ct.politician_name, ct.transaction_date,
                   ct.filing_date, ct.ticker, ct.asset_name, ct.transaction_type,
                   ct.amount_range, ct.owner, ct.extraction_confidence
            FROM congress_trades ct
            WHERE {where_str}
              AND ct.transaction_type IN ('Buy', 'Sale', 'Sale (Full)', 'Sale (Partial)')
            ORDER BY ct.filing_date ASC
        """
        cursor = conn.cursor()
        cursor.execute(query, params)
        trades = [dict(r) for r in cursor.fetchall()]

        # 2. SQS 分數 (按 ticker 取平均)
        cursor.execute("""
            SELECT ticker, AVG(sqs) as avg_sqs, grade
            FROM signal_quality_scores
            WHERE ticker IS NOT NULL
            GROUP BY ticker
        """)
        self.sqs_map = {}
        for row in cursor.fetchall():
            self.sqs_map[row["ticker"]] = row["avg_sqs"]

        # 3. 政治人物排名
        cursor.execute("""
            SELECT politician_name, rank, pis_total
            FROM politician_rankings
        """)
        self.politician_rank = {}
        for row in cursor.fetchall():
            self.politician_rank[row["politician_name"]] = {
                "rank": row["rank"],
                "pis_total": row["pis_total"],
            }

        # 4. 收斂訊號
        convergence_map = {}
        try:
            cursor.execute("""
                SELECT ticker, direction, politician_count, score
                FROM convergence_signals
            """)
            for row in cursor.fetchall():
                convergence_map[row["ticker"]] = dict(row)
        except sqlite3.OperationalError:
            pass

        conn.close()

        # 加工信號
        for t in trades:
            ticker = t["ticker"]
            sqs = self.sqs_map.get(ticker, 0)
            filing_lag = 0
            if t.get("transaction_date") and t.get("filing_date"):
                try:
                    td = datetime.strptime(t["transaction_date"][:10], "%Y-%m-%d")
                    fd = datetime.strptime(t["filing_date"][:10], "%Y-%m-%d")
                    filing_lag = (fd - td).days
                except (ValueError, TypeError):
                    pass

            amount_lower = _parse_amount_lower(t.get("amount_range", ""))
            amount_alpha = AMOUNT_ALPHA.get(t.get("amount_range", ""), 0.8)

            # 計算訊號分數 (0-100)
            score = 0.0
            # SQS 佔 40%
            score += min(sqs / 100.0, 1.0) * 40.0
            # Filing lag 佔 20% (越短越好)
            if filing_lag <= PREFERRED_FILING_LAG:
                score += 20.0
            elif filing_lag <= 30:
                score += 15.0
            elif filing_lag <= 45:
                score += 10.0
            else:
                score += 5.0
            # 金額佔 20%
            score += (amount_alpha / 1.5) * 20.0
            # 政治人物排名佔 10%
            pol_info = self.politician_rank.get(t["politician_name"])
            if pol_info:
                # rank 1 = 最佳, 越低越好
                rank_score = max(0, 1.0 - (pol_info["rank"] - 1) / 20.0)
                score += rank_score * 10.0
            else:
                score += 5.0  # 無排名給中等分
            # 收斂訊號佔 10%
            conv = convergence_map.get(ticker)
            if conv:
                score += min(conv["score"] / 2.0, 1.0) * 10.0

            direction = "Buy" if t["transaction_type"] == "Buy" else "Sale"

            self.signals.append({
                "ticker": ticker,
                "direction": direction,
                "filing_date": t["filing_date"],
                "transaction_date": t["transaction_date"],
                "politician_name": t["politician_name"],
                "chamber": t["chamber"],
                "amount_range": t.get("amount_range", ""),
                "amount_lower": amount_lower,
                "filing_lag": filing_lag,
                "sqs": sqs,
                "signal_score": round(score, 2),
                "amount_alpha": amount_alpha,
            })

        logger.info(f"載入 {len(self.signals)} 筆訊號")

    def filter_signals(self) -> List[dict]:
        """過濾訊號: Gold/Silver SQS 等級 (>= 44)，排除 Discard/Bronze。"""
        filtered = []
        for s in self.signals:
            # 硬門檻: SQS >= 44 (Silver 最低為 44.2，排除 Bronze/Discard)
            if s["sqs"] < MIN_SQS_SCORE:
                continue
            filtered.append(s)

        # 按 filing_date 排序
        filtered.sort(key=lambda x: x["filing_date"] or "")

        logger.info(f"過濾後 {len(filtered)} 筆訊號 (原 {len(self.signals)} 筆)")
        return filtered

    # ── 股價下載 ────────────────────────────────────────────────────

    def download_prices(self, signals: List[dict]):
        """下載所有需要的歷史股價。"""
        tickers = list(set(s["ticker"] for s in signals))

        # 計算日期範圍: 最早 transaction_date - 10 天 到 今天 + 5 天
        # 使用 transaction_date 確保涵蓋所有可能的交易日
        all_dates = []
        for s in signals:
            if s.get("transaction_date"):
                all_dates.append(s["transaction_date"][:10])
            if s.get("filing_date"):
                all_dates.append(s["filing_date"][:10])
        if not all_dates:
            logger.error("無有效日期")
            return

        min_date = min(all_dates)
        start = (datetime.strptime(min_date, "%Y-%m-%d") - timedelta(days=10)).strftime("%Y-%m-%d")
        end = (datetime.now() + timedelta(days=5)).strftime("%Y-%m-%d")

        print(f"  下載 {len(tickers)} 支股票 + SPY 歷史股價 ({start} ~ {end})...")
        self.price_cache = _download_prices_batch(tickers, start, end)

        if "SPY" in self.price_cache:
            self.spy_prices = self.price_cache["SPY"]

        print(f"  成功下載 {len(self.price_cache)} / {len(tickers) + 1} 支")

    # ── 模擬引擎 ────────────────────────────────────────────────────

    def _get_price_on_date(self, ticker: str, target_date: str,
                           offset_days: int = 1) -> Optional[Tuple[str, float]]:
        """取得指定日期後第 offset_days 個交易日的收盤價。

        如果 offset_days=1 但無次日數據，fallback 到 offset_days=0（當日收盤）。
        回傳 (actual_date, price) 或 None。
        """
        if ticker not in self.price_cache:
            return None

        prices = self.price_cache[ticker]
        try:
            target_ts = pd.Timestamp(target_date)
        except Exception:
            return None

        after = prices[prices.index >= target_ts]
        if len(after) == 0:
            return None

        # 優先取 offset_days 後的價格
        idx = min(offset_days, len(after) - 1)
        actual_date = after.index[idx].strftime("%Y-%m-%d")
        price = float(after.iloc[idx]["Close"])
        return (actual_date, price)

    def _position_size(self, signal: dict) -> float:
        """計算部位大小（佔 portfolio equity 的比例）。"""
        equity = self._current_equity()

        if self.strategy == "conviction":
            # 信念加權: signal_score 越高，權重越大
            base_pct = 0.03  # 最低 3%
            score_pct = (signal["signal_score"] / 100.0) * 0.07  # 最多 +7%
            pct = min(base_pct + score_pct, MAX_POSITION_PCT)
        else:
            # 等權重: 固定 5%
            pct = 0.05

        return equity * pct

    def _current_equity(self) -> float:
        """計算當前 portfolio 總價值（cash + 持倉市值）。"""
        total = self.cash
        for ticker, trade in self.positions.items():
            # 用最新可用價格估算
            if ticker in self.price_cache:
                prices = self.price_cache[ticker]
                if len(prices) > 0:
                    latest_price = float(prices.iloc[-1]["Close"])
                    total += trade.shares * latest_price
            else:
                # 用進場價估算
                total += trade.shares * trade.entry_price
        return total

    def _mark_to_market(self, date_str: str) -> float:
        """在指定日期 mark-to-market，回傳 portfolio 總價值。"""
        total = self.cash
        target_ts = pd.Timestamp(date_str)

        for ticker, trade in self.positions.items():
            if ticker in self.price_cache:
                prices = self.price_cache[ticker]
                # 取 <= 該日期的最新價格
                available = prices[prices.index <= target_ts]
                if len(available) > 0:
                    price = float(available.iloc[-1]["Close"])
                else:
                    price = trade.entry_price
            else:
                price = trade.entry_price

            total += trade.shares * price
        return total

    def simulate(self, signals: List[dict]):
        """執行模擬。"""
        if not signals:
            print("  [警告] 無訊號可模擬")
            return

        # 收集所有交易日
        all_dates = set()
        for ticker_df in self.price_cache.values():
            for dt in ticker_df.index:
                all_dates.add(dt.strftime("%Y-%m-%d"))
        all_dates = sorted(all_dates)

        if not all_dates:
            print("  [警告] 無股價數據")
            return

        # 建立 filing_date -> signals 映射
        # 將非交易日的 filing_date 映射到下一個交易日
        date_signals = defaultdict(list)
        for s in signals:
            if not s["filing_date"]:
                continue
            fd = s["filing_date"][:10]
            # 找到 >= filing_date 的第一個交易日
            matched_day = None
            for d in all_dates:
                if d >= fd:
                    matched_day = d
                    break
            if matched_day:
                date_signals[matched_day].append(s)

        # 逐日模擬
        signal_idx = 0
        entry_count = 0
        skip_count = 0

        for day in all_dates:
            # ── 1. 檢查現有持倉的停損/停利/最大天數 ──
            tickers_to_close = []
            for ticker, trade in self.positions.items():
                if ticker not in self.price_cache:
                    continue

                prices = self.price_cache[ticker]
                target_ts = pd.Timestamp(day)
                available = prices[prices.index <= target_ts]
                if len(available) == 0:
                    continue

                current_price = float(available.iloc[-1]["Close"])

                # 計算 P&L
                if trade.direction == "Long":
                    pnl_pct = (current_price - trade.entry_price) / trade.entry_price
                else:
                    pnl_pct = (trade.entry_price - current_price) / trade.entry_price

                # 計算持倉天數 (交易日)
                entry_ts = pd.Timestamp(trade.entry_date)
                holding_prices = prices[(prices.index >= entry_ts) & (prices.index <= target_ts)]
                holding_days = max(0, len(holding_prices) - 1)

                # 檢查停損
                if pnl_pct <= STOP_LOSS_PCT:
                    trade.exit_date = day
                    trade.exit_price = current_price
                    trade.exit_reason = f"停損 ({pnl_pct:.2%})"
                    trade.pnl_pct = pnl_pct
                    trade.holding_days = holding_days
                    if trade.direction == "Long":
                        trade.pnl = (current_price - trade.entry_price) * trade.shares
                    else:
                        trade.pnl = (trade.entry_price - current_price) * trade.shares
                    tickers_to_close.append(ticker)
                    continue

                # 檢查停利
                if pnl_pct >= TAKE_PROFIT_PCT:
                    trade.exit_date = day
                    trade.exit_price = current_price
                    trade.exit_reason = f"停利 ({pnl_pct:.2%})"
                    trade.pnl_pct = pnl_pct
                    trade.holding_days = holding_days
                    if trade.direction == "Long":
                        trade.pnl = (current_price - trade.entry_price) * trade.shares
                    else:
                        trade.pnl = (trade.entry_price - current_price) * trade.shares
                    tickers_to_close.append(ticker)
                    continue

                # 檢查最大持倉天數
                if holding_days >= MAX_HOLDING_DAYS:
                    trade.exit_date = day
                    trade.exit_price = current_price
                    trade.exit_reason = f"最大持倉 ({holding_days}日)"
                    trade.pnl_pct = pnl_pct
                    trade.holding_days = holding_days
                    if trade.direction == "Long":
                        trade.pnl = (current_price - trade.entry_price) * trade.shares
                    else:
                        trade.pnl = (trade.entry_price - current_price) * trade.shares
                    tickers_to_close.append(ticker)

            # 出場，回收資金
            for ticker in tickers_to_close:
                trade = self.positions.pop(ticker)
                self.cash += trade.shares * trade.exit_price
                self.closed_trades.append(trade)

            # ── 2. 處理當日新訊號 ──
            if day in date_signals:
                for signal in date_signals[day]:
                    ticker = signal["ticker"]

                    # 已有持倉，跳過
                    if ticker in self.positions:
                        skip_count += 1
                        continue

                    # 取得次日收盤價作為進場價
                    price_info = self._get_price_on_date(ticker, day, offset_days=1)
                    if price_info is None:
                        skip_count += 1
                        continue

                    entry_date_actual, entry_price = price_info

                    # 計算部位大小
                    position_value = self._position_size(signal)
                    if position_value <= 0 or entry_price <= 0:
                        skip_count += 1
                        continue

                    # 確保有足夠現金
                    if self.cash < position_value * 0.5:
                        skip_count += 1
                        continue

                    position_value = min(position_value, self.cash)
                    shares = position_value / entry_price

                    # 決定方向: Buy -> Long, Sale -> Long (反向操作)
                    if signal["direction"] == "Buy":
                        direction = "Long"
                        reason = f"國會買入訊號 (score={signal['signal_score']})"
                    else:
                        direction = "Long"  # Sale 作為反向指標，也做多
                        reason = f"國會賣出反向訊號 (score={signal['signal_score']})"

                    trade = SimTrade(
                        ticker=ticker,
                        direction=direction,
                        entry_date=entry_date_actual,
                        entry_price=entry_price,
                        shares=shares,
                        signal_score=signal["signal_score"],
                        politician=signal["politician_name"],
                        reason=reason,
                    )
                    self.positions[ticker] = trade
                    self.cash -= shares * entry_price
                    entry_count += 1

            # ── 3. 記錄每日 equity ──
            equity = self._mark_to_market(day)
            self.equity_history.append((day, equity))

        # ── 4. 結束: 強制平倉所有剩餘持倉 ──
        last_day = all_dates[-1] if all_dates else date.today().strftime("%Y-%m-%d")
        for ticker in list(self.positions.keys()):
            trade = self.positions.pop(ticker)
            if ticker in self.price_cache:
                prices = self.price_cache[ticker]
                if len(prices) > 0:
                    exit_price = float(prices.iloc[-1]["Close"])
                else:
                    exit_price = trade.entry_price
            else:
                exit_price = trade.entry_price

            trade.exit_date = last_day
            trade.exit_price = exit_price
            trade.exit_reason = "模擬結束平倉"

            if trade.direction == "Long":
                pnl_pct = (exit_price - trade.entry_price) / trade.entry_price if trade.entry_price > 0 else 0
                trade.pnl = (exit_price - trade.entry_price) * trade.shares
            else:
                pnl_pct = (trade.entry_price - exit_price) / trade.entry_price if trade.entry_price > 0 else 0
                trade.pnl = (trade.entry_price - exit_price) * trade.shares

            trade.pnl_pct = pnl_pct

            # 持倉天數
            try:
                entry_ts = pd.Timestamp(trade.entry_date)
                exit_ts = pd.Timestamp(trade.exit_date)
                if ticker in self.price_cache:
                    p = self.price_cache[ticker]
                    h = p[(p.index >= entry_ts) & (p.index <= exit_ts)]
                    trade.holding_days = max(0, len(h) - 1)
                else:
                    trade.holding_days = (exit_ts - entry_ts).days
            except Exception:
                trade.holding_days = 0

            self.cash += trade.shares * exit_price
            self.closed_trades.append(trade)

        print(f"  模擬完成: {entry_count} 筆進場, {skip_count} 筆跳過, "
              f"{len(self.closed_trades)} 筆已平倉")

    # ── 績效指標 ────────────────────────────────────────────────────

    def calculate_metrics(self) -> dict:
        """計算績效指標。"""
        if not self.equity_history:
            return {}

        # Equity curve
        dates = [e[0] for e in self.equity_history]
        equities = [e[1] for e in self.equity_history]

        final_equity = equities[-1]
        total_return = (final_equity - self.initial_capital) / self.initial_capital

        # 年化報酬率
        if len(dates) >= 2:
            start_dt = datetime.strptime(dates[0], "%Y-%m-%d")
            end_dt = datetime.strptime(dates[-1], "%Y-%m-%d")
            days_elapsed = (end_dt - start_dt).days
            if days_elapsed > 0:
                annual_return = (1 + total_return) ** (365.0 / days_elapsed) - 1
            else:
                annual_return = 0.0
        else:
            annual_return = 0.0
            days_elapsed = 0

        # 日報酬率序列
        equity_series = pd.Series(equities, index=pd.to_datetime(dates))
        daily_returns = equity_series.pct_change().dropna()

        # Sharpe Ratio (假設無風險利率 = 4.5% 年化)
        rf_daily = 0.045 / 252
        if len(daily_returns) > 1 and daily_returns.std() > 0:
            sharpe = (daily_returns.mean() - rf_daily) / daily_returns.std() * math.sqrt(252)
        else:
            sharpe = 0.0

        # Max Drawdown
        peak = equity_series.expanding().max()
        drawdown = (equity_series - peak) / peak
        max_drawdown = float(drawdown.min())

        # Max Drawdown Duration (交易日)
        max_dd_duration = 0
        current_dd_duration = 0
        for dd_val in drawdown.values:
            if dd_val < 0:
                current_dd_duration += 1
                max_dd_duration = max(max_dd_duration, current_dd_duration)
            else:
                current_dd_duration = 0

        # Win/Loss 統計
        trades = self.closed_trades
        if trades:
            wins = [t for t in trades if t.pnl > 0]
            losses = [t for t in trades if t.pnl <= 0]
            win_rate = len(wins) / len(trades)
            avg_win = np.mean([t.pnl_pct for t in wins]) if wins else 0.0
            avg_loss = np.mean([abs(t.pnl_pct) for t in losses]) if losses else 0.0
            win_loss_ratio = avg_win / avg_loss if avg_loss > 0 else float("inf")
            avg_holding = np.mean([t.holding_days for t in trades])
            total_pnl = sum(t.pnl for t in trades)
        else:
            win_rate = 0.0
            avg_win = 0.0
            avg_loss = 0.0
            win_loss_ratio = 0.0
            avg_holding = 0.0
            total_pnl = 0.0

        # Calmar Ratio
        calmar = annual_return / abs(max_drawdown) if max_drawdown < 0 else 0.0

        # SPY 比較 (Buy & Hold)
        spy_return = 0.0
        if self.spy_prices is not None and len(self.spy_prices) > 1:
            spy_start = float(self.spy_prices.iloc[0]["Close"])
            spy_end = float(self.spy_prices.iloc[-1]["Close"])
            spy_return = (spy_end - spy_start) / spy_start if spy_start > 0 else 0.0

        metrics = {
            "initial_capital": self.initial_capital,
            "final_equity": round(final_equity, 2),
            "total_return": round(total_return, 4),
            "annual_return": round(annual_return, 4),
            "sharpe_ratio": round(sharpe, 2),
            "max_drawdown": round(max_drawdown, 4),
            "max_dd_duration_days": max_dd_duration,
            "calmar_ratio": round(calmar, 2),
            "win_rate": round(win_rate, 4),
            "avg_win_pct": round(float(avg_win), 4),
            "avg_loss_pct": round(float(avg_loss), 4),
            "win_loss_ratio": round(win_loss_ratio, 2),
            "total_trades": len(trades),
            "avg_holding_days": round(float(avg_holding), 1),
            "total_pnl_dollar": round(total_pnl, 2),
            "spy_return": round(spy_return, 4),
            "excess_return": round(total_return - spy_return, 4),
            "simulation_days": days_elapsed,
            "strategy": self.strategy,
        }
        return metrics

    # ── 圖表 ────────────────────────────────────────────────────────

    def generate_plots(self, output_dir: Optional[str] = None):
        """產生圖表並存為 PNG。"""
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            import matplotlib.dates as mdates
        except ImportError:
            logger.warning("matplotlib 未安裝，跳過圖表生成")
            return

        if output_dir is None:
            output_dir = str(PROJECT_ROOT / "docs" / "plots")
        os.makedirs(output_dir, exist_ok=True)

        if not self.equity_history:
            return

        dates = pd.to_datetime([e[0] for e in self.equity_history])
        equities = [e[1] for e in self.equity_history]
        equity_series = pd.Series(equities, index=dates)

        # ── 1. Equity Curve: Portfolio vs SPY ──
        fig, ax = plt.subplots(figsize=(14, 6))

        # 正規化到 100
        portfolio_norm = equity_series / equity_series.iloc[0] * 100
        ax.plot(portfolio_norm.index, portfolio_norm.values,
                label="Portfolio", color="#2196F3", linewidth=2)

        if self.spy_prices is not None and len(self.spy_prices) > 0:
            spy_close = self.spy_prices["Close"]
            spy_norm = spy_close / spy_close.iloc[0] * 100
            # 對齊日期
            common = portfolio_norm.index.intersection(spy_norm.index)
            if len(common) > 0:
                ax.plot(common, spy_norm.loc[common].values,
                        label="SPY (Buy & Hold)", color="#FF9800",
                        linewidth=1.5, linestyle="--")

        ax.set_title("Portfolio vs SPY — Equity Curve", fontsize=14)
        ax.set_xlabel("Date")
        ax.set_ylabel("Normalized Value (Start = 100)")
        ax.legend()
        ax.grid(True, alpha=0.3)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
        fig.autofmt_xdate()
        fig.tight_layout()
        path1 = os.path.join(output_dir, "portfolio_equity_curve.png")
        fig.savefig(path1, dpi=150)
        plt.close(fig)
        print(f"  [圖表] Equity curve: {path1}")

        # ── 2. Drawdown Chart ──
        fig, ax = plt.subplots(figsize=(14, 4))
        peak = equity_series.expanding().max()
        drawdown = (equity_series - peak) / peak
        ax.fill_between(drawdown.index, drawdown.values, 0,
                        color="#F44336", alpha=0.4)
        ax.plot(drawdown.index, drawdown.values, color="#D32F2F", linewidth=1)
        ax.set_title("Portfolio Drawdown", fontsize=14)
        ax.set_xlabel("Date")
        ax.set_ylabel("Drawdown (%)")
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f"{y:.1%}"))
        ax.grid(True, alpha=0.3)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
        fig.autofmt_xdate()
        fig.tight_layout()
        path2 = os.path.join(output_dir, "portfolio_drawdown.png")
        fig.savefig(path2, dpi=150)
        plt.close(fig)
        print(f"  [圖表] Drawdown: {path2}")

        # ── 3. Monthly Return Heatmap ──
        daily_returns = equity_series.pct_change().dropna()
        if len(daily_returns) > 5:
            # 用 groupby 手動計算月報酬率
            monthly_data = []
            for dt, ret in daily_returns.items():
                monthly_data.append({
                    "year": dt.year,
                    "month": dt.month,
                    "return": ret,
                })
            monthly_df = pd.DataFrame(monthly_data)
            monthly_returns = monthly_df.groupby(["year", "month"])["return"].apply(
                lambda x: (1 + x).prod() - 1
            )

            if len(monthly_returns) > 0:
                fig, ax = plt.subplots(figsize=(10, 4))

                # 轉為表格形式
                month_labels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
                years = sorted(set(monthly_returns.index.get_level_values(0)))
                heatmap_data = []
                for year in years:
                    row = []
                    for month in range(1, 13):
                        if (year, month) in monthly_returns.index:
                            row.append(monthly_returns.loc[(year, month)] * 100)
                        else:
                            row.append(np.nan)
                    heatmap_data.append(row)

                heatmap_array = np.array(heatmap_data)
                im = ax.imshow(heatmap_array, cmap="RdYlGn", aspect="auto",
                               vmin=-5, vmax=5)

                ax.set_xticks(range(12))
                ax.set_xticklabels(month_labels)
                ax.set_yticks(range(len(years)))
                ax.set_yticklabels([str(y) for y in years])

                # 加數值標記
                for i in range(len(years)):
                    for j in range(12):
                        val = heatmap_array[i, j]
                        if not np.isnan(val):
                            ax.text(j, i, f"{val:.1f}%",
                                    ha="center", va="center",
                                    fontsize=9, fontweight="bold",
                                    color="black" if abs(val) < 3 else "white")

                plt.colorbar(im, ax=ax, label="Monthly Return (%)")
                ax.set_title("Monthly Returns Heatmap", fontsize=14)
                fig.tight_layout()
                path3 = os.path.join(output_dir, "portfolio_monthly_heatmap.png")
                fig.savefig(path3, dpi=150)
                plt.close(fig)
                print(f"  [圖表] Monthly heatmap: {path3}")

    # ── 資料庫寫入 ──────────────────────────────────────────────────

    def save_to_db(self, metrics: dict):
        """將模擬結果存入 portfolio_simulation 表。"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 建表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS portfolio_simulation (
                id TEXT PRIMARY KEY,
                simulation_date DATE NOT NULL,
                strategy TEXT NOT NULL,
                initial_capital REAL,
                final_equity REAL,
                total_return REAL,
                annual_return REAL,
                sharpe_ratio REAL,
                max_drawdown REAL,
                max_dd_duration_days INTEGER,
                calmar_ratio REAL,
                win_rate REAL,
                avg_win_pct REAL,
                avg_loss_pct REAL,
                win_loss_ratio REAL,
                total_trades INTEGER,
                avg_holding_days REAL,
                total_pnl_dollar REAL,
                spy_return REAL,
                excess_return REAL,
                simulation_days INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS simulation_trades (
                id TEXT PRIMARY KEY,
                simulation_id TEXT NOT NULL,
                ticker TEXT NOT NULL,
                direction TEXT,
                entry_date DATE,
                entry_price REAL,
                exit_date DATE,
                exit_price REAL,
                shares REAL,
                pnl REAL,
                pnl_pct REAL,
                holding_days INTEGER,
                exit_reason TEXT,
                signal_score REAL,
                politician TEXT,
                reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (simulation_id) REFERENCES portfolio_simulation(id)
            )
        """)

        sim_id = str(uuid.uuid4())
        today_str = date.today().strftime("%Y-%m-%d")

        cursor.execute("""
            INSERT INTO portfolio_simulation
            (id, simulation_date, strategy, initial_capital, final_equity,
             total_return, annual_return, sharpe_ratio, max_drawdown,
             max_dd_duration_days, calmar_ratio, win_rate, avg_win_pct,
             avg_loss_pct, win_loss_ratio, total_trades, avg_holding_days,
             total_pnl_dollar, spy_return, excess_return, simulation_days)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            sim_id, today_str, self.strategy,
            metrics.get("initial_capital"),
            metrics.get("final_equity"),
            metrics.get("total_return"),
            metrics.get("annual_return"),
            metrics.get("sharpe_ratio"),
            metrics.get("max_drawdown"),
            metrics.get("max_dd_duration_days"),
            metrics.get("calmar_ratio"),
            metrics.get("win_rate"),
            metrics.get("avg_win_pct"),
            metrics.get("avg_loss_pct"),
            metrics.get("win_loss_ratio"),
            metrics.get("total_trades"),
            metrics.get("avg_holding_days"),
            metrics.get("total_pnl_dollar"),
            metrics.get("spy_return"),
            metrics.get("excess_return"),
            metrics.get("simulation_days"),
        ))

        # 寫入交易明細
        for trade in self.closed_trades:
            cursor.execute("""
                INSERT INTO simulation_trades
                (id, simulation_id, ticker, direction, entry_date, entry_price,
                 exit_date, exit_price, shares, pnl, pnl_pct, holding_days,
                 exit_reason, signal_score, politician, reason)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                str(uuid.uuid4()), sim_id,
                trade.ticker, trade.direction,
                trade.entry_date, trade.entry_price,
                trade.exit_date, trade.exit_price,
                round(trade.shares, 4), round(trade.pnl, 2),
                round(trade.pnl_pct, 4), trade.holding_days,
                trade.exit_reason, trade.signal_score,
                trade.politician, trade.reason,
            ))

        conn.commit()
        conn.close()
        logger.info(f"已寫入模擬結果到 portfolio_simulation 表 (ID: {sim_id[:8]})")

    # ── 報告生成 ────────────────────────────────────────────────────

    def generate_report(self, metrics: dict, output_path: Optional[str] = None) -> str:
        """產生 Markdown 格式的回測報告。"""
        today_str = date.today().strftime("%Y-%m-%d")
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if output_path is None:
            report_dir = PROJECT_ROOT / "docs" / "reports"
            os.makedirs(str(report_dir), exist_ok=True)
            output_path = str(report_dir / f"Portfolio_Simulation_{today_str}.md")

        lines = []
        lines.append("# Portfolio Backtest Simulation Report")
        lines.append(f"**Date**: {today_str}")
        lines.append(f"**Generated**: {now_str}")
        lines.append("")
        lines.append("---")
        lines.append("")

        # ── 摘要 ──
        lines.append("## Performance Summary")
        lines.append("")
        lines.append("| Metric | Portfolio | SPY (Buy & Hold) |")
        lines.append("|--------|-----------|-------------------|")
        lines.append(f"| Initial Capital | ${metrics['initial_capital']:,.0f} | ${metrics['initial_capital']:,.0f} |")
        lines.append(f"| Final Equity | ${metrics['final_equity']:,.0f} | ${metrics['initial_capital'] * (1 + metrics['spy_return']):,.0f} |")
        lines.append(f"| Total Return | {metrics['total_return']:.2%} | {metrics['spy_return']:.2%} |")
        lines.append(f"| Annualized Return | {metrics['annual_return']:.2%} | — |")
        lines.append(f"| **Excess Return** | **{metrics['excess_return']:.2%}** | — |")
        lines.append("")

        # ── 風險指標 ──
        lines.append("## Risk Metrics")
        lines.append("")
        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        lines.append(f"| Sharpe Ratio | {metrics['sharpe_ratio']:.2f} |")
        lines.append(f"| Max Drawdown | {metrics['max_drawdown']:.2%} |")
        lines.append(f"| Max DD Duration | {metrics['max_dd_duration_days']} trading days |")
        lines.append(f"| Calmar Ratio | {metrics['calmar_ratio']:.2f} |")
        lines.append("")

        # ── 交易統計 ──
        lines.append("## Trade Statistics")
        lines.append("")
        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        lines.append(f"| Total Trades | {metrics['total_trades']} |")
        lines.append(f"| Win Rate | {metrics['win_rate']:.1%} |")
        lines.append(f"| Avg Win | {metrics['avg_win_pct']:.2%} |")
        lines.append(f"| Avg Loss | {metrics['avg_loss_pct']:.2%} |")
        lines.append(f"| Win/Loss Ratio | {metrics['win_loss_ratio']:.2f} |")
        lines.append(f"| Avg Holding Period | {metrics['avg_holding_days']:.0f} trading days |")
        lines.append(f"| Total P&L (Dollar) | ${metrics['total_pnl_dollar']:,.0f} |")
        lines.append("")

        # ── 模擬參數 ──
        lines.append("## Simulation Parameters")
        lines.append("")
        lines.append("| Parameter | Value |")
        lines.append("|-----------|-------|")
        lines.append(f"| Strategy | {metrics['strategy']} |")
        lines.append(f"| Initial Capital | ${metrics['initial_capital']:,.0f} |")
        lines.append(f"| Simulation Period | {metrics['simulation_days']} calendar days |")
        lines.append(f"| SQS Threshold | >= {MIN_SQS_SCORE:.0f} (Gold/Silver grade) |")
        lines.append(f"| Stop-Loss | {STOP_LOSS_PCT:.0%} |")
        lines.append(f"| Take-Profit | {TAKE_PROFIT_PCT:.0%} |")
        lines.append(f"| Max Holding Days | {MAX_HOLDING_DAYS} |")
        lines.append(f"| Max Position Size | {MAX_POSITION_PCT:.0%} |")
        lines.append("")

        # ── 交易明細 (Top 20) ──
        lines.append("## Trade Details (Top 20 by P&L)")
        lines.append("")
        sorted_trades = sorted(self.closed_trades, key=lambda t: t.pnl, reverse=True)
        top_trades = sorted_trades[:20]

        lines.append("| # | Ticker | Direction | Entry | Exit | Entry$ | Exit$ | P&L | P&L% | Days | Exit Reason | Politician |")
        lines.append("|---|--------|-----------|-------|------|--------|-------|-----|------|------|-------------|------------|")
        for i, t in enumerate(top_trades, 1):
            lines.append(
                f"| {i} | **{t.ticker}** | {t.direction} | "
                f"{t.entry_date} | {t.exit_date} | "
                f"${t.entry_price:.2f} | ${t.exit_price:.2f} | "
                f"${t.pnl:,.0f} | {t.pnl_pct:.2%} | "
                f"{t.holding_days} | {t.exit_reason} | {t.politician} |"
            )
        lines.append("")

        # ── 退出原因分布 ──
        lines.append("## Exit Reason Distribution")
        lines.append("")
        reason_counts = defaultdict(int)
        reason_pnl = defaultdict(float)
        for t in self.closed_trades:
            reason = t.exit_reason.split(" (")[0] if t.exit_reason else "Unknown"
            reason_counts[reason] += 1
            reason_pnl[reason] += t.pnl

        lines.append("| Exit Reason | Count | Total P&L |")
        lines.append("|-------------|-------|-----------|")
        for reason in sorted(reason_counts.keys()):
            lines.append(
                f"| {reason} | {reason_counts[reason]} | "
                f"${reason_pnl[reason]:,.0f} |"
            )
        lines.append("")

        # ── 圖表 ──
        lines.append("## Charts")
        lines.append("")
        lines.append("![Equity Curve](../plots/portfolio_equity_curve.png)")
        lines.append("")
        lines.append("![Drawdown](../plots/portfolio_drawdown.png)")
        lines.append("")
        lines.append("![Monthly Returns](../plots/portfolio_monthly_heatmap.png)")
        lines.append("")

        # ── 方法論 ──
        lines.append("## Methodology")
        lines.append("")
        lines.append("### Signal Generation")
        lines.append("")
        lines.append("- Source: congress_trades table (congressional trading disclosures)")
        lines.append(f"- Filter: SQS (Signal Quality Score) >= {MIN_SQS_SCORE} (Gold/Silver grade)")
        lines.append("- Signal scoring: 40% SQS + 20% filing lag + 20% amount + 10% politician rank + 10% convergence")
        lines.append("- Buy signals: enter long at next-day close")
        lines.append("- Sale signals: used as contrarian indicator (enter long)")
        lines.append("")
        lines.append("### Risk Management")
        lines.append("")
        lines.append(f"- Stop-loss: {STOP_LOSS_PCT:.0%} from entry")
        lines.append(f"- Take-profit: {TAKE_PROFIT_PCT:.0%} from entry")
        lines.append(f"- Max holding period: {MAX_HOLDING_DAYS} trading days")
        lines.append(f"- Max position size: {MAX_POSITION_PCT:.0%} of portfolio")
        lines.append("")
        lines.append("### Position Sizing")
        lines.append("")
        if self.strategy == "conviction":
            lines.append("- Conviction-weighted: 3% base + up to 7% based on signal score")
        else:
            lines.append("- Equal weight: 5% of portfolio per position")
        lines.append("")

        # ── 免責聲明 ──
        lines.append("## Disclaimer")
        lines.append("")
        lines.append("This is a historical simulation for research purposes only. It does not ")
        lines.append("constitute investment advice. Past performance does not guarantee future ")
        lines.append("results. Transaction costs, slippage, and market impact are not included. ")
        lines.append("Congressional trading disclosures are subject to reporting delays.")
        lines.append("")
        lines.append("---")
        lines.append(f"*Generated by Political Alpha Monitor — Portfolio Simulator v1.0 — {now_str}*")
        lines.append("")

        report_content = "\n".join(lines)

        # 寫入檔案
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(report_content)

        print(f"  [報告] {output_path}")
        return report_content


# ══════════════════════════════════════════════════════════════════════
#  終端輸出
# ══════════════════════════════════════════════════════════════════════

def print_simulation_summary(metrics: dict, closed_trades: List[SimTrade]):
    """在終端印出模擬摘要。"""
    print()
    print("=" * 80)
    print("  Portfolio Backtest Simulation — Political Alpha Monitor")
    print(f"  Strategy: {metrics.get('strategy', 'N/A')}")
    print("=" * 80)
    print()

    print("  [Performance Summary]")
    print(f"    Initial Capital:    ${metrics['initial_capital']:>12,.0f}")
    print(f"    Final Equity:       ${metrics['final_equity']:>12,.0f}")
    print(f"    Total Return:       {metrics['total_return']:>12.2%}")
    print(f"    Annualized Return:  {metrics['annual_return']:>12.2%}")
    print(f"    SPY Return:         {metrics['spy_return']:>12.2%}")
    print(f"    Excess Return:      {metrics['excess_return']:>12.2%}")
    print()

    print("  [Risk Metrics]")
    print(f"    Sharpe Ratio:       {metrics['sharpe_ratio']:>12.2f}")
    print(f"    Max Drawdown:       {metrics['max_drawdown']:>12.2%}")
    print(f"    Max DD Duration:    {metrics['max_dd_duration_days']:>12d} days")
    print(f"    Calmar Ratio:       {metrics['calmar_ratio']:>12.2f}")
    print()

    print("  [Trade Statistics]")
    print(f"    Total Trades:       {metrics['total_trades']:>12d}")
    print(f"    Win Rate:           {metrics['win_rate']:>12.1%}")
    print(f"    Avg Win:            {metrics['avg_win_pct']:>12.2%}")
    print(f"    Avg Loss:           {metrics['avg_loss_pct']:>12.2%}")
    print(f"    Win/Loss Ratio:     {metrics['win_loss_ratio']:>12.2f}")
    print(f"    Avg Holding:        {metrics['avg_holding_days']:>12.0f} days")
    print(f"    Total P&L:          ${metrics['total_pnl_dollar']:>12,.0f}")
    print()

    # Top 5 Winners / Losers
    if closed_trades:
        sorted_by_pnl = sorted(closed_trades, key=lambda t: t.pnl, reverse=True)

        print("  [Top 5 Winners]")
        for t in sorted_by_pnl[:5]:
            print(f"    {t.ticker:<8s}  {t.entry_date} -> {t.exit_date}  "
                  f"P&L: ${t.pnl:>8,.0f} ({t.pnl_pct:>+.2%})  "
                  f"{t.exit_reason}")

        print()
        print("  [Top 5 Losers]")
        for t in sorted_by_pnl[-5:]:
            print(f"    {t.ticker:<8s}  {t.entry_date} -> {t.exit_date}  "
                  f"P&L: ${t.pnl:>8,.0f} ({t.pnl_pct:>+.2%})  "
                  f"{t.exit_reason}")

    print()
    print("=" * 80)
    print()


# ══════════════════════════════════════════════════════════════════════
#  主流程
# ══════════════════════════════════════════════════════════════════════

def run_simulation(capital: float = 100000.0,
                   strategy: str = "equal",
                   start_date: Optional[str] = None,
                   end_date: Optional[str] = None,
                   db_path: Optional[str] = None) -> dict:
    """完整回測模擬流程。"""
    print()
    print("Portfolio Backtest Simulator — Political Alpha Monitor")
    print(f"  Capital: ${capital:,.0f}")
    print(f"  Strategy: {strategy}")
    if start_date:
        print(f"  Start date: {start_date}")
    if end_date:
        print(f"  End date: {end_date}")
    print()

    sim = PortfolioSimulator(
        capital=capital,
        strategy=strategy,
        start_date=start_date,
        end_date=end_date,
        db_path=db_path,
    )

    # 1. 載入資料
    print("[1/7] 載入交易資料...")
    sim.load_data()
    print(f"  載入 {len(sim.signals)} 筆原始訊號")

    # 2. 過濾訊號
    print("[2/7] 過濾訊號 (SQS >= 60)...")
    filtered = sim.filter_signals()
    print(f"  過濾後 {len(filtered)} 筆合格訊號")

    if not filtered:
        print("  [錯誤] 無合格訊號可模擬")
        return {}

    # 3. 下載股價
    print("[3/7] 下載歷史股價...")
    sim.download_prices(filtered)

    # 4. 執行模擬
    print("[4/7] 執行回測模擬...")
    sim.simulate(filtered)

    # 5. 計算績效
    print("[5/7] 計算績效指標...")
    metrics = sim.calculate_metrics()

    if not metrics:
        print("  [錯誤] 無法計算績效指標")
        return {}

    # 終端輸出
    print_simulation_summary(metrics, sim.closed_trades)

    # 6. 產生圖表
    print("[6/7] 產生圖表...")
    sim.generate_plots()

    # 7. 儲存結果
    print("[7/7] 儲存結果...")
    sim.save_to_db(metrics)
    report_content = sim.generate_report(metrics)

    print(f"  DB: portfolio_simulation + simulation_trades 表")
    print()

    return metrics
