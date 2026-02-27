"""Options Flow Analyzer — 異常選擇權活動分析模組

監控 alpha 訊號標的的選擇權市場異常活動，交叉比對國會交易訊號，
產生綜合情緒評分與訊號確認/警告標記。

分析邏輯:
  1. 取得 alpha_signals 前 N 檔標的
  2. 透過 yfinance 取得選擇權鏈 (options chain)
  3. 計算 put/call ratio (成交量加權)
  4. 辨識異常成交量 (volume > 2x open interest)
  5. 檢測隱含波動率變化
  6. 交叉比對國會交易方向，產生確認/警告訊號

訊號類型:
  - BULLISH_CONFIRMATION: 國會買入 + 高 call 量
  - HEDGING_WARNING:      國會買入 + 高 put 量
  - BEARISH_CONFIRMATION: 國會賣出 + 高 put 量
  - CONTRARIAN_WARNING:   國會賣出 + 高 call 量

用法:
    from src.options_flow import OptionsFlowAnalyzer
    analyzer = OptionsFlowAnalyzer()
    results = analyzer.analyze_top_signals(top_n=20)
"""

import logging
import sqlite3
import time
import uuid
from datetime import datetime, date
from typing import Dict, List, Optional, Tuple

import yfinance as yf

from src.config import DB_PATH

logger = logging.getLogger("OptionsFlow")

# ============================================================================
# 常數
# ============================================================================

# 異常成交量門檻: volume > UNUSUAL_VOLUME_RATIO * open_interest
UNUSUAL_VOLUME_RATIO = 2.0

# Put/Call ratio 閾值
PC_RATIO_BULLISH = 0.7    # < 0.7 → 偏多
PC_RATIO_BEARISH = 1.3    # > 1.3 → 偏空

# 情緒分數權重
WEIGHT_PC_RATIO = 0.35
WEIGHT_UNUSUAL_VOL = 0.25
WEIGHT_IV_SKEW = 0.20
WEIGHT_CONGRESS_CROSS = 0.20

# yfinance 呼叫間隔 (秒)
API_DELAY_SECONDS = 1.0


# ============================================================================
# OptionsFlowAnalyzer
# ============================================================================

class OptionsFlowAnalyzer:
    """分析選擇權異常活動並與國會交易訊號交叉比對。"""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or DB_PATH

    # ── 資料載入 ────────────────────────────────────────────────────────

    def _load_top_signals(self, top_n: int = 20) -> List[dict]:
        """從 alpha_signals 載入前 N 檔標的（依 signal_strength 排序，去重 ticker）。"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT ticker, MAX(signal_strength) as max_strength,
                   transaction_type, direction, politician_name, chamber
            FROM alpha_signals
            GROUP BY ticker
            ORDER BY max_strength DESC
            LIMIT ?
        """, (top_n,))

        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()

        logger.info(f"載入 {len(rows)} 檔 alpha 訊號標的")
        return rows

    # ── 選擇權資料抓取 ──────────────────────────────────────────────────

    def _fetch_options_data(self, ticker: str) -> Optional[dict]:
        """透過 yfinance 取得最近到期日的選擇權資料。

        Returns:
            {
                "expiration": str,
                "calls": DataFrame,
                "puts": DataFrame,
                "call_volume": int,
                "put_volume": int,
                "call_oi": int,
                "put_oi": int,
                "unusual_calls": list,
                "unusual_puts": list,
                "avg_call_iv": float,
                "avg_put_iv": float,
            }
            或 None（無法取得資料時）
        """
        try:
            stock = yf.Ticker(ticker)
            expirations = stock.options

            if not expirations:
                logger.warning(f"{ticker}: 無可用選擇權到期日")
                return None

            # 取最近的到期日
            nearest_exp = expirations[0]
            chain = stock.option_chain(nearest_exp)
            calls = chain.calls
            puts = chain.puts

            if calls.empty and puts.empty:
                logger.warning(f"{ticker}: 選擇權鏈為空 (到期日={nearest_exp})")
                return None

            # 基本統計
            call_volume = int(calls["volume"].sum()) if not calls.empty and "volume" in calls.columns else 0
            put_volume = int(puts["volume"].sum()) if not puts.empty and "volume" in puts.columns else 0
            call_oi = int(calls["openInterest"].sum()) if not calls.empty and "openInterest" in calls.columns else 0
            put_oi = int(puts["openInterest"].sum()) if not puts.empty and "openInterest" in puts.columns else 0

            # 異常成交量合約 (volume > 2x open interest)
            unusual_calls = []
            if not calls.empty and "volume" in calls.columns and "openInterest" in calls.columns:
                for _, row in calls.iterrows():
                    vol = row.get("volume", 0) or 0
                    oi = row.get("openInterest", 0) or 0
                    if oi > 0 and vol > UNUSUAL_VOLUME_RATIO * oi:
                        unusual_calls.append({
                            "strike": row.get("strike"),
                            "volume": int(vol),
                            "openInterest": int(oi),
                            "ratio": round(vol / oi, 2) if oi > 0 else 0,
                            "impliedVolatility": round(row.get("impliedVolatility", 0) or 0, 4),
                        })

            unusual_puts = []
            if not puts.empty and "volume" in puts.columns and "openInterest" in puts.columns:
                for _, row in puts.iterrows():
                    vol = row.get("volume", 0) or 0
                    oi = row.get("openInterest", 0) or 0
                    if oi > 0 and vol > UNUSUAL_VOLUME_RATIO * oi:
                        unusual_puts.append({
                            "strike": row.get("strike"),
                            "volume": int(vol),
                            "openInterest": int(oi),
                            "ratio": round(vol / oi, 2) if oi > 0 else 0,
                            "impliedVolatility": round(row.get("impliedVolatility", 0) or 0, 4),
                        })

            # 平均隱含波動率
            avg_call_iv = 0.0
            if not calls.empty and "impliedVolatility" in calls.columns:
                iv_vals = calls["impliedVolatility"].dropna()
                if len(iv_vals) > 0:
                    avg_call_iv = float(iv_vals.mean())

            avg_put_iv = 0.0
            if not puts.empty and "impliedVolatility" in puts.columns:
                iv_vals = puts["impliedVolatility"].dropna()
                if len(iv_vals) > 0:
                    avg_put_iv = float(iv_vals.mean())

            return {
                "expiration": nearest_exp,
                "call_volume": call_volume,
                "put_volume": put_volume,
                "call_oi": call_oi,
                "put_oi": put_oi,
                "unusual_calls": unusual_calls,
                "unusual_puts": unusual_puts,
                "avg_call_iv": round(avg_call_iv, 4),
                "avg_put_iv": round(avg_put_iv, 4),
            }

        except Exception as e:
            logger.warning(f"{ticker}: 取得選擇權資料失敗 — {e}")
            return None

    # ── 分析邏輯 ────────────────────────────────────────────────────────

    def _calc_put_call_ratio(self, options_data: dict) -> float:
        """計算成交量加權 put/call ratio。"""
        call_vol = options_data["call_volume"]
        put_vol = options_data["put_volume"]

        if call_vol == 0:
            return 99.0 if put_vol > 0 else 1.0  # 全 put / 無成交
        return round(put_vol / call_vol, 4)

    def _classify_signal(
        self, transaction_type: str, put_call_ratio: float
    ) -> str:
        """交叉比對國會交易方向與選擇權活動。

        Returns:
            訊號類型字串
        """
        is_buy = transaction_type in ("Buy", "Purchase", "purchase")
        is_bearish_options = put_call_ratio > PC_RATIO_BEARISH
        is_bullish_options = put_call_ratio < PC_RATIO_BULLISH

        if is_buy and is_bullish_options:
            return "BULLISH_CONFIRMATION"
        elif is_buy and is_bearish_options:
            return "HEDGING_WARNING"
        elif not is_buy and is_bearish_options:
            return "BEARISH_CONFIRMATION"
        elif not is_buy and is_bullish_options:
            return "CONTRARIAN_WARNING"
        else:
            return "NEUTRAL"

    def _calc_sentiment(
        self,
        put_call_ratio: float,
        unusual_calls: list,
        unusual_puts: list,
        avg_call_iv: float,
        avg_put_iv: float,
        signal_type: str,
    ) -> float:
        """計算綜合情緒分數 (-1.0 到 +1.0)。

        組成:
          - Put/Call ratio (35%): < 0.7 → +1, > 1.3 → -1
          - 異常成交量 (25%): call 多 → +, put 多 → -
          - IV skew (20%): call IV > put IV → +, 反之 → -
          - 國會訊號交叉 (20%): confirmation → +, warning → -
        """
        # Put/Call ratio 分數
        if put_call_ratio <= PC_RATIO_BULLISH:
            pc_score = 1.0
        elif put_call_ratio >= PC_RATIO_BEARISH:
            pc_score = -1.0
        else:
            # 線性內插 0.7~1.3 → +1~-1
            pc_score = 1.0 - 2.0 * (put_call_ratio - PC_RATIO_BULLISH) / (PC_RATIO_BEARISH - PC_RATIO_BULLISH)

        # 異常成交量分數
        n_unusual_calls = len(unusual_calls)
        n_unusual_puts = len(unusual_puts)
        total_unusual = n_unusual_calls + n_unusual_puts
        if total_unusual > 0:
            vol_score = (n_unusual_calls - n_unusual_puts) / total_unusual
        else:
            vol_score = 0.0

        # IV skew 分數
        if avg_call_iv > 0 and avg_put_iv > 0:
            iv_diff = avg_call_iv - avg_put_iv
            avg_iv = (avg_call_iv + avg_put_iv) / 2
            if avg_iv > 0:
                iv_score = max(-1.0, min(1.0, iv_diff / avg_iv * 5))
            else:
                iv_score = 0.0
        else:
            iv_score = 0.0

        # 國會訊號交叉分數
        cross_score_map = {
            "BULLISH_CONFIRMATION": 1.0,
            "BEARISH_CONFIRMATION": -1.0,
            "HEDGING_WARNING": -0.5,
            "CONTRARIAN_WARNING": 0.5,
            "NEUTRAL": 0.0,
        }
        cross_score = cross_score_map.get(signal_type, 0.0)

        # 加權合計
        sentiment = (
            WEIGHT_PC_RATIO * pc_score
            + WEIGHT_UNUSUAL_VOL * vol_score
            + WEIGHT_IV_SKEW * iv_score
            + WEIGHT_CONGRESS_CROSS * cross_score
        )

        return round(max(-1.0, min(1.0, sentiment)), 4)

    # ── 主流程 ──────────────────────────────────────────────────────────

    def analyze_ticker(
        self, ticker: str, transaction_type: str, signal_strength: float
    ) -> Optional[dict]:
        """分析單一標的的選擇權活動。

        Returns:
            分析結果 dict 或 None
        """
        options_data = self._fetch_options_data(ticker)
        if options_data is None:
            return None

        pc_ratio = self._calc_put_call_ratio(options_data)
        signal_type = self._classify_signal(transaction_type, pc_ratio)

        unusual_volume = len(options_data["unusual_calls"]) + len(options_data["unusual_puts"])

        sentiment = self._calc_sentiment(
            put_call_ratio=pc_ratio,
            unusual_calls=options_data["unusual_calls"],
            unusual_puts=options_data["unusual_puts"],
            avg_call_iv=options_data["avg_call_iv"],
            avg_put_iv=options_data["avg_put_iv"],
            signal_type=signal_type,
        )

        return {
            "ticker": ticker,
            "expiration": options_data["expiration"],
            "call_volume": options_data["call_volume"],
            "put_volume": options_data["put_volume"],
            "call_oi": options_data["call_oi"],
            "put_oi": options_data["put_oi"],
            "put_call_ratio": pc_ratio,
            "unusual_call_count": len(options_data["unusual_calls"]),
            "unusual_put_count": len(options_data["unusual_puts"]),
            "unusual_volume_total": unusual_volume,
            "avg_call_iv": options_data["avg_call_iv"],
            "avg_put_iv": options_data["avg_put_iv"],
            "signal_type": signal_type,
            "sentiment": sentiment,
            "congress_direction": transaction_type,
            "alpha_signal_strength": signal_strength,
            "unusual_calls_detail": options_data["unusual_calls"][:5],  # 前 5 筆
            "unusual_puts_detail": options_data["unusual_puts"][:5],
        }

    def analyze_top_signals(self, top_n: int = 20) -> List[dict]:
        """分析 alpha 訊號前 N 檔標的。

        Args:
            top_n: 取 alpha_signals 前 N 檔（去重 ticker）

        Returns:
            分析結果列表，按 |sentiment| 降序排列
        """
        signals = self._load_top_signals(top_n=top_n)
        if not signals:
            logger.warning("alpha_signals 表中無資料")
            return []

        results = []
        total = len(signals)

        for i, sig in enumerate(signals, start=1):
            ticker = sig["ticker"]
            tx_type = sig["transaction_type"]
            strength = sig["max_strength"]

            logger.info(f"[{i}/{total}] 分析 {ticker} 選擇權活動...")

            result = self.analyze_ticker(ticker, tx_type, strength)
            if result is not None:
                results.append(result)
                logger.info(
                    f"  {ticker}: P/C={result['put_call_ratio']:.2f}, "
                    f"sentiment={result['sentiment']:+.2f}, "
                    f"type={result['signal_type']}"
                )
            else:
                logger.info(f"  {ticker}: 無選擇權資料，跳過")

            # API 限流
            if i < total:
                time.sleep(API_DELAY_SECONDS)

        # 按 |sentiment| 降序
        results.sort(key=lambda r: abs(r["sentiment"]), reverse=True)

        logger.info(f"完成分析: {len(results)}/{total} 檔有選擇權資料")
        return results

    # ── 資料庫寫入 ────────────────────────────────────────────────────

    def save_results(self, results: List[dict]) -> dict:
        """將分析結果寫入 options_flow_signals 資料表。

        Returns:
            {"inserted": int, "skipped": int}
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS options_flow_signals (
                id TEXT PRIMARY KEY,
                ticker TEXT NOT NULL,
                expiration TEXT,
                call_volume INTEGER,
                put_volume INTEGER,
                call_oi INTEGER,
                put_oi INTEGER,
                put_call_ratio REAL,
                unusual_call_count INTEGER DEFAULT 0,
                unusual_put_count INTEGER DEFAULT 0,
                unusual_volume_total INTEGER DEFAULT 0,
                avg_call_iv REAL,
                avg_put_iv REAL,
                signal_type TEXT,
                sentiment REAL,
                congress_direction TEXT,
                alpha_signal_strength REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(ticker, created_at)
            )
        """)

        inserted = 0
        skipped = 0

        for r in results:
            try:
                cursor.execute("""
                    INSERT INTO options_flow_signals (
                        id, ticker, expiration, call_volume, put_volume,
                        call_oi, put_oi, put_call_ratio,
                        unusual_call_count, unusual_put_count, unusual_volume_total,
                        avg_call_iv, avg_put_iv,
                        signal_type, sentiment, congress_direction,
                        alpha_signal_strength
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    str(uuid.uuid4()),
                    r["ticker"],
                    r["expiration"],
                    r["call_volume"],
                    r["put_volume"],
                    r["call_oi"],
                    r["put_oi"],
                    r["put_call_ratio"],
                    r["unusual_call_count"],
                    r["unusual_put_count"],
                    r["unusual_volume_total"],
                    r["avg_call_iv"],
                    r["avg_put_iv"],
                    r["signal_type"],
                    r["sentiment"],
                    r["congress_direction"],
                    r["alpha_signal_strength"],
                ))
                inserted += 1
            except sqlite3.IntegrityError:
                skipped += 1

        conn.commit()
        conn.close()

        logger.info(f"寫入完成: 新增 {inserted}, 跳過 {skipped}")
        return {"inserted": inserted, "skipped": skipped}

    # ── Alpha 訊號整合 ──────────────────────────────────────────────────

    def apply_to_alpha_signals(self, results: List[dict]) -> int:
        """將選擇權情緒分數整合回 alpha_signals (bonus/penalty)。

        規則:
          - BULLISH_CONFIRMATION / BEARISH_CONFIRMATION: +0.15 bonus
          - HEDGING_WARNING / CONTRARIAN_WARNING: -0.10 penalty
          - NEUTRAL: 0

        Updates alpha_signals.signal_strength for matching tickers.

        Returns:
            更新筆數
        """
        if not results:
            return 0

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 確保欄位存在
        existing_cols = {
            row[1] for row in cursor.execute("PRAGMA table_info(alpha_signals)").fetchall()
        }
        if "options_sentiment" not in existing_cols:
            cursor.execute("ALTER TABLE alpha_signals ADD COLUMN options_sentiment REAL DEFAULT 0.0")
            logger.info("已新增 alpha_signals.options_sentiment 欄位")
        if "options_signal_type" not in existing_cols:
            cursor.execute("ALTER TABLE alpha_signals ADD COLUMN options_signal_type TEXT DEFAULT ''")
            logger.info("已新增 alpha_signals.options_signal_type 欄位")

        bonus_map = {
            "BULLISH_CONFIRMATION": 0.15,
            "BEARISH_CONFIRMATION": 0.15,
            "HEDGING_WARNING": -0.10,
            "CONTRARIAN_WARNING": -0.10,
            "NEUTRAL": 0.0,
        }

        updated = 0
        for r in results:
            ticker = r["ticker"]
            sentiment = r["sentiment"]
            signal_type = r["signal_type"]
            bonus = bonus_map.get(signal_type, 0.0)

            cursor.execute("""
                UPDATE alpha_signals
                SET signal_strength = signal_strength + ?,
                    options_sentiment = ?,
                    options_signal_type = ?
                WHERE ticker = ?
            """, (bonus, sentiment, signal_type, ticker))

            if cursor.rowcount > 0:
                updated += cursor.rowcount

        conn.commit()
        conn.close()

        logger.info(f"Alpha 訊號整合完成: 更新 {updated} 筆")
        return updated

    # ── 報告生成 ────────────────────────────────────────────────────────

    def generate_report(
        self, results: List[dict], output_path: str
    ) -> str:
        """生成 Markdown 報告。"""
        import os
        now = datetime.now()

        lines = []
        lines.append("# Options Flow Analysis Report")
        lines.append(f"**Generated**: {now.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"**Tickers Analyzed**: {len(results)}")
        lines.append("")

        # ── 方法論 ──
        lines.append("## Methodology")
        lines.append("")
        lines.append("針對 alpha 訊號前 20 檔標的，分析最近到期日的選擇權活動：")
        lines.append("")
        lines.append("1. **Put/Call Ratio**: 成交量加權。< 0.7 偏多，> 1.3 偏空")
        lines.append("2. **異常成交量**: volume > 2x open interest 的合約")
        lines.append("3. **IV Skew**: Call IV vs Put IV 差異")
        lines.append("4. **國會交易交叉比對**:")
        lines.append("   - Congress BUY + 高 call 量 = BULLISH_CONFIRMATION")
        lines.append("   - Congress BUY + 高 put 量 = HEDGING_WARNING")
        lines.append("   - Congress SELL + 高 put 量 = BEARISH_CONFIRMATION")
        lines.append("   - Congress SELL + 高 call 量 = CONTRARIAN_WARNING")
        lines.append("")

        if not results:
            lines.append("*無選擇權資料可分析。*")
            lines.append("")
        else:
            # ── 摘要統計 ──
            bullish = [r for r in results if r["signal_type"] == "BULLISH_CONFIRMATION"]
            bearish = [r for r in results if r["signal_type"] == "BEARISH_CONFIRMATION"]
            hedging = [r for r in results if r["signal_type"] == "HEDGING_WARNING"]
            contrarian = [r for r in results if r["signal_type"] == "CONTRARIAN_WARNING"]
            neutral = [r for r in results if r["signal_type"] == "NEUTRAL"]

            avg_sentiment = sum(r["sentiment"] for r in results) / len(results)
            avg_pc = sum(r["put_call_ratio"] for r in results) / len(results)
            total_unusual = sum(r["unusual_volume_total"] for r in results)

            lines.append("## Summary")
            lines.append("")
            lines.append("| 指標 | 數值 |")
            lines.append("|------|------|")
            lines.append(f"| BULLISH_CONFIRMATION | {len(bullish)} |")
            lines.append(f"| BEARISH_CONFIRMATION | {len(bearish)} |")
            lines.append(f"| HEDGING_WARNING | {len(hedging)} |")
            lines.append(f"| CONTRARIAN_WARNING | {len(contrarian)} |")
            lines.append(f"| NEUTRAL | {len(neutral)} |")
            lines.append(f"| 平均情緒分數 | {avg_sentiment:+.3f} |")
            lines.append(f"| 平均 Put/Call Ratio | {avg_pc:.3f} |")
            lines.append(f"| 異常成交量合約總數 | {total_unusual} |")
            lines.append("")

            # ── 詳細表格 ──
            lines.append("## Detailed Analysis")
            lines.append("")
            lines.append(
                "| # | Ticker | P/C Ratio | Sentiment | Signal Type | "
                "Call Vol | Put Vol | Unusual | Call IV | Put IV | "
                "Congress Dir | Alpha Str |"
            )
            lines.append(
                "|---|--------|-----------|-----------|-------------|"
                "---------|---------|---------|---------|--------|"
                "-------------|-----------|"
            )

            for i, r in enumerate(results, start=1):
                lines.append(
                    f"| {i} | **{r['ticker']}** | {r['put_call_ratio']:.2f} | "
                    f"{r['sentiment']:+.3f} | {r['signal_type']} | "
                    f"{r['call_volume']:,} | {r['put_volume']:,} | "
                    f"{r['unusual_volume_total']} | "
                    f"{r['avg_call_iv']:.2%} | {r['avg_put_iv']:.2%} | "
                    f"{r['congress_direction']} | {r['alpha_signal_strength']:.3f} |"
                )

            lines.append("")

            # ── 異常活動亮點 ──
            unusual_results = [r for r in results if r["unusual_volume_total"] > 0]
            if unusual_results:
                lines.append("## Unusual Activity Highlights")
                lines.append("")
                for r in unusual_results:
                    lines.append(f"### {r['ticker']} ({r['signal_type']})")
                    lines.append("")
                    if r["unusual_calls_detail"]:
                        lines.append("**異常 Call 合約:**")
                        lines.append("")
                        lines.append("| Strike | Volume | OI | Vol/OI | IV |")
                        lines.append("|--------|--------|----|--------|------|")
                        for c in r["unusual_calls_detail"]:
                            lines.append(
                                f"| {c['strike']} | {c['volume']:,} | "
                                f"{c['openInterest']:,} | {c['ratio']:.1f}x | "
                                f"{c['impliedVolatility']:.2%} |"
                            )
                        lines.append("")

                    if r["unusual_puts_detail"]:
                        lines.append("**異常 Put 合約:**")
                        lines.append("")
                        lines.append("| Strike | Volume | OI | Vol/OI | IV |")
                        lines.append("|--------|--------|----|--------|------|")
                        for p in r["unusual_puts_detail"]:
                            lines.append(
                                f"| {p['strike']} | {p['volume']:,} | "
                                f"{p['openInterest']:,} | {p['ratio']:.1f}x | "
                                f"{p['impliedVolatility']:.2%} |"
                            )
                        lines.append("")

        # ── 免責聲明 ──
        lines.append("## Disclaimer")
        lines.append("")
        lines.append(
            "選擇權資料來自 yfinance，可能存在延遲。"
            "本報告僅供研究參考，不構成投資建議。"
            "異常活動不一定代表方向性押注，可能為避險或套利操作。"
        )
        lines.append("")
        lines.append("---")
        lines.append(
            f"*Generated by Political Alpha Monitor — "
            f"Options Flow Analyzer v1.0 — {now.strftime('%Y-%m-%d %H:%M')}*"
        )
        lines.append("")

        report_content = "\n".join(lines)

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(report_content)

        logger.info(f"報告已生成: {output_path}")
        return report_content
