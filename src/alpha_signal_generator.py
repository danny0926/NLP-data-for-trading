"""Alpha Signal Generator — 即時交易訊號產生模組

根據歷史回測研究結果 (5000+ 筆交易)，將 ETL Pipeline 抓取的國會交易資料
轉換為可操作的 alpha 交易訊號。

回測實證依據:
  Capitol Trades (近 12 個月, 3063 筆):
    - Buy: +0.77% CAR_5d (p<0.001***), +0.79% CAR_20d (p=0.007**)
    - Sale: 反向 alpha — 國會賣出後股價反而上漲
      CAR_5d: -0.50%, CAR_20d: -1.48%, CAR_60d: -5.49% (all p<0.001)
    - House > Senate alpha
    - $15K-$50K 金額區間 alpha 最強 (CAR_20d = +1.45%)
    - Filing lag < 15 天: +1.13% CAR_5d (p=0.003***)

  Senate Stock Watcher (2019-2020, 2282 筆):
    - 全樣本: +0.76% CAR_5d (p<0.001***)
    - Buy +0.44%, Sale +1.05% (均為正)

訊號邏輯:
  1. 基礎 alpha 估計 (transaction_type)
  2. 乘數調整 (chamber, amount, filing_lag, politician_grade)
  3. 匯聚加分 (convergence_signals)
  4. 信心度整合 (SQS + alpha 幅度 + 匯聚)
  5. 方向: Buy → LONG, Sale → LONG (反向 alpha)

用法:
    python -m src.alpha_signal_generator              # 所有交易產生訊號
    python -m src.alpha_signal_generator --top 20     # 顯示前 20 名
    python -m src.alpha_signal_generator --ticker AAPL # 篩選特定標的
    python -m src.alpha_signal_generator --days 30    # 僅最近 30 天交易

Research Brief: RB-003
"""

import argparse
import logging
import os
import re
import sqlite3
import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple

from src.config import DB_PATH

logger = logging.getLogger("AlphaSignal")

# ============================================================================
# 回測實證常數 — 來自 5000+ 筆交易的 Event Study 結果
# ============================================================================

# 基礎 alpha 估計 (%)，以 CAR_5d 為主要指標
BASE_ALPHA = {
    "Buy": {
        "5d": 0.77,    # +0.77% CAR_5d (p<0.001***)
        "20d": 0.79,   # +0.79% CAR_20d (p=0.007**)
    },
    "Sale": {
        # 反向 alpha: 國會賣出 → 股價上漲，所以我們做多
        "5d": 0.50,    # Sale CAR_5d = -0.50% (反轉後 = +0.50%)
        "20d": 1.48,   # Sale CAR_20d = -1.48% (反轉後 = +1.48%)
    },
}

# ── 乘數：院別 ──
# 回測顯示 House > Senate 在 alpha 生成上更強
CHAMBER_MULTIPLIER = {
    "House": 1.2,
    "Senate": 0.8,
}

# ── 乘數：金額區間 ──
# $15K-$50K 區間 alpha 最強 (CAR_20d = +1.45%)
AMOUNT_MULTIPLIER = {
    "$1,001 - $15,000": 1.0,
    "$15,001 - $50,000": 1.5,      # 最強 alpha
    "$50,001 - $100,000": 1.3,
    "$100,001 - $250,000": 1.2,
    "$250,001 - $500,000": 1.2,
    "$500,001 - $1,000,000": 1.2,
    "$1,000,001 - $5,000,000": 1.2,
    "$5,000,001 - $25,000,000": 1.2,
    "$25,000,001 - $50,000,000": 1.2,
    "$50,000,000+": 1.2,
    "Over $50,000,000": 1.2,
}

# ── 乘數：Filing Lag ──
# Filing lag < 15 天: +1.13% CAR_5d (p=0.003***)
FILING_LAG_MULTIPLIER = {
    "fast": 1.4,     # < 15 天
    "normal": 1.0,   # 15-44 天
    "slow": 0.5,     # >= 45 天
}

# ── 匯聚加分 ──
CONVERGENCE_BONUS_PCT = 0.5   # 同標的多議員匯聚 → 加 0.5%

# ── 議員品質乘數 ──
# PIS grade A/B → 1.3x (根據 politician_rankings 表的 pis_total)
POLITICIAN_GRADE_MULTIPLIER = {
    "A": 1.3,    # PIS >= 75
    "B": 1.3,    # PIS >= 50
    "C": 1.0,    # PIS >= 25
    "D": 0.8,    # PIS < 25
    "unknown": 1.0,  # 不在排名表中
}

# ── SEC Form 4 內部人交易匯聚 ──
# 國會交易與 SEC 內部人交易同方向 → 加分，反方向 → 扣分
INSIDER_CONVERGENCE_BONUS = 0.3    # 同方向加分
INSIDER_DIVERGENCE_PENALTY = -0.2  # 反方向扣分
INSIDER_WINDOW_DAYS = 30           # 時間窗口

# Form 4 transaction_type 分類
# P=Purchase, A/A(D)=Acquisition(grant/award), M/M(D)=Exercise
# S=Sale, F=Payment of exercise price or tax (disposition)
INSIDER_BUY_TYPES = {"P", "A", "A(D)", "M", "M(D)", "P(D)"}
INSIDER_SELL_TYPES = {"S", "F", "D"}


# ============================================================================
# 工具函式
# ============================================================================

def _parse_date(val) -> Optional[date]:
    """將日期字串轉為 date 物件。解析失敗返回 None。"""
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    if isinstance(val, datetime):
        return val.date()
    if not val:
        return None
    try:
        return datetime.strptime(str(val).strip(), "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _calc_filing_lag(transaction_date_str: str, filing_date_str: str) -> Optional[int]:
    """計算交易日到申報日的天數差。"""
    tx = _parse_date(transaction_date_str)
    fl = _parse_date(filing_date_str)
    if tx is None or fl is None:
        return None
    lag = (fl - tx).days
    return max(lag, 0)  # 負數視為 0


def _get_amount_multiplier(amount_range: str) -> float:
    """根據金額區間回傳乘數。"""
    if not amount_range:
        return 1.0

    cleaned = amount_range.strip()

    # 精確匹配
    if cleaned in AMOUNT_MULTIPLIER:
        return AMOUNT_MULTIPLIER[cleaned]

    # 模糊匹配：從金額字串提取數字，判斷所屬區間
    numbers = re.findall(r'[\d,]+', cleaned)
    if numbers:
        try:
            first_num = float(numbers[0].replace(",", ""))
        except ValueError:
            return 1.0

        if first_num >= 100_001:
            return 1.2
        elif first_num >= 50_001:
            return 1.3
        elif first_num >= 15_001:
            return 1.5
        else:
            return 1.0

    return 1.0


def _get_filing_lag_multiplier(lag_days: Optional[int]) -> float:
    """根據 filing lag 回傳乘數。"""
    if lag_days is None:
        return FILING_LAG_MULTIPLIER["normal"]
    if lag_days < 15:
        return FILING_LAG_MULTIPLIER["fast"]
    elif lag_days < 45:
        return FILING_LAG_MULTIPLIER["normal"]
    else:
        return FILING_LAG_MULTIPLIER["slow"]


def _pis_to_grade(pis_total: Optional[float]) -> str:
    """將 PIS 總分轉為等級。"""
    if pis_total is None:
        return "unknown"
    if pis_total >= 75:
        return "A"
    elif pis_total >= 50:
        return "B"
    elif pis_total >= 25:
        return "C"
    else:
        return "D"


def _normalize_direction(transaction_type: str) -> Optional[str]:
    """將 transaction_type 正規化為 Buy/Sale。"""
    if not transaction_type:
        return None
    t = transaction_type.strip()
    if t in ("Buy", "Purchase", "purchase"):
        return "Buy"
    elif t.startswith("Sale") or t in ("Sell", "sell"):
        return "Sale"
    return None


# ============================================================================
# AlphaSignalGenerator
# ============================================================================

class AlphaSignalGenerator:
    """根據回測實證結果，從國會交易資料產生 alpha 交易訊號。"""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or DB_PATH

    # ── 資料載入 ────────────────────────────────────────────────────────

    def _load_trades(
        self,
        days: Optional[int] = None,
        ticker: Optional[str] = None,
    ) -> List[dict]:
        """從 congress_trades 載入交易資料。

        Args:
            days: 僅載入最近 N 天的交易（以 filing_date 計算）
            ticker: 僅載入特定標的
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        query = """
            SELECT id, chamber, politician_name, transaction_date, filing_date,
                   ticker, asset_name, asset_type, transaction_type, amount_range,
                   owner, comment, source_url, source_format, extraction_confidence
            FROM congress_trades
            WHERE ticker IS NOT NULL AND ticker != ''
        """
        params: list = []

        if days is not None:
            cutoff = (date.today() - timedelta(days=days)).strftime("%Y-%m-%d")
            query += " AND filing_date >= ?"
            params.append(cutoff)

        if ticker is not None:
            query += " AND ticker = ?"
            params.append(ticker.upper())

        query += " ORDER BY filing_date DESC"

        cursor.execute(query, params)
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()

        logger.info(f"載入 {len(rows)} 筆有效交易（有 ticker）")
        return rows

    def _load_sqs_scores(self) -> Dict[str, dict]:
        """載入 signal_quality_scores，回傳 {trade_id: {sqs, grade, ...}}。"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        scores = {}
        try:
            cursor.execute("""
                SELECT trade_id, sqs, grade, action
                FROM signal_quality_scores
            """)
            for row in cursor.fetchall():
                scores[row["trade_id"]] = dict(row)
        except sqlite3.OperationalError:
            logger.warning("signal_quality_scores 表不存在，跳過 SQS 整合")

        conn.close()
        logger.info(f"載入 {len(scores)} 筆 SQS 評分")
        return scores

    def _load_convergence_tickers(self) -> Dict[str, dict]:
        """載入 convergence_signals，回傳 {ticker: {direction, score, ...}}。"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        convergence = {}
        try:
            cursor.execute("""
                SELECT ticker, direction, politician_count, score, politicians
                FROM convergence_signals
            """)
            for row in cursor.fetchall():
                # 若同一 ticker 有多個事件，取分數最高的
                t = row["ticker"]
                if t not in convergence or row["score"] > convergence[t]["score"]:
                    convergence[t] = dict(row)
        except sqlite3.OperationalError:
            logger.warning("convergence_signals 表不存在，跳過匯聚訊號")

        conn.close()
        logger.info(f"載入 {len(convergence)} 個匯聚標的")
        return convergence

    def _load_insider_trades(self) -> Dict[str, List[dict]]:
        """載入 sec_form4_trades，回傳 {ticker: [trades...]}。"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        insider = defaultdict(list)
        try:
            cursor.execute("""
                SELECT ticker, transaction_type, transaction_date
                FROM sec_form4_trades
                WHERE ticker IS NOT NULL AND ticker != ''
            """)
            for row in cursor.fetchall():
                insider[row["ticker"]].append(dict(row))
        except sqlite3.OperationalError:
            logger.warning("sec_form4_trades 表不存在，跳過內部人交易匯聚")

        conn.close()
        logger.info(f"載入 {sum(len(v) for v in insider.values())} 筆內部人交易（{len(insider)} 個標的）")
        return dict(insider)

    def _calc_insider_convergence(
        self,
        ticker: str,
        congress_direction: str,
        transaction_date_str: str,
        insider_trades: Dict[str, List[dict]],
    ) -> Tuple[int, float]:
        """計算 SEC 內部人交易匯聚加分/扣分。

        Args:
            ticker: 股票代號
            congress_direction: 國會交易方向 ("Buy" 或 "Sale")
            transaction_date_str: 國會交易日期
            insider_trades: {ticker: [trades...]}

        Returns:
            (overlap_count, convergence_bonus)
        """
        trades = insider_trades.get(ticker, [])
        if not trades:
            return 0, 0.0

        tx_date = _parse_date(transaction_date_str)
        if tx_date is None:
            return 0, 0.0

        # 找出時間窗口內的內部人交易
        insider_buys = 0
        insider_sells = 0
        overlap_count = 0

        for t in trades:
            insider_date = _parse_date(t.get("transaction_date"))
            if insider_date is None:
                continue

            day_diff = abs((tx_date - insider_date).days)
            if day_diff > INSIDER_WINDOW_DAYS:
                continue

            overlap_count += 1
            ins_type = t.get("transaction_type", "")
            if ins_type in INSIDER_BUY_TYPES:
                insider_buys += 1
            elif ins_type in INSIDER_SELL_TYPES:
                insider_sells += 1

        if overlap_count == 0:
            return 0, 0.0

        # 計算加分/扣分
        # 國會 Buy + 內部人 Buy（同方向）→ +0.3
        # 國會 Buy + 內部人 Sell（反方向）→ -0.2
        # 國會 Sale + 內部人 Sell（同方向，強化反向 alpha）→ +0.3
        # 國會 Sale + 內部人 Buy（反方向）→ -0.2
        if congress_direction == "Buy":
            if insider_buys > insider_sells:
                bonus = INSIDER_CONVERGENCE_BONUS
            elif insider_sells > insider_buys:
                bonus = INSIDER_DIVERGENCE_PENALTY
            else:
                bonus = 0.0  # 買賣數相等，無明確訊號
        else:
            # Sale (反向 alpha)
            if insider_sells > insider_buys:
                bonus = INSIDER_CONVERGENCE_BONUS
            elif insider_buys > insider_sells:
                bonus = INSIDER_DIVERGENCE_PENALTY
            else:
                bonus = 0.0

        return overlap_count, bonus

    def _load_politician_grades(self) -> Dict[str, str]:
        """載入 politician_rankings，回傳 {politician_name: grade}。"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        grades = {}
        try:
            cursor.execute("""
                SELECT politician_name, pis_total
                FROM politician_rankings
            """)
            for row in cursor.fetchall():
                grades[row["politician_name"]] = _pis_to_grade(row["pis_total"])
        except sqlite3.OperationalError:
            logger.warning("politician_rankings 表不存在，跳過議員品質評估")

        conn.close()
        logger.info(f"載入 {len(grades)} 位議員排名")
        return grades

    # ── 訊號計算核心 ──────────────────────────────────────────────────

    def generate_signal(
        self,
        trade: dict,
        sqs_data: Optional[dict],
        convergence_data: Optional[dict],
        politician_grade: str,
        insider_trades: Optional[Dict[str, List[dict]]] = None,
    ) -> Optional[dict]:
        """為單筆交易產生 alpha 訊號。

        Returns:
            訊號 dict 或 None（若無法產生有效訊號）
        """
        ticker = trade.get("ticker")
        tx_type = trade.get("transaction_type", "")

        # 方向正規化
        direction = _normalize_direction(tx_type)
        if direction is None:
            return None  # Exchange 或無法辨識的交易類型

        # ── Step 1: 基礎 alpha 估計 ──
        base_5d = BASE_ALPHA[direction]["5d"]
        base_20d = BASE_ALPHA[direction]["20d"]

        # ── Step 2: 計算乘數 ──
        # 院別乘數
        chamber = trade.get("chamber", "")
        chamber_mult = CHAMBER_MULTIPLIER.get(chamber, 1.0)

        # 金額乘數
        amount_range = trade.get("amount_range", "")
        amount_mult = _get_amount_multiplier(amount_range)

        # Filing lag 乘數
        filing_lag = _calc_filing_lag(
            trade.get("transaction_date"),
            trade.get("filing_date"),
        )
        lag_mult = _get_filing_lag_multiplier(filing_lag)

        # 議員品質乘數
        grade_mult = POLITICIAN_GRADE_MULTIPLIER.get(politician_grade, 1.0)

        # 綜合乘數
        combined_multiplier = chamber_mult * amount_mult * lag_mult * grade_mult

        # ── Step 3: 匯聚加分 ──
        convergence_bonus = 0.0
        has_convergence = False
        if convergence_data is not None:
            convergence_bonus = CONVERGENCE_BONUS_PCT
            has_convergence = True

        # ── Step 3b: SEC 內部人交易匯聚 ──
        insider_overlap_count = 0
        insider_convergence_bonus = 0.0
        if insider_trades is not None:
            insider_overlap_count, insider_convergence_bonus = self._calc_insider_convergence(
                ticker=ticker,
                congress_direction=direction,
                transaction_date_str=trade.get("transaction_date", ""),
                insider_trades=insider_trades,
            )

        # ── Step 4: 計算最終預期 alpha ──
        expected_alpha_5d = base_5d * combined_multiplier + convergence_bonus
        expected_alpha_20d = base_20d * combined_multiplier + convergence_bonus

        # ── Step 5: 訊號方向 ──
        # Buy → LONG (順勢), Sale → LONG (反向 alpha, 國會賣出後股價上漲)
        signal_direction = "LONG"

        # ── Step 6: 信心度計算 ──
        # 組合: SQS 評分(40%) + alpha 幅度(30%) + 匯聚加成(15%) + 資料品質(15%)
        confidence = self._calc_confidence(
            sqs_data=sqs_data,
            expected_alpha_5d=expected_alpha_5d,
            has_convergence=has_convergence,
            extraction_confidence=trade.get("extraction_confidence"),
        )

        # ── Step 7: 訊號強度（排序用）──
        # 加入 SEC 內部人匯聚調整
        signal_strength = expected_alpha_5d * confidence + insider_convergence_bonus

        # ── Step 8: 建構推理說明 ──
        reasoning = self._build_reasoning(
            trade=trade,
            direction=direction,
            base_5d=base_5d,
            chamber_mult=chamber_mult,
            amount_mult=amount_mult,
            lag_mult=lag_mult,
            grade_mult=grade_mult,
            politician_grade=politician_grade,
            filing_lag=filing_lag,
            convergence_bonus=convergence_bonus,
            has_convergence=has_convergence,
            expected_alpha_5d=expected_alpha_5d,
            expected_alpha_20d=expected_alpha_20d,
            insider_overlap_count=insider_overlap_count,
            insider_convergence_bonus=insider_convergence_bonus,
        )

        return {
            "trade_id": trade.get("id", ""),
            "ticker": ticker,
            "asset_name": trade.get("asset_name", ""),
            "politician_name": trade.get("politician_name", ""),
            "chamber": chamber,
            "transaction_type": tx_type,
            "transaction_date": trade.get("transaction_date"),
            "filing_date": trade.get("filing_date"),
            "amount_range": amount_range,
            "direction": signal_direction,
            "expected_alpha_5d": round(expected_alpha_5d, 4),
            "expected_alpha_20d": round(expected_alpha_20d, 4),
            "confidence": round(confidence, 4),
            "signal_strength": round(signal_strength, 4),
            "combined_multiplier": round(combined_multiplier, 4),
            "convergence_bonus": round(convergence_bonus, 4),
            "has_convergence": has_convergence,
            "politician_grade": politician_grade,
            "filing_lag_days": filing_lag,
            "sqs_score": sqs_data["sqs"] if sqs_data else None,
            "sqs_grade": sqs_data["grade"] if sqs_data else None,
            "insider_overlap_count": insider_overlap_count,
            "insider_convergence_bonus": round(insider_convergence_bonus, 4),
            "reasoning": reasoning,
        }

    def _calc_confidence(
        self,
        sqs_data: Optional[dict],
        expected_alpha_5d: float,
        has_convergence: bool,
        extraction_confidence: Optional[float],
    ) -> float:
        """計算訊號信心度 (0.0 ~ 1.0)。

        組成:
          - SQS 評分 (40%): 來自 signal_quality_scores
          - Alpha 幅度 (30%): 預期 alpha 越大信心越高
          - 匯聚加成 (15%): 有匯聚訊號 → 滿分
          - 資料品質 (15%): extraction_confidence

        每個維度正規化到 [0, 1]，加權合計。
        """
        # SQS 維度 (0-100 → 0-1)
        if sqs_data and sqs_data.get("sqs") is not None:
            sqs_norm = min(sqs_data["sqs"] / 100.0, 1.0)
        else:
            sqs_norm = 0.5  # 無 SQS 資料時給中間值

        # Alpha 幅度維度
        # 預期 alpha 1% → 0.5, 2% → 0.8, 3%+ → 1.0
        alpha_norm = min(expected_alpha_5d / 3.0, 1.0)
        alpha_norm = max(alpha_norm, 0.0)

        # 匯聚維度
        convergence_norm = 1.0 if has_convergence else 0.0

        # 資料品質維度
        if extraction_confidence is not None:
            try:
                quality_norm = float(extraction_confidence)
            except (ValueError, TypeError):
                quality_norm = 0.5
        else:
            quality_norm = 0.5

        # 加權合計
        confidence = (
            0.40 * sqs_norm
            + 0.30 * alpha_norm
            + 0.15 * convergence_norm
            + 0.15 * quality_norm
        )

        return max(0.0, min(confidence, 1.0))

    def _build_reasoning(
        self,
        trade: dict,
        direction: str,
        base_5d: float,
        chamber_mult: float,
        amount_mult: float,
        lag_mult: float,
        grade_mult: float,
        politician_grade: str,
        filing_lag: Optional[int],
        convergence_bonus: float,
        has_convergence: bool,
        expected_alpha_5d: float,
        expected_alpha_20d: float,
        insider_overlap_count: int = 0,
        insider_convergence_bonus: float = 0.0,
    ) -> str:
        """建構人類可讀的訊號推理說明。"""
        parts = []

        # 基礎邏輯
        if direction == "Buy":
            parts.append(
                f"國會議員買入 → 順勢做多 (基礎 alpha +{base_5d:.2f}%)"
            )
        else:
            parts.append(
                f"國會議員賣出 → 反向做多 (回測顯示賣出後股價上漲, "
                f"基礎 alpha +{base_5d:.2f}%)"
            )

        # 乘數說明
        chamber = trade.get("chamber", "")
        parts.append(
            f"院別={chamber} ({chamber_mult:.1f}x), "
            f"金額={trade.get('amount_range', 'N/A')} ({amount_mult:.1f}x), "
            f"Filing lag={filing_lag if filing_lag is not None else 'N/A'}天 ({lag_mult:.1f}x), "
            f"議員等級={politician_grade} ({grade_mult:.1f}x)"
        )

        # 匯聚
        if has_convergence:
            parts.append(
                f"匯聚訊號加成 +{convergence_bonus:.2f}% (多位議員同標的)"
            )

        # SEC 內部人交易匯聚
        if insider_overlap_count > 0:
            if insider_convergence_bonus > 0:
                parts.append(
                    f"SEC 內部人匯聚 +{insider_convergence_bonus:+.2f} "
                    f"(同方向, {insider_overlap_count} 筆重合)"
                )
            elif insider_convergence_bonus < 0:
                parts.append(
                    f"SEC 內部人背離 {insider_convergence_bonus:+.2f} "
                    f"(反方向, {insider_overlap_count} 筆重合)"
                )

        # 結論
        parts.append(
            f"預期 alpha: 5d={expected_alpha_5d:+.2f}%, "
            f"20d={expected_alpha_20d:+.2f}%"
        )

        return " | ".join(parts)

    # ── 批量生成 ──────────────────────────────────────────────────────

    def generate_all(
        self,
        days: Optional[int] = None,
        ticker: Optional[str] = None,
        top_n: Optional[int] = None,
    ) -> List[dict]:
        """批量生成所有交易的 alpha 訊號。

        Args:
            days: 僅處理最近 N 天交易
            ticker: 僅處理特定標的
            top_n: 僅回傳前 N 名（按 signal_strength 排序）

        Returns:
            alpha 訊號列表，按 signal_strength 降序
        """
        # 載入所有相關資料
        trades = self._load_trades(days=days, ticker=ticker)
        sqs_scores = self._load_sqs_scores()
        convergence = self._load_convergence_tickers()
        politician_grades = self._load_politician_grades()
        insider_trades = self._load_insider_trades()

        if not trades:
            logger.warning("無可用交易資料，無法生成訊號")
            return []

        # 逐筆生成訊號
        signals = []
        skipped = 0

        for trade in trades:
            trade_id = trade.get("id", "")
            ticker_val = trade.get("ticker")
            politician = trade.get("politician_name", "")

            # 查詢關聯資料
            sqs_data = sqs_scores.get(trade_id)
            convergence_data = convergence.get(ticker_val)
            grade = politician_grades.get(politician, "unknown")

            signal = self.generate_signal(
                trade=trade,
                sqs_data=sqs_data,
                convergence_data=convergence_data,
                politician_grade=grade,
                insider_trades=insider_trades,
            )

            if signal is not None:
                signals.append(signal)
            else:
                skipped += 1

        # 按 signal_strength 降序排序
        signals.sort(key=lambda s: s["signal_strength"], reverse=True)

        logger.info(
            f"生成 {len(signals)} 個訊號 (跳過 {skipped} 筆無法辨識方向的交易)"
        )

        if top_n is not None:
            return signals[:top_n]
        return signals

    # ── 資料庫寫入 ────────────────────────────────────────────────────

    def save_signals(self, signals: List[dict]) -> dict:
        """將訊號寫入 alpha_signals 資料表。

        Returns:
            {"inserted": int, "updated": int}
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 建表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alpha_signals (
                id TEXT PRIMARY KEY,
                trade_id TEXT NOT NULL,
                ticker TEXT NOT NULL,
                asset_name TEXT,
                politician_name TEXT,
                chamber TEXT,
                transaction_type TEXT,
                transaction_date DATE,
                filing_date DATE,
                amount_range TEXT,
                direction TEXT NOT NULL,
                expected_alpha_5d REAL NOT NULL,
                expected_alpha_20d REAL NOT NULL,
                confidence REAL NOT NULL,
                signal_strength REAL NOT NULL,
                combined_multiplier REAL,
                convergence_bonus REAL,
                has_convergence BOOLEAN,
                politician_grade TEXT,
                filing_lag_days INTEGER,
                sqs_score REAL,
                sqs_grade TEXT,
                insider_overlap_count INTEGER DEFAULT 0,
                insider_convergence_bonus REAL DEFAULT 0.0,
                reasoning TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(trade_id)
            )
        """)

        # 若表已存在但缺少新欄位，動態新增
        existing_cols = {
            row[1] for row in cursor.execute("PRAGMA table_info(alpha_signals)").fetchall()
        }
        if "insider_overlap_count" not in existing_cols:
            cursor.execute("ALTER TABLE alpha_signals ADD COLUMN insider_overlap_count INTEGER DEFAULT 0")
            logger.info("已新增 insider_overlap_count 欄位")
        if "insider_convergence_bonus" not in existing_cols:
            cursor.execute("ALTER TABLE alpha_signals ADD COLUMN insider_convergence_bonus REAL DEFAULT 0.0")
            logger.info("已新增 insider_convergence_bonus 欄位")

        inserted = 0
        updated = 0

        for signal in signals:
            signal_id = str(uuid.uuid4())
            try:
                cursor.execute("""
                    INSERT INTO alpha_signals (
                        id, trade_id, ticker, asset_name, politician_name,
                        chamber, transaction_type, transaction_date, filing_date,
                        amount_range, direction, expected_alpha_5d, expected_alpha_20d,
                        confidence, signal_strength, combined_multiplier,
                        convergence_bonus, has_convergence, politician_grade,
                        filing_lag_days, sqs_score, sqs_grade,
                        insider_overlap_count, insider_convergence_bonus, reasoning
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    signal_id,
                    signal["trade_id"],
                    signal["ticker"],
                    signal["asset_name"],
                    signal["politician_name"],
                    signal["chamber"],
                    signal["transaction_type"],
                    signal["transaction_date"],
                    signal["filing_date"],
                    signal["amount_range"],
                    signal["direction"],
                    signal["expected_alpha_5d"],
                    signal["expected_alpha_20d"],
                    signal["confidence"],
                    signal["signal_strength"],
                    signal["combined_multiplier"],
                    signal["convergence_bonus"],
                    1 if signal["has_convergence"] else 0,
                    signal["politician_grade"],
                    signal["filing_lag_days"],
                    signal["sqs_score"],
                    signal["sqs_grade"],
                    signal.get("insider_overlap_count", 0),
                    signal.get("insider_convergence_bonus", 0.0),
                    signal["reasoning"],
                ))
                inserted += 1
            except sqlite3.IntegrityError:
                # trade_id 已存在，更新
                cursor.execute("""
                    UPDATE alpha_signals
                    SET ticker = ?, direction = ?,
                        expected_alpha_5d = ?, expected_alpha_20d = ?,
                        confidence = ?, signal_strength = ?,
                        combined_multiplier = ?, convergence_bonus = ?,
                        has_convergence = ?, politician_grade = ?,
                        filing_lag_days = ?, sqs_score = ?, sqs_grade = ?,
                        insider_overlap_count = ?, insider_convergence_bonus = ?,
                        reasoning = ?, created_at = CURRENT_TIMESTAMP
                    WHERE trade_id = ?
                """, (
                    signal["ticker"],
                    signal["direction"],
                    signal["expected_alpha_5d"],
                    signal["expected_alpha_20d"],
                    signal["confidence"],
                    signal["signal_strength"],
                    signal["combined_multiplier"],
                    signal["convergence_bonus"],
                    1 if signal["has_convergence"] else 0,
                    signal["politician_grade"],
                    signal["filing_lag_days"],
                    signal["sqs_score"],
                    signal["sqs_grade"],
                    signal.get("insider_overlap_count", 0),
                    signal.get("insider_convergence_bonus", 0.0),
                    signal["reasoning"],
                    signal["trade_id"],
                ))
                updated += 1

        conn.commit()
        conn.close()

        logger.info(f"訊號寫入完成: 新增 {inserted}, 更新 {updated}")
        return {"inserted": inserted, "updated": updated}

    # ── 報告生成 ──────────────────────────────────────────────────────

    def generate_report(
        self, signals: List[dict], output_path: str
    ) -> str:
        """生成 Markdown 報告並寫入檔案。

        Args:
            signals: alpha 訊號列表（已按 signal_strength 排序）
            output_path: 輸出檔案路徑

        Returns:
            報告內容字串
        """
        now = datetime.now()
        today_str = now.strftime("%Y-%m-%d")

        lines = []
        lines.append(f"# Alpha Trading Signals Report")
        lines.append(f"**Generated**: {now.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"**Total Signals**: {len(signals)}")
        lines.append("")

        # ── 方法論摘要 ──
        lines.append("## Methodology")
        lines.append("")
        lines.append("基於 5000+ 筆國會交易的 Event Study 回測結果，應用以下模型：")
        lines.append("")
        lines.append("| 參數 | 設定 |")
        lines.append("|------|------|")
        lines.append("| Buy 基礎 alpha | +0.77% (5d), +0.79% (20d) |")
        lines.append("| Sale 基礎 alpha (反向) | +0.50% (5d), +1.48% (20d) |")
        lines.append("| 院別乘數 | House 1.2x, Senate 0.8x |")
        lines.append("| 最佳金額區間 | $15K-$50K (1.5x) |")
        lines.append("| Filing lag < 15 天 | 1.4x 乘數 |")
        lines.append("| 匯聚加成 | +0.5% (多議員同標的) |")
        lines.append("| 議員品質 A/B 等級 | 1.3x 乘數 |")
        lines.append("")

        # ── 統計摘要 ──
        if signals:
            buy_signals = [s for s in signals if s["transaction_type"] == "Buy"]
            sale_signals = [s for s in signals
                           if s["transaction_type"] != "Buy"]
            conv_signals = [s for s in signals if s["has_convergence"]]

            avg_alpha = sum(s["expected_alpha_5d"] for s in signals) / len(signals)
            avg_conf = sum(s["confidence"] for s in signals) / len(signals)

            lines.append("## Summary Statistics")
            lines.append("")
            lines.append(f"| 指標 | 數值 |")
            lines.append(f"|------|------|")
            lines.append(f"| Buy 訊號 | {len(buy_signals)} |")
            lines.append(f"| Sale 訊號 (反向做多) | {len(sale_signals)} |")
            lines.append(f"| 匯聚訊號 | {len(conv_signals)} |")
            lines.append(f"| 平均預期 alpha (5d) | {avg_alpha:+.2f}% |")
            lines.append(f"| 平均信心度 | {avg_conf:.2f} |")
            lines.append("")

            # 標的分布
            ticker_counts = defaultdict(int)
            for s in signals:
                ticker_counts[s["ticker"]] += 1
            top_tickers = sorted(
                ticker_counts.items(), key=lambda x: x[1], reverse=True
            )[:10]

            lines.append("### Top 標的 (出現頻率)")
            lines.append("")
            lines.append("| Ticker | 訊號數 |")
            lines.append("|--------|--------|")
            for t, cnt in top_tickers:
                lines.append(f"| {t} | {cnt} |")
            lines.append("")

        # ── Top Signals ──
        top_n = min(30, len(signals))
        if top_n > 0:
            lines.append(f"## Top {top_n} Alpha Signals")
            lines.append("")
            lines.append(
                "| # | Ticker | Direction | Alpha(5d) | Alpha(20d) | "
                "Confidence | Strength | Politician | Chamber | Filing Lag | "
                "Grade | Convergence |"
            )
            lines.append(
                "|---|--------|-----------|-----------|------------|"
                "------------|----------|------------|---------|-----------|"
                "-------|-------------|"
            )

            for i, s in enumerate(signals[:top_n], start=1):
                lag_str = (
                    f"{s['filing_lag_days']}天"
                    if s["filing_lag_days"] is not None
                    else "N/A"
                )
                conv_str = "Y" if s["has_convergence"] else ""
                name = s["politician_name"]
                if len(name) > 20:
                    name = name[:18] + ".."

                lines.append(
                    f"| {i} | **{s['ticker']}** | {s['direction']} | "
                    f"{s['expected_alpha_5d']:+.2f}% | "
                    f"{s['expected_alpha_20d']:+.2f}% | "
                    f"{s['confidence']:.2f} | {s['signal_strength']:.3f} | "
                    f"{name} | {s['chamber']} | {lag_str} | "
                    f"{s['politician_grade']} | {conv_str} |"
                )

            lines.append("")

        # ── 免責聲明 ──
        lines.append("## Disclaimer")
        lines.append("")
        lines.append(
            "本報告基於歷史統計模型生成，不構成投資建議。"
            "過去的統計顯著性不保證未來表現。"
            "國會交易資訊具有資訊延遲(filing lag)風險。"
        )
        lines.append("")
        lines.append("---")
        lines.append(
            f"*Generated by Political Alpha Monitor — "
            f"Alpha Signal Generator v1.0 — {now.strftime('%Y-%m-%d %H:%M')}*"
        )
        lines.append("")

        report_content = "\n".join(lines)

        # 寫入檔案
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(report_content)

        logger.info(f"報告已生成: {output_path}")
        return report_content


# ============================================================================
# 終端摘要輸出
# ============================================================================

def print_signal_summary(signals: List[dict], top_n: int = 10):
    """在終端印出 alpha 訊號摘要。"""
    if not signals:
        print("\n  [無資料] 沒有生成任何 alpha 訊號。\n")
        return

    total = len(signals)
    buy_count = sum(1 for s in signals if s["transaction_type"] == "Buy")
    sale_count = total - buy_count
    conv_count = sum(1 for s in signals if s["has_convergence"])
    avg_alpha = sum(s["expected_alpha_5d"] for s in signals) / total
    avg_conf = sum(s["confidence"] for s in signals) / total

    # SEC 內部人匯聚統計
    insider_boosted = sum(
        1 for s in signals if s.get("insider_convergence_bonus", 0) > 0
    )
    insider_penalized = sum(
        1 for s in signals if s.get("insider_convergence_bonus", 0) < 0
    )
    insider_overlap_total = sum(
        1 for s in signals if s.get("insider_overlap_count", 0) > 0
    )

    print()
    print("=" * 100)
    print("  Alpha Trading Signals — 國會交易 Alpha 訊號產生器")
    print("=" * 100)
    print(f"  總訊號數: {total}")
    print(f"  Buy 訊號: {buy_count}  |  Sale 反向訊號: {sale_count}")
    print(f"  匯聚訊號: {conv_count}")
    print(f"  SEC 內部人重合: {insider_overlap_total} (加分: {insider_boosted}, 扣分: {insider_penalized})")
    print(f"  平均預期 alpha (5d): {avg_alpha:+.3f}%")
    print(f"  平均信心度: {avg_conf:.3f}")
    print()

    # ── Top N 訊號 ──
    display_n = min(top_n, total)
    print(f"  Top {display_n} Signals (按 signal_strength 排序):")
    print()
    header = (
        f"  {'#':>3}  "
        f"{'Ticker':<8}  "
        f"{'Dir':<5}  "
        f"{'Alpha5d':>8}  "
        f"{'Alpha20d':>9}  "
        f"{'Conf':>6}  "
        f"{'Str':>7}  "
        f"{'Politician':<22}  "
        f"{'Ch':<6}  "
        f"{'Lag':>5}  "
        f"{'Grd':<4}  "
        f"{'Conv':<4}"
    )
    print(header)
    print(f"  {'-' * 96}")

    for i, s in enumerate(signals[:display_n], start=1):
        lag_str = (
            f"{s['filing_lag_days']}d"
            if s["filing_lag_days"] is not None
            else "N/A"
        )
        conv_str = "Y" if s["has_convergence"] else ""
        name = s["politician_name"]
        if len(name) > 20:
            name = name[:18] + ".."

        print(
            f"  {i:>3}  "
            f"{s['ticker']:<8}  "
            f"{s['direction']:<5}  "
            f"{s['expected_alpha_5d']:>+7.2f}%  "
            f"{s['expected_alpha_20d']:>+8.2f}%  "
            f"{s['confidence']:>6.3f}  "
            f"{s['signal_strength']:>7.3f}  "
            f"{name:<22}  "
            f"{s['chamber']:<6}  "
            f"{lag_str:>5}  "
            f"{s['politician_grade']:<4}  "
            f"{conv_str:<4}"
        )

    print()

    # ── 乘數分布統計 ──
    print(f"  乘數分布統計:")
    mults = [s["combined_multiplier"] for s in signals]
    print(
        f"    綜合乘數: 最小={min(mults):.2f}, "
        f"最大={max(mults):.2f}, "
        f"平均={sum(mults)/len(mults):.2f}"
    )

    # 按議員等級統計
    grade_dist = defaultdict(int)
    for s in signals:
        grade_dist[s["politician_grade"]] += 1
    grade_parts = [
        f"{g}: {c}" for g, c in sorted(grade_dist.items())
    ]
    print(f"    議員等級分布: {', '.join(grade_parts)}")

    print()
    print("=" * 100)


# ============================================================================
# CLI 入口
# ============================================================================

def main():
    """CLI 入口: 產生 alpha 交易訊號。"""
    parser = argparse.ArgumentParser(
        description="Alpha Signal Generator — 國會交易 Alpha 訊號產生器"
    )
    parser.add_argument(
        "--top", type=int, default=None,
        help="顯示前 N 名訊號（預設: 全部）"
    )
    parser.add_argument(
        "--ticker", type=str, default=None,
        help="篩選特定標的 (例: AAPL)"
    )
    parser.add_argument(
        "--days", type=int, default=None,
        help="僅處理最近 N 天的交易（以 filing_date 計算）"
    )
    parser.add_argument(
        "--db", type=str, default=None,
        help="指定資料庫路徑（預設: data/data.db）"
    )
    parser.add_argument(
        "--no-save", action="store_true",
        help="不寫入資料庫"
    )
    parser.add_argument(
        "--no-report", action="store_true",
        help="不生成 Markdown 報告"
    )
    args = parser.parse_args()

    # 設定日誌
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    print("Alpha Signal Generator — 國會交易 Alpha 訊號產生器")
    print(f"資料庫: {args.db or DB_PATH}")
    if args.days:
        print(f"時間範圍: 最近 {args.days} 天")
    if args.ticker:
        print(f"標的篩選: {args.ticker}")

    # 產生訊號
    generator = AlphaSignalGenerator(db_path=args.db)
    signals = generator.generate_all(
        days=args.days,
        ticker=args.ticker,
    )

    if not signals:
        print("\n  沒有生成任何 alpha 訊號。請確認 congress_trades 表中有資料。")
        return

    # 終端輸出
    display_top = args.top if args.top else 10
    print_signal_summary(signals, top_n=display_top)

    # 寫入資料庫
    if not args.no_save:
        result = generator.save_signals(signals)
        print(f"  DB 寫入結果: 新增 {result['inserted']}, 更新 {result['updated']}")
        print(f"  訊號已存入 alpha_signals 表")

    # 生成報告
    if not args.no_report:
        today_str = date.today().strftime("%Y-%m-%d")
        report_path = os.path.join(
            "docs", "reports", f"Alpha_Signals_{today_str}.md"
        )

        # 報告中包含 top 限制或全部
        report_signals = signals[:args.top] if args.top else signals
        generator.generate_report(report_signals, report_path)
        print(f"\n  報告已生成: {report_path}")


if __name__ == "__main__":
    main()
