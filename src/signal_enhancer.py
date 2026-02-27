"""Signal Enhancer v2 — 基於回測實證的信號增強模組

將 RB-001~RB-007 的研究發現整合進信號評分系統:
  1. VIX 體制偵測: VIX 14-16 黃金區間加乘, <14 或 >16 降權 (RB-004)
  2. PACS 多信號融合: 50% signal_strength + 25% filing_lag_inv + 15% options_sentiment + 10% convergence (RB-006)
  3. SQS 權重修正: SQS 負相關問題修正 — actionability 優先 (RB-006)
  4. Buy-Only 模式: Buy +1.10% vs Sale -3.21% CAR_20d (RB-004)
  5. 社群媒體情緒整合: social_signals 表的 sentiment 加權 (新模組)

研究實證依據:
  RB-004: VIX 15-16 最佳 (+1.03% CAR_20d, 63.2% WR), VIX<14 -2.94%, VIX>16 -1.68%
  RB-006: PACS Q1-Q4 alpha 差距 6.5%; SQS conviction r=-0.50 (負相關)
  RB-007: Congress NET BUY 66.7% hit rate, NET SELL 38.9% (不可靠)

用法:
    python -m src.signal_enhancer                    # 增強現有 alpha_signals
    python -m src.signal_enhancer --buy-only         # 僅保留 Buy 信號
    python -m src.signal_enhancer --dry-run          # 預覽不寫入
    python -m src.signal_enhancer --days 30          # 僅處理近 30 天

Research Brief: RB-008
"""

import argparse
import logging
import sqlite3
import time
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple

from src.config import DB_PATH

logger = logging.getLogger("SignalEnhancer")


# ============================================================================
# VIX 體制常數 (RB-004)
# ============================================================================

# VIX Goldilocks Zone: 14-16 是最佳交易環境
VIX_ZONES = {
    "ultra_low": {"range": (0, 14), "multiplier": 0.6, "label": "Risk-Off (VIX<14, 回測 -2.94%)"},
    "goldilocks": {"range": (14, 16), "multiplier": 1.3, "label": "Goldilocks (VIX 14-16, +1.03% CAR_20d)"},
    "moderate": {"range": (16, 20), "multiplier": 0.8, "label": "Elevated (VIX 16-20, -1.68%)"},
    "high": {"range": (20, 30), "multiplier": 0.5, "label": "High Vol (VIX 20-30)"},
    "extreme": {"range": (30, 100), "multiplier": 0.3, "label": "Crisis (VIX>30)"},
}

# ============================================================================
# PACS 權重 (RB-006: Political Alpha Composite Score)
# ============================================================================

PACS_WEIGHT_SIGNAL_STRENGTH = 0.50    # 原始信號強度
PACS_WEIGHT_FILING_LAG_INV = 0.25     # Filing lag 反向 (越快越好)
PACS_WEIGHT_OPTIONS_SENTIMENT = 0.15  # 選擇權情緒
PACS_WEIGHT_CONVERGENCE = 0.10        # 匯聚信號

# ============================================================================
# 修正後的信心度權重 (解決 SQS r=-0.50 問題)
# ============================================================================

# 原始: SQS 40%, Alpha 30%, Conv 15%, Quality 15%
# 修正: Actionability 30%, Alpha 30%, Conv 20%, Quality 10%, SQS 10%
CONFIDENCE_V2_WEIGHTS = {
    "actionability": 0.30,  # SQS 的 actionability 子維度 (唯一正相關維度)
    "alpha_magnitude": 0.30,
    "convergence": 0.20,
    "quality": 0.10,
    "sqs_total": 0.10,      # 降至 10% (原 40%)
}


# ============================================================================
# VIX 體制偵測器
# ============================================================================

class VIXRegimeDetector:
    """透過 yfinance 取得 VIX 並分類當前市場體制。"""

    def __init__(self):
        self._cached_vix = None
        self._cache_time = None
        self._cache_ttl = 3600  # 1 小時快取

    def get_current_vix(self) -> Optional[float]:
        """取得當前 VIX 值。快取 1 小時。"""
        now = time.time()
        if self._cached_vix is not None and self._cache_time and (now - self._cache_time) < self._cache_ttl:
            return self._cached_vix

        try:
            import yfinance as yf
            vix = yf.Ticker("^VIX")
            hist = vix.history(period="5d")
            if hist.empty:
                logger.warning("VIX: 無法取得數據")
                return None
            current_vix = float(hist["Close"].iloc[-1])
            self._cached_vix = round(current_vix, 2)
            self._cache_time = now
            logger.info(f"VIX 當前值: {self._cached_vix}")
            return self._cached_vix
        except ImportError:
            logger.warning("yfinance 未安裝，無法取得 VIX")
            return None
        except Exception as e:
            logger.warning(f"VIX 取得失敗: {e}")
            return None

    def classify_regime(self, vix_value: Optional[float] = None) -> dict:
        """分類 VIX 體制，回傳 zone 資訊。

        Returns:
            {"zone": str, "vix": float, "multiplier": float, "label": str}
        """
        if vix_value is None:
            vix_value = self.get_current_vix()

        if vix_value is None:
            return {
                "zone": "unknown",
                "vix": None,
                "multiplier": 1.0,
                "label": "VIX unavailable (no adjustment)",
            }

        for zone_name, zone_info in VIX_ZONES.items():
            low, high = zone_info["range"]
            if low <= vix_value < high:
                return {
                    "zone": zone_name,
                    "vix": vix_value,
                    "multiplier": zone_info["multiplier"],
                    "label": zone_info["label"],
                }

        # fallback
        return {
            "zone": "extreme",
            "vix": vix_value,
            "multiplier": 0.3,
            "label": f"VIX={vix_value} (extreme)",
        }


# ============================================================================
# Signal Enhancer
# ============================================================================

class SignalEnhancer:
    """基於回測實證增強 alpha 信號。非破壞性 — 在 alpha_signals 上疊加增強層。"""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or DB_PATH
        self.vix_detector = VIXRegimeDetector()

    # ── 資料載入 ────────────────────────────────────────────────────

    def _load_alpha_signals(self, days: Optional[int] = None) -> List[dict]:
        """載入現有 alpha_signals。"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        query = """
            SELECT a.*,
                   s.actionability, s.timeliness, s.conviction,
                   s.information_edge, s.market_impact
            FROM alpha_signals a
            LEFT JOIN signal_quality_scores s ON a.trade_id = s.trade_id
        """
        params = []

        if days is not None:
            cutoff = (date.today() - timedelta(days=days)).strftime("%Y-%m-%d")
            query += " WHERE a.filing_date >= ?"
            params.append(cutoff)

        query += " ORDER BY a.signal_strength DESC"

        cursor = conn.execute(query, params)
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()

        logger.info(f"載入 {len(rows)} 筆 alpha 信號")
        return rows

    def _load_options_sentiment(self) -> Dict[str, dict]:
        """載入最新的選擇權情緒資料 (options_flow_signals)。"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        sentiment = {}
        try:
            cursor = conn.execute("""
                SELECT ticker, sentiment, signal_type,
                       put_call_ratio, unusual_volume_total
                FROM options_flow_signals
                WHERE id IN (
                    SELECT id FROM options_flow_signals
                    GROUP BY ticker
                    HAVING MAX(created_at)
                )
            """)
            for row in cursor.fetchall():
                sentiment[row["ticker"]] = dict(row)
        except sqlite3.OperationalError:
            logger.info("options_flow_signals 表不存在，跳過選擇權情緒")

        conn.close()
        logger.info(f"載入 {len(sentiment)} 檔選擇權情緒")
        return sentiment

    def _load_social_sentiment(self) -> Dict[str, dict]:
        """載入社群媒體情緒 (social_signals)。"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        social = {}
        try:
            cursor = conn.execute("""
                SELECT DISTINCT politician_name, sentiment, impact_score,
                       tickers, speech_trade_alignment
                FROM social_signals
                WHERE sentiment IS NOT NULL
                ORDER BY analyzed_at DESC
            """)
            for row in cursor.fetchall():
                name = row["politician_name"]
                if name not in social:
                    social[name] = dict(row)
        except sqlite3.OperationalError:
            logger.info("social_signals 表不存在，跳過社群情緒")

        conn.close()
        logger.info(f"載入 {len(social)} 位議員社群情緒")
        return social

    def _load_convergence_data(self) -> Dict[str, dict]:
        """載入收斂信號。"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        convergence = {}
        try:
            cursor = conn.execute("""
                SELECT ticker, direction, politician_count, score
                FROM convergence_signals
            """)
            for row in cursor.fetchall():
                t = row["ticker"]
                if t not in convergence or row["score"] > convergence[t]["score"]:
                    convergence[t] = dict(row)
        except sqlite3.OperationalError:
            pass

        conn.close()
        return convergence

    # ── PACS 計算核心 ──────────────────────────────────────────────

    def _calc_pacs_score(
        self,
        signal: dict,
        options_data: Optional[dict],
        convergence_data: Optional[dict],
    ) -> Tuple[float, dict]:
        """計算 PACS (Political Alpha Composite Score)。

        公式: PACS = 50% * signal_strength_norm
                   + 25% * filing_lag_inverse_norm
                   + 15% * options_sentiment_norm
                   + 10% * convergence_norm

        Returns:
            (pacs_score, component_details)
        """
        # 1. Signal Strength (50%) — 正規化到 [0, 1]
        raw_strength = signal.get("signal_strength", 0)
        # 典型範圍 0 ~ 2.0，用 sigmoid-like 正規化
        strength_norm = min(raw_strength / 1.5, 1.0)

        # 2. Filing Lag Inverse (25%) — 越快越好
        filing_lag = signal.get("filing_lag_days")
        if filing_lag is not None and filing_lag >= 0:
            # 0 天 → 1.0, 15 天 → 0.7, 30 天 → 0.4, 45 天 → 0.1
            lag_inv = max(0.0, 1.0 - filing_lag / 50.0)
        else:
            lag_inv = 0.5  # 未知時給中間值

        # 3. Options Sentiment (15%)
        if options_data is not None:
            # sentiment 範圍 [-1, +1]，轉為 [0, 1]
            raw_sentiment = options_data.get("sentiment", 0)
            options_norm = (raw_sentiment + 1.0) / 2.0
        else:
            options_norm = 0.5  # 無資料時中性

        # 4. Convergence (10%)
        if convergence_data is not None:
            conv_score = convergence_data.get("score", 0)
            # 分數範圍約 0 ~ 10
            convergence_norm = min(conv_score / 5.0, 1.0)
        else:
            convergence_norm = 0.0

        # 加權合計
        pacs = (
            PACS_WEIGHT_SIGNAL_STRENGTH * strength_norm
            + PACS_WEIGHT_FILING_LAG_INV * lag_inv
            + PACS_WEIGHT_OPTIONS_SENTIMENT * options_norm
            + PACS_WEIGHT_CONVERGENCE * convergence_norm
        )

        components = {
            "signal_strength_norm": round(strength_norm, 4),
            "filing_lag_inv": round(lag_inv, 4),
            "options_sentiment_norm": round(options_norm, 4),
            "convergence_norm": round(convergence_norm, 4),
            "pacs_raw": round(pacs, 4),
        }

        return round(pacs, 4), components

    def _calc_confidence_v2(self, signal: dict) -> float:
        """修正版信心度 — 降低 SQS 總分權重，提升 actionability。

        原始 (v1): SQS 40%, Alpha 30%, Conv 15%, Quality 15%
        修正 (v2): Actionability 30%, Alpha 30%, Conv 20%, Quality 10%, SQS 10%

        RB-006 發現: SQS conviction r=-0.50 (負相關), 但 actionability 可能有正相關
        """
        # Actionability 維度 (0-100 → 0-1)
        actionability = signal.get("actionability")
        if actionability is not None:
            act_norm = min(float(actionability) / 100.0, 1.0)
        else:
            act_norm = 0.5

        # Alpha 幅度
        alpha_5d = abs(signal.get("expected_alpha_5d", 0))
        alpha_norm = min(alpha_5d / 3.0, 1.0)

        # 匯聚
        convergence_norm = 1.0 if signal.get("has_convergence") else 0.0

        # 資料品質
        quality_norm = 0.5  # 預設

        # SQS 總分 (降至 10%)
        sqs = signal.get("sqs_score")
        if sqs is not None:
            sqs_norm = min(float(sqs) / 100.0, 1.0)
        else:
            sqs_norm = 0.5

        confidence_v2 = (
            CONFIDENCE_V2_WEIGHTS["actionability"] * act_norm
            + CONFIDENCE_V2_WEIGHTS["alpha_magnitude"] * alpha_norm
            + CONFIDENCE_V2_WEIGHTS["convergence"] * convergence_norm
            + CONFIDENCE_V2_WEIGHTS["quality"] * quality_norm
            + CONFIDENCE_V2_WEIGHTS["sqs_total"] * sqs_norm
        )

        return round(max(0.0, min(confidence_v2, 1.0)), 4)

    # ── 增強主流程 ──────────────────────────────────────────────────

    def enhance_signals(
        self,
        days: Optional[int] = None,
        buy_only: bool = False,
    ) -> List[dict]:
        """增強所有 alpha 信號。

        Steps:
          1. 載入 alpha_signals + SQS 子維度
          2. 取得 VIX 體制
          3. 載入選擇權情緒
          4. 載入社群情緒
          5. 載入收斂信號
          6. 計算 PACS、修正信心度、VIX 調整
          7. Buy-Only 過濾 (可選)

        Returns:
            增強後的信號列表，按 enhanced_strength 降序
        """
        # Step 1: 載入基礎資料
        signals = self._load_alpha_signals(days=days)
        if not signals:
            logger.warning("無 alpha 信號可增強")
            return []

        # Step 2: VIX 體制
        vix_regime = self.vix_detector.classify_regime()
        vix_mult = vix_regime["multiplier"]
        logger.info(f"VIX 體制: {vix_regime['label']} (multiplier={vix_mult})")

        # Step 3-5: 載入輔助資料
        options_sentiment = self._load_options_sentiment()
        social_sentiment = self._load_social_sentiment()
        convergence_data = self._load_convergence_data()

        # Step 6: 逐筆增強
        enhanced = []
        filtered_buy_only = 0

        for sig in signals:
            ticker = sig.get("ticker", "")
            politician = sig.get("politician_name", "")
            tx_type = sig.get("transaction_type", "")

            # Buy-Only 過濾 (RB-004)
            if buy_only and tx_type not in ("Buy", "Purchase", "purchase"):
                filtered_buy_only += 1
                continue

            # 取得輔助資料
            opts = options_sentiment.get(ticker)
            conv = convergence_data.get(ticker)
            social = social_sentiment.get(politician)

            # PACS 分數
            pacs, pacs_components = self._calc_pacs_score(sig, opts, conv)

            # 修正信心度
            confidence_v2 = self._calc_confidence_v2(sig)

            # VIX 調整後的增強信號強度
            enhanced_strength = pacs * vix_mult

            # 社群情緒加成
            social_bonus = 0.0
            social_alignment = None
            if social is not None:
                alignment = social.get("speech_trade_alignment")
                social_alignment = alignment
                if alignment == "CONSISTENT":
                    social_bonus = 0.05
                elif alignment == "CONTRADICTORY":
                    social_bonus = -0.03

            enhanced_strength += social_bonus

            # 建構增強信號
            enhanced_sig = {
                # 原始欄位
                "trade_id": sig.get("trade_id"),
                "ticker": ticker,
                "asset_name": sig.get("asset_name"),
                "politician_name": politician,
                "chamber": sig.get("chamber"),
                "transaction_type": tx_type,
                "transaction_date": sig.get("transaction_date"),
                "filing_date": sig.get("filing_date"),
                "amount_range": sig.get("amount_range"),
                "direction": sig.get("direction"),
                # 原始分數
                "original_alpha_5d": sig.get("expected_alpha_5d"),
                "original_alpha_20d": sig.get("expected_alpha_20d"),
                "original_confidence": sig.get("confidence"),
                "original_strength": sig.get("signal_strength"),
                # 增強分數
                "pacs_score": pacs,
                "confidence_v2": confidence_v2,
                "vix_multiplier": vix_mult,
                "vix_zone": vix_regime["zone"],
                "enhanced_strength": round(enhanced_strength, 4),
                # PACS 明細
                "pacs_signal_component": pacs_components["signal_strength_norm"],
                "pacs_lag_component": pacs_components["filing_lag_inv"],
                "pacs_options_component": pacs_components["options_sentiment_norm"],
                "pacs_convergence_component": pacs_components["convergence_norm"],
                # 輔助資訊
                "options_sentiment": opts.get("sentiment") if opts else None,
                "options_signal_type": opts.get("signal_type") if opts else None,
                "social_alignment": social_alignment,
                "social_bonus": social_bonus,
                "has_convergence": sig.get("has_convergence", False),
                "politician_grade": sig.get("politician_grade"),
                "filing_lag_days": sig.get("filing_lag_days"),
                "sqs_score": sig.get("sqs_score"),
            }

            enhanced.append(enhanced_sig)

        # 排序
        enhanced.sort(key=lambda s: s["enhanced_strength"], reverse=True)

        logger.info(
            f"增強完成: {len(enhanced)} 信號 "
            f"(VIX={vix_regime['zone']}, buy-only過濾={filtered_buy_only})"
        )

        return enhanced

    # ── 資料庫寫入 ──────────────────────────────────────────────────

    def save_enhanced(self, signals: List[dict]) -> dict:
        """將增強信號寫入 enhanced_signals 資料表。

        Returns:
            {"inserted": int, "updated": int}
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS enhanced_signals (
                trade_id TEXT PRIMARY KEY,
                ticker TEXT NOT NULL,
                politician_name TEXT,
                chamber TEXT,
                transaction_type TEXT,
                direction TEXT,
                original_strength REAL,
                original_confidence REAL,
                pacs_score REAL NOT NULL,
                confidence_v2 REAL NOT NULL,
                enhanced_strength REAL NOT NULL,
                vix_zone TEXT,
                vix_multiplier REAL,
                pacs_signal_component REAL,
                pacs_lag_component REAL,
                pacs_options_component REAL,
                pacs_convergence_component REAL,
                options_sentiment REAL,
                options_signal_type TEXT,
                social_alignment TEXT,
                social_bonus REAL DEFAULT 0,
                has_convergence BOOLEAN,
                politician_grade TEXT,
                filing_lag_days INTEGER,
                sqs_score REAL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        inserted = 0
        updated = 0

        for sig in signals:
            trade_id = sig["trade_id"]
            try:
                cursor.execute("""
                    INSERT INTO enhanced_signals (
                        trade_id, ticker, politician_name, chamber,
                        transaction_type, direction,
                        original_strength, original_confidence,
                        pacs_score, confidence_v2, enhanced_strength,
                        vix_zone, vix_multiplier,
                        pacs_signal_component, pacs_lag_component,
                        pacs_options_component, pacs_convergence_component,
                        options_sentiment, options_signal_type,
                        social_alignment, social_bonus,
                        has_convergence, politician_grade,
                        filing_lag_days, sqs_score
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    trade_id, sig["ticker"], sig["politician_name"],
                    sig["chamber"], sig["transaction_type"], sig["direction"],
                    sig["original_strength"], sig["original_confidence"],
                    sig["pacs_score"], sig["confidence_v2"], sig["enhanced_strength"],
                    sig["vix_zone"], sig["vix_multiplier"],
                    sig["pacs_signal_component"], sig["pacs_lag_component"],
                    sig["pacs_options_component"], sig["pacs_convergence_component"],
                    sig["options_sentiment"], sig["options_signal_type"],
                    sig["social_alignment"], sig["social_bonus"],
                    1 if sig["has_convergence"] else 0,
                    sig["politician_grade"], sig["filing_lag_days"],
                    sig["sqs_score"],
                ))
                inserted += 1
            except sqlite3.IntegrityError:
                cursor.execute("""
                    UPDATE enhanced_signals
                    SET pacs_score = ?, confidence_v2 = ?, enhanced_strength = ?,
                        vix_zone = ?, vix_multiplier = ?,
                        pacs_signal_component = ?, pacs_lag_component = ?,
                        pacs_options_component = ?, pacs_convergence_component = ?,
                        options_sentiment = ?, options_signal_type = ?,
                        social_alignment = ?, social_bonus = ?,
                        has_convergence = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE trade_id = ?
                """, (
                    sig["pacs_score"], sig["confidence_v2"], sig["enhanced_strength"],
                    sig["vix_zone"], sig["vix_multiplier"],
                    sig["pacs_signal_component"], sig["pacs_lag_component"],
                    sig["pacs_options_component"], sig["pacs_convergence_component"],
                    sig["options_sentiment"], sig["options_signal_type"],
                    sig["social_alignment"], sig["social_bonus"],
                    1 if sig["has_convergence"] else 0,
                    trade_id,
                ))
                updated += 1

        conn.commit()
        conn.close()

        logger.info(f"增強信號寫入: 新增 {inserted}, 更新 {updated}")
        return {"inserted": inserted, "updated": updated}

    # ── A/B 比較分析 ────────────────────────────────────────────────

    def compare_v1_v2(self, signals: List[dict]) -> dict:
        """比較 v1 (原始) vs v2 (增強) 排名差異。

        Returns:
            統計摘要 dict
        """
        if not signals:
            return {}

        # 排名變化
        rank_changes = []
        for i, sig in enumerate(signals):
            v1_rank = None
            # 用 original_strength 重新排名
            v1_sorted = sorted(signals, key=lambda s: s["original_strength"] or 0, reverse=True)
            for j, v1_sig in enumerate(v1_sorted):
                if v1_sig["trade_id"] == sig["trade_id"]:
                    v1_rank = j
                    break
            if v1_rank is not None:
                rank_changes.append(v1_rank - i)

        # 信號分布
        vix_zones = defaultdict(int)
        social_types = defaultdict(int)
        options_types = defaultdict(int)

        for sig in signals:
            vix_zones[sig.get("vix_zone", "unknown")] += 1
            if sig.get("social_alignment"):
                social_types[sig["social_alignment"]] += 1
            if sig.get("options_signal_type"):
                options_types[sig["options_signal_type"]] += 1

        avg_pacs = sum(s["pacs_score"] for s in signals) / len(signals)
        avg_enhanced = sum(s["enhanced_strength"] for s in signals) / len(signals)
        avg_original = sum((s["original_strength"] or 0) for s in signals) / len(signals)

        return {
            "total_signals": len(signals),
            "avg_pacs_score": round(avg_pacs, 4),
            "avg_enhanced_strength": round(avg_enhanced, 4),
            "avg_original_strength": round(avg_original, 4),
            "avg_rank_change": round(sum(rank_changes) / max(len(rank_changes), 1), 2),
            "max_rank_improvement": max(rank_changes) if rank_changes else 0,
            "max_rank_decline": min(rank_changes) if rank_changes else 0,
            "vix_zone_distribution": dict(vix_zones),
            "social_alignment_distribution": dict(social_types),
            "options_signal_distribution": dict(options_types),
        }


# ============================================================================
# 終端輸出
# ============================================================================

def print_enhanced_summary(signals: List[dict], comparison: dict, top_n: int = 15):
    """印出增強信號摘要。"""
    if not signals:
        print("\n  [無資料] 無增強信號。\n")
        return

    vix_zone = signals[0].get("vix_zone", "unknown") if signals else "unknown"
    vix_mult = signals[0].get("vix_multiplier", 1.0) if signals else 1.0

    print()
    print("=" * 110)
    print("  Signal Enhancer v2 — PACS + VIX + Social + Options 多信號融合")
    print("=" * 110)

    # VIX 狀態
    print(f"\n  VIX 體制: {vix_zone} (multiplier={vix_mult})")

    # 比較摘要
    print(f"\n  --- v1 vs v2 比較 ---")
    print(f"  信號總數: {comparison.get('total_signals', 0)}")
    print(f"  平均 PACS 分數: {comparison.get('avg_pacs_score', 0):.4f}")
    print(f"  平均增強強度: {comparison.get('avg_enhanced_strength', 0):.4f} (原始: {comparison.get('avg_original_strength', 0):.4f})")
    print(f"  平均排名變化: {comparison.get('avg_rank_change', 0):+.1f} (正=提升, 負=下降)")

    # 分布
    social_dist = comparison.get("social_alignment_distribution", {})
    if social_dist:
        parts = [f"{k}: {v}" for k, v in social_dist.items()]
        print(f"  社群比對: {', '.join(parts)}")

    options_dist = comparison.get("options_signal_distribution", {})
    if options_dist:
        parts = [f"{k}: {v}" for k, v in options_dist.items()]
        print(f"  選擇權: {', '.join(parts)}")

    # Top N 信號
    display_n = min(top_n, len(signals))
    print(f"\n  Top {display_n} Enhanced Signals:")
    print()

    header = (
        f"  {'#':>3}  "
        f"{'Ticker':<8}  "
        f"{'TxType':<6}  "
        f"{'PACS':>6}  "
        f"{'Enh.Str':>8}  "
        f"{'Orig.Str':>8}  "
        f"{'ConfV2':>7}  "
        f"{'VIX':>5}  "
        f"{'OptSent':>7}  "
        f"{'Social':>12}  "
        f"{'Politician':<20}  "
        f"{'Grade':<5}"
    )
    print(header)
    print(f"  {'-' * 108}")

    for i, sig in enumerate(signals[:display_n], start=1):
        opt_sent = sig.get("options_sentiment")
        opt_str = f"{opt_sent:+.2f}" if opt_sent is not None else "  N/A"
        social_str = sig.get("social_alignment") or "N/A"
        name = sig["politician_name"] or ""
        if len(name) > 18:
            name = name[:16] + ".."

        print(
            f"  {i:>3}  "
            f"{sig['ticker']:<8}  "
            f"{sig['transaction_type']:<6}  "
            f"{sig['pacs_score']:>6.4f}  "
            f"{sig['enhanced_strength']:>8.4f}  "
            f"{(sig['original_strength'] or 0):>8.4f}  "
            f"{sig['confidence_v2']:>7.4f}  "
            f"{sig.get('vix_zone', '?')[:5]:>5}  "
            f"{opt_str:>7}  "
            f"{social_str:>12}  "
            f"{name:<20}  "
            f"{sig.get('politician_grade', '?'):<5}"
        )

    print()
    print("=" * 110)


# ============================================================================
# CLI
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Signal Enhancer v2 — PACS + VIX + Social + Options 多信號融合"
    )
    parser.add_argument("--days", type=int, default=None, help="僅處理近 N 天信號")
    parser.add_argument("--buy-only", action="store_true", help="僅保留 Buy 信號 (RB-004)")
    parser.add_argument("--dry-run", action="store_true", help="預覽不寫入 DB")
    parser.add_argument("--top", type=int, default=15, help="顯示前 N 名 (預設 15)")
    parser.add_argument("--db", type=str, default=None, help="指定資料庫路徑")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    enhancer = SignalEnhancer(db_path=args.db)
    signals = enhancer.enhance_signals(days=args.days, buy_only=args.buy_only)

    if not signals:
        print("\n  無可增強的 alpha 信號。")
        return

    comparison = enhancer.compare_v1_v2(signals)
    print_enhanced_summary(signals, comparison, top_n=args.top)

    if not args.dry_run:
        result = enhancer.save_enhanced(signals)
        print(f"  DB 寫入: 新增 {result['inserted']}, 更新 {result['updated']}")
        print(f"  信號已存入 enhanced_signals 表")
    else:
        print("  (Dry Run — 未寫入 DB)")


if __name__ == "__main__":
    main()
