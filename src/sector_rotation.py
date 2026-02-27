"""
Sector Rotation Detector — 國會交易板塊輪動分析

基於 RB-007 研究結論:
- Congress NET BUY signals predictive: 66.7% hit rate, +2.51% 20d return
- NET SELL NOT reliable: 38.9% hit rate → 僅參考
- Energy paradox: Congress bad at energy timing → 排除 Energy
- Recommended: follow buy-only, overweight XLI/XLB/XLV

功能:
1. 聚合國會交易至板塊層級 (淨買/賣、金額加權、議員數量)
2. 計算板塊動能分數 (30/60/90 天滾動窗口)
3. 偵測板塊輪動 (資金流入/流出轉向)
4. 生成板塊層級交易信號 (Buy-only, 排除 Energy)
5. ETF 映射 (板塊 → SPDR ETF)

使用方式:
    python -m src.sector_rotation                    # 完整分析
    python -m src.sector_rotation --days 90          # 回溯 90 天
    python -m src.sector_rotation --top 5            # 只顯示 Top 5
    python -m src.sector_rotation --dry-run          # 不寫入 DB
"""

import json
import logging
import os
import re
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ============================================================================
# 常數
# ============================================================================

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "data.db")
SECTOR_JSON = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "ticker_sectors.json")

# 板塊 → SPDR ETF 映射
SECTOR_ETF_MAP = {
    "Technology": "XLK",
    "Financial Services": "XLF",
    "Healthcare": "XLV",
    "Consumer Cyclical": "XLY",
    "Consumer Defensive": "XLP",
    "Industrials": "XLI",
    "Energy": "XLE",
    "Basic Materials": "XLB",
    "Real Estate": "XLRE",
    "Communication Services": "XLC",
    "Utilities": "XLU",
}

# RB-007: Energy sector excluded (congress bad at energy timing)
EXCLUDED_SECTORS = {"Energy"}

# 金額區間 → 代表金額 (與 convergence_detector.py 一致)
AMOUNT_RANGES = {
    "$1,001 - $15,000": 8_000,
    "$15,001 - $50,000": 32_500,
    "$50,001 - $100,000": 75_000,
    "$100,001 - $250,000": 175_000,
    "$250,001 - $500,000": 375_000,
    "$500,001 - $1,000,000": 750_000,
    "$1,000,001 - $5,000,000": 3_000_000,
    "$5,000,001 - $25,000,000": 15_000_000,
    "$25,000,001 - $50,000,000": 37_500_000,
    "$50,000,000+": 50_000_000,
    "Over $50,000,000": 50_000_000,
}

# 分析窗口 (天)
WINDOWS = [30, 60, 90]

# 板塊信號門檻
MIN_TRADES = 3              # 最少交易數
MIN_POLITICIANS = 2         # 最少議員數
NET_BUY_THRESHOLD = 0.55    # 淨買比例門檻 (buy_count / total >= 55%)
MOMENTUM_SCORE_MIN = 0.30   # 動能分數門檻


# ============================================================================
# 工具函式
# ============================================================================

def _parse_amount(amount_str: str) -> float:
    """解析金額區間字串，返回代表金額。"""
    if not amount_str:
        return 0.0
    amount_str = amount_str.strip()
    if amount_str in AMOUNT_RANGES:
        return float(AMOUNT_RANGES[amount_str])
    numbers = re.findall(r'[\d,]+', amount_str)
    if numbers:
        parsed = []
        for n in numbers:
            try:
                parsed.append(float(n.replace(",", "")))
            except ValueError:
                continue
        if parsed:
            return sum(parsed) / len(parsed)
    return 0.0


def _load_sector_map() -> Dict[str, dict]:
    """載入 ticker → sector 映射。"""
    if not os.path.exists(SECTOR_JSON):
        logger.warning("ticker_sectors.json not found: %s", SECTOR_JSON)
        return {}
    with open(SECTOR_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("sector_map", {})


# ============================================================================
# 核心類別
# ============================================================================

class SectorRotationDetector:
    """國會交易板塊輪動偵測器。"""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.sector_map = _load_sector_map()
        logger.info("SectorRotationDetector init: %d ticker-sector mappings loaded",
                     len(self.sector_map))

    # ────────────────────────────────────────────────────────
    # 資料載入
    # ────────────────────────────────────────────────────────

    def _load_trades(self, days: int = 90) -> List[dict]:
        """從 congress_trades 載入指定天數內的交易。"""
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT id, politician_name, chamber, ticker, transaction_type,
                   amount_range, transaction_date, filing_date, asset_type
            FROM congress_trades
            WHERE transaction_date >= ?
              AND ticker IS NOT NULL
              AND transaction_type IN ('Buy', 'Sale', 'Purchase', 'purchase',
                                       'Sale (Full)', 'Sale (Partial)')
            ORDER BY transaction_date DESC
        """, (cutoff,)).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    # ────────────────────────────────────────────────────────
    # 板塊聚合
    # ────────────────────────────────────────────────────────

    def aggregate_by_sector(self, days: int = 90) -> Dict[str, dict]:
        """
        聚合國會交易至板塊層級。

        Returns:
            dict: {sector_name: {
                trades, buy_count, sale_count, net_ratio,
                dollar_buy, dollar_sale, net_dollar,
                politicians: set, chambers: set, tickers: set,
                etf, excluded
            }}
        """
        trades = self._load_trades(days)
        sectors = defaultdict(lambda: {
            "trades": 0, "buy_count": 0, "sale_count": 0,
            "dollar_buy": 0.0, "dollar_sale": 0.0,
            "politicians": set(), "chambers": set(), "tickers": set(),
        })

        unmapped = 0
        for t in trades:
            ticker = (t.get("ticker") or "").strip().upper()
            if not ticker or ticker not in self.sector_map:
                unmapped += 1
                continue

            sector = self.sector_map[ticker]["sector"]
            info = sectors[sector]
            info["trades"] += 1
            info["politicians"].add(t["politician_name"])
            info["chambers"].add(t["chamber"])
            info["tickers"].add(ticker)

            amount = _parse_amount(t.get("amount_range", ""))
            tx_type = (t.get("transaction_type") or "").lower()

            if "buy" in tx_type or "purchase" in tx_type:
                info["buy_count"] += 1
                info["dollar_buy"] += amount
            else:
                info["sale_count"] += 1
                info["dollar_sale"] += amount

        # 後處理
        result = {}
        for sector, info in sectors.items():
            total = info["buy_count"] + info["sale_count"]
            net_ratio = info["buy_count"] / total if total > 0 else 0.5
            result[sector] = {
                "sector": sector,
                "etf": SECTOR_ETF_MAP.get(sector, "N/A"),
                "excluded": sector in EXCLUDED_SECTORS,
                "trades": total,
                "buy_count": info["buy_count"],
                "sale_count": info["sale_count"],
                "net_ratio": round(net_ratio, 4),
                "dollar_buy": info["dollar_buy"],
                "dollar_sale": info["dollar_sale"],
                "net_dollar": info["dollar_buy"] - info["dollar_sale"],
                "politician_count": len(info["politicians"]),
                "politicians": sorted(info["politicians"]),
                "chambers": sorted(info["chambers"]),
                "ticker_count": len(info["tickers"]),
                "tickers": sorted(info["tickers"]),
                "window_days": days,
            }

        logger.info("Sector aggregation (%dd): %d sectors, %d trades mapped, %d unmapped",
                     days, len(result), sum(s["trades"] for s in result.values()), unmapped)
        return result

    # ────────────────────────────────────────────────────────
    # 板塊動能分數
    # ────────────────────────────────────────────────────────

    def calc_momentum_scores(self, days: int = 90) -> List[dict]:
        """
        計算每個板塊的動能分數。

        動能分數 = weighted_sum(
            net_ratio × 0.35,           # 淨買比例
            dollar_flow_norm × 0.25,    # 金額流向 (歸一化)
            politician_breadth × 0.20,  # 議員廣度
            ticker_diversity × 0.10,    # 標的多樣性
            cross_chamber × 0.10        # 跨院加分
        )
        """
        sector_data = self.aggregate_by_sector(days)
        if not sector_data:
            return []

        # 歸一化用最大值
        max_dollar = max(abs(s["net_dollar"]) for s in sector_data.values()) or 1.0
        max_politicians = max(s["politician_count"] for s in sector_data.values()) or 1
        max_tickers = max(s["ticker_count"] for s in sector_data.values()) or 1

        scores = []
        for sector, data in sector_data.items():
            # 淨買比例: 0.5=中性, >0.5=偏買, <0.5=偏賣
            net_ratio_score = (data["net_ratio"] - 0.5) * 2  # [-1, +1]

            # 金額流向歸一化
            dollar_flow_norm = data["net_dollar"] / max_dollar  # [-1, +1]

            # 議員廣度 (更多議員 = 信號更強)
            politician_breadth = data["politician_count"] / max_politicians  # [0, 1]

            # 標的多樣性
            ticker_diversity = min(data["ticker_count"] / max_tickers, 1.0)  # [0, 1]

            # 跨院加分
            cross_chamber = 1.0 if len(data["chambers"]) > 1 else 0.0

            # 加權動能分數
            momentum = (
                net_ratio_score * 0.35
                + dollar_flow_norm * 0.25
                + politician_breadth * 0.20
                + ticker_diversity * 0.10
                + cross_chamber * 0.10
            )

            scores.append({
                **data,
                "momentum_score": round(momentum, 4),
                "net_ratio_score": round(net_ratio_score, 4),
                "dollar_flow_norm": round(dollar_flow_norm, 4),
                "politician_breadth": round(politician_breadth, 4),
                "ticker_diversity": round(ticker_diversity, 4),
                "cross_chamber": cross_chamber,
            })

        # 按動能分數排序
        scores.sort(key=lambda x: x["momentum_score"], reverse=True)
        return scores

    # ────────────────────────────────────────────────────────
    # 多窗口分析 (輪動偵測)
    # ────────────────────────────────────────────────────────

    def detect_rotation(self) -> List[dict]:
        """
        偵測板塊輪動: 比較 30d vs 90d 動能變化。

        輪動信號:
        - ACCELERATING: 短期動能 > 長期動能 (資金加速流入)
        - DECELERATING: 短期動能 < 長期動能 (資金流入放緩)
        - REVERSING_UP: 長期偏賣 → 短期偏買 (反轉向上)
        - REVERSING_DOWN: 長期偏買 → 短期偏賣 (反轉向下)
        - STABLE: 動能穩定
        """
        scores_30d = {s["sector"]: s for s in self.calc_momentum_scores(30)}
        scores_90d = {s["sector"]: s for s in self.calc_momentum_scores(90)}

        rotations = []
        all_sectors = set(scores_30d.keys()) | set(scores_90d.keys())

        for sector in all_sectors:
            s30 = scores_30d.get(sector, {})
            s90 = scores_90d.get(sector, {})
            m30 = s30.get("momentum_score", 0.0)
            m90 = s90.get("momentum_score", 0.0)
            delta = m30 - m90

            # 分類輪動類型
            if m90 < -0.1 and m30 > 0.1:
                rotation_type = "REVERSING_UP"
            elif m90 > 0.1 and m30 < -0.1:
                rotation_type = "REVERSING_DOWN"
            elif delta > 0.15:
                rotation_type = "ACCELERATING"
            elif delta < -0.15:
                rotation_type = "DECELERATING"
            else:
                rotation_type = "STABLE"

            rotations.append({
                "sector": sector,
                "etf": SECTOR_ETF_MAP.get(sector, "N/A"),
                "excluded": sector in EXCLUDED_SECTORS,
                "momentum_30d": m30,
                "momentum_90d": m90,
                "momentum_delta": round(delta, 4),
                "rotation_type": rotation_type,
                "trades_30d": s30.get("trades", 0),
                "trades_90d": s90.get("trades", 0),
                "politician_count_30d": s30.get("politician_count", 0),
                "net_ratio_30d": s30.get("net_ratio", 0.5),
                "net_dollar_30d": s30.get("net_dollar", 0.0),
            })

        rotations.sort(key=lambda x: x["momentum_delta"], reverse=True)
        return rotations

    # ────────────────────────────────────────────────────────
    # 板塊信號生成
    # ────────────────────────────────────────────────────────

    def generate_signals(self, days: int = 90) -> List[dict]:
        """
        生成板塊層級交易信號。

        規則 (基於 RB-007):
        1. Buy-only: 只生成 NET BUY 信號 (NET SELL 僅供參考)
        2. 排除 Energy: Congress bad at energy timing
        3. 門檻: trades >= 3, politicians >= 2, net_ratio >= 60%
        4. 動能分數 >= 0.50
        5. 信號強度 = momentum_score × (1 + rotation_bonus)
        """
        scores = self.calc_momentum_scores(days)
        rotations = {r["sector"]: r for r in self.detect_rotation()}
        signals = []

        for s in scores:
            sector = s["sector"]

            # 排除 Energy
            if s["excluded"]:
                continue

            # 門檻過濾
            if s["trades"] < MIN_TRADES:
                continue
            if s["politician_count"] < MIN_POLITICIANS:
                continue
            if s["net_ratio"] < NET_BUY_THRESHOLD:
                continue
            if s["momentum_score"] < MOMENTUM_SCORE_MIN:
                continue

            # 輪動加分
            rotation = rotations.get(sector, {})
            rotation_type = rotation.get("rotation_type", "STABLE")
            rotation_bonus = {
                "ACCELERATING": 0.20,
                "REVERSING_UP": 0.30,
                "STABLE": 0.0,
                "DECELERATING": -0.10,
                "REVERSING_DOWN": -0.30,
            }.get(rotation_type, 0.0)

            signal_strength = min(s["momentum_score"] * (1 + rotation_bonus), 1.0)
            signal_strength = max(signal_strength, 0.0)

            # RB-007 預期 alpha: NET BUY +2.51% 20d
            expected_alpha = 2.51 * signal_strength

            signals.append({
                "sector": sector,
                "etf": s["etf"],
                "direction": "LONG",
                "signal_strength": round(signal_strength, 4),
                "expected_alpha_20d": round(expected_alpha, 4),
                "momentum_score": s["momentum_score"],
                "net_ratio": s["net_ratio"],
                "net_dollar": s["net_dollar"],
                "trades": s["trades"],
                "buy_count": s["buy_count"],
                "sale_count": s["sale_count"],
                "politician_count": s["politician_count"],
                "ticker_count": s["ticker_count"],
                "cross_chamber": s["cross_chamber"],
                "rotation_type": rotation_type,
                "rotation_bonus": rotation_bonus,
                "top_tickers": s["tickers"][:10],
                "window_days": days,
                "created_at": datetime.now().isoformat(),
            })

        signals.sort(key=lambda x: x["signal_strength"], reverse=True)
        logger.info("Sector signals generated: %d (from %d sectors, %dd window)",
                     len(signals), len(scores), days)
        return signals

    # ────────────────────────────────────────────────────────
    # 儲存
    # ────────────────────────────────────────────────────────

    def save_signals(self, signals: List[dict]) -> dict:
        """寫入 sector_rotation_signals 表。"""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sector_rotation_signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sector TEXT NOT NULL,
                etf TEXT,
                direction TEXT DEFAULT 'LONG',
                signal_strength REAL,
                expected_alpha_20d REAL,
                momentum_score REAL,
                net_ratio REAL,
                net_dollar REAL,
                trades INTEGER,
                buy_count INTEGER,
                sale_count INTEGER,
                politician_count INTEGER,
                ticker_count INTEGER,
                cross_chamber REAL,
                rotation_type TEXT,
                rotation_bonus REAL,
                top_tickers TEXT,
                window_days INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        inserted = 0
        for s in signals:
            conn.execute("""
                INSERT INTO sector_rotation_signals
                (sector, etf, direction, signal_strength, expected_alpha_20d,
                 momentum_score, net_ratio, net_dollar, trades, buy_count,
                 sale_count, politician_count, ticker_count, cross_chamber,
                 rotation_type, rotation_bonus, top_tickers, window_days, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                s["sector"], s["etf"], s["direction"], s["signal_strength"],
                s["expected_alpha_20d"], s["momentum_score"], s["net_ratio"],
                s["net_dollar"], s["trades"], s["buy_count"], s["sale_count"],
                s["politician_count"], s["ticker_count"], s["cross_chamber"],
                s["rotation_type"], s["rotation_bonus"],
                json.dumps(s["top_tickers"]), s["window_days"], s["created_at"],
            ))
            inserted += 1
        conn.commit()
        conn.close()
        logger.info("Saved %d sector rotation signals", inserted)
        return {"inserted": inserted}

    # ────────────────────────────────────────────────────────
    # 報告
    # ────────────────────────────────────────────────────────

    def print_report(self, days: int = 90, top: int = 0):
        """印出板塊輪動分析報告。"""
        print(f"\n{'='*70}")
        print(f"  Sector Rotation Analysis  ({days}d window)")
        print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*70}")

        # 板塊動能
        scores = self.calc_momentum_scores(days)
        if not scores:
            print("  No sector data available.")
            return

        print(f"\n  --- Sector Momentum ({days}d) ---")
        print(f"  {'Sector':<25} {'ETF':>5} {'Mom':>7} {'NetR':>6} "
              f"{'Trades':>6} {'Pol':>4} {'Tickers':>7} {'Note':>10}")
        print(f"  {'-'*25} {'-'*5} {'-'*7} {'-'*6} {'-'*6} {'-'*4} {'-'*7} {'-'*10}")

        display = scores[:top] if top > 0 else scores
        for s in display:
            note = "EXCLUDED" if s["excluded"] else ""
            print(f"  {s['sector']:<25} {s['etf']:>5} {s['momentum_score']:>+7.3f} "
                  f"{s['net_ratio']:>6.1%} {s['trades']:>6} {s['politician_count']:>4} "
                  f"{s['ticker_count']:>7} {note:>10}")

        # 輪動偵測
        rotations = self.detect_rotation()
        active = [r for r in rotations if r["rotation_type"] != "STABLE"]
        if active:
            print(f"\n  --- Rotation Detected ---")
            for r in active:
                arrow = {"ACCELERATING": ">>", "REVERSING_UP": "/\\",
                         "DECELERATING": "<<", "REVERSING_DOWN": "\\/"}
                symbol = arrow.get(r["rotation_type"], "--")
                print(f"  {symbol} {r['sector']:<22} {r['rotation_type']:<18} "
                      f"delta={r['momentum_delta']:+.3f}  "
                      f"(90d={r['momentum_90d']:+.3f} -> 30d={r['momentum_30d']:+.3f})")

        # 信號
        signals = self.generate_signals(days)
        if signals:
            print(f"\n  --- Sector Signals (Buy-Only, excl. Energy) ---")
            print(f"  {'Sector':<25} {'ETF':>5} {'Str':>6} {'E[a]20d':>8} "
                  f"{'Rotation':>14} {'Pol':>4} {'Trades':>6}")
            print(f"  {'-'*25} {'-'*5} {'-'*6} {'-'*8} {'-'*14} {'-'*4} {'-'*6}")
            for s in signals:
                print(f"  {s['sector']:<25} {s['etf']:>5} {s['signal_strength']:>6.3f} "
                      f"{s['expected_alpha_20d']:>+7.2f}% {s['rotation_type']:>14} "
                      f"{s['politician_count']:>4} {s['trades']:>6}")
        else:
            print(f"\n  No sector signals above threshold.")

        print(f"\n{'='*70}")


# ============================================================================
# CLI
# ============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Sector Rotation Detector")
    parser.add_argument("--days", type=int, default=90, help="Analysis window (days, default 90)")
    parser.add_argument("--top", type=int, default=0, help="Show top N sectors only (0=all)")
    parser.add_argument("--dry-run", action="store_true", help="Don't write to DB")
    args = parser.parse_args()

    detector = SectorRotationDetector()

    # 報告
    detector.print_report(days=args.days, top=args.top)

    # 信號生成 + 存檔
    signals = detector.generate_signals(days=args.days)
    if signals and not args.dry_run:
        result = detector.save_signals(signals)
        print(f"\n  Saved {result['inserted']} sector signals to DB.")
    elif args.dry_run:
        print(f"\n  (Dry run -- {len(signals)} signals NOT saved)")


if __name__ == "__main__":
    main()
