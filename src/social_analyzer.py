"""
Social Media Analyzer — 交叉比對 + 信號生成
將社群媒體 NLP 分析結果與國會交易記錄交叉比對，
產生一致性/矛盾性信號，並輸出至 alpha_signals 與告警系統。

交叉比對邏輯:
  - CONSISTENT (說看多 + 買入) → convergence_bonus +0.3
  - CONTRADICTORY (說看多 + 賣出) → 異常告警
  - NO_TRADE → 純社群信號，正常權重

使用方式:
    python -m src.social_analyzer                  # 分析 DB 中最近 24 小時貼文
    python -m src.social_analyzer --hours 48       # 過去 48 小時
    python -m src.social_analyzer --dry-run        # 只分析，不寫入 DB
"""

import argparse
import json
import logging
import os
import sqlite3
import sys
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.config import DB_PATH
from src.social_targets import (
    POLITICIAN_SOCIAL_TARGETS,
    KOL_SOCIAL_TARGETS,
)
from src.social_nlp import analyze_posts

logger = logging.getLogger("SocialAnalyzer")

# ── 交叉比對常數 ──
TRADE_LOOKBACK_DAYS = 30          # 比對國會交易的時間窗口
CONVERGENCE_BONUS = 0.3           # 言行一致加分
CONTRADICTORY_PENALTY = -0.2      # 言行矛盾扣分

# ── 信號方向映射 ──
SENTIMENT_DIRECTION = {
    "Bullish": "LONG",
    "Bearish": "SHORT",
    "Neutral": None,
}

TRADE_DIRECTION = {
    "Purchase": "LONG",
    "Buy": "LONG",
    "Sale": "SHORT",
    "Sale (Full)": "SHORT",
    "Sale (Partial)": "SHORT",
    "Exchange": None,
}


class SocialAnalyzer:
    """社群媒體分析器 — 交叉比對 + 信號生成"""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or DB_PATH
        self._targets_config = self._build_targets_config()

    # ================================================================
    # 公開介面
    # ================================================================

    def analyze_batch(
        self,
        hours: int = 24,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        批次分析 social_posts 中最近的貼文。

        流程:
        1. 從 DB 讀取未分析的貼文
        2. 呼叫 social_nlp.analyze_posts 做 NLP 分析
        3. 對議員類型的信號做交叉比對
        4. 寫入 social_signals 表
        5. 產生 alpha_signals（高影響力信號）

        Returns:
            統計摘要 dict
        """
        # Step 1: 讀取貼文
        posts = self._load_unanalyzed_posts(hours)
        if not posts:
            logger.info("無新貼文需要分析")
            return {"total": 0, "signals": 0, "consistent": 0, "contradictory": 0, "no_trade": 0}

        logger.info(f"載入 {len(posts)} 篇待分析貼文")

        # Step 2: NLP 分析
        signals = analyze_posts(posts, self._targets_config)
        logger.info(f"NLP 分析完成: {len(signals)} 篇信號")

        # Step 3: 交叉比對（僅議員）
        consistent_count = 0
        contradictory_count = 0
        no_trade_count = 0

        for signal in signals:
            if signal["author_type"] == "politician":
                alignment = self._cross_reference_speech_trade(signal)
                signal["speech_trade_alignment"] = alignment
                signal["congress_trade_match"] = 1 if alignment != "NO_TRADE" else 0
                if alignment == "CONSISTENT":
                    consistent_count += 1
                elif alignment == "CONTRADICTORY":
                    contradictory_count += 1
                else:
                    no_trade_count += 1
            else:
                signal["speech_trade_alignment"] = None
                signal["congress_trade_match"] = 0
                no_trade_count += 1

        # Step 4: 寫入 DB
        if not dry_run:
            saved = self._save_signals(signals)
            logger.info(f"寫入 {saved} 筆信號至 social_signals")

            # Step 5: 高影響力信號 → alpha_signals
            alpha_count = self._generate_alpha_signals(signals)
            logger.info(f"產生 {alpha_count} 筆 alpha signals")
        else:
            logger.info("[Dry Run] 跳過 DB 寫入")
            saved = 0
            alpha_count = 0

        stats = {
            "total": len(posts),
            "signals": len(signals),
            "saved": saved,
            "alpha_signals": alpha_count,
            "consistent": consistent_count,
            "contradictory": contradictory_count,
            "no_trade": no_trade_count,
        }

        # 摘要 log
        logger.info(
            f"分析摘要: 貼文={stats['total']}, 信號={stats['signals']}, "
            f"一致={consistent_count}, 矛盾={contradictory_count}, 無交易比對={no_trade_count}"
        )

        return stats

    def generate_report(self, hours: int = 24) -> str:
        """
        產生社群分析摘要報告（Markdown 格式），供 daily_report 整合使用。

        Args:
            hours: 回溯時間窗口

        Returns:
            Markdown 格式的摘要文字
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        # 統計信號數量
        cursor.execute(
            "SELECT COUNT(*) as cnt FROM social_signals WHERE created_at >= ?",
            (cutoff,),
        )
        total_signals = cursor.fetchone()["cnt"]

        # 按平台統計
        cursor.execute(
            """
            SELECT platform, COUNT(*) as cnt
            FROM social_signals WHERE created_at >= ?
            GROUP BY platform ORDER BY cnt DESC
            """,
            (cutoff,),
        )
        by_platform = cursor.fetchall()

        # 高影響力信號 (impact_score >= 7)
        cursor.execute(
            """
            SELECT author_name, platform, sentiment, impact_score, signal_type,
                   speech_trade_alignment, reasoning
            FROM social_signals
            WHERE created_at >= ? AND impact_score >= 7
            ORDER BY impact_score DESC
            LIMIT 10
            """,
            (cutoff,),
        )
        top_signals = cursor.fetchall()

        # 矛盾信號
        cursor.execute(
            """
            SELECT author_name, sentiment, reasoning
            FROM social_signals
            WHERE created_at >= ? AND speech_trade_alignment = 'CONTRADICTORY'
            ORDER BY impact_score DESC
            """,
            (cutoff,),
        )
        contradictions = cursor.fetchall()

        conn.close()

        # 組合報告
        lines = []
        lines.append(f"## Social Media Analysis (past {hours}h)")
        lines.append(f"- Total signals analyzed: **{total_signals}**")

        if by_platform:
            platforms_str = ", ".join(
                f"{r['platform']}: {r['cnt']}" for r in by_platform
            )
            lines.append(f"- By platform: {platforms_str}")

        if top_signals:
            lines.append("")
            lines.append("### High-Impact Signals (score >= 7)")
            for s in top_signals:
                alignment = f" [{s['speech_trade_alignment']}]" if s["speech_trade_alignment"] else ""
                lines.append(
                    f"- **{s['author_name']}** ({s['platform']}) — "
                    f"{s['sentiment']} (impact: {s['impact_score']}) "
                    f"{s['signal_type']}{alignment}"
                )
                if s["reasoning"]:
                    lines.append(f"  > {s['reasoning'][:120]}")

        if contradictions:
            lines.append("")
            lines.append("### CONTRADICTORY Signals (speech vs trade)")
            for c in contradictions:
                lines.append(
                    f"- **{c['author_name']}**: says {c['sentiment']} but trades opposite"
                )

        return "\n".join(lines)

    # ================================================================
    # 交叉比對
    # ================================================================

    def _cross_reference_speech_trade(self, signal: Dict[str, Any]) -> str:
        """
        比對議員社群發言與國會交易記錄。

        邏輯:
        1. 用 author_name 模糊匹配 congress_trades.politician_name
        2. 查找最近 30 天的交易
        3. 從信號中取出 sentiment + tickers
        4. 比對 sentiment 方向與 transaction_type 方向

        Returns:
            'CONSISTENT' | 'CONTRADICTORY' | 'NO_TRADE'
        """
        author_name = signal.get("author_name", "")
        sentiment = signal.get("sentiment", "Neutral")

        # Neutral 無法判斷方向
        if sentiment == "Neutral":
            return "NO_TRADE"

        sentiment_dir = SENTIMENT_DIRECTION.get(sentiment)
        if not sentiment_dir:
            return "NO_TRADE"

        # 取出信號提到的 tickers
        tickers = set()
        for field in ("tickers_explicit", "tickers_implied"):
            raw = signal.get(field, "[]")
            if isinstance(raw, str):
                try:
                    parsed = json.loads(raw)
                    if isinstance(parsed, list):
                        tickers.update(t.upper() for t in parsed if t)
                except (json.JSONDecodeError, TypeError):
                    pass
            elif isinstance(raw, list):
                tickers.update(t.upper() for t in raw if t)

        if not tickers:
            return "NO_TRADE"

        # 查詢國會交易
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cutoff_date = (
            datetime.now(timezone.utc) - timedelta(days=TRADE_LOOKBACK_DAYS)
        ).strftime("%Y-%m-%d")

        # 用 LIKE 做模糊匹配（姓氏匹配）
        # 取姓氏（最後一個詞）
        name_parts = author_name.strip().split()
        last_name = name_parts[-1] if name_parts else author_name
        # 也嘗試全名
        search_patterns = [f"%{last_name}%"]
        if len(name_parts) > 1:
            search_patterns.append(f"%{name_parts[0]}%{name_parts[-1]}%")

        trades = []
        ticker_placeholders = ",".join("?" * len(tickers))
        for pattern in search_patterns:
            cursor.execute(
                f"""
                SELECT politician_name, ticker, transaction_type, transaction_date
                FROM congress_trades
                WHERE politician_name LIKE ?
                  AND ticker IN ({ticker_placeholders})
                  AND transaction_date >= ?
                ORDER BY transaction_date DESC
                """,
                (pattern, *tickers, cutoff_date),
            )
            trades.extend(cursor.fetchall())

        conn.close()

        if not trades:
            return "NO_TRADE"

        # 比對方向
        # 使用最近的交易作為比對依據
        for trade in trades:
            trade_dir = TRADE_DIRECTION.get(trade["transaction_type"])
            if trade_dir is None:
                continue

            if trade_dir == sentiment_dir:
                logger.info(
                    f"CONSISTENT: {author_name} says {sentiment} + "
                    f"traded {trade['transaction_type']} {trade['ticker']}"
                )
                return "CONSISTENT"
            else:
                logger.warning(
                    f"CONTRADICTORY: {author_name} says {sentiment} but "
                    f"traded {trade['transaction_type']} {trade['ticker']}"
                )
                return "CONTRADICTORY"

        return "NO_TRADE"

    # ================================================================
    # DB 操作
    # ================================================================

    def _load_unanalyzed_posts(self, hours: int) -> List[Dict[str, Any]]:
        """
        從 social_posts 載入尚未分析的貼文。
        已在 social_signals 中存在的 post_id 會被跳過。
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        cursor.execute(
            """
            SELECT sp.id as db_id, sp.platform, sp.author_name, sp.author_handle,
                   sp.author_type, sp.post_id, sp.post_text, sp.post_url,
                   sp.post_time, sp.likes, sp.retweets, sp.replies
            FROM social_posts sp
            LEFT JOIN social_signals ss ON sp.id = ss.post_id
            WHERE sp.fetched_at >= ? AND ss.id IS NULL
            ORDER BY sp.post_time DESC
            """,
            (cutoff,),
        )

        rows = cursor.fetchall()
        conn.close()

        return [dict(r) for r in rows]

    def _save_signals(self, signals: List[Dict[str, Any]]) -> int:
        """寫入 social_signals 表。"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        saved = 0

        for signal in signals:
            try:
                cursor.execute(
                    """
                    INSERT INTO social_signals (
                        post_id, author_name, author_type, platform,
                        sentiment, sentiment_score, signal_type,
                        sarcasm_detected, tickers_explicit, tickers_implied,
                        sector, analysis_model, impact_score, reasoning,
                        congress_trade_match, speech_trade_alignment
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        signal.get("post_id"),
                        signal["author_name"],
                        signal["author_type"],
                        signal["platform"],
                        signal.get("sentiment"),
                        signal.get("sentiment_score"),
                        signal.get("signal_type"),
                        signal.get("sarcasm_detected", 0),
                        signal.get("tickers_explicit", "[]"),
                        signal.get("tickers_implied", "[]"),
                        signal.get("sector", ""),
                        signal.get("analysis_model", ""),
                        signal.get("impact_score"),
                        signal.get("reasoning", ""),
                        signal.get("congress_trade_match", 0),
                        signal.get("speech_trade_alignment"),
                    ),
                )
                saved += 1
            except Exception as e:
                logger.error(f"寫入 social_signals 失敗: {e}")

        conn.commit()
        conn.close()
        return saved

    def _generate_alpha_signals(self, signals: List[Dict[str, Any]]) -> int:
        """
        將高影響力社群信號轉換為 alpha_signals 記錄。

        選入條件：
        - impact_score >= 7
        - 有明確 ticker
        - sentiment != Neutral

        交叉比對加分：
        - CONSISTENT → convergence_bonus +0.3
        - CONTRADICTORY → convergence_bonus -0.2（仍生成信號，但降權）
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 確保表存在（alpha_signal_generator 可能已建立）
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

        inserted = 0

        for signal in signals:
            sentiment = signal.get("sentiment", "Neutral")
            if sentiment == "Neutral":
                continue

            impact = signal.get("impact_score", 0)
            if impact is None or impact < 7:
                continue

            # 取出 tickers
            tickers = set()
            for field in ("tickers_explicit", "tickers_implied"):
                raw = signal.get(field, "[]")
                if isinstance(raw, str):
                    try:
                        parsed = json.loads(raw)
                        if isinstance(parsed, list):
                            tickers.update(t for t in parsed if t)
                    except (json.JSONDecodeError, TypeError):
                        pass
                elif isinstance(raw, list):
                    tickers.update(t for t in raw if t)

            if not tickers:
                continue

            # 方向
            direction = SENTIMENT_DIRECTION.get(sentiment, "LONG")

            # 交叉比對加分
            alignment = signal.get("speech_trade_alignment")
            convergence_bonus = 0.0
            if alignment == "CONSISTENT":
                convergence_bonus = CONVERGENCE_BONUS
            elif alignment == "CONTRADICTORY":
                convergence_bonus = CONTRADICTORY_PENALTY

            # 估算 alpha（社群信號基礎 alpha 較保守）
            confidence = min(signal.get("sentiment_score", 0.5), 1.0)
            base_alpha = (impact / 10.0) * 0.5  # 基於 impact 估算
            expected_5d = base_alpha * (1.0 + convergence_bonus)
            expected_20d = expected_5d * 1.5  # 20d 通常更大
            signal_strength = confidence * (impact / 10.0) * (1.0 + convergence_bonus)

            # 為每個 ticker 生成一筆 alpha signal
            for ticker in tickers:
                signal_id = str(uuid.uuid4())
                # trade_id 用 social signal 的唯一標識
                trade_id = f"social_{signal.get('post_id', 'unknown')}_{ticker}"

                try:
                    cursor.execute(
                        """
                        INSERT INTO alpha_signals (
                            id, trade_id, ticker, asset_name, politician_name,
                            chamber, transaction_type, direction,
                            expected_alpha_5d, expected_alpha_20d,
                            confidence, signal_strength, combined_multiplier,
                            convergence_bonus, has_convergence, politician_grade,
                            reasoning
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            signal_id,
                            trade_id,
                            ticker.upper(),
                            None,
                            signal["author_name"],
                            None,  # 社群信號無 chamber
                            f"social_{signal.get('signal_type', 'UNKNOWN')}",
                            direction,
                            expected_5d,
                            expected_20d,
                            confidence,
                            signal_strength,
                            1.0 + convergence_bonus,
                            convergence_bonus,
                            1 if alignment == "CONSISTENT" else 0,
                            None,
                            f"[Social] {signal.get('reasoning', '')}",
                        ),
                    )
                    inserted += 1
                except sqlite3.IntegrityError:
                    # trade_id 重複，跳過
                    pass
                except Exception as e:
                    logger.error(f"寫入 alpha_signals 失敗 ({ticker}): {e}")

        conn.commit()
        conn.close()
        return inserted

    # ================================================================
    # 輔助方法
    # ================================================================

    def _build_targets_config(self) -> Dict[str, Dict]:
        """
        從追蹤清單建立目標人物設定 dict。
        供 social_nlp.analyze_posts 使用。
        """
        config = {}

        for p in POLITICIAN_SOCIAL_TARGETS:
            config[p["name"]] = {
                "committees": ", ".join(p.get("committees", [])) or "Unknown",
                "sector_focus": p.get("sector_focus", []),
                "author_type": "politician",
            }

        for k in KOL_SOCIAL_TARGETS:
            config[k["name"]] = {
                "influence_profile": k.get("influence", ""),
                "key_tickers": k.get("key_tickers", []),
                "contrarian": k.get("contrarian", False),
                "author_type": "kol",
            }

        return config


# ================================================================
# CLI 入口 (python -m src.social_analyzer)
# ================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Social Media Analyzer — 交叉比對 + 信號生成"
    )
    parser.add_argument(
        "--hours", type=int, default=24,
        help="回溯時間窗口（小時，預設 24）"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="只分析，不寫入資料庫"
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="[%(levelname)s] %(name)s: %(message)s",
    )

    analyzer = SocialAnalyzer()
    stats = analyzer.analyze_batch(hours=args.hours, dry_run=args.dry_run)

    print(f"\n{'='*60}")
    print("Social Media Analysis Complete")
    print(f"{'='*60}")
    for key, value in stats.items():
        print(f"  {key}: {value}")
    if args.dry_run:
        print("  (Dry Run)")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
