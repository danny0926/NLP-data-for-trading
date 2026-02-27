"""
異常交易偵測模組 — Anomaly Detector

偵測國會議員不尋常的交易模式：
1. Volume anomaly: 交易頻率異常（z-score > 2）
2. Timing anomaly: 申報延遲異常快（<5天）或異常慢（>60天）
3. Cluster anomaly: 多位議員同一 sector 5 天內集中交易
4. Size anomaly: 交易金額顯著偏離該議員慣常範圍
5. Reversal anomaly: 同一標的 30 天內買後賣

Python 3.9+ 相容。
"""

import logging
import sqlite3
import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Tuple

from src.config import DB_PATH

logger = logging.getLogger("AnomalyDetector")


class Severity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


# 金額區間 → 中位數估計值（用於數值比較）
AMOUNT_MIDPOINTS: Dict[str, float] = {
    "$1 - $1,000": 500,
    "$1,001 - $15,000": 8000,
    "$15,001 - $50,000": 32500,
    "$50,001 - $100,000": 75000,
    "$100,001 - $250,000": 175000,
    "$250,001 - $500,000": 375000,
    "$500,001 - $1,000,000": 750000,
    "$1,000,001 - $5,000,000": 3000000,
    "$5,000,001 - $25,000,000": 15000000,
    "$25,000,001 - $50,000,000": 37500000,
    "Over $50,000,000": 75000000,
}


def _amount_to_numeric(amount_range: str) -> float:
    """將金額區間字串轉為中位數數值估計"""
    if not amount_range:
        return 0.0
    # 嘗試精確匹配
    if amount_range in AMOUNT_MIDPOINTS:
        return AMOUNT_MIDPOINTS[amount_range]
    # 模糊匹配：取第一個命中的
    amount_lower = amount_range.lower().replace(",", "").replace(" ", "")
    for key, val in AMOUNT_MIDPOINTS.items():
        key_lower = key.lower().replace(",", "").replace(" ", "")
        if key_lower in amount_lower or amount_lower in key_lower:
            return val
    # fallback: 嘗試解析數字
    import re
    nums = re.findall(r'[\d,]+', amount_range.replace(",", ""))
    if nums:
        parsed = [float(n) for n in nums]
        return sum(parsed) / len(parsed)
    return 0.0


class Anomaly:
    """單一異常偵測結果"""

    def __init__(
        self,
        politician: str,
        ticker: Optional[str],
        anomaly_type: str,
        severity: Severity,
        score: float,
        description: str,
        transaction_date: Optional[str] = None,
        related_trades: Optional[List[str]] = None,
    ):
        self.politician = politician
        self.ticker = ticker
        self.anomaly_type = anomaly_type
        self.severity = severity
        self.score = score  # 0~10 的分數，越高越異常
        self.description = description
        self.transaction_date = transaction_date
        self.related_trades = related_trades or []

    def to_dict(self) -> dict:
        return {
            "politician": self.politician,
            "ticker": self.ticker,
            "anomaly_type": self.anomaly_type,
            "severity": self.severity.value,
            "score": round(self.score, 2),
            "description": self.description,
            "transaction_date": self.transaction_date,
            "related_trades_count": len(self.related_trades),
        }

    def __repr__(self) -> str:
        return (
            f"Anomaly({self.anomaly_type}, {self.severity.value}, "
            f"{self.politician}, {self.ticker}, score={self.score:.1f})"
        )


class AnomalyDetector:
    """國會交易異常偵測引擎"""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or DB_PATH
        self._trades = []
        self._loaded = False

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _load_trades(self) -> List[dict]:
        """載入所有 congress_trades 資料"""
        if self._loaded:
            return self._trades
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, chamber, politician_name, transaction_date, filing_date,
                   ticker, asset_name, asset_type, transaction_type, amount_range,
                   owner, comment, source_url, created_at
            FROM congress_trades
            WHERE transaction_date IS NOT NULL
            ORDER BY transaction_date
        """)
        self._trades = [dict(row) for row in cursor.fetchall()]
        conn.close()
        self._loaded = True
        logger.info(f"載入 {len(self._trades)} 筆交易資料")
        return self._trades

    # ── 1. Volume Anomaly: 交易頻率異常 ──

    def detect_volume_anomalies(self, window_days: int = 30, z_threshold: float = 2.0) -> List[Anomaly]:
        """偵測議員在特定時間窗口內交易頻率異常（z-score > threshold）"""
        trades = self._load_trades()
        anomalies = []

        # 按議員分組，計算每月交易次數
        politician_trades: Dict[str, List[str]] = defaultdict(list)
        for t in trades:
            politician_trades[t["politician_name"]].append(t["transaction_date"])

        for politician, dates in politician_trades.items():
            if len(dates) < 3:
                continue  # 資料太少無法計算統計

            # 計算每個 window 的交易次數
            sorted_dates = sorted(dates)
            # 用滾動窗口計算每個月的交易數
            window_counts = []
            start = datetime.strptime(sorted_dates[0], "%Y-%m-%d")
            end = datetime.strptime(sorted_dates[-1], "%Y-%m-%d")

            current = start
            while current <= end:
                window_end = current + timedelta(days=window_days)
                count = sum(
                    1 for d in sorted_dates
                    if current <= datetime.strptime(d, "%Y-%m-%d") < window_end
                )
                window_counts.append((current.strftime("%Y-%m-%d"), count))
                current += timedelta(days=window_days)

            if len(window_counts) < 2:
                continue

            counts = [c for _, c in window_counts]
            mean = sum(counts) / len(counts)
            if mean == 0:
                continue
            variance = sum((c - mean) ** 2 for c in counts) / len(counts)
            std = variance ** 0.5

            if std == 0:
                continue

            for window_start, count in window_counts:
                z_score = (count - mean) / std
                if z_score > z_threshold:
                    severity = Severity.HIGH if z_score > 3 else Severity.MEDIUM
                    score = min(10.0, z_score * 2.5)
                    anomalies.append(Anomaly(
                        politician=politician,
                        ticker=None,
                        anomaly_type="VOLUME",
                        severity=severity,
                        score=score,
                        description=(
                            f"{politician} 在 {window_start} 起 {window_days} 天內交易 {count} 次，"
                            f"平均 {mean:.1f} 次/窗口，z-score={z_score:.2f}"
                        ),
                        transaction_date=window_start,
                    ))

        logger.info(f"Volume 異常偵測完成：{len(anomalies)} 筆")
        return anomalies

    # ── 2. Timing Anomaly: 申報延遲異常 ──

    def detect_timing_anomalies(self, fast_threshold: int = 5, slow_threshold: int = 60) -> List[Anomaly]:
        """偵測申報延遲異常快或異常慢的交易"""
        trades = self._load_trades()
        anomalies = []

        for t in trades:
            if not t["filing_date"] or not t["transaction_date"]:
                continue

            tx_date = datetime.strptime(t["transaction_date"], "%Y-%m-%d")
            file_date = datetime.strptime(t["filing_date"], "%Y-%m-%d")
            lag_days = (file_date - tx_date).days

            if lag_days < 0:
                # 申報日在交易日之前（資料錯誤）
                anomalies.append(Anomaly(
                    politician=t["politician_name"],
                    ticker=t["ticker"],
                    anomaly_type="TIMING",
                    severity=Severity.HIGH,
                    score=8.0,
                    description=(
                        f"{t['politician_name']} 申報日({t['filing_date']})早於"
                        f"交易日({t['transaction_date']})，延遲={lag_days}天（資料異常）"
                    ),
                    transaction_date=t["transaction_date"],
                    related_trades=[t["id"]],
                ))
            elif lag_days < fast_threshold:
                anomalies.append(Anomaly(
                    politician=t["politician_name"],
                    ticker=t["ticker"],
                    anomaly_type="TIMING",
                    severity=Severity.MEDIUM,
                    score=6.0,
                    description=(
                        f"{t['politician_name']} 交易 {t['ticker'] or t['asset_name']} "
                        f"後僅 {lag_days} 天即申報（異常快速，"
                        f"交易日={t['transaction_date']}，申報日={t['filing_date']}）"
                    ),
                    transaction_date=t["transaction_date"],
                    related_trades=[t["id"]],
                ))
            elif lag_days > slow_threshold:
                severity = Severity.CRITICAL if lag_days > 90 else Severity.HIGH
                score = min(10.0, 5.0 + (lag_days - slow_threshold) / 10)
                anomalies.append(Anomaly(
                    politician=t["politician_name"],
                    ticker=t["ticker"],
                    anomaly_type="TIMING",
                    severity=severity,
                    score=score,
                    description=(
                        f"{t['politician_name']} 交易 {t['ticker'] or t['asset_name']} "
                        f"延遲 {lag_days} 天才申報（超過 {slow_threshold} 天門檻，"
                        f"交易日={t['transaction_date']}，申報日={t['filing_date']}）"
                    ),
                    transaction_date=t["transaction_date"],
                    related_trades=[t["id"]],
                ))

        logger.info(f"Timing 異常偵測完成：{len(anomalies)} 筆")
        return anomalies

    # ── 3. Cluster Anomaly: 多位議員同一標的集中交易 ──

    def detect_cluster_anomalies(self, window_days: int = 5, min_politicians: int = 3) -> List[Anomaly]:
        """偵測多位議員在短時間內交易同一 ticker"""
        trades = self._load_trades()
        anomalies = []

        # 只看有 ticker 的交易
        ticker_trades: Dict[str, List[dict]] = defaultdict(list)
        for t in trades:
            if t["ticker"]:
                ticker_trades[t["ticker"]].append(t)

        seen_clusters = set()  # 避免重複報告

        for ticker, t_list in ticker_trades.items():
            if len(t_list) < min_politicians:
                continue

            # 按日期排序
            t_list.sort(key=lambda x: x["transaction_date"])

            # 滑動窗口找集群
            for i, anchor in enumerate(t_list):
                anchor_date = datetime.strptime(anchor["transaction_date"], "%Y-%m-%d")
                window_end = anchor_date + timedelta(days=window_days)

                cluster = []
                cluster_politicians = set()
                for t in t_list:
                    t_date = datetime.strptime(t["transaction_date"], "%Y-%m-%d")
                    if anchor_date <= t_date <= window_end:
                        cluster.append(t)
                        cluster_politicians.add(t["politician_name"])

                if len(cluster_politicians) >= min_politicians:
                    # 建立唯一 key 避免重複
                    cluster_key = (ticker, frozenset(cluster_politicians))
                    if cluster_key in seen_clusters:
                        continue
                    seen_clusters.add(cluster_key)

                    n = len(cluster_politicians)
                    severity = Severity.CRITICAL if n >= 4 else Severity.HIGH
                    score = min(10.0, 5.0 + n * 1.5)

                    names = ", ".join(sorted(cluster_politicians))
                    dates = sorted(set(t["transaction_date"] for t in cluster))

                    anomalies.append(Anomaly(
                        politician=names,
                        ticker=ticker,
                        anomaly_type="CLUSTER",
                        severity=severity,
                        score=score,
                        description=(
                            f"{n} 位議員在 {window_days} 天內交易 {ticker}：{names}。"
                            f"日期：{', '.join(dates)}"
                        ),
                        transaction_date=dates[0],
                        related_trades=[t["id"] for t in cluster],
                    ))

        logger.info(f"Cluster 異常偵測完成：{len(anomalies)} 筆")
        return anomalies

    # ── 4. Size Anomaly: 金額偏離慣常範圍 ──

    def detect_size_anomalies(self, z_threshold: float = 2.0) -> List[Anomaly]:
        """偵測交易金額顯著偏離該議員歷史平均範圍"""
        trades = self._load_trades()
        anomalies = []

        # 按議員分組
        politician_trades: Dict[str, List[dict]] = defaultdict(list)
        for t in trades:
            politician_trades[t["politician_name"]].append(t)

        for politician, t_list in politician_trades.items():
            if len(t_list) < 3:
                continue

            # 將金額區間轉換為數值
            amounts = []
            for t in t_list:
                val = _amount_to_numeric(t["amount_range"])
                amounts.append((t, val))

            values = [a[1] for a in amounts]
            mean = sum(values) / len(values)
            variance = sum((v - mean) ** 2 for v in values) / len(values)
            std = variance ** 0.5

            if std == 0:
                continue

            for t, val in amounts:
                z_score = (val - mean) / std
                if z_score > z_threshold:
                    severity = Severity.CRITICAL if z_score > 3 else Severity.HIGH
                    score = min(10.0, z_score * 2.0)
                    anomalies.append(Anomaly(
                        politician=politician,
                        ticker=t["ticker"],
                        anomaly_type="SIZE",
                        severity=severity,
                        score=score,
                        description=(
                            f"{politician} 交易 {t['ticker'] or t['asset_name']} "
                            f"金額 {t['amount_range']}（估值 ${val:,.0f}），"
                            f"遠高於個人平均 ${mean:,.0f}，z-score={z_score:.2f}"
                        ),
                        transaction_date=t["transaction_date"],
                        related_trades=[t["id"]],
                    ))

        logger.info(f"Size 異常偵測完成：{len(anomalies)} 筆")
        return anomalies

    # ── 5. Reversal Anomaly: 短期買後賣 ──

    def detect_reversal_anomalies(self, max_days: int = 30) -> List[Anomaly]:
        """偵測同一議員、同一 ticker 在 max_days 天內先買後賣"""
        trades = self._load_trades()
        anomalies = []

        # 按 (議員, ticker) 分組
        key_trades: Dict[Tuple[str, str], List[dict]] = defaultdict(list)
        for t in trades:
            if t["ticker"]:
                key_trades[(t["politician_name"], t["ticker"])].append(t)

        seen_pairs = set()

        for (politician, ticker), t_list in key_trades.items():
            buys = [t for t in t_list if t["transaction_type"] == "Buy"]
            sells = [t for t in t_list if t["transaction_type"] == "Sale"]

            for buy in buys:
                buy_date = datetime.strptime(buy["transaction_date"], "%Y-%m-%d")
                for sell in sells:
                    sell_date = datetime.strptime(sell["transaction_date"], "%Y-%m-%d")
                    days_held = (sell_date - buy_date).days

                    if 0 <= days_held <= max_days:
                        pair_key = (politician, ticker, buy["transaction_date"], sell["transaction_date"])
                        if pair_key in seen_pairs:
                            continue
                        seen_pairs.add(pair_key)

                        if days_held <= 7:
                            severity = Severity.CRITICAL
                            score = 9.0
                        elif days_held <= 14:
                            severity = Severity.HIGH
                            score = 7.5
                        else:
                            severity = Severity.MEDIUM
                            score = 6.0

                        anomalies.append(Anomaly(
                            politician=politician,
                            ticker=ticker,
                            anomaly_type="REVERSAL",
                            severity=severity,
                            score=score,
                            description=(
                                f"{politician} 買入 {ticker} ({buy['transaction_date']}) "
                                f"後僅 {days_held} 天賣出 ({sell['transaction_date']})，"
                                f"買入金額 {buy['amount_range']}，賣出金額 {sell['amount_range']}"
                            ),
                            transaction_date=buy["transaction_date"],
                            related_trades=[buy["id"], sell["id"]],
                        ))

        logger.info(f"Reversal 異常偵測完成：{len(anomalies)} 筆")
        return anomalies

    # ── 綜合偵測 ──

    def run_all_detections(self) -> List[Anomaly]:
        """執行所有異常偵測方法，回傳合併結果（按 score 降序）"""
        all_anomalies = []
        all_anomalies.extend(self.detect_volume_anomalies())
        all_anomalies.extend(self.detect_timing_anomalies())
        all_anomalies.extend(self.detect_cluster_anomalies())
        all_anomalies.extend(self.detect_size_anomalies())
        all_anomalies.extend(self.detect_reversal_anomalies())

        # 按分數降序排列
        all_anomalies.sort(key=lambda a: a.score, reverse=True)

        logger.info(
            f"綜合偵測完成：共 {len(all_anomalies)} 筆異常 — "
            f"CRITICAL={sum(1 for a in all_anomalies if a.severity == Severity.CRITICAL)}, "
            f"HIGH={sum(1 for a in all_anomalies if a.severity == Severity.HIGH)}, "
            f"MEDIUM={sum(1 for a in all_anomalies if a.severity == Severity.MEDIUM)}, "
            f"LOW={sum(1 for a in all_anomalies if a.severity == Severity.LOW)}"
        )
        return all_anomalies

    # ── 複合異常分數 ──

    def compute_composite_scores(self, anomalies: List[Anomaly]) -> Dict[str, float]:
        """
        計算每位議員的複合異常分數。
        多種異常類型疊加 → 分數加權加總。
        """
        politician_scores: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))

        for a in anomalies:
            # Cluster anomaly 涉及多位議員
            if a.anomaly_type == "CLUSTER":
                for name in a.politician.split(", "):
                    politician_scores[name][a.anomaly_type] = max(
                        politician_scores[name][a.anomaly_type], a.score
                    )
            else:
                politician_scores[a.politician][a.anomaly_type] = max(
                    politician_scores[a.politician][a.anomaly_type], a.score
                )

        # 加權計算（多種異常類型疊加有加分）
        type_weights = {
            "VOLUME": 1.0,
            "TIMING": 1.2,
            "CLUSTER": 1.5,
            "SIZE": 1.3,
            "REVERSAL": 1.8,
        }

        composite = {}
        for politician, type_scores in politician_scores.items():
            base = sum(
                score * type_weights.get(atype, 1.0)
                for atype, score in type_scores.items()
            )
            # 多類型加成：每多一種異常類型 +10%
            diversity_bonus = 1.0 + (len(type_scores) - 1) * 0.1
            composite[politician] = round(min(100.0, base * diversity_bonus), 2)

        return dict(sorted(composite.items(), key=lambda x: x[1], reverse=True))

    # ── 資料庫持久化 ──

    def save_to_db(self, anomalies: List[Anomaly]) -> int:
        """將偵測結果寫入 anomaly_detections 表"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 建立表（如不存在）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS anomaly_detections (
                id TEXT PRIMARY KEY,
                politician_name TEXT NOT NULL,
                ticker TEXT,
                anomaly_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                score REAL NOT NULL,
                description TEXT,
                transaction_date TEXT,
                related_trades_count INTEGER DEFAULT 0,
                detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_anomaly_politician ON anomaly_detections(politician_name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_anomaly_type ON anomaly_detections(anomaly_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_anomaly_severity ON anomaly_detections(severity)")

        count = 0
        for a in anomalies:
            try:
                cursor.execute("""
                    INSERT INTO anomaly_detections (
                        id, politician_name, ticker, anomaly_type, severity,
                        score, description, transaction_date, related_trades_count
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    str(uuid.uuid4()),
                    a.politician,
                    a.ticker,
                    a.anomaly_type,
                    a.severity.value,
                    a.score,
                    a.description,
                    a.transaction_date,
                    len(a.related_trades),
                ))
                count += 1
            except Exception as e:
                logger.warning(f"寫入異常偵測結果失敗: {e}")

        conn.commit()
        conn.close()
        logger.info(f"已儲存 {count} 筆異常偵測結果到 anomaly_detections 表")
        return count

    # ── Markdown 報告生成 ──

    def generate_report(self, anomalies: List[Anomaly], composite: Dict[str, float]) -> str:
        """生成 Markdown 格式的異常偵測報告"""
        today = date.today().isoformat()

        severity_counts = defaultdict(int)
        type_counts = defaultdict(int)
        for a in anomalies:
            severity_counts[a.severity.value] += 1
            type_counts[a.anomaly_type] += 1

        lines = [
            f"# 國會交易異常偵測報告",
            f"",
            f"**偵測日期**: {today}",
            f"**資料來源**: congress_trades (SQLite)",
            f"**偵測筆數**: {len(anomalies)}",
            f"",
            f"---",
            f"",
            f"## 摘要統計",
            f"",
            f"### 嚴重度分布",
            f"| 嚴重度 | 數量 |",
            f"|--------|------|",
        ]
        for sev in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
            lines.append(f"| {sev} | {severity_counts.get(sev, 0)} |")

        lines.extend([
            f"",
            f"### 異常類型分布",
            f"| 類型 | 說明 | 數量 |",
            f"|------|------|------|",
            f"| VOLUME | 交易頻率異常 | {type_counts.get('VOLUME', 0)} |",
            f"| TIMING | 申報延遲異常 | {type_counts.get('TIMING', 0)} |",
            f"| CLUSTER | 多議員同標的集中交易 | {type_counts.get('CLUSTER', 0)} |",
            f"| SIZE | 交易金額偏離慣常範圍 | {type_counts.get('SIZE', 0)} |",
            f"| REVERSAL | 短期買後賣 | {type_counts.get('REVERSAL', 0)} |",
            f"",
        ])

        # 複合風險排名
        lines.extend([
            f"---",
            f"",
            f"## 議員複合異常分數排名",
            f"",
            f"| 排名 | 議員 | 複合分數 | 風險等級 |",
            f"|------|------|----------|----------|",
        ])
        for rank, (politician, score) in enumerate(composite.items(), 1):
            if score >= 20:
                risk = "CRITICAL"
            elif score >= 12:
                risk = "HIGH"
            elif score >= 6:
                risk = "MEDIUM"
            else:
                risk = "LOW"
            lines.append(f"| {rank} | {politician} | {score:.2f} | {risk} |")

        # CRITICAL 和 HIGH 異常詳情
        lines.extend([
            f"",
            f"---",
            f"",
            f"## 重大異常詳情（CRITICAL + HIGH）",
            f"",
        ])

        critical_high = [a for a in anomalies if a.severity in (Severity.CRITICAL, Severity.HIGH)]
        if not critical_high:
            lines.append("*無重大異常*")
        else:
            for i, a in enumerate(critical_high, 1):
                lines.extend([
                    f"### {i}. [{a.severity.value}] {a.anomaly_type} — {a.politician}",
                    f"- **標的**: {a.ticker or 'N/A'}",
                    f"- **分數**: {a.score:.1f}/10",
                    f"- **日期**: {a.transaction_date or 'N/A'}",
                    f"- **描述**: {a.description}",
                    f"",
                ])

        # 所有異常完整列表
        lines.extend([
            f"---",
            f"",
            f"## 完整異常列表",
            f"",
            f"| # | 類型 | 嚴重度 | 分數 | 議員 | 標的 | 描述 |",
            f"|---|------|--------|------|------|------|------|",
        ])
        for i, a in enumerate(anomalies, 1):
            desc_short = a.description[:80] + "..." if len(a.description) > 80 else a.description
            lines.append(
                f"| {i} | {a.anomaly_type} | {a.severity.value} | {a.score:.1f} | "
                f"{a.politician[:20]} | {a.ticker or 'N/A'} | {desc_short} |"
            )

        lines.extend([
            f"",
            f"---",
            f"",
            f"*報告由 AnomalyDetector 自動生成 — {today}*",
        ])

        return "\n".join(lines)
