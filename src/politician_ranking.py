"""
議員交易排名模組 — Politician Intelligence Score (PIS)

根據 congress_trades 資料表中的交易紀錄，為每位議員計算綜合交易情報分數。
分數由四個維度組成：
  1. 活躍度 (Activity)        — 每月交易頻率
  2. 信念度 (Conviction)      — 平均交易規模
  3. 分散度 (Diversification) — 投資標的多樣性
  4. 時效性 (Timing)          — 交易到申報的時間差

用法:
    python -m src.politician_ranking              # 全部議員排名
    python -m src.politician_ranking --top 10     # 前 10 名
    python -m src.politician_ranking --chamber Senate  # 僅參議員
"""

import argparse
import logging
import re
import sqlite3
from datetime import datetime, date
from typing import Optional, List, Dict, Tuple

from src.config import DB_PATH

logger = logging.getLogger("PoliticianRanking")

# ── 金額區間 → 下界值映射 ──
# 美國國會財務揭露的標準金額區間
AMOUNT_LOWER_BOUNDS: Dict[str, float] = {
    "$1,001 - $15,000": 1_001,
    "$15,001 - $50,000": 15_001,
    "$50,001 - $100,000": 50_001,
    "$100,001 - $250,000": 100_001,
    "$250,001 - $500,000": 250_001,
    "$500,001 - $1,000,000": 500_001,
    "$1,000,001 - $5,000,000": 1_000_001,
    "$5,000,001 - $25,000,000": 5_000_001,
    "$25,000,001 - $50,000,000": 25_000_001,
    "$50,000,001 +": 50_000_001,
    "Over $50,000,000": 50_000_001,
}


def parse_amount_lower_bound(amount_range: str) -> float:
    """
    解析金額區間字串，回傳下界值。
    優先查表，若不在表中則用正規表達式提取第一個金額數字。
    """
    if not amount_range:
        return 0.0

    # 先查已知映射表
    cleaned = amount_range.strip()
    if cleaned in AMOUNT_LOWER_BOUNDS:
        return AMOUNT_LOWER_BOUNDS[cleaned]

    # Fallback: 正規表達式提取第一個 $ 數字
    match = re.search(r'\$([0-9,]+)', cleaned)
    if match:
        try:
            return float(match.group(1).replace(',', ''))
        except ValueError:
            pass

    logger.warning(f"無法解析金額區間: {amount_range!r}，回傳 0")
    return 0.0


def _calculate_month_span(dates: List[str]) -> float:
    """
    計算日期列表跨越的月數（至少回傳 1.0，避免除以零）。
    日期格式: YYYY-MM-DD
    """
    if not dates:
        return 1.0

    parsed = []
    for d in dates:
        if d:
            try:
                parsed.append(datetime.strptime(d, "%Y-%m-%d").date())
            except (ValueError, TypeError):
                continue

    if len(parsed) < 2:
        return 1.0

    earliest = min(parsed)
    latest = max(parsed)
    delta_days = (latest - earliest).days
    months = delta_days / 30.44  # 平均每月天數
    return max(months, 1.0)


def _calculate_filing_lag(transaction_date: str, filing_date: str) -> Optional[float]:
    """
    計算交易日到申報日的天數差。
    回傳 None 表示日期無效或缺失。
    """
    if not transaction_date or not filing_date:
        return None
    try:
        t_date = datetime.strptime(transaction_date, "%Y-%m-%d").date()
        f_date = datetime.strptime(filing_date, "%Y-%m-%d").date()
        lag = (f_date - t_date).days
        # 申報日應在交易日之後，若為負則視為異常，仍回傳絕對值
        return abs(lag) if lag != 0 else 0.0
    except (ValueError, TypeError):
        return None


class PoliticianRanker:
    """議員交易排名引擎"""

    # PIS 各維度滿分權重（總計 100 分）
    WEIGHT_ACTIVITY = 25.0
    WEIGHT_CONVICTION = 25.0
    WEIGHT_DIVERSIFICATION = 25.0
    WEIGHT_TIMING = 25.0

    def __init__(self, db_path: str = None):
        self.db_path = db_path or DB_PATH

    def _fetch_trades(self, chamber: Optional[str] = None) -> List[Dict]:
        """從 congress_trades 讀取所有交易紀錄"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        query = """
            SELECT politician_name, ticker, transaction_type,
                   transaction_date, filing_date, chamber, amount_range
            FROM congress_trades
        """
        params: list = []

        if chamber:
            query += " WHERE chamber = ?"
            params.append(chamber)

        cursor.execute(query, params)
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()

        logger.info(f"讀取 {len(rows)} 筆交易紀錄" +
                    (f" (篩選: {chamber})" if chamber else ""))
        return rows

    def _aggregate_by_politician(self, trades: List[Dict]) -> Dict[str, Dict]:
        """
        將交易紀錄按議員聚合，計算原始統計量。
        回傳格式: {politician_name: {...metrics...}}
        """
        politicians: Dict[str, Dict] = {}

        for trade in trades:
            name = trade["politician_name"]
            if name not in politicians:
                politicians[name] = {
                    "politician_name": name,
                    "chamber": trade["chamber"],
                    "total_trades": 0,
                    "buy_count": 0,
                    "sale_count": 0,
                    "exchange_count": 0,
                    "tickers": set(),
                    "amount_values": [],
                    "transaction_dates": [],
                    "filing_lags": [],
                }

            p = politicians[name]
            p["total_trades"] += 1

            # 交易類型計數
            tx_type = (trade["transaction_type"] or "").strip()
            if tx_type.lower().startswith("buy") or tx_type.lower() == "purchase":
                p["buy_count"] += 1
            elif tx_type.lower().startswith("sale") or tx_type.lower() == "sell":
                p["sale_count"] += 1
            elif tx_type.lower() == "exchange":
                p["exchange_count"] += 1

            # 追蹤 ticker
            ticker = trade.get("ticker")
            if ticker:
                p["tickers"].add(ticker)

            # 金額下界
            amount = parse_amount_lower_bound(trade.get("amount_range", ""))
            if amount > 0:
                p["amount_values"].append(amount)

            # 交易日期
            if trade.get("transaction_date"):
                p["transaction_dates"].append(trade["transaction_date"])

            # 申報延遲
            lag = _calculate_filing_lag(
                trade.get("transaction_date"),
                trade.get("filing_date")
            )
            if lag is not None:
                p["filing_lags"].append(lag)

            # 如果議員在多個 chamber 出現，取最近的
            if trade["chamber"]:
                p["chamber"] = trade["chamber"]

        return politicians

    def _compute_metrics(self, politicians: Dict[str, Dict]) -> List[Dict]:
        """
        根據聚合資料計算每位議員的衍生指標。
        """
        results = []

        for name, p in politicians.items():
            total = p["total_trades"]
            unique_tickers = len(p["tickers"])

            # 平均交易規模
            avg_trade_size = (
                sum(p["amount_values"]) / len(p["amount_values"])
                if p["amount_values"] else 0.0
            )

            # 每月交易頻率
            month_span = _calculate_month_span(p["transaction_dates"])
            trades_per_month = total / month_span

            # 買賣比 (Buy/Sale ratio)
            buy_sale_ratio = (
                p["buy_count"] / p["sale_count"]
                if p["sale_count"] > 0 else
                float(p["buy_count"]) if p["buy_count"] > 0 else 0.0
            )

            # 平均申報延遲（天）
            avg_filing_lag = (
                sum(p["filing_lags"]) / len(p["filing_lags"])
                if p["filing_lags"] else None
            )

            # 分散度指標 (unique_tickers / total_trades)
            diversification_ratio = unique_tickers / total if total > 0 else 0.0

            results.append({
                "politician_name": name,
                "chamber": p["chamber"],
                "total_trades": total,
                "avg_trade_size": avg_trade_size,
                "trades_per_month": trades_per_month,
                "unique_tickers": unique_tickers,
                "buy_count": p["buy_count"],
                "sale_count": p["sale_count"],
                "buy_sale_ratio": buy_sale_ratio,
                "avg_filing_lag_days": avg_filing_lag,
                "diversification_ratio": diversification_ratio,
            })

        return results

    def _score_politicians(self, metrics_list: List[Dict]) -> List[Dict]:
        """
        計算 Politician Intelligence Score (PIS)。
        每個維度 0-25 分，總計 0-100 分。使用 min-max 正規化。
        """
        if not metrics_list:
            return []

        # ── 收集各維度的數值範圍，用於正規化 ──
        all_tpm = [m["trades_per_month"] for m in metrics_list]
        all_size = [m["avg_trade_size"] for m in metrics_list]
        all_div = [m["diversification_ratio"] for m in metrics_list]
        all_lag = [m["avg_filing_lag_days"] for m in metrics_list
                   if m["avg_filing_lag_days"] is not None]

        def _normalize(value: float, values: List[float]) -> float:
            """Min-Max 正規化到 [0, 1]"""
            if not values:
                return 0.0
            min_v = min(values)
            max_v = max(values)
            if max_v == min_v:
                return 1.0  # 所有值相同，給滿分
            return (value - min_v) / (max_v - min_v)

        def _normalize_inverse(value: float, values: List[float]) -> float:
            """反向正規化（越小越好）"""
            if not values:
                return 0.0
            min_v = min(values)
            max_v = max(values)
            if max_v == min_v:
                return 1.0
            return 1.0 - (value - min_v) / (max_v - min_v)

        for m in metrics_list:
            # 活躍度分數：交易頻率越高越好
            pis_activity = _normalize(m["trades_per_month"], all_tpm) * self.WEIGHT_ACTIVITY

            # 信念度分數：平均交易規模越大越好
            pis_conviction = _normalize(m["avg_trade_size"], all_size) * self.WEIGHT_CONVICTION

            # 分散度分數：多樣性越高越好
            pis_diversification = _normalize(m["diversification_ratio"], all_div) * self.WEIGHT_DIVERSIFICATION

            # 時效性分數：申報延遲越短越好（反向）
            if m["avg_filing_lag_days"] is not None and all_lag:
                pis_timing = _normalize_inverse(m["avg_filing_lag_days"], all_lag) * self.WEIGHT_TIMING
            else:
                # 無申報延遲資料，給中間分數
                pis_timing = self.WEIGHT_TIMING * 0.5

            pis_total = pis_activity + pis_conviction + pis_diversification + pis_timing

            m["pis_activity"] = round(pis_activity, 2)
            m["pis_conviction"] = round(pis_conviction, 2)
            m["pis_diversification"] = round(pis_diversification, 2)
            m["pis_timing"] = round(pis_timing, 2)
            m["pis_total"] = round(pis_total, 2)

        # 按 PIS 總分降序排名
        metrics_list.sort(key=lambda x: x["pis_total"], reverse=True)
        for i, m in enumerate(metrics_list, start=1):
            m["rank"] = i

        return metrics_list

    def _save_rankings(self, rankings: List[Dict]):
        """
        將排名結果寫入 politician_rankings 資料表。
        每次執行會清空舊資料，重新寫入。
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 建表（如不存在）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS politician_rankings (
                politician_name TEXT PRIMARY KEY,
                chamber TEXT,
                total_trades INTEGER,
                avg_trade_size REAL,
                trades_per_month REAL,
                unique_tickers INTEGER,
                buy_count INTEGER,
                sale_count INTEGER,
                buy_sale_ratio REAL,
                avg_filing_lag_days REAL,
                diversification_ratio REAL,
                pis_activity REAL,
                pis_conviction REAL,
                pis_diversification REAL,
                pis_timing REAL,
                pis_total REAL,
                rank INTEGER,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 清空舊資料
        cursor.execute("DELETE FROM politician_rankings")

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        for r in rankings:
            cursor.execute('''
                INSERT INTO politician_rankings (
                    politician_name, chamber, total_trades, avg_trade_size,
                    trades_per_month, unique_tickers, buy_count, sale_count,
                    buy_sale_ratio, avg_filing_lag_days, diversification_ratio,
                    pis_activity, pis_conviction, pis_diversification,
                    pis_timing, pis_total, rank, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                r["politician_name"],
                r["chamber"],
                r["total_trades"],
                round(r["avg_trade_size"], 2),
                round(r["trades_per_month"], 4),
                r["unique_tickers"],
                r["buy_count"],
                r["sale_count"],
                round(r["buy_sale_ratio"], 4),
                round(r["avg_filing_lag_days"], 1) if r["avg_filing_lag_days"] is not None else None,
                round(r["diversification_ratio"], 4),
                r["pis_activity"],
                r["pis_conviction"],
                r["pis_diversification"],
                r["pis_timing"],
                r["pis_total"],
                r["rank"],
                now,
            ))

        conn.commit()
        conn.close()
        logger.info(f"已將 {len(rankings)} 位議員排名寫入 politician_rankings 表")

    def rank(self, chamber: Optional[str] = None, top_n: Optional[int] = None) -> List[Dict]:
        """
        執行完整排名流程：讀取 → 聚合 → 計算指標 → 評分 → 儲存。
        回傳排名結果列表。
        """
        # Step 1: 讀取交易紀錄
        trades = self._fetch_trades(chamber=chamber)
        if not trades:
            logger.warning("congress_trades 表中無資料，無法產生排名")
            return []

        # Step 2: 按議員聚合
        politicians = self._aggregate_by_politician(trades)

        # Step 3: 計算衍生指標
        metrics_list = self._compute_metrics(politicians)

        # Step 4: 計算 PIS 並排名
        rankings = self._score_politicians(metrics_list)

        # Step 5: 儲存到資料庫
        self._save_rankings(rankings)

        # Step 6: 回傳（可選擇只回傳前 N 名）
        if top_n:
            return rankings[:top_n]
        return rankings


def print_ranking_table(rankings: List[Dict], title: str = "議員交易情報排名"):
    """
    格式化輸出排名表格到終端。
    """
    if not rankings:
        print("\n  [無資料] congress_trades 表中沒有交易紀錄。\n")
        return

    # ── 表頭 ──
    print()
    print(f"{'=' * 120}")
    print(f"  {title}")
    print(f"  更新時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  共 {len(rankings)} 位議員")
    print(f"{'=' * 120}")

    # ── 欄位標題 ──
    header = (
        f"{'排名':>4}  "
        f"{'議員姓名':<30}  "
        f"{'院別':<7}  "
        f"{'交易數':>6}  "
        f"{'月均頻率':>8}  "
        f"{'均額($)':>12}  "
        f"{'標的數':>6}  "
        f"{'買/賣':>6}  "
        f"{'申報延遲':>8}  "
        f"{'PIS分數':>7}"
    )
    print(f"\n{header}")
    print(f"{'-' * 120}")

    # ── 資料列 ──
    for r in rankings:
        # 格式化買賣比
        bsr = f"{r['buy_sale_ratio']:.1f}" if r['buy_sale_ratio'] is not None else "N/A"

        # 格式化申報延遲
        lag = f"{r['avg_filing_lag_days']:.0f}天" if r['avg_filing_lag_days'] is not None else "N/A"

        # 格式化平均金額
        avg_size = f"{r['avg_trade_size']:,.0f}"

        # 格式化月均頻率
        tpm = f"{r['trades_per_month']:.1f}"

        # PIS 總分帶分級標示
        pis = r["pis_total"]
        if pis >= 75:
            grade = "A"
        elif pis >= 50:
            grade = "B"
        elif pis >= 25:
            grade = "C"
        else:
            grade = "D"

        row = (
            f"{r['rank']:>4}  "
            f"{r['politician_name']:<30}  "
            f"{r['chamber']:<7}  "
            f"{r['total_trades']:>6}  "
            f"{tpm:>8}  "
            f"{avg_size:>12}  "
            f"{r['unique_tickers']:>6}  "
            f"{bsr:>6}  "
            f"{lag:>8}  "
            f"{pis:>5.1f} {grade}"
        )
        print(row)

    print(f"{'-' * 120}")

    # ── PIS 維度明細（前 5 名）──
    top5 = rankings[:5]
    if top5:
        print(f"\n  PIS 維度明細（前 5 名，各維度滿分 25 分）:")
        print(f"  {'議員姓名':<30}  {'活躍度':>7}  {'信念度':>7}  {'分散度':>7}  {'時效性':>7}  {'總分':>7}")
        print(f"  {'-' * 100}")
        for r in top5:
            print(
                f"  {r['politician_name']:<30}  "
                f"{r['pis_activity']:>7.1f}  "
                f"{r['pis_conviction']:>7.1f}  "
                f"{r['pis_diversification']:>7.1f}  "
                f"{r['pis_timing']:>7.1f}  "
                f"{r['pis_total']:>7.1f}"
            )

    print(f"\n{'=' * 120}\n")


def main():
    """CLI 入口"""
    parser = argparse.ArgumentParser(
        description="議員交易情報排名系統 (Politician Intelligence Score)"
    )
    parser.add_argument(
        "--top", type=int, default=None,
        help="僅顯示前 N 名（預設: 全部）"
    )
    parser.add_argument(
        "--chamber", type=str, choices=["Senate", "House"], default=None,
        help="篩選院別（預設: 兩院皆含）"
    )
    parser.add_argument(
        "--db", type=str, default=None,
        help="指定資料庫路徑（預設: data/data.db）"
    )
    args = parser.parse_args()

    # 設定日誌
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    # 執行排名
    ranker = PoliticianRanker(db_path=args.db)
    rankings = ranker.rank(chamber=args.chamber, top_n=args.top)

    # 輸出結果
    title = "議員交易情報排名 (Politician Intelligence Score)"
    if args.chamber:
        title += f" — {args.chamber}"
    if args.top:
        title += f" — Top {args.top}"

    print_ranking_table(rankings, title=title)


if __name__ == "__main__":
    main()
