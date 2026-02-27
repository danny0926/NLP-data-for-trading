"""Signal Quality Score (SQS) 評分模組 — Political Alpha Monitor

五維度加權評分系統，將國會交易資料轉換為可操作的投資訊號等級。

SQS = w1*A + w2*T + w3*C + w4*I + w5*M
  A = Actionability  (可操作性)  w1 = 0.30
  T = Timeliness     (時效性)    w2 = 0.20
  C = Conviction     (確信度)    w3 = 0.25
  I = Information Edge(資訊優勢) w4 = 0.15
  M = Market Impact  (市場影響)  w5 = 0.10

品質等級:
  Platinum (80-100) → 自動信號, MOO
  Gold     (60-79)  → 信號, MOC
  Silver   (40-59)  → 觀察清單
  Bronze   (20-39)  → 人工審閱
  Discard  (0-19)   → 淘汰

Research Brief: RB-001
"""

import logging
import re
import sqlite3
from collections import Counter
from datetime import date, datetime
from typing import Dict, List, Optional, Tuple

from src.config import DB_PATH
from src.targets import CONGRESS_TARGETS, get_target_by_name

logger = logging.getLogger("SQS.Scorer")

# ============================================================================
# 常數
# ============================================================================

# SQS 權重
WEIGHTS = {
    "actionability": 0.30,
    "timeliness": 0.20,
    "conviction": 0.25,
    "information_edge": 0.15,
    "market_impact": 0.10,
}

# 品質等級定義（下限含、上限不含，最高等級上限為 inf）
GRADE_THRESHOLDS: List[Tuple[str, float, float, str]] = [
    # (等級名稱, 下限(含), 上限(不含), 行動建議)
    ("Platinum", 80, float("inf"), "自動信號，MOO"),
    ("Gold",     60,  80, "信號，MOC"),
    ("Silver",   40,  60, "觀察清單"),
    ("Bronze",   20,  40, "人工審閱"),
    ("Discard",   0,  20, "淘汰"),
]

# 金額區間 → 代表金額（用於 Conviction 評分）
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


# ============================================================================
# SignalScorer
# ============================================================================

class SignalScorer:
    """五維度 Signal Quality Score 評分器"""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or DB_PATH

    # ── 主要 API ────────────────────────────────────────────────────────

    def score_signal(self, trade_data: dict) -> dict:
        """計算單筆交易的 SQS 及各維度分數。

        Args:
            trade_data: 來自 congress_trades 表的交易 dict

        Returns:
            {
                "sqs": float,
                "grade": str,
                "action": str,
                "dimensions": {
                    "actionability": float,
                    "timeliness": float,
                    "conviction": float,
                    "information_edge": float,
                    "market_impact": float,
                },
                "trade_id": str,
                "politician_name": str,
                "ticker": str,
            }
        """
        a = self._calc_actionability(trade_data)
        t = self._calc_timeliness(trade_data)
        c = self._calc_conviction(trade_data)
        i = self._calc_information_edge(trade_data)
        m = self._calc_market_impact(trade_data)

        sqs = (
            WEIGHTS["actionability"] * a
            + WEIGHTS["timeliness"] * t
            + WEIGHTS["conviction"] * c
            + WEIGHTS["information_edge"] * i
            + WEIGHTS["market_impact"] * m
        )
        sqs = round(sqs, 2)

        grade, action = self.classify_signal(sqs)

        return {
            "sqs": sqs,
            "grade": grade,
            "action": action,
            "dimensions": {
                "actionability": a,
                "timeliness": t,
                "conviction": c,
                "information_edge": i,
                "market_impact": m,
            },
            "trade_id": trade_data.get("id", ""),
            "politician_name": trade_data.get("politician_name", ""),
            "ticker": trade_data.get("ticker"),
        }

    def classify_signal(self, sqs: float) -> Tuple[str, str]:
        """根據 SQS 分數返回等級名稱和行動建議。"""
        for grade_name, lo, hi, action in GRADE_THRESHOLDS:
            if lo <= sqs < hi:
                return grade_name, action
        return "Discard", "淘汰"

    def score_all_signals(self, db_path: Optional[str] = None) -> List[dict]:
        """批量評分所有 congress_trades 交易。

        Returns:
            評分結果列表，每個元素為 score_signal() 的回傳值
        """
        target_db = db_path or self.db_path
        conn = sqlite3.connect(target_db)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, chamber, politician_name, transaction_date, filing_date,
                   ticker, asset_name, asset_type, transaction_type, amount_range,
                   owner, comment, source_url, source_format, extraction_confidence
            FROM congress_trades
        """)
        rows = cursor.fetchall()

        # 預先查詢同方向交易，供 Conviction 使用
        cursor.execute("""
            SELECT politician_name, ticker, transaction_type, COUNT(*) as cnt
            FROM congress_trades
            WHERE ticker IS NOT NULL
            GROUP BY politician_name, ticker, transaction_type
            HAVING cnt > 1
        """)
        multi_trades = {}
        for row in cursor.fetchall():
            key = (row[0], row[1], row[2])
            multi_trades[key] = row[3]

        conn.close()

        results = []
        for row in rows:
            trade_data = dict(row)
            # 注入多筆同方向資訊
            key = (
                trade_data.get("politician_name"),
                trade_data.get("ticker"),
                trade_data.get("transaction_type"),
            )
            trade_data["_multi_same_direction"] = multi_trades.get(key, 0)
            results.append(self.score_signal(trade_data))

        return results

    def save_scores(self, scores: List[dict], db_path: Optional[str] = None):
        """將評分結果寫入 signal_quality_scores 表。"""
        target_db = db_path or self.db_path
        conn = sqlite3.connect(target_db)
        cursor = conn.cursor()

        # 建表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS signal_quality_scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_id TEXT NOT NULL,
                politician_name TEXT,
                ticker TEXT,
                sqs REAL NOT NULL,
                grade TEXT NOT NULL,
                action TEXT,
                actionability REAL,
                timeliness REAL,
                conviction REAL,
                information_edge REAL,
                market_impact REAL,
                scored_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(trade_id)
            )
        """)

        inserted = 0
        updated = 0
        for s in scores:
            try:
                cursor.execute("""
                    INSERT INTO signal_quality_scores
                        (trade_id, politician_name, ticker, sqs, grade, action,
                         actionability, timeliness, conviction, information_edge,
                         market_impact)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    s["trade_id"],
                    s["politician_name"],
                    s["ticker"],
                    s["sqs"],
                    s["grade"],
                    s["action"],
                    s["dimensions"]["actionability"],
                    s["dimensions"]["timeliness"],
                    s["dimensions"]["conviction"],
                    s["dimensions"]["information_edge"],
                    s["dimensions"]["market_impact"],
                ))
                inserted += 1
            except sqlite3.IntegrityError:
                # trade_id 已存在，更新
                cursor.execute("""
                    UPDATE signal_quality_scores
                    SET sqs = ?, grade = ?, action = ?,
                        actionability = ?, timeliness = ?, conviction = ?,
                        information_edge = ?, market_impact = ?,
                        scored_at = CURRENT_TIMESTAMP
                    WHERE trade_id = ?
                """, (
                    s["sqs"],
                    s["grade"],
                    s["action"],
                    s["dimensions"]["actionability"],
                    s["dimensions"]["timeliness"],
                    s["dimensions"]["conviction"],
                    s["dimensions"]["information_edge"],
                    s["dimensions"]["market_impact"],
                    s["trade_id"],
                ))
                updated += 1

        conn.commit()
        conn.close()
        logger.info(f"評分結果已寫入: 新增 {inserted}, 更新 {updated}")
        return {"inserted": inserted, "updated": updated}

    # ── 維度計算 ────────────────────────────────────────────────────────

    def _calc_actionability(self, trade: dict) -> float:
        """A - 可操作性 (0-100)

        有 Ticker + Buy/Sale 方向 = 100
        有 Ticker 但方向模糊 = 70
        有 Sector 但無 Ticker = 30
        僅文字描述 = 0
        """
        ticker = trade.get("ticker")
        tx_type = (trade.get("transaction_type") or "").strip()

        has_ticker = ticker is not None and ticker.strip() != ""
        has_direction = tx_type in ("Buy", "Sale", "Exchange")

        if has_ticker and has_direction:
            return 100.0
        if has_ticker:
            return 70.0

        # 檢查 asset_name 是否暗示特定產業 (sector)
        asset_name = (trade.get("asset_name") or "").lower()
        sector_keywords = [
            "tech", "energy", "health", "biotech", "pharma", "defense",
            "financial", "bank", "oil", "semiconductor", "etf", "fund",
        ]
        if any(kw in asset_name for kw in sector_keywords):
            return 30.0

        return 0.0

    def _calc_timeliness(self, trade: dict) -> float:
        """T - 時效性 (0-100)

        根據 filing_date 與 transaction_date 的差距（filing lag）。
        <= 7 天 = 100, 8-15 = 75, 16-30 = 50, 31-45 = 25, > 45 = 0
        """
        tx_date_str = trade.get("transaction_date")
        filing_date_str = trade.get("filing_date")

        if not tx_date_str or not filing_date_str:
            return 25.0  # 缺少日期，給保守分數

        try:
            tx_date = self._parse_date(tx_date_str)
            filing_date = self._parse_date(filing_date_str)
        except (ValueError, TypeError):
            return 25.0

        lag_days = (filing_date - tx_date).days
        if lag_days < 0:
            lag_days = 0  # 可能是資料順序問題

        if lag_days <= 7:
            return 100.0
        elif lag_days <= 15:
            return 75.0
        elif lag_days <= 30:
            return 50.0
        elif lag_days <= 45:
            return 25.0
        else:
            return 0.0

    def _calc_conviction(self, trade: dict) -> float:
        """C - 確信度 (0-100)

        組成:
        - 金額分: >$250K(+40), $50K-$250K(+25), $15K-$50K(+15), <$15K(+5)
        - Owner: Self(+20), Joint/Spouse(+10), Child/Other(+5)
        - 多筆同方向(+20)
        - confidence >= 0.9(+20)
        """
        score = 0.0

        # 金額分
        amount_val = self._parse_amount(trade.get("amount_range", ""))
        if amount_val > 250_000:
            score += 40
        elif amount_val > 50_000:
            score += 25
        elif amount_val > 15_000:
            score += 15
        else:
            score += 5

        # Owner 分
        owner = (trade.get("owner") or "").lower().strip()
        if owner in ("self",):
            score += 20
        elif owner in ("joint", "spouse"):
            score += 10
        elif owner:
            score += 5

        # 多筆同方向
        multi_count = trade.get("_multi_same_direction", 0)
        if multi_count > 1:
            score += 20

        # extraction_confidence
        confidence = trade.get("extraction_confidence")
        if confidence is not None:
            try:
                if float(confidence) >= 0.9:
                    score += 20
            except (ValueError, TypeError):
                pass

        return min(score, 100.0)

    def _calc_information_edge(self, trade: dict) -> float:
        """I - 資訊優勢 (0-100)

        根據 targets.py 中的 note 欄位判斷:
        - 「主席」或「chair」= 100
        - 「委員會」或「committee」= 70
        - 有產業背景描述 = 50
        - 其他 = 20
        """
        politician_name = trade.get("politician_name", "")
        target = get_target_by_name(politician_name)

        if target is None:
            return 20.0

        note = (target.get("note") or "").lower()

        # 主席
        if "主席" in note or "chair" in note:
            return 100.0
        # 委員會成員
        if "委員會" in note or "committee" in note:
            return 70.0
        # 產業背景相關關鍵字
        industry_keywords = [
            "對沖基金", "hedge fund", "金融背景", "前議長",
            "科技", "國防", "能源",
        ]
        if any(kw in note for kw in industry_keywords):
            return 50.0

        return 20.0

    def _calc_market_impact(self, trade: dict) -> float:
        """M - 市場影響潛力 (0-100)

        暫用固定值 50（後續迭代可加入 yfinance 市值數據）。
        """
        return 50.0

    # ── 工具函式 ────────────────────────────────────────────────────────

    @staticmethod
    def _parse_date(val) -> date:
        """將日期字串或 date 物件轉為 date。"""
        if isinstance(val, date):
            return val
        if isinstance(val, datetime):
            return val.date()
        return datetime.strptime(str(val).strip(), "%Y-%m-%d").date()

    @staticmethod
    def _parse_amount(amount_str: str) -> float:
        """解析金額區間字串，返回代表金額。

        先查表，查不到就從字串中提取數字取平均。
        """
        if not amount_str:
            return 0.0

        amount_str = amount_str.strip()

        # 先精確匹配
        if amount_str in AMOUNT_RANGES:
            return float(AMOUNT_RANGES[amount_str])

        # 模糊匹配：提取所有數字
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


# ============================================================================
# 統計報告
# ============================================================================

def print_summary(scores: List[dict]):
    """輸出 SQS 評分統計摘要。"""
    if not scores:
        print("  (無資料)")
        return

    total = len(scores)
    avg_sqs = sum(s["sqs"] for s in scores) / total

    grade_counts = Counter(s["grade"] for s in scores)
    grade_avg = {}
    for grade_name, _, _, _ in GRADE_THRESHOLDS:
        grade_scores = [s["sqs"] for s in scores if s["grade"] == grade_name]
        grade_avg[grade_name] = (
            sum(grade_scores) / len(grade_scores) if grade_scores else 0
        )

    print(f"\n{'='*60}")
    print(f"  Signal Quality Score (SQS) 評分報告")
    print(f"{'='*60}")
    print(f"  總交易筆數: {total}")
    print(f"  整體平均 SQS: {avg_sqs:.1f}")
    print()
    print(f"  {'等級':<12} {'筆數':>6} {'佔比':>8} {'平均 SQS':>10}")
    print(f"  {'-'*40}")
    for grade_name, lo, hi, action in GRADE_THRESHOLDS:
        count = grade_counts.get(grade_name, 0)
        pct = count / total * 100 if total > 0 else 0
        avg = grade_avg.get(grade_name, 0)
        print(f"  {grade_name:<12} {count:>6} {pct:>7.1f}% {avg:>10.1f}")

    print()

    # 顯示 Top 10 最高分
    top10 = sorted(scores, key=lambda s: s["sqs"], reverse=True)[:10]
    print(f"  Top 10 最高分交易:")
    print(f"  {'SQS':>6} {'等級':<10} {'議員':<22} {'Ticker':<8} {'A':>4} {'T':>4} {'C':>4} {'I':>4} {'M':>4}")
    print(f"  {'-'*70}")
    for s in top10:
        d = s["dimensions"]
        ticker = s.get("ticker") or "--"
        name = s["politician_name"][:20]
        print(
            f"  {s['sqs']:>6.1f} {s['grade']:<10} {name:<22} {ticker:<8}"
            f" {d['actionability']:>4.0f} {d['timeliness']:>4.0f}"
            f" {d['conviction']:>4.0f} {d['information_edge']:>4.0f}"
            f" {d['market_impact']:>4.0f}"
        )

    print(f"\n{'='*60}")


# ============================================================================
# CLI 入口
# ============================================================================

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    print("Signal Quality Score (SQS) 評分系統")
    print(f"資料庫: {DB_PATH}")

    scorer = SignalScorer()

    # 批量評分
    scores = scorer.score_all_signals()
    if not scores:
        print("\n  congress_trades 表中無資料，無法評分。")
    else:
        # 輸出統計
        print_summary(scores)

        # 寫入 DB
        result = scorer.save_scores(scores)
        print(f"\n  DB 寫入結果: 新增 {result['inserted']}, 更新 {result['updated']}")
        print(f"  評分結果已存入 signal_quality_scores 表")
