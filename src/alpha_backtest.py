"""Alpha 回測引擎 — Event Study 方法。

使用國會議員交易申報資料，計算申報日後的累積異常報酬 (CAR)，
評估國會交易是否存在 alpha。

方法論：
- 事件日：Filing Date（申報日）
- 事件窗口：[0, +5], [0, +20], [0, +60] 交易日
- Benchmark：SPY (S&P 500 ETF)
- 異常報酬：AR = R_stock - R_SPY
- 累積異常報酬：CAR = sum(AR)
"""

import sqlite3
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple
from scipy import stats
from pathlib import Path

from src.config import DB_PATH


class AlphaBacktester:
    """國會交易 Alpha 回測引擎。"""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.price_cache: Dict[str, pd.DataFrame] = {}
        self.spy_prices: Optional[pd.DataFrame] = None

    # ── 資料取得 ──

    def get_backtest_universe(self) -> pd.DataFrame:
        """取得可回測的交易數據。"""
        query = """
        SELECT politician_name, ticker, transaction_type, transaction_date,
               filing_date, amount_range, chamber, owner, extraction_confidence
        FROM congress_trades
        WHERE ticker IS NOT NULL AND ticker != ''
          AND transaction_type IN ('Buy', 'Sale', 'Sale (Full)', 'Sale (Partial)')
          AND transaction_date <= DATE('now')
        ORDER BY filing_date DESC
        """
        conn = sqlite3.connect(self.db_path)
        df = pd.read_sql_query(query, conn)
        conn.close()

        # 轉換日期欄位
        df["transaction_date"] = pd.to_datetime(df["transaction_date"], errors="coerce")
        df["filing_date"] = pd.to_datetime(df["filing_date"], errors="coerce")

        # 過濾無效日期
        df = df.dropna(subset=["filing_date"])

        # 計算 filing lag（天數）
        df["filing_lag"] = (df["filing_date"] - df["transaction_date"]).dt.days

        # 解析金額範圍 → 取下限用於分層
        df["amount_lower"] = df["amount_range"].apply(self._parse_amount_lower)

        # 統一交易方向
        df["direction"] = df["transaction_type"].apply(
            lambda x: "Buy" if x == "Buy" else "Sale"
        )

        # 標準化 ticker（yfinance 用 - 而非 .）
        df["ticker"] = df["ticker"].str.replace(".", "-", regex=False)

        print(f"[回測宇宙] 共 {len(df)} 筆交易，{df['ticker'].nunique()} 個標的")
        return df

    def download_prices(self, tickers: List[str], start: str, end: str) -> Dict[str, pd.DataFrame]:
        """批量下載股價，回傳 {ticker: DataFrame(Date, Close)} 字典。"""
        # 加入 SPY 作為 benchmark
        all_tickers = list(set(tickers + ["SPY"]))

        print(f"[下載股價] 共 {len(all_tickers)} 個標的，期間 {start} ~ {end}")

        # 批量下載（yfinance 建議方式）
        try:
            data = yf.download(
                all_tickers,
                start=start,
                end=end,
                auto_adjust=True,
                progress=False,
                threads=True,
            )
        except Exception as e:
            print(f"[警告] 批量下載失敗: {e}，改用逐一下載")
            data = pd.DataFrame()

        # 解析結果到 price_cache
        failed_tickers = []

        if not data.empty:
            for ticker in all_tickers:
                try:
                    if len(all_tickers) == 1:
                        # 單一標的，data 直接是 DataFrame
                        prices = data[["Close"]].copy()
                    else:
                        # 多標的，data 是 MultiIndex columns
                        prices = data["Close"][[ticker]].copy()
                        prices.columns = ["Close"]

                    prices = prices.dropna()
                    if len(prices) > 0:
                        self.price_cache[ticker] = prices
                    else:
                        failed_tickers.append(ticker)
                except (KeyError, TypeError):
                    failed_tickers.append(ticker)
        else:
            failed_tickers = all_tickers

        # SPY 單獨存
        if "SPY" in self.price_cache:
            self.spy_prices = self.price_cache["SPY"]

        if failed_tickers:
            print(f"[警告] {len(failed_tickers)} 個標的無法下載: {failed_tickers[:10]}...")

        print(f"[下載完成] 成功 {len(self.price_cache)} / {len(all_tickers)} 個標的")
        return self.price_cache

    # ── CAR 計算 ──

    def calculate_car(
        self, ticker: str, event_date: pd.Timestamp, window: int, direction: str
    ) -> Optional[float]:
        """計算單筆交易的 CAR（累積異常報酬）。

        Args:
            ticker: 股票代碼
            event_date: 事件日（filing_date）
            window: 事件窗口天數
            direction: 'Buy' 或 'Sale'

        Returns:
            CAR 值，無法計算時回傳 None
        """
        if ticker not in self.price_cache or self.spy_prices is None:
            return None

        stock_prices = self.price_cache[ticker]
        spy_prices = self.spy_prices

        # 找事件日後的交易日
        event_date_ts = pd.Timestamp(event_date)

        # 取事件日之後的股價（含當日）
        stock_after = stock_prices[stock_prices.index >= event_date_ts]
        spy_after = spy_prices[spy_prices.index >= event_date_ts]

        # 需要 window+1 個交易日的數據（含事件日當天）
        if len(stock_after) < window + 1 or len(spy_after) < window + 1:
            return None

        # 取窗口內的收盤價
        stock_window = stock_after.iloc[: window + 1]["Close"]
        spy_window = spy_after.iloc[: window + 1]["Close"]

        # 計算日報酬率
        stock_returns = stock_window.pct_change().dropna()
        spy_returns = spy_window.pct_change().dropna()

        # 對齊日期
        common_dates = stock_returns.index.intersection(spy_returns.index)
        if len(common_dates) < 1:
            return None

        stock_returns = stock_returns.loc[common_dates]
        spy_returns = spy_returns.loc[common_dates]

        # 異常報酬
        ar = stock_returns.values - spy_returns.values

        # 累積異常報酬
        car = float(np.sum(ar))

        # Sale 方向：取反（空方 alpha 為正 = 股價下跌）
        if direction == "Sale":
            car = -car

        return car

    # ── 回測執行 ──

    def run_backtest(self, windows: Optional[List[int]] = None) -> pd.DataFrame:
        """執行完整回測。"""
        if windows is None:
            windows = [5, 20, 60]

        # 1. 取得回測宇宙
        universe = self.get_backtest_universe()
        if universe.empty:
            print("[錯誤] 無可回測數據")
            return pd.DataFrame()

        # 2. 計算下載日期範圍
        # 最早日期：取 filing_date 最小值 - 5 天
        # 最晚日期：今天（未來數據不存在）
        min_date = universe["filing_date"].min() - timedelta(days=5)
        max_date = pd.Timestamp.now() + timedelta(days=1)  # +1 確保含今天

        # 3. 下載股價
        tickers = universe["ticker"].unique().tolist()
        self.download_prices(
            tickers,
            start=min_date.strftime("%Y-%m-%d"),
            end=max_date.strftime("%Y-%m-%d"),
        )

        # 4. 計算每筆交易的 CAR
        results = []
        total = len(universe)

        for idx, row in universe.iterrows():
            record = {
                "politician_name": row["politician_name"],
                "ticker": row["ticker"],
                "transaction_type": row["transaction_type"],
                "direction": row["direction"],
                "transaction_date": row["transaction_date"],
                "filing_date": row["filing_date"],
                "filing_lag": row["filing_lag"],
                "amount_range": row["amount_range"],
                "amount_lower": row["amount_lower"],
                "chamber": row["chamber"],
                "owner": row["owner"],
            }

            for w in windows:
                car = self.calculate_car(
                    row["ticker"], row["filing_date"], w, row["direction"]
                )
                record[f"CAR_{w}d"] = car

            results.append(record)

        results_df = pd.DataFrame(results)

        # 統計
        for w in windows:
            col = f"CAR_{w}d"
            valid = results_df[col].notna().sum()
            print(f"[CAR {w}d] 有效計算: {valid}/{total} 筆")

        return results_df

    # ── 分層分析 ──

    def stratified_analysis(self, results: pd.DataFrame) -> Dict:
        """分層分析 CAR。"""
        analysis = {}

        windows = [5, 20, 60]
        car_cols = [f"CAR_{w}d" for w in windows]

        # 1. 全樣本
        analysis["全樣本"] = self._compute_stats(results, car_cols)

        # 2. 按交易方向
        for direction in ["Buy", "Sale"]:
            subset = results[results["direction"] == direction]
            if len(subset) > 0:
                analysis[f"交易方向: {direction}"] = self._compute_stats(subset, car_cols)

        # 3. 按金額（>$50K vs <=$50K）
        high_amount = results[results["amount_lower"] > 50000]
        low_amount = results[results["amount_lower"] <= 50000]
        if len(high_amount) > 0:
            analysis["金額 > $50K"] = self._compute_stats(high_amount, car_cols)
        if len(low_amount) > 0:
            analysis["金額 <= $50K"] = self._compute_stats(low_amount, car_cols)

        # 4. 按院別
        for chamber in ["House", "Senate"]:
            subset = results[results["chamber"] == chamber]
            if len(subset) > 0:
                analysis[f"院別: {chamber}"] = self._compute_stats(subset, car_cols)

        # 5. 按申報時效（filing lag < 15天 vs >= 15天）
        fast_filers = results[results["filing_lag"] < 15]
        slow_filers = results[results["filing_lag"] >= 15]
        if len(fast_filers) > 0:
            analysis["Filing Lag < 15天"] = self._compute_stats(fast_filers, car_cols)
        if len(slow_filers) > 0:
            analysis["Filing Lag >= 15天"] = self._compute_stats(slow_filers, car_cols)

        return analysis

    def _compute_stats(self, df: pd.DataFrame, car_cols: List[str]) -> Dict:
        """計算 CAR 統計量。"""
        stats_dict = {}
        for col in car_cols:
            valid = df[col].dropna()
            n = len(valid)
            if n < 2:
                stats_dict[col] = {
                    "n": n,
                    "mean": float(valid.mean()) if n > 0 else None,
                    "median": None,
                    "std": None,
                    "t_stat": None,
                    "p_value": None,
                    "hit_rate": None,
                }
                continue

            mean_car = float(valid.mean())
            median_car = float(valid.median())
            std_car = float(valid.std())
            t_stat, p_value = stats.ttest_1samp(valid, 0)

            # Hit Rate：Buy 方向正 CAR 為 hit，Sale 方向也是正 CAR（已反轉）
            hit_rate = float((valid > 0).sum() / n)

            stats_dict[col] = {
                "n": n,
                "mean": mean_car,
                "median": median_car,
                "std": std_car,
                "t_stat": float(t_stat),
                "p_value": float(p_value),
                "hit_rate": hit_rate,
            }
        return stats_dict

    # ── 報告生成 ──

    def generate_report(self, results: pd.DataFrame, output_path: str):
        """生成 Markdown 回測報告。"""
        analysis = self.stratified_analysis(results)

        lines = []
        lines.append("# Alpha 回測初步報告")
        lines.append(f"日期: {datetime.now().strftime('%Y-%m-%d')}")
        lines.append("")

        # 方法論
        lines.append("## 方法論")
        lines.append("")
        lines.append("| 參數 | 設定 |")
        lines.append("|------|------|")
        lines.append("| 事件日 | Filing Date（申報日） |")
        lines.append("| 事件窗口 | [0, +5], [0, +20], [0, +60] 交易日 |")
        lines.append("| Benchmark | SPY (S&P 500 ETF) |")
        lines.append("| 異常報酬 | AR = R_stock - R_SPY |")
        lines.append("| 累積異常報酬 | CAR = sum(AR) |")
        lines.append("| Sale 方向 | CAR 取反（股價下跌 = 正 alpha） |")
        lines.append("")

        # 資料概覽
        lines.append("## 資料概覽")
        lines.append("")
        lines.append(f"- 總交易筆數: {len(results)}")
        lines.append(f"- 標的數: {results['ticker'].nunique()}")
        lines.append(f"- 政治人物數: {results['politician_name'].nunique()}")
        lines.append(f"- 交易日期範圍: {results['transaction_date'].min().strftime('%Y-%m-%d') if pd.notna(results['transaction_date'].min()) else 'N/A'} ~ {results['transaction_date'].max().strftime('%Y-%m-%d') if pd.notna(results['transaction_date'].max()) else 'N/A'}")
        lines.append(f"- 申報日期範圍: {results['filing_date'].min().strftime('%Y-%m-%d')} ~ {results['filing_date'].max().strftime('%Y-%m-%d')}")

        buy_count = len(results[results["direction"] == "Buy"])
        sale_count = len(results[results["direction"] == "Sale"])
        lines.append(f"- Buy / Sale: {buy_count} / {sale_count}")

        median_lag = results["filing_lag"].median()
        lines.append(f"- 中位數 Filing Lag: {median_lag:.0f} 天")
        lines.append("")

        # 各分層結果
        for group_name, group_stats in analysis.items():
            lines.append(f"## {group_name}")
            lines.append("")
            lines.append("| 窗口 | 樣本數 | 平均 CAR | 中位數 CAR | 標準差 | t-stat | p-value | Hit Rate |")
            lines.append("|------|--------|---------|-----------|--------|--------|---------|----------|")

            for col, s in group_stats.items():
                window_label = col.replace("CAR_", "").replace("d", " 日")
                n = s["n"]
                mean_str = f"{s['mean']:.4f}" if s["mean"] is not None else "N/A"
                median_str = f"{s['median']:.4f}" if s["median"] is not None else "N/A"
                std_str = f"{s['std']:.4f}" if s["std"] is not None else "N/A"
                t_str = f"{s['t_stat']:.3f}" if s["t_stat"] is not None else "N/A"
                p_str = f"{s['p_value']:.4f}" if s["p_value"] is not None else "N/A"
                hit_str = f"{s['hit_rate']:.1%}" if s["hit_rate"] is not None else "N/A"

                # 標記顯著性
                sig = ""
                if s["p_value"] is not None:
                    if s["p_value"] < 0.01:
                        sig = " ***"
                    elif s["p_value"] < 0.05:
                        sig = " **"
                    elif s["p_value"] < 0.10:
                        sig = " *"

                lines.append(
                    f"| {window_label} | {n} | {mean_str}{sig} | {median_str} | "
                    f"{std_str} | {t_str} | {p_str} | {hit_str} |"
                )

            lines.append("")

        # 結論與建議
        lines.append("## 結論與建議")
        lines.append("")

        # 自動生成簡要結論
        full_stats = analysis.get("全樣本", {})
        car5 = full_stats.get("CAR_5d", {})
        car20 = full_stats.get("CAR_20d", {})
        car60 = full_stats.get("CAR_60d", {})

        if car5.get("mean") is not None:
            lines.append(f"1. **短期效應 (5日)**：平均 CAR = {car5['mean']:.4f}，")
            if car5.get("p_value") is not None and car5["p_value"] < 0.05:
                lines.append(f"   統計顯著 (p = {car5['p_value']:.4f})，Hit Rate = {car5['hit_rate']:.1%}")
            else:
                p_str = f"{car5['p_value']:.4f}" if car5.get("p_value") else "N/A"
                lines.append(f"   統計不顯著 (p = {p_str})")

        if car20.get("mean") is not None:
            lines.append(f"2. **中期效應 (20日)**：平均 CAR = {car20['mean']:.4f}，")
            if car20.get("p_value") is not None and car20["p_value"] < 0.05:
                lines.append(f"   統計顯著 (p = {car20['p_value']:.4f})，Hit Rate = {car20['hit_rate']:.1%}")
            else:
                p_str = f"{car20['p_value']:.4f}" if car20.get("p_value") else "N/A"
                lines.append(f"   統計不顯著 (p = {p_str})")

        if car60.get("mean") is not None:
            lines.append(f"3. **長期效應 (60日)**：平均 CAR = {car60['mean']:.4f}，")
            if car60.get("p_value") is not None and car60["p_value"] < 0.05:
                lines.append(f"   統計顯著 (p = {car60['p_value']:.4f})，Hit Rate = {car60['hit_rate']:.1%}")
            else:
                p_str = f"{car60['p_value']:.4f}" if car60.get("p_value") else "N/A"
                lines.append(f"   統計不顯著 (p = {p_str})")

        lines.append("")
        lines.append("### 限制與後續方向")
        lines.append("")
        lines.append("- 樣本期間較短，需累積更多歷史數據以提高統計檢定力")
        lines.append("- 目前使用簡化版 Market-Adjusted Model，後續可改用 Market Model (CAPM) 或 Fama-French 三因子")
        lines.append("- 部分 ticker 可能無法在 yfinance 找到（已下市、非美股等），已排除")
        lines.append("- Filing Date 為事件日，尚未考慮盤前/盤後效應")
        lines.append("- 未考慮交易成本與市場衝擊")
        lines.append("")
        lines.append("---")
        lines.append(f"*報告由 Political Alpha Monitor 自動生成 — {datetime.now().strftime('%Y-%m-%d %H:%M')}*")
        lines.append("")

        # 寫入檔案
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("\n".join(lines), encoding="utf-8")

        print(f"\n[報告] 已生成: {output_path}")

        # 同時印出摘要
        print("\n" + "=" * 70)
        print("  Alpha 回測摘要")
        print("=" * 70)
        self._print_summary(analysis)

    def _print_summary(self, analysis: Dict):
        """印出摘要統計。"""
        for group_name, group_stats in analysis.items():
            print(f"\n--- {group_name} ---")
            for col, s in group_stats.items():
                window = col.replace("CAR_", "").replace("d", "")
                n = s["n"]
                if n < 2:
                    print(f"  {window}日: n={n}, 樣本不足")
                    continue

                mean = s["mean"]
                p = s["p_value"]
                hit = s["hit_rate"]

                sig = ""
                if p < 0.01:
                    sig = "***"
                elif p < 0.05:
                    sig = "**"
                elif p < 0.10:
                    sig = "*"

                print(
                    f"  {window}日: n={n}, "
                    f"mean={mean:+.4f}, "
                    f"p={p:.4f}{sig}, "
                    f"hit={hit:.1%}"
                )

    # ── 輔助函數 ──

    @staticmethod
    def _parse_amount_lower(amount_range: str) -> float:
        """解析 amount_range 字串，回傳下限金額。

        例如 '$15,001 - $50,000' → 15001.0
             '$1,001 - $15,000' → 1001.0
             '$Over $50,000,000' → 50000000.0
        """
        if not amount_range or not isinstance(amount_range, str):
            return 0.0

        # 移除 $ 和 , 和空白
        cleaned = amount_range.replace("$", "").replace(",", "").strip()

        # 嘗試取第一個數字
        import re
        numbers = re.findall(r"[\d]+(?:\.[\d]+)?", cleaned)
        if numbers:
            return float(numbers[0])
        return 0.0


if __name__ == "__main__":
    bt = AlphaBacktester()
    results = bt.run_backtest()
    if not results.empty:
        bt.generate_report(
            results,
            "docs/reports/Alpha_Backtest_Preliminary_2026-02-27.md",
        )
