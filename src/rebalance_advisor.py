"""
投資組合再平衡顧問 — 比較現有持倉與最新信號，生成可操作的調整建議

功能:
1. 讀取當前 portfolio_positions (上一次配置)
2. 重新計算最新 conviction scores
3. 比較差異: 新進場 / 應出場 / 權重調整 / 維持
4. 整合 risk_assessments + sector_rotation_signals 提供風險考量
5. 輸出 Rebalance Report

用法:
    python -m src.rebalance_advisor                    # 標準報告
    python -m src.rebalance_advisor --threshold 0.02   # 調整門檻 2%
    python -m src.rebalance_advisor --dry-run           # 只看建議，不寫入
"""

import argparse
import logging
import sqlite3
from collections import defaultdict
from datetime import datetime, date
from typing import Dict, List, Optional, Tuple

from src.config import DB_PATH, PROJECT_ROOT
from src.portfolio_optimizer import (
    TickerScorer,
    load_congress_trades,
    load_sqs_scores,
    load_convergence_signals,
    load_sector_map,
    load_politician_rankings,
)

logger = logging.getLogger("RebalanceAdvisor")

# ── 常數 ──
WEIGHT_CHANGE_THRESHOLD = 0.01   # 權重變動 > 1% 才報告
NEW_ENTRY_MIN_SCORE = 40.0       # 新進場最低 conviction score
EXIT_MAX_SCORE = 25.0            # 低於此分數建議出場


# ══════════════════════════════════════════════════════════════════════
#  資料讀取
# ══════════════════════════════════════════════════════════════════════

def load_current_positions(db_path: str = None) -> Dict[str, dict]:
    """讀取當前 portfolio_positions，以 ticker 為 key"""
    if db_path is None:
        db_path = DB_PATH
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT ticker, sector, weight, conviction_score, expected_alpha,
               volatility_30d, sharpe_estimate, reasoning, created_at
        FROM portfolio_positions
        ORDER BY weight DESC
    """).fetchall()
    conn.close()
    result = {}
    for r in rows:
        result[r["ticker"]] = dict(r)
    return result


def load_risk_warnings(db_path: str = None) -> Dict[str, List[str]]:
    """讀取最新 risk_assessments，以 ticker 為 key 整理風險警告"""
    if db_path is None:
        db_path = DB_PATH
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("""
            SELECT ticker, risk_score, violations, actions
            FROM risk_assessments
            ORDER BY risk_score DESC
        """).fetchall()
        conn.close()
        result = {}
        for r in rows:
            if r["risk_score"] and r["risk_score"] > 50:
                result[r["ticker"]] = {
                    "risk_score": r["risk_score"],
                    "violations": r["violations"] or "",
                    "actions": r["actions"] or "",
                }
        return result
    except Exception:
        conn.close()
        return {}


def load_sector_rotation_recs(db_path: str = None) -> Dict[str, dict]:
    """讀取 sector_rotation_signals 的板塊建議"""
    if db_path is None:
        db_path = DB_PATH
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("""
            SELECT sector, etf_ticker, direction, signal_strength,
                   momentum_score, rotation_type
            FROM sector_rotation_signals
            ORDER BY signal_strength DESC
        """).fetchall()
        conn.close()
        result = {}
        for r in rows:
            result[r["sector"]] = dict(r)
        return result
    except Exception:
        conn.close()
        return {}


# ══════════════════════════════════════════════════════════════════════
#  差異分析引擎
# ══════════════════════════════════════════════════════════════════════

class RebalanceAdvisor:
    """比較現有持倉與最新評分，生成再平衡建議"""

    def __init__(
        self,
        current_positions: Dict[str, dict],
        new_scores: List[dict],
        risk_warnings: Optional[Dict[str, dict]] = None,
        sector_recs: Optional[Dict[str, dict]] = None,
        threshold: float = WEIGHT_CHANGE_THRESHOLD,
    ):
        self.current = current_positions
        self.new_scores = {s["ticker"]: s for s in new_scores}
        self.risk_warnings = risk_warnings or {}
        self.sector_recs = sector_recs or {}
        self.threshold = threshold

    def analyze(self) -> dict:
        """執行差異分析，回傳分類建議"""
        current_tickers = set(self.current.keys())
        new_tickers = set(self.new_scores.keys())

        # 分類
        new_entries = []     # 新進場建議
        exits = []           # 出場建議
        increases = []       # 增加權重
        decreases = []       # 減少權重
        holds = []           # 維持不變

        # 1. 新進場: 在 new_scores 但不在 current
        for ticker in (new_tickers - current_tickers):
            score = self.new_scores[ticker]
            if score["conviction_score"] >= NEW_ENTRY_MIN_SCORE:
                new_entries.append({
                    "ticker": ticker,
                    "sector": score["sector"],
                    "conviction_score": score["conviction_score"],
                    "expected_alpha": score["expected_alpha"],
                    "buy_count": score["buy_count"],
                    "reasoning": score["reasoning"],
                    "action": "BUY",
                    "risk_note": self._get_risk_note(ticker, score["sector"]),
                })

        # 2. 出場: 在 current 但不在 new_scores (或分數過低)
        for ticker in current_tickers:
            cur = self.current[ticker]
            new = self.new_scores.get(ticker)
            if new is None:
                exits.append({
                    "ticker": ticker,
                    "sector": cur["sector"],
                    "old_weight": cur["weight"],
                    "old_score": cur["conviction_score"],
                    "reason": "不在最新評分中（無近期 Buy 交易）",
                    "action": "SELL",
                    "risk_note": self._get_risk_note(ticker, cur["sector"]),
                })
            elif new["conviction_score"] < EXIT_MAX_SCORE:
                exits.append({
                    "ticker": ticker,
                    "sector": cur["sector"],
                    "old_weight": cur["weight"],
                    "old_score": cur["conviction_score"],
                    "new_score": new["conviction_score"],
                    "reason": f"分數降至 {new['conviction_score']:.1f} (門檻 {EXIT_MAX_SCORE})",
                    "action": "SELL",
                    "risk_note": self._get_risk_note(ticker, cur["sector"]),
                })

        # 3. 既有持倉: 比較分數變化
        for ticker in (current_tickers & new_tickers):
            cur = self.current[ticker]
            new = self.new_scores[ticker]

            if new["conviction_score"] < EXIT_MAX_SCORE:
                continue  # 已在 exits 處理

            score_delta = new["conviction_score"] - cur["conviction_score"]
            # 根據分數變化推估權重變動方向
            if score_delta > 5.0:
                increases.append({
                    "ticker": ticker,
                    "sector": cur["sector"],
                    "old_weight": cur["weight"],
                    "old_score": cur["conviction_score"],
                    "new_score": new["conviction_score"],
                    "score_delta": round(score_delta, 1),
                    "expected_alpha": new["expected_alpha"],
                    "action": "INCREASE",
                    "risk_note": self._get_risk_note(ticker, cur["sector"]),
                })
            elif score_delta < -5.0:
                decreases.append({
                    "ticker": ticker,
                    "sector": cur["sector"],
                    "old_weight": cur["weight"],
                    "old_score": cur["conviction_score"],
                    "new_score": new["conviction_score"],
                    "score_delta": round(score_delta, 1),
                    "expected_alpha": new["expected_alpha"],
                    "action": "DECREASE",
                    "risk_note": self._get_risk_note(ticker, cur["sector"]),
                })
            else:
                holds.append({
                    "ticker": ticker,
                    "sector": cur["sector"],
                    "old_weight": cur["weight"],
                    "old_score": cur["conviction_score"],
                    "new_score": new["conviction_score"],
                    "score_delta": round(score_delta, 1),
                    "action": "HOLD",
                })

        # 排序
        new_entries.sort(key=lambda x: x["conviction_score"], reverse=True)
        exits.sort(key=lambda x: x.get("old_weight", 0), reverse=True)
        increases.sort(key=lambda x: x["score_delta"], reverse=True)
        decreases.sort(key=lambda x: x["score_delta"])

        return {
            "new_entries": new_entries,
            "exits": exits,
            "increases": increases,
            "decreases": decreases,
            "holds": holds,
            "summary": {
                "current_positions": len(current_tickers),
                "new_candidates": len(new_tickers),
                "actions_buy": len(new_entries),
                "actions_sell": len(exits),
                "actions_increase": len(increases),
                "actions_decrease": len(decreases),
                "actions_hold": len(holds),
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            },
        }

    def _get_risk_note(self, ticker: str, sector: str) -> str:
        """整合風險警告和板塊建議"""
        notes = []
        # 個股風險
        risk = self.risk_warnings.get(ticker)
        if risk:
            notes.append(f"Risk={risk['risk_score']:.0f}")
        # 板塊建議
        sec_rec = self.sector_recs.get(sector)
        if sec_rec:
            rot = sec_rec.get("rotation_type", "")
            if "DECELERATING" in rot or "REVERSING_DOWN" in rot:
                notes.append(f"Sector {rot}")
            elif "ACCELERATING" in rot:
                notes.append(f"Sector ACCELERATING")
        return "; ".join(notes) if notes else ""


# ══════════════════════════════════════════════════════════════════════
#  報告輸出
# ══════════════════════════════════════════════════════════════════════

def print_rebalance_report(result: dict):
    """格式化輸出再平衡建議"""
    summary = result["summary"]

    print()
    print("=" * 72)
    print("   Portfolio Rebalance Advisor — Political Alpha Monitor")
    print(f"   {summary['timestamp']}")
    print("=" * 72)
    print()

    # 摘要
    print("  [Summary]")
    print(f"    Current positions:   {summary['current_positions']}")
    print(f"    New candidates:      {summary['new_candidates']}")
    print(f"    Actions: BUY={summary['actions_buy']}  "
          f"SELL={summary['actions_sell']}  "
          f"INCREASE={summary['actions_increase']}  "
          f"DECREASE={summary['actions_decrease']}  "
          f"HOLD={summary['actions_hold']}")
    print()

    # 新進場
    entries = result["new_entries"]
    if entries:
        print(f"  [NEW ENTRIES] ({len(entries)})")
        print(f"  {'Ticker':<8s} {'Sector':<20s} {'Score':>6s} {'Alpha':>8s} {'Buys':>5s}  Risk")
        print("  " + "-" * 65)
        for e in entries[:10]:
            risk = e.get("risk_note", "")
            risk_str = f"  {risk}" if risk else ""
            print(f"  {e['ticker']:<8s} {e['sector']:<20s} {e['conviction_score']:6.1f} "
                  f"{e['expected_alpha']:.4%} {e['buy_count']:5d}{risk_str}")
        print()

    # 出場
    exits = result["exits"]
    if exits:
        print(f"  [EXITS] ({len(exits)})")
        print(f"  {'Ticker':<8s} {'Sector':<20s} {'Weight':>7s} {'OldScore':>8s}  Reason")
        print("  " + "-" * 65)
        for e in exits[:10]:
            print(f"  {e['ticker']:<8s} {e['sector']:<20s} {e['old_weight']:7.2%} "
                  f"{e['old_score']:8.1f}  {e['reason'][:40]}")
        print()

    # 增加權重
    increases = result["increases"]
    if increases:
        print(f"  [INCREASE WEIGHT] ({len(increases)})")
        print(f"  {'Ticker':<8s} {'Sector':<20s} {'Weight':>7s} {'Delta':>7s} {'NewScore':>8s}")
        print("  " + "-" * 55)
        for e in increases[:10]:
            print(f"  {e['ticker']:<8s} {e['sector']:<20s} {e['old_weight']:7.2%} "
                  f"{e['score_delta']:+7.1f} {e['new_score']:8.1f}")
        print()

    # 減少權重
    decreases = result["decreases"]
    if decreases:
        print(f"  [DECREASE WEIGHT] ({len(decreases)})")
        print(f"  {'Ticker':<8s} {'Sector':<20s} {'Weight':>7s} {'Delta':>7s} {'NewScore':>8s}")
        print("  " + "-" * 55)
        for e in decreases[:10]:
            print(f"  {e['ticker']:<8s} {e['sector']:<20s} {e['old_weight']:7.2%} "
                  f"{e['score_delta']:+7.1f} {e['new_score']:8.1f}")
        print()

    # 維持
    holds = result["holds"]
    if holds:
        print(f"  [HOLD] ({len(holds)})")
        for e in holds[:5]:
            print(f"    {e['ticker']:<8s} weight={e['old_weight']:.2%}  "
                  f"score={e['old_score']:.1f}->{e['new_score']:.1f} ({e['score_delta']:+.1f})")
        if len(holds) > 5:
            print(f"    ... and {len(holds) - 5} more")
        print()

    # Turnover 估算
    total_actions = (summary['actions_buy'] + summary['actions_sell']
                     + summary['actions_increase'] + summary['actions_decrease'])
    total_all = total_actions + summary['actions_hold']
    if total_all > 0:
        turnover = total_actions / total_all
        print(f"  [TURNOVER ESTIMATE]")
        print(f"    Portfolio turnover: {turnover:.0%}")
        if turnover < 0.2:
            print(f"    Status: LOW turnover — minimal rebalancing needed")
        elif turnover < 0.5:
            print(f"    Status: MODERATE turnover — selective rebalancing")
        else:
            print(f"    Status: HIGH turnover — significant portfolio restructuring")
    print()
    print("=" * 72)
    print()


def save_rebalance_to_db(result: dict, db_path: str = None):
    """將再平衡建議儲存到 rebalance_history 表"""
    if db_path is None:
        db_path = DB_PATH
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rebalance_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            action TEXT NOT NULL,
            sector TEXT,
            old_weight REAL,
            old_score REAL,
            new_score REAL,
            score_delta REAL,
            expected_alpha REAL,
            risk_note TEXT,
            reason TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    records = []

    for entry in result["new_entries"]:
        records.append((
            entry["ticker"], "BUY", entry["sector"],
            None, None, entry["conviction_score"], None,
            entry["expected_alpha"], entry.get("risk_note", ""),
            entry.get("reasoning", ""), now,
        ))

    for entry in result["exits"]:
        records.append((
            entry["ticker"], "SELL", entry["sector"],
            entry["old_weight"], entry["old_score"],
            entry.get("new_score"), None,
            None, entry.get("risk_note", ""),
            entry.get("reason", ""), now,
        ))

    for entry in result["increases"]:
        records.append((
            entry["ticker"], "INCREASE", entry["sector"],
            entry["old_weight"], entry["old_score"],
            entry["new_score"], entry["score_delta"],
            entry["expected_alpha"], entry.get("risk_note", ""),
            "", now,
        ))

    for entry in result["decreases"]:
        records.append((
            entry["ticker"], "DECREASE", entry["sector"],
            entry["old_weight"], entry["old_score"],
            entry["new_score"], entry["score_delta"],
            entry["expected_alpha"], entry.get("risk_note", ""),
            "", now,
        ))

    if records:
        cursor.executemany("""
            INSERT INTO rebalance_history
            (ticker, action, sector, old_weight, old_score, new_score,
             score_delta, expected_alpha, risk_note, reason, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, records)

    conn.commit()
    conn.close()
    logger.info(f"Saved {len(records)} rebalance records to rebalance_history")
    return len(records)


# ══════════════════════════════════════════════════════════════════════
#  主流程
# ══════════════════════════════════════════════════════════════════════

def run_rebalance_analysis(
    days: int = 90,
    threshold: float = WEIGHT_CHANGE_THRESHOLD,
    dry_run: bool = False,
    db_path: str = None,
) -> dict:
    """完整再平衡分析流程"""
    if db_path is None:
        db_path = DB_PATH

    print("\n[1/5] Loading current portfolio positions...")
    current = load_current_positions(db_path)
    print(f"      {len(current)} positions loaded")
    if not current:
        print("      [WARN] No current positions — run portfolio_optimizer first")

    print("[2/5] Computing fresh conviction scores...")
    trades = load_congress_trades(db_path, days=days)
    sqs_map = load_sqs_scores(db_path)
    conv_map = load_convergence_signals(db_path)
    sector_map = load_sector_map()
    pol_map = load_politician_rankings(db_path)

    scorer = TickerScorer(trades, sqs_map, conv_map, sector_map, pol_map)
    new_scores = scorer.score_all()
    print(f"      {len(new_scores)} tickers scored")

    print("[3/5] Loading risk warnings and sector signals...")
    risk_warnings = load_risk_warnings(db_path)
    sector_recs = load_sector_rotation_recs(db_path)
    print(f"      {len(risk_warnings)} risk warnings, {len(sector_recs)} sector signals")

    print("[4/5] Analyzing rebalance opportunities...")
    advisor = RebalanceAdvisor(
        current_positions=current,
        new_scores=new_scores,
        risk_warnings=risk_warnings,
        sector_recs=sector_recs,
        threshold=threshold,
    )
    result = advisor.analyze()

    # 輸出報告
    print_rebalance_report(result)

    # 儲存
    if not dry_run:
        print("[5/5] Saving rebalance history...")
        count = save_rebalance_to_db(result, db_path)
        print(f"      {count} records saved to rebalance_history")
    else:
        print("[5/5] Dry run — no DB writes")

    return result


# ══════════════════════════════════════════════════════════════════════
#  CLI 入口
# ══════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="投資組合再平衡顧問 — Political Alpha Monitor",
    )
    parser.add_argument("--days", type=int, default=90,
                        help="評分回溯天數 (預設 90)")
    parser.add_argument("--threshold", type=float, default=WEIGHT_CHANGE_THRESHOLD,
                        help=f"權重變動門檻 (預設 {WEIGHT_CHANGE_THRESHOLD})")
    parser.add_argument("--dry-run", action="store_true",
                        help="只看建議，不寫入 DB")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    run_rebalance_analysis(
        days=args.days,
        threshold=args.threshold,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
