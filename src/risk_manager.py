"""風險管理模組 — 投資組合風險評估與控制

針對 Political Alpha Monitor 的投資組合提供完整風險管理:
  1. 部位層級風險規則 (停損、停利、持倉天數、追蹤止損)
  2. 投資組合層級規則 (板塊集中度、單一部位上限、Beta、回撤)
  3. 訊號層級風險過濾 (SQS、Filing lag、收斂數據點)
  4. 綜合風險評分 (0-100，越高越危險)
  5. 風險評估資料庫表 (risk_assessments)

用法:
    python -m src.risk_manager           # 執行風險檢查
    python run_risk_check.py             # 透過入口點執行

Research Brief: RB-005
"""

import logging
import math
import os
import sqlite3
import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple

from src.config import DB_PATH, PROJECT_ROOT

logger = logging.getLogger("RiskManager")

# ══════════════════════════════════════════════════════════════════════
#  VIX 體制感知 (RB-004: VIX Goldilocks Zone)
# ══════════════════════════════════════════════════════════════════════

# VIX 體制 → 風險乘數 (越高=越危險)
# 基於 RB-004: VIX 14-16 最佳，<14 或 >16 均不利
VIX_RISK_MULTIPLIER = {
    "ultra_low":  0.9,   # VIX<12: 市場自滿，低波動但隱含風險
    "goldilocks": 0.7,   # VIX 14-16: 最佳交易區間，降低風險
    "moderate":   1.0,   # VIX 16-20: 正常
    "high":       1.3,   # VIX 20-30: 高波動，提高風險
    "extreme":    1.6,   # VIX>30: 極端恐慌，大幅提高風險
    "unknown":    1.0,   # 無法取得 VIX
}

# VIX 極端區域自動觸發的行動建議
VIX_EXTREME_THRESHOLD = 30    # VIX > 30 → 建議暫停新進場
VIX_HIGH_THRESHOLD = 25       # VIX > 25 → 建議減倉


# ══════════════════════════════════════════════════════════════════════
#  風險參數常數
# ══════════════════════════════════════════════════════════════════════

# ── 部位層級 ──
STOP_LOSS_PCT = -0.05          # 停損線: -5%
TAKE_PROFIT_PCT = 0.15         # 停利線: +15% (部分出場)
MAX_HOLDING_DAYS = 60          # 最大持倉天數 (交易日)
TRAILING_STOP_ACTIVATION = 0.05  # 追蹤止損啟動門檻: +5%
TRAILING_STOP_PCT = -0.03     # 追蹤止損回撤: -3% (從高點)

# ── 投資組合層級 ──
MAX_SECTOR_EXPOSURE = 0.30    # 單一板塊最大曝險: 30%
MAX_SINGLE_POSITION = 0.10    # 單一部位最大權重: 10%
MAX_PORTFOLIO_BETA = 1.3      # 投資組合 Beta 上限
DRAWDOWN_LIMIT = -0.10        # 回撤限制: -10% → 風險控制模式

# ── 訊號層級 ──
MIN_SQS_THRESHOLD = 0.40      # SQS 最低門檻 (40/100 = Bronze/Discard 以下拒絕)
MAX_FILING_LAG_DAYS = 45      # Filing lag 最大天數
MIN_CONVERGENCE_POINTS = 2    # 收斂訊號最少資料點數

# ── 風險評分權重 ──
RISK_WEIGHT_PNL = 25          # P&L 接近停損的風險
RISK_WEIGHT_SECTOR = 20       # 板塊集中度風險
RISK_WEIGHT_VOLATILITY = 20   # 波動率風險
RISK_WEIGHT_FRESHNESS = 15    # 資料新鮮度風險
RISK_WEIGHT_SQS = 10          # 訊號品質風險
RISK_WEIGHT_HOLDING = 10      # 持倉時間風險


# ══════════════════════════════════════════════════════════════════════
#  市場數據取得
# ══════════════════════════════════════════════════════════════════════

def fetch_current_prices(tickers: List[str]) -> Dict[str, dict]:
    """透過 yfinance 取得最新價格、30d 波動率、beta。"""
    try:
        import yfinance as yf
    except ImportError:
        logger.warning("yfinance 未安裝，無法取得即時價格")
        return {}

    result = {}
    batch_size = 20
    for i in range(0, len(tickers), batch_size):
        batch = tickers[i:i + batch_size]
        ticker_str = " ".join(batch)
        try:
            data = yf.download(ticker_str, period="65d", interval="1d",
                               progress=False, threads=True)
            if data.empty:
                continue

            # SPY 作為 beta 基準
            spy_data = yf.download("SPY", period="65d", interval="1d",
                                   progress=False)
            spy_returns = spy_data["Close"].squeeze().pct_change().dropna() if not spy_data.empty else None

            for t in batch:
                try:
                    if len(batch) > 1:
                        try:
                            close = data["Close"][t].dropna()
                        except (KeyError, TypeError):
                            close = data["Close"].dropna()
                    else:
                        close = data["Close"].dropna()
                        if hasattr(close, "columns"):
                            close = close.squeeze()

                    if len(close) < 5:
                        continue

                    price = float(close.iloc[-1])
                    peak = float(close.max())
                    returns = close.pct_change().dropna()

                    vol_30d = float(returns.std() * math.sqrt(252)) if len(returns) >= 5 else 0.0

                    # Beta 計算
                    beta = 1.0
                    if spy_returns is not None and len(returns) >= 10:
                        # 對齊日期
                        common = returns.index.intersection(spy_returns.index)
                        if len(common) >= 10:
                            r_stock = returns.loc[common]
                            r_spy = spy_returns.loc[common]
                            cov = float(r_stock.cov(r_spy))
                            var_spy = float(r_spy.var())
                            if var_spy > 0:
                                beta = round(cov / var_spy, 2)

                    result[t] = {
                        "price": round(price, 2),
                        "peak_60d": round(peak, 2),
                        "volatility_30d": round(vol_30d, 4),
                        "beta": beta,
                    }
                except Exception as e:
                    logger.debug(f"處理 {t} 失敗: {e}")
        except Exception as e:
            logger.warning(f"yfinance 批次下載失敗: {e}")

    return result


def fetch_entry_prices(tickers: List[str], entry_date: str) -> Dict[str, float]:
    """取得指定日期附近的股價作為進場價。"""
    try:
        import yfinance as yf
    except ImportError:
        return {}

    result = {}
    # 多抓幾天，防止非交易日
    start = (datetime.strptime(entry_date, "%Y-%m-%d") - timedelta(days=5)).strftime("%Y-%m-%d")
    end = (datetime.strptime(entry_date, "%Y-%m-%d") + timedelta(days=5)).strftime("%Y-%m-%d")

    ticker_str = " ".join(tickers)
    try:
        data = yf.download(ticker_str, start=start, end=end,
                           progress=False, threads=True)
        if data.empty:
            return result

        for t in tickers:
            try:
                if len(tickers) > 1:
                    try:
                        close = data["Close"][t].dropna()
                    except (KeyError, TypeError):
                        close = data["Close"].dropna()
                else:
                    close = data["Close"].dropna()
                    if hasattr(close, "columns"):
                        close = close.squeeze()

                if len(close) > 0:
                    # 取最接近 entry_date 的收盤價
                    result[t] = round(float(close.iloc[0]), 2)
            except Exception:
                pass
    except Exception as e:
        logger.warning(f"取得進場價失敗: {e}")

    return result


# ══════════════════════════════════════════════════════════════════════
#  資料庫操作
# ══════════════════════════════════════════════════════════════════════

def init_risk_table(db_path: Optional[str] = None):
    """建立 risk_assessments 資料表。"""
    if db_path is None:
        db_path = DB_PATH
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS risk_assessments (
            id TEXT PRIMARY KEY,
            ticker TEXT NOT NULL,
            assessment_date DATE NOT NULL,
            current_price REAL,
            entry_price REAL,
            pnl_pct REAL,
            peak_price REAL,
            drawdown_from_peak REAL,
            holding_days INTEGER,
            risk_score REAL NOT NULL,
            risk_level TEXT NOT NULL,
            violations TEXT,
            action_required TEXT,
            sector TEXT,
            weight REAL,
            beta REAL,
            volatility_30d REAL,
            sqs_avg REAL,
            filing_lag_avg REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_risk_date
        ON risk_assessments(assessment_date)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_risk_ticker
        ON risk_assessments(ticker)
    """)

    conn.commit()
    conn.close()


def save_assessments(assessments: List[dict], db_path: Optional[str] = None):
    """將風險評估結果寫入 DB。"""
    if db_path is None:
        db_path = DB_PATH
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    init_risk_table(db_path)

    today_str = date.today().strftime("%Y-%m-%d")
    # 清除今日已有的評估
    cursor.execute("DELETE FROM risk_assessments WHERE assessment_date = ?",
                   (today_str,))

    for a in assessments:
        cursor.execute("""
            INSERT INTO risk_assessments
            (id, ticker, assessment_date, current_price, entry_price, pnl_pct,
             peak_price, drawdown_from_peak, holding_days, risk_score, risk_level,
             violations, action_required, sector, weight, beta, volatility_30d,
             sqs_avg, filing_lag_avg)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            str(uuid.uuid4()),
            a["ticker"],
            today_str,
            a.get("current_price"),
            a.get("entry_price"),
            a.get("pnl_pct"),
            a.get("peak_price"),
            a.get("drawdown_from_peak"),
            a.get("holding_days"),
            a["risk_score"],
            a["risk_level"],
            "; ".join(a.get("violations", [])),
            "; ".join(a.get("actions", [])),
            a.get("sector"),
            a.get("weight"),
            a.get("beta"),
            a.get("volatility_30d"),
            a.get("sqs_avg"),
            a.get("filing_lag_avg"),
        ))

    conn.commit()
    conn.close()
    logger.info(f"已寫入 {len(assessments)} 筆風險評估到 risk_assessments 表")


# ══════════════════════════════════════════════════════════════════════
#  RiskManager 主類別
# ══════════════════════════════════════════════════════════════════════

class RiskManager:
    """投資組合風險管理器。

    執行三層風險檢查:
      1. 部位層級: 停損、停利、持倉天數、追蹤止損
      2. 投資組合層級: 板塊集中度、單一部位上限、Beta、回撤
      3. 訊號層級: SQS、Filing lag、收斂數據點
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or DB_PATH
        self.positions = []           # type: List[dict]
        self.market_data = {}         # type: Dict[str, dict]
        self.entry_prices = {}        # type: Dict[str, float]
        self.sqs_map = {}             # type: Dict[str, List[dict]]
        self.alpha_signals = {}       # type: Dict[str, List[dict]]
        self.convergence_map = {}     # type: Dict[str, dict]
        self.vix_regime = {"zone": "unknown", "vix": None, "multiplier": 1.0, "label": "N/A"}

    # ── 資料載入 ────────────────────────────────────────────────────

    def load_portfolio(self) -> List[dict]:
        """從 portfolio_positions 載入當前持倉。"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, ticker, sector, weight, conviction_score,
                   expected_alpha, volatility_30d, sharpe_estimate,
                   reasoning, created_at
            FROM portfolio_positions
            ORDER BY weight DESC
        """)
        self.positions = [dict(r) for r in cursor.fetchall()]
        conn.close()
        logger.info(f"載入 {len(self.positions)} 筆持倉")
        return self.positions

    def load_sqs_scores(self) -> Dict[str, List[dict]]:
        """載入 SQS 評分，按 ticker 分組。"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        self.sqs_map = defaultdict(list)
        try:
            cursor.execute("""
                SELECT ticker, sqs, grade, actionability, timeliness,
                       conviction, information_edge, market_impact
                FROM signal_quality_scores
                WHERE ticker IS NOT NULL
            """)
            for row in cursor.fetchall():
                self.sqs_map[row["ticker"]].append(dict(row))
        except sqlite3.OperationalError:
            logger.warning("signal_quality_scores 表不存在")

        conn.close()
        return dict(self.sqs_map)

    def load_alpha_signals(self) -> Dict[str, List[dict]]:
        """載入 alpha_signals，按 ticker 分組。"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        self.alpha_signals = defaultdict(list)
        try:
            cursor.execute("""
                SELECT ticker, direction, expected_alpha_5d, confidence,
                       signal_strength, filing_lag_days, sqs_score, sqs_grade,
                       has_convergence, politician_grade
                FROM alpha_signals
                WHERE ticker IS NOT NULL
            """)
            for row in cursor.fetchall():
                self.alpha_signals[row["ticker"]].append(dict(row))
        except sqlite3.OperationalError:
            logger.warning("alpha_signals 表不存在")

        conn.close()
        return dict(self.alpha_signals)

    def load_convergence(self) -> Dict[str, dict]:
        """載入收斂訊號。"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        self.convergence_map = {}
        try:
            cursor.execute("""
                SELECT ticker, direction, politician_count, score
                FROM convergence_signals
            """)
            for row in cursor.fetchall():
                self.convergence_map[row["ticker"]] = dict(row)
        except sqlite3.OperationalError:
            logger.warning("convergence_signals 表不存在")

        conn.close()
        return self.convergence_map

    def load_vix_regime(self) -> dict:
        """載入當前 VIX 體制 (透過 signal_enhancer 的 VIXRegimeDetector)。"""
        try:
            from src.signal_enhancer import VIXRegimeDetector
            detector = VIXRegimeDetector()
            regime = detector.classify_regime()
            self.vix_regime = regime
            logger.info("VIX regime: %.2f (%s, risk_mult=%.1f)",
                        regime.get("vix", 0) or 0,
                        regime.get("zone", "unknown"),
                        VIX_RISK_MULTIPLIER.get(regime.get("zone", "unknown"), 1.0))
        except Exception as e:
            logger.warning("VIX regime detection failed: %s", e)
            self.vix_regime = {"zone": "unknown", "vix": None, "multiplier": 1.0, "label": "N/A"}
        return self.vix_regime

    # ── 部位層級風險檢查 ────────────────────────────────────────────

    def check_position_risks(self, pos: dict) -> dict:
        """檢查單一部位的風險規則。

        回傳:
            {violations: list, actions: list, metrics: dict}
        """
        ticker = pos["ticker"]
        violations = []
        actions = []
        metrics = {}

        mkt = self.market_data.get(ticker, {})
        current_price = mkt.get("price", 0)
        peak_price = mkt.get("peak_60d", current_price)
        entry_price = self.entry_prices.get(ticker, current_price)

        # P&L 計算
        pnl_pct = 0.0
        if entry_price > 0:
            pnl_pct = (current_price - entry_price) / entry_price
        metrics["pnl_pct"] = round(pnl_pct, 4)
        metrics["current_price"] = current_price
        metrics["entry_price"] = entry_price
        metrics["peak_price"] = peak_price

        # 從高點回撤
        drawdown_from_peak = 0.0
        if peak_price > 0:
            drawdown_from_peak = (current_price - peak_price) / peak_price
        metrics["drawdown_from_peak"] = round(drawdown_from_peak, 4)

        # ── 規則 1: 停損 ──
        if pnl_pct <= STOP_LOSS_PCT:
            violations.append(
                f"STOP_LOSS: P&L {pnl_pct:.2%} 觸及停損線 ({STOP_LOSS_PCT:.0%})"
            )
            actions.append(f"EXIT: 立即停損出場 {ticker}")

        # ── 規則 2: 停利 ──
        if pnl_pct >= TAKE_PROFIT_PCT:
            violations.append(
                f"TAKE_PROFIT: P&L {pnl_pct:.2%} 達到停利線 ({TAKE_PROFIT_PCT:.0%})"
            )
            actions.append(f"PARTIAL_EXIT: 部分獲利了結 {ticker} (建議減倉 50%)")

        # ── 規則 3: 最大持倉天數 ──
        created_at = pos.get("created_at", "")
        holding_days = 0
        if created_at:
            try:
                entry_dt = datetime.strptime(created_at[:10], "%Y-%m-%d")
                holding_days = (datetime.now() - entry_dt).days
            except (ValueError, TypeError):
                pass
        metrics["holding_days"] = holding_days

        if holding_days > MAX_HOLDING_DAYS:
            violations.append(
                f"MAX_HOLDING: 持倉 {holding_days} 天超過上限 ({MAX_HOLDING_DAYS} 天)"
            )
            actions.append(f"REVIEW: 檢視是否應繼續持有 {ticker}")

        # ── 規則 4: 追蹤止損 ──
        if pnl_pct >= TRAILING_STOP_ACTIVATION and drawdown_from_peak <= TRAILING_STOP_PCT:
            violations.append(
                f"TRAILING_STOP: 已獲利 {pnl_pct:.2%} 但從高點回撤 "
                f"{drawdown_from_peak:.2%} 觸及追蹤止損 ({TRAILING_STOP_PCT:.0%})"
            )
            actions.append(f"EXIT: 追蹤止損觸發，出場 {ticker}")

        return {"violations": violations, "actions": actions, "metrics": metrics}

    # ── 投資組合層級風險檢查 ────────────────────────────────────────

    def check_portfolio_risks(self) -> dict:
        """檢查投資組合層級的風險規則。

        回傳:
            {violations: list, actions: list, metrics: dict}
        """
        violations = []
        actions = []
        metrics = {}

        if not self.positions:
            return {"violations": [], "actions": [], "metrics": {}}

        # ── 規則 1: 板塊集中度 ──
        sector_weights = defaultdict(float)
        for pos in self.positions:
            sector_weights[pos.get("sector", "Unknown")] += pos["weight"]

        metrics["sector_weights"] = dict(sector_weights)
        breached_sectors = []
        for sector, weight in sector_weights.items():
            if weight > MAX_SECTOR_EXPOSURE:
                breached_sectors.append((sector, weight))
                violations.append(
                    f"SECTOR_CONCENTRATION: {sector} 佔比 {weight:.2%} "
                    f"超過上限 ({MAX_SECTOR_EXPOSURE:.0%})"
                )
                actions.append(
                    f"REBALANCE: 減少 {sector} 曝險至 {MAX_SECTOR_EXPOSURE:.0%} 以下"
                )
        metrics["breached_sectors"] = breached_sectors

        # ── 規則 2: 單一部位上限 ──
        for pos in self.positions:
            if pos["weight"] > MAX_SINGLE_POSITION:
                violations.append(
                    f"POSITION_LIMIT: {pos['ticker']} 權重 {pos['weight']:.2%} "
                    f"超過上限 ({MAX_SINGLE_POSITION:.0%})"
                )
                actions.append(
                    f"REDUCE: 減少 {pos['ticker']} 權重至 {MAX_SINGLE_POSITION:.0%}"
                )

        # ── 規則 3: 投資組合 Beta ──
        total_beta = 0.0
        beta_count = 0
        for pos in self.positions:
            ticker = pos["ticker"]
            mkt = self.market_data.get(ticker, {})
            beta = mkt.get("beta", 1.0)
            total_beta += beta * pos["weight"]
            beta_count += 1

        # 加權 Beta（需要歸一化，因為 weight 總和可能不為 1）
        total_weight = sum(p["weight"] for p in self.positions)
        portfolio_beta = total_beta / total_weight if total_weight > 0 else 1.0
        metrics["portfolio_beta"] = round(portfolio_beta, 2)

        if portfolio_beta > MAX_PORTFOLIO_BETA:
            violations.append(
                f"HIGH_BETA: 組合 Beta {portfolio_beta:.2f} "
                f"超過上限 ({MAX_PORTFOLIO_BETA})"
            )
            actions.append("HEDGE: 考慮降低高 Beta 部位或增加防禦性部位")

        # ── 規則 4: 組合回撤 ──
        # 簡化: 用加權 P&L 作為回撤估計
        weighted_pnl = 0.0
        for pos in self.positions:
            ticker = pos["ticker"]
            mkt = self.market_data.get(ticker, {})
            entry = self.entry_prices.get(ticker, 0)
            current = mkt.get("price", 0)
            if entry > 0:
                pnl = (current - entry) / entry
                weighted_pnl += pnl * pos["weight"]

        portfolio_pnl = weighted_pnl / total_weight if total_weight > 0 else 0.0
        metrics["portfolio_pnl"] = round(portfolio_pnl, 4)

        if portfolio_pnl <= DRAWDOWN_LIMIT:
            violations.append(
                f"DRAWDOWN: 組合加權回撤 {portfolio_pnl:.2%} "
                f"觸及回撤限制 ({DRAWDOWN_LIMIT:.0%}) → 風險控制模式"
            )
            actions.append("RISK_OFF: 進入風險控制模式，暫停新進場訊號")

        # ── 規則 5: VIX 體制 (RB-004) ──
        vix_val = self.vix_regime.get("vix")
        vix_zone = self.vix_regime.get("zone", "unknown")
        metrics["vix"] = vix_val
        metrics["vix_zone"] = vix_zone
        metrics["vix_risk_multiplier"] = VIX_RISK_MULTIPLIER.get(vix_zone, 1.0)

        if vix_val is not None:
            if vix_val >= VIX_EXTREME_THRESHOLD:
                violations.append(
                    f"VIX_EXTREME: VIX={vix_val:.1f} (>={VIX_EXTREME_THRESHOLD}) "
                    f"市場恐慌，建議暫停所有新進場"
                )
                actions.append("RISK_OFF: VIX 極端，暫停新進場，考慮減倉 50%")
            elif vix_val >= VIX_HIGH_THRESHOLD:
                violations.append(
                    f"VIX_HIGH: VIX={vix_val:.1f} (>={VIX_HIGH_THRESHOLD}) "
                    f"高波動環境，建議減少曝險"
                )
                actions.append("REDUCE: VIX 偏高，建議減倉至原來的 70%")

        return {"violations": violations, "actions": actions, "metrics": metrics}

    # ── 訊號層級風險過濾 ────────────────────────────────────────────

    def check_signal_risks(self, ticker: str) -> dict:
        """檢查訊號層級的風險規則。

        回傳:
            {violations: list, actions: list, metrics: dict}
        """
        violations = []
        actions = []
        metrics = {}

        # ── 規則 1: SQS 門檻 ──
        sqs_records = self.sqs_map.get(ticker, [])
        if sqs_records:
            avg_sqs = sum(r["sqs"] for r in sqs_records) / len(sqs_records)
            metrics["avg_sqs"] = round(avg_sqs, 2)
            # SQS 是 0-100 的分數，40 = Bronze/Discard 門檻
            sqs_normalized = avg_sqs / 100.0
            if sqs_normalized < MIN_SQS_THRESHOLD:
                violations.append(
                    f"LOW_SQS: {ticker} 平均 SQS {avg_sqs:.1f}/100 "
                    f"低於門檻 ({MIN_SQS_THRESHOLD * 100:.0f})"
                )
                actions.append(f"REJECT: 因 SQS 過低拒絕 {ticker} 訊號")
        else:
            metrics["avg_sqs"] = None

        # ── 規則 2: Filing lag ──
        signals = self.alpha_signals.get(ticker, [])
        if signals:
            lags = [s["filing_lag_days"] for s in signals if s.get("filing_lag_days") is not None]
            if lags:
                avg_lag = sum(lags) / len(lags)
                metrics["avg_filing_lag"] = round(avg_lag, 1)
                if avg_lag > MAX_FILING_LAG_DAYS:
                    violations.append(
                        f"STALE_DATA: {ticker} 平均 filing lag {avg_lag:.0f} 天 "
                        f"超過上限 ({MAX_FILING_LAG_DAYS} 天)"
                    )
                    actions.append(f"REJECT: 因資料過舊拒絕 {ticker} 訊號")
            else:
                metrics["avg_filing_lag"] = None
        else:
            metrics["avg_filing_lag"] = None

        # ── 規則 3: 收斂資料點數 ──
        convergence = self.convergence_map.get(ticker)
        if convergence:
            politician_count = convergence.get("politician_count", 0)
            metrics["convergence_points"] = politician_count
            if politician_count < MIN_CONVERGENCE_POINTS:
                violations.append(
                    f"WEAK_CONVERGENCE: {ticker} 僅 {politician_count} 個收斂資料點 "
                    f"(需要 >= {MIN_CONVERGENCE_POINTS})"
                )
                actions.append(f"CAUTION: {ticker} 收斂訊號不足，降低信心度")
        else:
            metrics["convergence_points"] = 0

        return {"violations": violations, "actions": actions, "metrics": metrics}

    # ── 綜合風險評分 ────────────────────────────────────────────────

    def calculate_risk_score(self, pos: dict, pos_risk: dict,
                             signal_risk: dict) -> float:
        """計算單一部位的綜合風險評分 (0-100，越高越危險)。

        組成:
          - P&L 風險 (25): P&L 越接近停損線越危險
          - 板塊集中度 (20): 所屬板塊總權重越高越危險
          - 波動率 (20): 30d 年化波動率越高越危險
          - 資料新鮮度 (15): filing lag 越長越危險
          - 訊號品質 (10): SQS 越低越危險
          - 持倉時間 (10): 持倉越久越危險
        """
        ticker = pos["ticker"]
        metrics = pos_risk.get("metrics", {})
        sig_metrics = signal_risk.get("metrics", {})

        # ── 1. P&L 風險 (0-25) ──
        pnl = metrics.get("pnl_pct", 0)
        if pnl <= STOP_LOSS_PCT:
            pnl_score = 25.0  # 已觸停損
        elif pnl <= 0:
            # 虧損中: 線性映射 [STOP_LOSS, 0] → [25, 5]
            pnl_score = 5.0 + (abs(pnl) / abs(STOP_LOSS_PCT)) * 20.0
        elif pnl < TRAILING_STOP_ACTIVATION:
            pnl_score = 3.0  # 小獲利，低風險
        else:
            # 大獲利但可能有追蹤止損風險
            pnl_score = 5.0  # 中低風險
        pnl_score = min(pnl_score, RISK_WEIGHT_PNL)

        # ── 2. 板塊集中度風險 (0-20) ──
        sector = pos.get("sector", "Unknown")
        sector_weights = defaultdict(float)
        for p in self.positions:
            sector_weights[p.get("sector", "Unknown")] += p["weight"]
        sector_exposure = sector_weights.get(sector, 0)
        # 線性映射 [0, MAX_SECTOR_EXPOSURE+0.1] → [0, 20]
        sector_score = min((sector_exposure / (MAX_SECTOR_EXPOSURE + 0.1)) * RISK_WEIGHT_SECTOR,
                           RISK_WEIGHT_SECTOR)

        # ── 3. 波動率風險 (0-20) ──
        mkt = self.market_data.get(ticker, {})
        vol = mkt.get("volatility_30d", 0)
        # 正常股票波動率 20-40%，>50% 為高風險
        vol_score = min((vol / 0.50) * RISK_WEIGHT_VOLATILITY, RISK_WEIGHT_VOLATILITY)

        # ── 4. 資料新鮮度風險 (0-15) ──
        avg_lag = sig_metrics.get("avg_filing_lag")
        if avg_lag is not None:
            # 線性映射 [0, MAX_FILING_LAG_DAYS+15] → [0, 15]
            freshness_score = min((avg_lag / (MAX_FILING_LAG_DAYS + 15)) * RISK_WEIGHT_FRESHNESS,
                                  RISK_WEIGHT_FRESHNESS)
        else:
            freshness_score = RISK_WEIGHT_FRESHNESS * 0.5  # 無資料時給中間值

        # ── 5. 訊號品質風險 (0-10) ──
        avg_sqs = sig_metrics.get("avg_sqs")
        if avg_sqs is not None:
            # SQS 越高品質越好，風險越低
            # 反轉: 100 → 0分風險, 0 → 10分風險
            sqs_score = (1.0 - avg_sqs / 100.0) * RISK_WEIGHT_SQS
        else:
            sqs_score = RISK_WEIGHT_SQS * 0.5

        # ── 6. 持倉時間風險 (0-10) ──
        holding_days = metrics.get("holding_days", 0)
        holding_score = min((holding_days / MAX_HOLDING_DAYS) * RISK_WEIGHT_HOLDING,
                            RISK_WEIGHT_HOLDING)

        total = pnl_score + sector_score + vol_score + freshness_score + sqs_score + holding_score

        # ── VIX 體制風險乘數 (RB-004) ──
        vix_zone = self.vix_regime.get("zone", "unknown")
        vix_mult = VIX_RISK_MULTIPLIER.get(vix_zone, 1.0)
        total = total * vix_mult

        return round(min(total, 100.0), 1)

    @staticmethod
    def risk_level(score: float) -> str:
        """將風險分數轉為等級。"""
        if score >= 70:
            return "CRITICAL"
        elif score >= 50:
            return "HIGH"
        elif score >= 30:
            return "MEDIUM"
        else:
            return "LOW"

    # ── 完整風險檢查 ────────────────────────────────────────────────

    def run_full_check(self) -> dict:
        """執行完整的風險檢查流程。

        回傳:
            {
                assessments: list[dict],    # 每個部位的評估
                portfolio_risk: dict,       # 投資組合層級風險
                summary: dict,              # 摘要統計
            }
        """
        # 1. 載入資料
        print("\n[1/5] 載入持倉資料...")
        self.load_portfolio()
        if not self.positions:
            print("  [警告] 無持倉資料，請先執行 portfolio_optimizer")
            return {"assessments": [], "portfolio_risk": {}, "summary": {}}

        print(f"  載入 {len(self.positions)} 個持倉")

        # 2. 載入輔助資料
        print("[2/5] 載入品質分數與收斂訊號...")
        self.load_sqs_scores()
        self.load_alpha_signals()
        self.load_convergence()

        # 2b. VIX 體制偵測
        print("[2b/5] VIX regime detection...")
        self.load_vix_regime()
        vix_val = self.vix_regime.get("vix")
        vix_zone = self.vix_regime.get("zone", "unknown")
        vix_mult = VIX_RISK_MULTIPLIER.get(vix_zone, 1.0)
        if vix_val is not None:
            print(f"  VIX={vix_val:.1f} ({vix_zone}), risk_mult={vix_mult:.1f}x")
        else:
            print(f"  VIX unavailable, using neutral multiplier")

        # 3. 取得市場數據
        print("[3/5] 取得即時市場數據...")
        tickers = [p["ticker"] for p in self.positions]
        self.market_data = fetch_current_prices(tickers)
        print(f"  成功取得 {len(self.market_data)}/{len(tickers)} 支股票數據")

        # 取得進場價
        if self.positions:
            entry_date = self.positions[0].get("created_at", "")[:10]
            if entry_date:
                self.entry_prices = fetch_entry_prices(tickers, entry_date)
                print(f"  取得 {len(self.entry_prices)}/{len(tickers)} 支進場價")

        # 4. 逐部位風險檢查
        print("[4/5] 執行風險檢查...")
        assessments = []
        total_violations = 0

        for pos in self.positions:
            ticker = pos["ticker"]

            # 部位層級
            pos_risk = self.check_position_risks(pos)

            # 訊號層級
            sig_risk = self.check_signal_risks(ticker)

            # 綜合風險評分
            score = self.calculate_risk_score(pos, pos_risk, sig_risk)
            level = self.risk_level(score)

            all_violations = pos_risk["violations"] + sig_risk["violations"]
            all_actions = pos_risk["actions"] + sig_risk["actions"]
            total_violations += len(all_violations)

            assessment = {
                "ticker": ticker,
                "sector": pos.get("sector", "Unknown"),
                "weight": pos["weight"],
                "conviction_score": pos.get("conviction_score", 0),
                "current_price": pos_risk["metrics"].get("current_price", 0),
                "entry_price": pos_risk["metrics"].get("entry_price", 0),
                "pnl_pct": pos_risk["metrics"].get("pnl_pct", 0),
                "peak_price": pos_risk["metrics"].get("peak_price", 0),
                "drawdown_from_peak": pos_risk["metrics"].get("drawdown_from_peak", 0),
                "holding_days": pos_risk["metrics"].get("holding_days", 0),
                "volatility_30d": self.market_data.get(ticker, {}).get("volatility_30d", 0),
                "beta": self.market_data.get(ticker, {}).get("beta", 1.0),
                "sqs_avg": sig_risk["metrics"].get("avg_sqs"),
                "filing_lag_avg": sig_risk["metrics"].get("avg_filing_lag"),
                "risk_score": score,
                "risk_level": level,
                "violations": all_violations,
                "actions": all_actions,
            }
            assessments.append(assessment)

        # 5. 投資組合層級檢查
        portfolio_risk = self.check_portfolio_risks()
        total_violations += len(portfolio_risk["violations"])

        # 摘要
        summary = self._build_summary(assessments, portfolio_risk)

        # 排序: 風險分數最高的在前
        assessments.sort(key=lambda a: a["risk_score"], reverse=True)

        print(f"  檢查完成: {len(assessments)} 個部位, {total_violations} 個違規")

        return {
            "assessments": assessments,
            "portfolio_risk": portfolio_risk,
            "summary": summary,
        }

    def _build_summary(self, assessments: List[dict], portfolio_risk: dict) -> dict:
        """建構風險摘要統計。"""
        if not assessments:
            return {}

        scores = [a["risk_score"] for a in assessments]
        levels = defaultdict(int)
        for a in assessments:
            levels[a["risk_level"]] += 1

        all_violations = []
        for a in assessments:
            all_violations.extend(a["violations"])
        all_violations.extend(portfolio_risk.get("violations", []))

        all_actions = []
        for a in assessments:
            all_actions.extend(a["actions"])
        all_actions.extend(portfolio_risk.get("actions", []))

        # 需要立即行動的部位
        critical_positions = [a for a in assessments if a["risk_level"] == "CRITICAL"]
        high_positions = [a for a in assessments if a["risk_level"] == "HIGH"]

        portfolio_metrics = portfolio_risk.get("metrics", {})

        return {
            "total_positions": len(assessments),
            "avg_risk_score": round(sum(scores) / len(scores), 1),
            "max_risk_score": max(scores),
            "min_risk_score": min(scores),
            "risk_distribution": dict(levels),
            "total_violations": len(all_violations),
            "critical_count": len(critical_positions),
            "high_count": len(high_positions),
            "portfolio_beta": portfolio_metrics.get("portfolio_beta", 0),
            "portfolio_pnl": portfolio_metrics.get("portfolio_pnl", 0),
            "all_violations": all_violations,
            "all_actions": all_actions,
            "risk_off_mode": portfolio_metrics.get("portfolio_pnl", 0) <= DRAWDOWN_LIMIT,
            "vix": portfolio_metrics.get("vix"),
            "vix_zone": portfolio_metrics.get("vix_zone", "unknown"),
            "vix_risk_multiplier": portfolio_metrics.get("vix_risk_multiplier", 1.0),
        }


# ══════════════════════════════════════════════════════════════════════
#  報告生成
# ══════════════════════════════════════════════════════════════════════

def generate_risk_report(result: dict) -> str:
    """生成 Markdown 格式的風險評估報告。"""
    assessments = result["assessments"]
    portfolio_risk = result["portfolio_risk"]
    summary = result["summary"]
    today_str = date.today().strftime("%Y-%m-%d")
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = []
    lines.append("# Risk Assessment Report")
    lines.append(f"**Date**: {today_str}")
    lines.append(f"**Generated**: {now_str}")
    lines.append("")
    lines.append("---")
    lines.append("")

    if not summary:
        lines.append("**No portfolio data available.**")
        return "\n".join(lines)

    # ── 風險總覽 ──
    lines.append("## Risk Overview")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Total Positions | {summary['total_positions']} |")
    lines.append(f"| Avg Risk Score | {summary['avg_risk_score']}/100 |")
    lines.append(f"| Max Risk Score | {summary['max_risk_score']}/100 |")
    lines.append(f"| Total Violations | {summary['total_violations']} |")
    lines.append(f"| CRITICAL Positions | {summary['critical_count']} |")
    lines.append(f"| HIGH Risk Positions | {summary['high_count']} |")
    lines.append(f"| Portfolio Beta | {summary.get('portfolio_beta', 'N/A')} |")
    lines.append(f"| Portfolio P&L | {summary.get('portfolio_pnl', 0):.2%} |")
    vix_val = summary.get("vix")
    if vix_val is not None:
        lines.append(f"| VIX | {vix_val:.1f} ({summary.get('vix_zone', '?')}) |")
        lines.append(f"| VIX Risk Multiplier | {summary.get('vix_risk_multiplier', 1.0):.1f}x |")

    if summary.get("risk_off_mode"):
        lines.append(f"| **MODE** | **RISK-OFF** |")

    lines.append("")

    # ── 風險分布 ──
    lines.append("## Risk Distribution")
    lines.append("")
    dist = summary.get("risk_distribution", {})
    lines.append("| Level | Count | Description |")
    lines.append("|-------|-------|-------------|")
    lines.append(f"| CRITICAL | {dist.get('CRITICAL', 0)} | Score >= 70, immediate action |")
    lines.append(f"| HIGH | {dist.get('HIGH', 0)} | Score 50-69, close monitoring |")
    lines.append(f"| MEDIUM | {dist.get('MEDIUM', 0)} | Score 30-49, normal monitoring |")
    lines.append(f"| LOW | {dist.get('LOW', 0)} | Score < 30, healthy |")
    lines.append("")

    # ── 投資組合層級違規 ──
    portfolio_violations = portfolio_risk.get("violations", [])
    if portfolio_violations:
        lines.append("## Portfolio-Level Violations")
        lines.append("")
        for v in portfolio_violations:
            lines.append(f"- {v}")
        lines.append("")

    portfolio_actions = portfolio_risk.get("actions", [])
    if portfolio_actions:
        lines.append("### Recommended Actions")
        lines.append("")
        for a in portfolio_actions:
            lines.append(f"- {a}")
        lines.append("")

    # ── 部位明細 ──
    lines.append("## Position Risk Details")
    lines.append("")
    lines.append(
        "| # | Ticker | Sector | Weight | P&L | Risk Score | Level | "
        "Beta | Vol(30d) | Holding | Violations |"
    )
    lines.append(
        "|---|--------|--------|--------|-----|-----------|-------|"
        "-----|---------|---------|------------|"
    )

    for i, a in enumerate(assessments, 1):
        v_count = len(a["violations"])
        v_str = f"{v_count} issue(s)" if v_count > 0 else "Clean"
        pnl_str = f"{a['pnl_pct']:.2%}" if a.get("pnl_pct") else "N/A"

        lines.append(
            f"| {i} | **{a['ticker']}** | {a['sector']} | "
            f"{a['weight']:.2%} | {pnl_str} | "
            f"{a['risk_score']:.0f} | {a['risk_level']} | "
            f"{a.get('beta', 1.0):.2f} | {a.get('volatility_30d', 0):.2%} | "
            f"{a.get('holding_days', 0)}d | {v_str} |"
        )

    lines.append("")

    # ── 違規明細 ──
    flagged = [a for a in assessments if a["violations"]]
    if flagged:
        lines.append("## Violation Details")
        lines.append("")
        for a in flagged:
            lines.append(f"### {a['ticker']} (Risk Score: {a['risk_score']:.0f})")
            lines.append("")
            for v in a["violations"]:
                lines.append(f"- {v}")
            if a["actions"]:
                lines.append("")
                lines.append("**Actions:**")
                for act in a["actions"]:
                    lines.append(f"- {act}")
            lines.append("")

    # ── 風險參數 ──
    lines.append("## Risk Parameters")
    lines.append("")
    lines.append("### Position-Level Rules")
    lines.append("")
    lines.append("| Rule | Threshold |")
    lines.append("|------|-----------|")
    lines.append(f"| Stop-Loss | {STOP_LOSS_PCT:.0%} from entry |")
    lines.append(f"| Take-Profit | {TAKE_PROFIT_PCT:.0%} from entry (partial exit) |")
    lines.append(f"| Max Holding Period | {MAX_HOLDING_DAYS} trading days |")
    lines.append(f"| Trailing Stop Activation | +{TRAILING_STOP_ACTIVATION:.0%} gain |")
    lines.append(f"| Trailing Stop Distance | {TRAILING_STOP_PCT:.0%} from peak |")
    lines.append("")

    lines.append("### Portfolio-Level Rules")
    lines.append("")
    lines.append("| Rule | Threshold |")
    lines.append("|------|-----------|")
    lines.append(f"| Max Sector Exposure | {MAX_SECTOR_EXPOSURE:.0%} |")
    lines.append(f"| Max Single Position | {MAX_SINGLE_POSITION:.0%} |")
    lines.append(f"| Max Portfolio Beta | {MAX_PORTFOLIO_BETA} |")
    lines.append(f"| Drawdown Limit (Risk-Off) | {DRAWDOWN_LIMIT:.0%} |")
    lines.append("")

    lines.append("### Signal-Level Filters")
    lines.append("")
    lines.append("| Rule | Threshold |")
    lines.append("|------|-----------|")
    lines.append(f"| Min SQS Score | {MIN_SQS_THRESHOLD * 100:.0f}/100 |")
    lines.append(f"| Max Filing Lag | {MAX_FILING_LAG_DAYS} days |")
    lines.append(f"| Min Convergence Points | {MIN_CONVERGENCE_POINTS} |")
    lines.append("")

    # ── 免責聲明 ──
    lines.append("## Disclaimer")
    lines.append("")
    lines.append(
        "This risk assessment is based on quantitative models and historical data. "
        "It does not constitute investment advice. All risk thresholds are configurable "
        "and should be adjusted based on individual risk tolerance."
    )
    lines.append("")
    lines.append("---")
    lines.append(
        f"*Generated by Political Alpha Monitor — "
        f"Risk Manager v1.0 — {now_str}*"
    )
    lines.append("")

    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════
#  終端輸出
# ══════════════════════════════════════════════════════════════════════

def print_risk_summary(result: dict):
    """在終端印出風險檢查摘要。"""
    assessments = result["assessments"]
    portfolio_risk = result["portfolio_risk"]
    summary = result["summary"]

    if not summary:
        print("\n  [無資料] 沒有持倉資料可供檢查。\n")
        return

    print()
    print("=" * 90)
    print("  Risk Assessment -- Political Alpha Monitor")
    print(f"  Date: {date.today().strftime('%Y-%m-%d')}")
    print("=" * 90)

    # 風險總覽
    print()
    print("  [Risk Overview]")
    print(f"    Positions:          {summary['total_positions']}")
    print(f"    Avg Risk Score:     {summary['avg_risk_score']}/100")
    print(f"    Max Risk Score:     {summary['max_risk_score']}/100")
    print(f"    Total Violations:   {summary['total_violations']}")
    print(f"    Portfolio Beta:     {summary.get('portfolio_beta', 'N/A')}")
    print(f"    Portfolio P&L:      {summary.get('portfolio_pnl', 0):.2%}")
    vix_val = summary.get("vix")
    if vix_val is not None:
        print(f"    VIX:                {vix_val:.1f} ({summary.get('vix_zone', '?')})")
        print(f"    VIX Risk Mult:      {summary.get('vix_risk_multiplier', 1.0):.1f}x")
    else:
        print(f"    VIX:                N/A")

    if summary.get("risk_off_mode"):
        print(f"    *** RISK-OFF MODE ACTIVATED ***")

    # 風險分布
    print()
    dist = summary.get("risk_distribution", {})
    print("  [Risk Distribution]")
    for level in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
        count = dist.get(level, 0)
        bar = "#" * (count * 3)
        print(f"    {level:<10s} {count:>3d}  {bar}")

    # 投資組合違規
    pv = portfolio_risk.get("violations", [])
    if pv:
        print()
        print("  [Portfolio Violations]")
        for v in pv:
            print(f"    ! {v}")

    # 部位明細
    print()
    print("  [Position Risk Details]")
    header = (
        f"  {'#':>3}  {'Ticker':<8}  {'Sector':<22}  {'Wt':>6}  "
        f"{'P&L':>7}  {'Score':>5}  {'Level':<9}  {'Violations'}"
    )
    print(header)
    print("  " + "-" * 86)

    for i, a in enumerate(assessments, 1):
        pnl_str = f"{a['pnl_pct']:.2%}" if a.get("pnl_pct") else "  N/A"
        v_count = len(a["violations"])
        v_str = f"{v_count} issue(s)" if v_count > 0 else "Clean"
        print(
            f"  {i:>3}  {a['ticker']:<8}  {a['sector']:<22}  "
            f"{a['weight']:>5.2%}  {pnl_str:>7}  "
            f"{a['risk_score']:>5.0f}  {a['risk_level']:<9}  {v_str}"
        )

    # 需要行動的項目
    all_actions = summary.get("all_actions", [])
    if all_actions:
        print()
        print("  [Required Actions]")
        for act in all_actions:
            print(f"    >> {act}")

    print()
    print("=" * 90)
    print()


# ══════════════════════════════════════════════════════════════════════
#  主流程
# ══════════════════════════════════════════════════════════════════════

def run_risk_assessment(db_path: Optional[str] = None) -> dict:
    """完整風險評估流程。"""
    if db_path is None:
        db_path = DB_PATH

    print()
    print("Risk Manager -- Political Alpha Monitor")
    print(f"Database: {db_path}")
    print()

    # 初始化 DB 表
    init_risk_table(db_path)

    # 執行風險檢查
    manager = RiskManager(db_path=db_path)
    result = manager.run_full_check()

    assessments = result["assessments"]
    summary = result["summary"]

    if not assessments:
        print("  No portfolio positions found. Run portfolio_optimizer first.")
        return result

    # 終端輸出
    print_risk_summary(result)

    # 儲存到 DB
    print("[5/5] Saving results...")
    save_assessments(assessments, db_path)

    # 生成報告
    report_dir = PROJECT_ROOT / "docs" / "reports"
    os.makedirs(str(report_dir), exist_ok=True)
    today_str = date.today().strftime("%Y-%m-%d")
    report_path = report_dir / f"Risk_Assessment_{today_str}.md"
    report_content = generate_risk_report(result)
    with open(str(report_path), "w", encoding="utf-8") as f:
        f.write(report_content)
    print(f"  Report saved: {report_path}")
    print(f"  DB assessments saved: risk_assessments table ({len(assessments)} rows)")
    print()

    return result


# ══════════════════════════════════════════════════════════════════════
#  CLI 入口
# ══════════════════════════════════════════════════════════════════════

def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Risk Manager -- Political Alpha Monitor"
    )
    parser.add_argument("--db", type=str, default=None,
                        help="Database path (default: data/data.db)")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    run_risk_assessment(db_path=args.db)


if __name__ == "__main__":
    main()
