"""
Smart Alert System — Political Alpha Monitor
智慧告警系統：自動偵測高優先級交易信號並發送通知

觸發條件:
1. 高強度 Alpha 信號 (signal_strength > 0.7)
2. 收斂信號 (多議員同向交易)
3. 大額交易 ($100K+)
4. Top-ranked 議員新交易 (PIS grade A/B)
5. 異常 filing lag (< 3 天 = 可能緊急)

使用方式:
    python -m src.smart_alerts                # 檢查並發送告警
    python -m src.smart_alerts --dry-run      # 只顯示，不發送
    python -m src.smart_alerts --days 1       # 只看最近 1 天
    python -m src.smart_alerts --threshold 0.5  # 降低閾值
"""

import argparse
import logging
import sqlite3
import sys
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.config import DB_PATH

logger = logging.getLogger(__name__)

# ── 告警閾值 ──
DEFAULT_ALPHA_THRESHOLD = 0.7    # signal_strength 閾值
DEFAULT_CONVERGENCE_SCORE = 1.0  # 收斂信號分數閾值
LARGE_TRADE_AMOUNTS = ['$100,001 - $250,000', '$250,001 - $500,000',
                       '$500,001 - $1,000,000', '$1,000,001 - $5,000,000',
                       '$5,000,001 - $25,000,000', '$25,000,001 - $50,000,000',
                       'Over $50,000,000']
TOP_POLITICIAN_GRADES = ['A', 'B']
URGENT_LAG_DAYS = 3


class SmartAlertSystem:
    """智慧告警系統。"""

    def __init__(self, db_path: str = DB_PATH, days: int = 1,
                 alpha_threshold: float = DEFAULT_ALPHA_THRESHOLD):
        self.db_path = db_path
        self.days = days
        self.alpha_threshold = alpha_threshold
        self.alerts = []  # type: List[Dict]

    def _query(self, sql: str, params: tuple = ()) -> List[Dict]:
        """安全查詢資料庫。"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            rows = conn.execute(sql, params).fetchall()
            conn.close()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.warning(f"Query failed: {e}")
            return []

    def check_high_alpha_signals(self) -> List[Dict]:
        """檢查高強度 Alpha 信號。"""
        cutoff = (datetime.now() - timedelta(days=self.days)).strftime('%Y-%m-%d')
        rows = self._query("""
            SELECT a.ticker, a.direction, a.expected_alpha_5d, a.expected_alpha_20d,
                   a.confidence, a.signal_strength, a.reasoning,
                   c.politician_name, c.chamber, c.transaction_type, c.amount_range
            FROM alpha_signals a
            JOIN congress_trades c ON a.trade_id = c.id
            WHERE a.signal_strength >= ? AND a.created_at >= ?
            ORDER BY a.signal_strength DESC
            LIMIT 10
        """, (self.alpha_threshold, cutoff))

        alerts = []
        for r in rows:
            alerts.append({
                'type': 'HIGH_ALPHA',
                'priority': 'HIGH' if r['signal_strength'] > 0.8 else 'MEDIUM',
                'ticker': r['ticker'],
                'direction': r['direction'],
                'alpha_5d': r['expected_alpha_5d'],
                'alpha_20d': r['expected_alpha_20d'],
                'confidence': r['confidence'],
                'strength': r['signal_strength'],
                'politician': r['politician_name'],
                'chamber': r['chamber'],
                'tx_type': r['transaction_type'],
                'amount': r['amount_range'],
                'message': (f"[HIGH ALPHA] {r['ticker']} {r['direction']} "
                           f"alpha_5d={r['expected_alpha_5d']:+.2f}% "
                           f"conf={r['confidence']:.0%} "
                           f"({r['politician_name']}, {r['chamber']})")
            })
        return alerts

    def check_convergence_alerts(self) -> List[Dict]:
        """檢查收斂信號。"""
        cutoff = (datetime.now() - timedelta(days=self.days * 7)).strftime('%Y-%m-%d')
        rows = self._query("""
            SELECT ticker, direction, politician_count, politicians, score
            FROM convergence_signals
            WHERE score >= ? AND detected_at >= ?
            ORDER BY score DESC
        """, (DEFAULT_CONVERGENCE_SCORE, cutoff))

        alerts = []
        for r in rows:
            alerts.append({
                'type': 'CONVERGENCE',
                'priority': 'HIGH' if r['politician_count'] >= 3 else 'MEDIUM',
                'ticker': r['ticker'],
                'direction': r['direction'],
                'politician_count': r['politician_count'],
                'politicians': r['politicians'],
                'score': r['score'],
                'message': (f"[CONVERGENCE] {r['ticker']} — "
                           f"{r['politician_count']} politicians {r['direction']} "
                           f"(score={r['score']:.2f})")
            })
        return alerts

    def check_large_trades(self) -> List[Dict]:
        """檢查大額交易。"""
        cutoff = (datetime.now() - timedelta(days=self.days)).strftime('%Y-%m-%d')
        placeholders = ','.join('?' * len(LARGE_TRADE_AMOUNTS))
        rows = self._query(f"""
            SELECT politician_name, ticker, transaction_type, amount_range,
                   chamber, transaction_date, filing_date
            FROM congress_trades
            WHERE amount_range IN ({placeholders}) AND created_at >= ?
            ORDER BY created_at DESC
        """, (*LARGE_TRADE_AMOUNTS, cutoff))

        alerts = []
        for r in rows:
            alerts.append({
                'type': 'LARGE_TRADE',
                'priority': 'HIGH',
                'ticker': r['ticker'] or 'N/A',
                'politician': r['politician_name'],
                'tx_type': r['transaction_type'],
                'amount': r['amount_range'],
                'chamber': r['chamber'],
                'message': (f"[LARGE TRADE] {r['politician_name']} "
                           f"{r['transaction_type']} {r['ticker'] or 'N/A'} "
                           f"({r['amount_range']})")
            })
        return alerts

    def check_top_politician_trades(self) -> List[Dict]:
        """檢查 Top-ranked 議員的新交易。"""
        cutoff = (datetime.now() - timedelta(days=self.days)).strftime('%Y-%m-%d')
        placeholders = ','.join('?' * len(TOP_POLITICIAN_GRADES))
        # politician_rankings 沒有 grade 欄位，用 pis_total >= 45 當作 A/B 門檻
        rows = self._query("""
            SELECT c.politician_name, c.ticker, c.transaction_type, c.amount_range,
                   c.chamber, p.pis_total, p.rank
            FROM congress_trades c
            JOIN politician_rankings p ON c.politician_name = p.politician_name
            WHERE p.pis_total >= 45 AND c.created_at >= ?
            ORDER BY p.pis_total DESC
        """, (cutoff,))

        alerts = []
        for r in rows:
            grade = 'A' if r['pis_total'] >= 50 else 'B'
            alerts.append({
                'type': 'TOP_POLITICIAN',
                'priority': 'MEDIUM',
                'ticker': r['ticker'] or 'N/A',
                'politician': r['politician_name'],
                'grade': grade,
                'pis_score': r['pis_total'],
                'tx_type': r['transaction_type'],
                'message': (f"[TOP POLITICIAN] {r['politician_name']} (Grade {grade}, "
                           f"PIS={r['pis_total']:.1f}) "
                           f"{r['transaction_type']} {r['ticker'] or 'N/A'}")
            })
        return alerts

    def check_urgent_filings(self) -> List[Dict]:
        """檢查快速申報（filing lag < 3 天 = 可能緊急）。"""
        cutoff = (datetime.now() - timedelta(days=self.days * 30)).strftime('%Y-%m-%d')
        rows = self._query("""
            SELECT politician_name, ticker, transaction_type, amount_range,
                   chamber, transaction_date, filing_date
            FROM congress_trades
            WHERE filing_date IS NOT NULL AND transaction_date IS NOT NULL
              AND created_at >= ?
            ORDER BY filing_date DESC
        """, (cutoff,))

        alerts = []
        for r in rows:
            try:
                tx_date = datetime.strptime(r['transaction_date'], '%Y-%m-%d')
                filing = datetime.strptime(r['filing_date'], '%Y-%m-%d')
                lag = (filing - tx_date).days
                if 0 <= lag <= URGENT_LAG_DAYS:
                    alerts.append({
                        'type': 'URGENT_FILING',
                        'priority': 'HIGH',
                        'ticker': r['ticker'] or 'N/A',
                        'politician': r['politician_name'],
                        'lag_days': lag,
                        'tx_type': r['transaction_type'],
                        'message': (f"[URGENT FILING] {r['politician_name']} "
                                   f"{r['transaction_type']} {r['ticker'] or 'N/A'} — "
                                   f"filed in {lag} day(s)")
                    })
            except (ValueError, TypeError):
                continue

        return alerts[:10]  # 最多 10 筆

    def run_all_checks(self) -> List[Dict]:
        """執行所有告警檢查。"""
        all_alerts = []

        checks = [
            ('High Alpha Signals', self.check_high_alpha_signals),
            ('Convergence Events', self.check_convergence_alerts),
            ('Large Trades', self.check_large_trades),
            ('Top Politician Trades', self.check_top_politician_trades),
            ('Urgent Filings', self.check_urgent_filings),
        ]

        for name, check_fn in checks:
            try:
                alerts = check_fn()
                all_alerts.extend(alerts)
                logger.info(f"{name}: {len(alerts)} alerts")
            except Exception as e:
                logger.warning(f"{name} check failed: {e}")

        # 按優先級排序
        priority_order = {'HIGH': 0, 'MEDIUM': 1, 'LOW': 2}
        all_alerts.sort(key=lambda x: priority_order.get(x.get('priority', 'LOW'), 2))

        self.alerts = all_alerts
        return all_alerts

    def format_telegram_message(self) -> str:
        """格式化 Telegram 告警訊息。"""
        if not self.alerts:
            return ""

        high = [a for a in self.alerts if a.get('priority') == 'HIGH']
        medium = [a for a in self.alerts if a.get('priority') == 'MEDIUM']

        lines = [
            "<b>Political Alpha Monitor Alert</b>",
            f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"Alerts: {len(self.alerts)} ({len(high)} HIGH, {len(medium)} MEDIUM)",
            ""
        ]

        if high:
            lines.append("<b>== HIGH PRIORITY ==</b>")
            for a in high[:5]:
                lines.append(a['message'])
            lines.append("")

        if medium:
            lines.append("<b>== MEDIUM PRIORITY ==</b>")
            for a in medium[:5]:
                lines.append(a['message'])

        return "\n".join(lines)

    def send_alerts(self) -> bool:
        """發送告警到 Telegram。"""
        msg = self.format_telegram_message()
        if not msg:
            logger.info("No alerts to send")
            return True

        try:
            from src.notifications import send_telegram
            return send_telegram(msg)
        except ImportError:
            logger.warning("notifications module not available")
            return False

    def print_summary(self) -> None:
        """終端輸出告警摘要。"""
        if not self.alerts:
            print("\n  No alerts triggered.\n")
            return

        high = [a for a in self.alerts if a.get('priority') == 'HIGH']
        medium = [a for a in self.alerts if a.get('priority') == 'MEDIUM']

        print(f"\n{'='*70}")
        print(f"  Smart Alert Summary")
        print(f"  Total: {len(self.alerts)} | HIGH: {len(high)} | MEDIUM: {len(medium)}")
        print(f"{'='*70}")

        # 按類型分組
        types = {}  # type: Dict[str, List[Dict]]
        for a in self.alerts:
            t = a.get('type', 'UNKNOWN')
            if t not in types:
                types[t] = []
            types[t].append(a)

        for alert_type, alerts in types.items():
            print(f"\n  --- {alert_type} ({len(alerts)}) ---")
            for a in alerts[:5]:
                priority_tag = '[!]' if a.get('priority') == 'HIGH' else '[ ]'
                print(f"  {priority_tag} {a['message']}")
            if len(alerts) > 5:
                print(f"  ... and {len(alerts) - 5} more")

        print(f"\n{'='*70}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Political Alpha Monitor Smart Alert System"
    )
    parser.add_argument("--days", type=int, default=1,
                        help="Look back N days (default 1)")
    parser.add_argument("--threshold", type=float, default=DEFAULT_ALPHA_THRESHOLD,
                        help=f"Alpha signal_strength threshold (default {DEFAULT_ALPHA_THRESHOLD})")
    parser.add_argument("--dry-run", action="store_true",
                        help="Only display, don't send notifications")
    parser.add_argument("--db", type=str, default=DB_PATH,
                        help="Database path")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    system = SmartAlertSystem(
        db_path=args.db,
        days=args.days,
        alpha_threshold=args.threshold
    )

    alerts = system.run_all_checks()
    system.print_summary()

    if not args.dry_run and alerts:
        sent = system.send_alerts()
        if sent:
            print("  Telegram notification sent.")
        else:
            print("  Telegram not configured (set TELEGRAM_BOT_TOKEN/CHAT_ID in .env)")


if __name__ == "__main__":
    main()
