"""多議員匯聚訊號偵測模組 — Political Alpha Monitor

偵測 congress_trades 資料庫中，同一檔股票在 30 天視窗內被 2 位以上不同議員
朝同一方向交易的「匯聚事件」(Convergence Event)。

評分邏輯:
  - 基礎分: 議員數量 (2→1.0, 3→1.5, 4→2.0, ...)
  - 跨院加分: 同時有 House + Senate → +0.5
  - 時間密度: 交易越密集分越高 (1.0 - span_days/30)
  - 金額加權: 平均金額越大分越高

Research Brief: RB-002
"""

import logging
import re
import sqlite3
import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple

from src.config import DB_PATH

logger = logging.getLogger("Convergence.Detector")

# ============================================================================
# 常數
# ============================================================================

# 匯聚視窗天數
CONVERGENCE_WINDOW_DAYS = 30

# 爆發式收斂子視窗 (Quant validation: convergence +36% EA20d premium)
BURST_WINDOW_DAYS = 7
BURST_BONUS = 0.5  # 7 天內多議員同向交易的額外加分

# 交易方向映射（transaction_type → Buy/Sale）
DIRECTION_MAP = {
    "Buy": "Buy",
    "Purchase": "Buy",
    "purchase": "Buy",
    "Sale": "Sale",
    "Sale (Full)": "Sale",
    "Sale (Partial)": "Sale",
    "sell": "Sale",
    "Sell": "Sale",
}

# 金額區間 → 代表金額（與 signal_scorer.py 一致）
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

# 金額最大值（用於歸一化）
MAX_AMOUNT = 5_000_000


# ============================================================================
# 工具函式
# ============================================================================

def _parse_date(val) -> Optional[date]:
    """將日期字串轉為 date 物件。解析失敗返回 None。"""
    if isinstance(val, date):
        return val
    if isinstance(val, datetime):
        return val.date()
    if not val:
        return None
    try:
        return datetime.strptime(str(val).strip(), "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _parse_amount(amount_str: str) -> float:
    """解析金額區間字串，返回代表金額。"""
    if not amount_str:
        return 0.0

    amount_str = amount_str.strip()

    # 精確匹配
    if amount_str in AMOUNT_RANGES:
        return float(AMOUNT_RANGES[amount_str])

    # 模糊匹配：提取數字取平均
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


def _map_direction(transaction_type: str) -> Optional[str]:
    """將 transaction_type 映射為 Buy/Sale 方向。Exchange 和無法辨識的忽略。"""
    if not transaction_type:
        return None
    return DIRECTION_MAP.get(transaction_type.strip(), None)


# ============================================================================
# 匯聚偵測核心
# ============================================================================

class ConvergenceDetector:
    """多議員匯聚訊號偵測器"""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or DB_PATH

    def detect(self) -> List[dict]:
        """偵測所有匯聚事件。

        Returns:
            匯聚事件列表，每個事件為 dict:
            {
                "ticker": str,
                "direction": "Buy" | "Sale",
                "politicians": [{"name": str, "chamber": str, "date": str, "amount": str}],
                "politician_count": int,
                "chambers": ["House", "Senate"],
                "window_start": str,
                "window_end": str,
                "span_days": int,
                "score": float,
                "score_breakdown": {...},
            }
        """
        # 1. 讀取所有有效交易
        trades = self._fetch_trades()
        if not trades:
            logger.warning("congress_trades 表中無有效交易資料")
            return []

        logger.info(f"共讀取 {len(trades)} 筆有效交易（有 ticker + 可辨識方向）")

        # 2. 按 (ticker, direction) 分組
        groups = defaultdict(list)
        for t in trades:
            key = (t["ticker"], t["direction"])
            groups[key].append(t)

        # 3. 在每個分組中尋找 30 天視窗內 2+ 不同議員的匯聚事件
        convergence_events = []
        for (ticker, direction), group_trades in groups.items():
            events = self._find_convergences(ticker, direction, group_trades)
            convergence_events.extend(events)

        # 4. 按分數排序
        convergence_events.sort(key=lambda e: e["score"], reverse=True)

        logger.info(f"偵測到 {len(convergence_events)} 個匯聚事件")
        return convergence_events

    def _fetch_trades(self) -> List[dict]:
        """從 congress_trades 讀取所有有 ticker 且方向可辨識的交易。"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT politician_name, ticker, transaction_type, transaction_date,
                   filing_date, chamber, amount_range
            FROM congress_trades
            WHERE ticker IS NOT NULL AND ticker != ''
        """)
        rows = cursor.fetchall()
        conn.close()

        trades = []
        for row in rows:
            direction = _map_direction(row["transaction_type"])
            if direction is None:
                continue

            tx_date = _parse_date(row["transaction_date"])
            if tx_date is None:
                continue

            trades.append({
                "politician_name": row["politician_name"],
                "ticker": row["ticker"],
                "direction": direction,
                "transaction_date": tx_date,
                "filing_date": row["filing_date"],
                "chamber": row["chamber"],
                "amount_range": row["amount_range"] or "",
            })

        return trades

    def _find_convergences(self, ticker: str, direction: str,
                           group_trades: List[dict]) -> List[dict]:
        """在同一 (ticker, direction) 分組中，找出 30 天視窗內的匯聚事件。

        演算法:
        - 按 transaction_date 排序
        - 以每筆交易為視窗起點，向前看 30 天
        - 若視窗內有 2+ 不同議員，記錄為匯聚事件
        - 選擇涵蓋最多議員的最佳視窗（避免重複報告）
        """
        # 按日期排序
        sorted_trades = sorted(group_trades, key=lambda t: t["transaction_date"])

        # 已被涵蓋的交易索引集合（用於去重）
        covered = set()
        events = []

        for i, anchor in enumerate(sorted_trades):
            if i in covered:
                continue

            window_end = anchor["transaction_date"] + timedelta(days=CONVERGENCE_WINDOW_DAYS)

            # 收集視窗內所有交易
            window_trades = []
            window_indices = []
            for j in range(i, len(sorted_trades)):
                if sorted_trades[j]["transaction_date"] <= window_end:
                    window_trades.append(sorted_trades[j])
                    window_indices.append(j)
                else:
                    break

            # 檢查是否有 2+ 不同議員
            unique_politicians = set(t["politician_name"] for t in window_trades)
            if len(unique_politicians) < 2:
                continue

            # 記錄匯聚事件
            event = self._build_event(ticker, direction, window_trades)
            events.append(event)

            # 標記已涵蓋的交易
            for idx in window_indices:
                covered.add(idx)

        return events

    def _build_event(self, ticker: str, direction: str,
                     window_trades: List[dict]) -> dict:
        """從視窗內的交易建構匯聚事件並計算評分。"""
        # 每位議員取最早的一筆交易作為代表
        politician_map = {}
        for t in window_trades:
            name = t["politician_name"]
            if name not in politician_map:
                politician_map[name] = t
            elif t["transaction_date"] < politician_map[name]["transaction_date"]:
                politician_map[name] = t

        politicians = []
        for name, t in politician_map.items():
            politicians.append({
                "name": name,
                "chamber": t["chamber"],
                "date": str(t["transaction_date"]),
                "amount": t["amount_range"],
            })

        # 時間範圍
        dates = [t["transaction_date"] for t in window_trades]
        window_start = min(dates)
        window_end = max(dates)
        span_days = (window_end - window_start).days

        # 涉及的院別
        chambers = sorted(set(t["chamber"] for t in window_trades))

        # 計算評分
        score, breakdown = self._calc_score(
            politician_count=len(politician_map),
            chambers=chambers,
            span_days=span_days,
            trades=list(politician_map.values()),
        )

        return {
            "ticker": ticker,
            "direction": direction,
            "politicians": politicians,
            "politician_count": len(politician_map),
            "chambers": chambers,
            "window_start": str(window_start),
            "window_end": str(window_end),
            "span_days": span_days,
            "score": round(score, 3),
            "score_breakdown": breakdown,
        }

    def _calc_score(self, politician_count: int, chambers: List[str],
                    span_days: int, trades: List[dict]) -> Tuple[float, dict]:
        """計算匯聚事件的綜合評分。

        Returns:
            (total_score, breakdown_dict)
        """
        # 1. 基礎分: 議員數量
        #    2人=1.0, 3人=1.5, 4人=2.0 → 公式: 0.5 * (n - 1)
        base = 0.5 * (politician_count - 1)

        # 2. 跨院加分: 同時有 House + Senate → +0.5
        cross_chamber = 0.5 if len(chambers) >= 2 else 0.0

        # 3. 時間密度: 越密集分越高
        #    span_days / 30 → 0~1, 反轉 → 1.0 - ratio
        #    同一天交易 → 1.0, 30天 → 0.0
        if span_days <= 0:
            time_density = 1.0
        else:
            time_density = max(0.0, 1.0 - (span_days / CONVERGENCE_WINDOW_DAYS))

        # 4. 金額加權: 所有議員代表交易的平均金額，歸一化到 0~1
        amounts = [_parse_amount(t["amount_range"]) for t in trades]
        avg_amount = sum(amounts) / len(amounts) if amounts else 0
        amount_weight = min(1.0, avg_amount / MAX_AMOUNT)

        # 5. 爆發式收斂加分: 7 天內的密集收斂 (Quant validation: +36% EA20d)
        burst_bonus = BURST_BONUS if span_days <= BURST_WINDOW_DAYS else 0.0

        # 綜合評分 = 基礎分 + 跨院加分 + 時間密度 * 0.5 + 金額加權 * 0.5 + burst
        total = base + cross_chamber + (time_density * 0.5) + (amount_weight * 0.5) + burst_bonus

        breakdown = {
            "base": round(base, 3),
            "cross_chamber": round(cross_chamber, 3),
            "time_density": round(time_density, 3),
            "amount_weight": round(amount_weight, 3),
            "burst_bonus": round(burst_bonus, 3),
        }

        return total, breakdown

    # ── 資料庫寫入 ──────────────────────────────────────────────────────

    def save_signals(self, events: List[dict]) -> dict:
        """將匯聚事件寫入 convergence_signals 表。

        Returns:
            {"inserted": int, "updated": int}
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 建表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS convergence_signals (
                id TEXT PRIMARY KEY,
                ticker TEXT NOT NULL,
                direction TEXT NOT NULL,
                politician_count INTEGER NOT NULL,
                politicians TEXT NOT NULL,
                chambers TEXT NOT NULL,
                window_start DATE NOT NULL,
                window_end DATE NOT NULL,
                span_days INTEGER NOT NULL,
                score REAL NOT NULL,
                score_base REAL,
                score_cross_chamber REAL,
                score_time_density REAL,
                score_amount_weight REAL,
                detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(ticker, direction, window_start, window_end)
            )
        """)

        inserted = 0
        updated = 0

        for event in events:
            signal_id = str(uuid.uuid4())
            politicians_str = ", ".join(
                f"{p['name']}({p['chamber']})" for p in event["politicians"]
            )
            chambers_str = "/".join(event["chambers"])
            breakdown = event["score_breakdown"]

            try:
                cursor.execute("""
                    INSERT INTO convergence_signals
                        (id, ticker, direction, politician_count, politicians, chambers,
                         window_start, window_end, span_days, score,
                         score_base, score_cross_chamber, score_time_density,
                         score_amount_weight)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    signal_id,
                    event["ticker"],
                    event["direction"],
                    event["politician_count"],
                    politicians_str,
                    chambers_str,
                    event["window_start"],
                    event["window_end"],
                    event["span_days"],
                    event["score"],
                    breakdown["base"],
                    breakdown["cross_chamber"],
                    breakdown["time_density"],
                    breakdown["amount_weight"],
                ))
                inserted += 1
            except sqlite3.IntegrityError:
                # 同一 (ticker, direction, window_start, window_end) 已存在，更新
                cursor.execute("""
                    UPDATE convergence_signals
                    SET politician_count = ?, politicians = ?, chambers = ?,
                        span_days = ?, score = ?,
                        score_base = ?, score_cross_chamber = ?,
                        score_time_density = ?, score_amount_weight = ?,
                        detected_at = CURRENT_TIMESTAMP
                    WHERE ticker = ? AND direction = ?
                      AND window_start = ? AND window_end = ?
                """, (
                    event["politician_count"],
                    politicians_str,
                    chambers_str,
                    event["span_days"],
                    event["score"],
                    breakdown["base"],
                    breakdown["cross_chamber"],
                    breakdown["time_density"],
                    breakdown["amount_weight"],
                    event["ticker"],
                    event["direction"],
                    event["window_start"],
                    event["window_end"],
                ))
                updated += 1

        conn.commit()
        conn.close()

        logger.info(f"匯聚訊號寫入完成: 新增 {inserted}, 更新 {updated}")
        return {"inserted": inserted, "updated": updated}


# ============================================================================
# 摘要報告
# ============================================================================

def print_summary(events: List[dict]):
    """輸出匯聚訊號摘要報告。"""
    if not events:
        print("  (無匯聚事件)")
        return

    total = len(events)
    buy_events = [e for e in events if e["direction"] == "Buy"]
    sale_events = [e for e in events if e["direction"] == "Sale"]
    cross_chamber = [e for e in events if len(e["chambers"]) >= 2]

    print(f"\n{'='*70}")
    print(f"  多議員匯聚訊號偵測報告 (Convergence Detector)")
    print(f"{'='*70}")
    print(f"  匯聚事件總數: {total}")
    print(f"  買入匯聚: {len(buy_events)}  |  賣出匯聚: {len(sale_events)}")
    print(f"  跨院匯聚 (House+Senate): {len(cross_chamber)}")
    print()

    # 統計議員數量分布
    count_dist = defaultdict(int)
    for e in events:
        count_dist[e["politician_count"]] += 1
    print(f"  議員數量分布:")
    for cnt in sorted(count_dist.keys()):
        print(f"    {cnt} 位議員: {count_dist[cnt]} 個事件")
    print()

    # Top 匯聚事件
    print(f"  Top {min(15, total)} 匯聚事件（按評分排序）:")
    print(f"  {'分數':>6} {'Ticker':<8} {'方向':<6} {'人數':>4} {'院別':<14}"
          f" {'時間跨度':>8} {'議員'}")
    print(f"  {'-'*80}")

    for event in events[:15]:
        chambers_str = "/".join(event["chambers"])
        politicians_str = ", ".join(p["name"] for p in event["politicians"])
        # 截斷過長的議員名單
        if len(politicians_str) > 40:
            politicians_str = politicians_str[:37] + "..."

        direction_label = "買入" if event["direction"] == "Buy" else "賣出"
        span_label = f"{event['span_days']}天"

        print(
            f"  {event['score']:>6.3f} {event['ticker']:<8} {direction_label:<6}"
            f" {event['politician_count']:>4} {chambers_str:<14}"
            f" {span_label:>8} {politicians_str}"
        )

    # 評分細項（第一名）
    if events:
        top = events[0]
        bd = top["score_breakdown"]
        print()
        print(f"  最高分事件評分細項 ({top['ticker']} {top['direction']}):")
        print(f"    基礎分 (議員數量):    {bd['base']:.3f}")
        print(f"    跨院加分:              {bd['cross_chamber']:.3f}")
        print(f"    時間密度 (×0.5):       {bd['time_density']:.3f}")
        print(f"    金額加權 (×0.5):       {bd['amount_weight']:.3f}")
        print(f"    總分:                  {top['score']:.3f}")

    print(f"\n{'='*70}")


# ============================================================================
# CLI 入口
# ============================================================================

def main():
    """主函式：偵測匯聚訊號 → 評分 → 儲存 → 輸出報告。"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    print("多議員匯聚訊號偵測系統 (Convergence Detector)")
    print(f"資料庫: {DB_PATH}")
    print(f"匯聚視窗: {CONVERGENCE_WINDOW_DAYS} 天")

    detector = ConvergenceDetector()

    # 偵測匯聚事件
    events = detector.detect()

    if not events:
        print("\n  congress_trades 表中未偵測到匯聚事件。")
        return

    # 輸出摘要
    print_summary(events)

    # 寫入資料庫
    result = detector.save_signals(events)
    print(f"\n  DB 寫入結果: 新增 {result['inserted']}, 更新 {result['updated']}")
    print(f"  匯聚訊號已存入 convergence_signals 表")


if __name__ == "__main__":
    main()
