"""Fama-French 三因子 Alpha 模型。

使用 Kenneth French Data Library 的日頻因子數據，
透過 OLS 回歸計算因子調整後的異常報酬 (Factor-Adjusted CAR)。

方法論：
- 估計窗口：事件日前 [-250, -10] 交易日
- 事件窗口：[0, +W] 交易日（W = 5, 20, 60）
- 模型：R_i - R_f = alpha + b1*(Mkt-RF) + b2*SMB + b3*HML + epsilon
- 因子調整 AR_t = (R_i,t - R_f,t) - [b1_hat*(Mkt-RF)_t + b2_hat*SMB_t + b3_hat*HML_t]
- 因子調整 CAR = sum(AR_t) over event window
"""

import io
import zipfile
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple

import numpy as np
import pandas as pd
import requests
import statsmodels.api as sm

from src.config import DB_PATH

# ── 常數 ──
FF_URL = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_Factors_daily_CSV.zip"
FF_CACHE_PATH = Path(__file__).parent.parent / "data" / "ff_factors_daily.csv"

# 估計窗口參數
EST_WINDOW_START = -250  # 事件日前 250 個交易日
EST_WINDOW_END = -10     # 事件日前 10 個交易日（避免事件污染）
MIN_EST_OBS = 60         # 最少需要 60 個觀測值才做回歸


class FamaFrenchModel:
    """Fama-French 三因子模型，用於 Event Study 異常報酬計算。"""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.ff_data: Optional[pd.DataFrame] = None
        self.price_cache: Dict[str, pd.DataFrame] = {}

    # ── 因子數據下載與解析 ──

    def load_ff_factors(self, force_download: bool = False) -> pd.DataFrame:
        """下載並解析 Fama-French 三因子日頻數據。

        數據來源：Kenneth French Data Library
        欄位：Date, Mkt-RF, SMB, HML, RF（均為百分比，需除以 100）
        """
        # 嘗試讀取快取
        if not force_download and FF_CACHE_PATH.exists():
            cached = pd.read_csv(FF_CACHE_PATH, parse_dates=["Date"], index_col="Date")
            if len(cached) > 0:
                self.ff_data = cached
                print(f"[FF3] 從快取載入因子數據: {len(cached)} 筆 "
                      f"({cached.index.min().strftime('%Y-%m-%d')} ~ "
                      f"{cached.index.max().strftime('%Y-%m-%d')})")
                return cached

        print("[FF3] 正在下載 Fama-French 三因子數據...")
        resp = requests.get(FF_URL, timeout=30)
        resp.raise_for_status()

        # 解壓 ZIP
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            csv_name = [n for n in zf.namelist() if n.lower().endswith(".csv")][0]
            raw_text = zf.read(csv_name).decode("utf-8")

        # 解析 CSV — 需要跳過描述行，找到日頻數據區塊
        lines = raw_text.strip().split("\n")
        data_start = None
        data_end = None

        for i, line in enumerate(lines):
            stripped = line.strip()
            # 日頻數據開始於數字開頭的行（YYYYMMDD 格式）
            if data_start is None and stripped and stripped[0].isdigit() and len(stripped.split(",")[0].strip()) == 8:
                data_start = i
            # 日頻數據結束於空行或非數字開頭（月頻數據區塊）
            elif data_start is not None and data_end is None:
                if not stripped or (not stripped[0].isdigit()):
                    data_end = i
                    break

        if data_start is None:
            raise ValueError("無法解析 Fama-French CSV 文件")

        if data_end is None:
            data_end = len(lines)

        # 組合數據行
        header = "Date,Mkt-RF,SMB,HML,RF\n"
        data_lines = "\n".join(lines[data_start:data_end])
        csv_text = header + data_lines

        df = pd.read_csv(io.StringIO(csv_text))
        df["Date"] = pd.to_datetime(df["Date"].astype(str), format="%Y%m%d")
        df = df.set_index("Date")

        # 因子值從百分比轉為小數（例如 0.05 表示 0.05%，轉為 0.0005）
        for col in ["Mkt-RF", "SMB", "HML", "RF"]:
            df[col] = df[col].astype(float) / 100.0

        # 移除缺失值
        df = df.dropna()

        # 快取到本地
        FF_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(FF_CACHE_PATH)

        self.ff_data = df
        print(f"[FF3] 下載完成: {len(df)} 筆因子數據 "
              f"({df.index.min().strftime('%Y-%m-%d')} ~ "
              f"{df.index.max().strftime('%Y-%m-%d')})")
        return df

    def extend_ff_with_spy(self):
        """用 SPY 報酬延伸因子數據到最近日期。

        Kenneth French 數據通常滯後 1-2 個月。對於缺失日期：
        - Mkt-RF = SPY 日報酬 - RF（RF 用最後已知值）
        - SMB = 0（近似值，長期日均接近 0）
        - HML = 0（近似值）
        - RF = 最後已知值
        """
        if self.ff_data is None or "SPY" not in self.price_cache:
            return

        ff_max = self.ff_data.index.max()
        spy_prices = self.price_cache["SPY"]
        spy_ret = spy_prices["Close"].pct_change().dropna()

        # 取 FF 數據之後的 SPY 報酬
        spy_after = spy_ret[spy_ret.index > ff_max]
        if len(spy_after) == 0:
            return

        last_rf = self.ff_data["RF"].iloc[-1]

        # 建立延伸的因子 DataFrame
        ext = pd.DataFrame(index=spy_after.index)
        ext["Mkt-RF"] = spy_after.values - last_rf
        ext["SMB"] = 0.0
        ext["HML"] = 0.0
        ext["RF"] = last_rf

        self.ff_data = pd.concat([self.ff_data, ext])
        self.ff_data = self.ff_data[~self.ff_data.index.duplicated(keep="first")]
        self.ff_data.sort_index(inplace=True)

        print(f"[FF3] 已用 SPY 延伸因子數據 {len(spy_after)} 天 "
              f"(至 {self.ff_data.index.max().strftime('%Y-%m-%d')})")

    # ── 股價數據 ──

    def download_prices(self, tickers: List[str], start: str, end: str):
        """批量下載股價（含 SPY）。"""
        import yfinance as yf

        all_tickers = list(set(tickers + ["SPY"]))
        print(f"[FF3] 下載股價: {len(all_tickers)} 個標的，{start} ~ {end}")

        try:
            data = yf.download(
                all_tickers, start=start, end=end,
                auto_adjust=True, progress=False, threads=True
            )
        except Exception as e:
            print(f"[警告] 批量下載失敗: {e}")
            data = pd.DataFrame()

        failed = []
        if not data.empty:
            for ticker in all_tickers:
                try:
                    if len(all_tickers) == 1:
                        prices = data[["Close"]].copy()
                    else:
                        prices = data["Close"][[ticker]].copy()
                        prices.columns = ["Close"]
                    prices = prices.dropna()
                    if len(prices) > 0:
                        self.price_cache[ticker] = prices
                    else:
                        failed.append(ticker)
                except (KeyError, TypeError):
                    failed.append(ticker)
        else:
            failed = all_tickers

        if failed:
            print(f"[警告] {len(failed)} 個標的無法下載: {failed[:10]}...")
        print(f"[FF3] 股價下載完成: {len(self.price_cache)}/{len(all_tickers)}")

    # ── 單筆交易的因子調整 CAR ──

    def calculate_ff3_car(
        self,
        ticker: str,
        event_date: pd.Timestamp,
        window: int,
        direction: str,
    ) -> Optional[Dict]:
        """計算單筆交易的 Fama-French 三因子調整 CAR。

        Returns:
            dict with keys: ff3_car, market_car, alpha, betas, r_squared, n_est, n_event
            or None if insufficient data.
        """
        if self.ff_data is None:
            raise RuntimeError("請先呼叫 load_ff_factors()")

        if ticker not in self.price_cache or "SPY" not in self.price_cache:
            return None

        stock_prices = self.price_cache[ticker]
        spy_prices = self.price_cache["SPY"]

        event_ts = pd.Timestamp(event_date)

        # ── 建立股票日報酬序列 ──
        stock_ret = stock_prices["Close"].pct_change().dropna()
        spy_ret = spy_prices["Close"].pct_change().dropna()

        # ── 找事件日在交易日序列中的位置 ──
        # 取事件日或之後最近的交易日
        valid_dates = stock_ret.index[stock_ret.index >= event_ts]
        if len(valid_dates) == 0:
            return None
        actual_event_date = valid_dates[0]

        # 事件日在 stock_ret 中的整數位置
        event_loc = stock_ret.index.get_loc(actual_event_date)

        # ── 估計窗口 ──
        est_start_loc = event_loc + EST_WINDOW_START
        est_end_loc = event_loc + EST_WINDOW_END
        if est_start_loc < 0:
            est_start_loc = 0

        est_dates = stock_ret.index[est_start_loc:est_end_loc]
        if len(est_dates) < MIN_EST_OBS:
            return None

        # ── 事件窗口 ──
        event_end_loc = event_loc + window + 1
        if event_end_loc > len(stock_ret):
            return None
        event_dates = stock_ret.index[event_loc:event_end_loc]
        if len(event_dates) < 1:
            return None

        # ── 對齊數據 ──
        ff = self.ff_data

        # 估計窗口
        est_common = est_dates.intersection(ff.index).intersection(spy_ret.index)
        if len(est_common) < MIN_EST_OBS:
            return None

        stock_est = stock_ret.loc[est_common].values
        ff_est = ff.loc[est_common]
        rf_est = ff_est["RF"].values

        # 超額報酬 = 股票報酬 - 無風險利率
        y_est = stock_est - rf_est
        X_est = ff_est[["Mkt-RF", "SMB", "HML"]].values
        X_est_const = sm.add_constant(X_est)

        # ── OLS 回歸（估計窗口）──
        try:
            model = sm.OLS(y_est, X_est_const).fit()
        except Exception:
            return None

        alpha_est = model.params[0]
        betas = model.params[1:]  # [b_mkt, b_smb, b_hml]
        r_squared = model.rsquared

        # ── 事件窗口異常報酬 ──
        event_common = event_dates.intersection(ff.index).intersection(spy_ret.index)
        if len(event_common) < 1:
            return None

        stock_event = stock_ret.loc[event_common].values
        spy_event = spy_ret.loc[event_common].values
        ff_event = ff.loc[event_common]
        rf_event = ff_event["RF"].values

        # Fama-French 因子調整 AR
        # AR_t = (R_i,t - RF_t) - [b1*(Mkt-RF)_t + b2*SMB_t + b3*HML_t]
        expected_excess = (
            betas[0] * ff_event["Mkt-RF"].values +
            betas[1] * ff_event["SMB"].values +
            betas[2] * ff_event["HML"].values
        )
        ar_ff3 = (stock_event - rf_event) - expected_excess
        car_ff3 = float(np.sum(ar_ff3))

        # 簡單市場調整 CAR（對照組）
        ar_market = stock_event - spy_event
        car_market = float(np.sum(ar_market))

        # Sale 方向取反
        if direction == "Sale":
            car_ff3 = -car_ff3
            car_market = -car_market

        return {
            "ff3_car": car_ff3,
            "market_car": car_market,
            "alpha_est": float(alpha_est),
            "beta_mkt": float(betas[0]),
            "beta_smb": float(betas[1]),
            "beta_hml": float(betas[2]),
            "r_squared": float(r_squared),
            "n_est": len(est_common),
            "n_event": len(event_common),
        }

    # ── 批量回測 ──

    def get_backtest_trades(self) -> pd.DataFrame:
        """從 DB 取得回測交易數據。"""
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

        df["transaction_date"] = pd.to_datetime(df["transaction_date"], errors="coerce")
        df["filing_date"] = pd.to_datetime(df["filing_date"], errors="coerce")
        df = df.dropna(subset=["filing_date"])

        df["filing_lag"] = (df["filing_date"] - df["transaction_date"]).dt.days
        df["direction"] = df["transaction_type"].apply(
            lambda x: "Buy" if x == "Buy" else "Sale"
        )
        df["ticker"] = df["ticker"].str.replace(".", "-", regex=False)

        # 解析金額下限
        import re
        def parse_amount_lower(s):
            if not s or not isinstance(s, str):
                return 0.0
            cleaned = s.replace("$", "").replace(",", "").strip()
            nums = re.findall(r"[\d]+(?:\.[\d]+)?", cleaned)
            return float(nums[0]) if nums else 0.0

        df["amount_lower"] = df["amount_range"].apply(parse_amount_lower)

        print(f"[FF3 回測] 共 {len(df)} 筆交易，{df['ticker'].nunique()} 個標的")
        return df

    def run_backtest(
        self,
        windows: Optional[List[int]] = None,
        trades: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:
        """執行 Fama-French 三因子回測。

        同時計算 Market-Adjusted CAR 和 FF3-Adjusted CAR 以供比較。
        """
        if windows is None:
            windows = [5, 20, 60]

        # 1. 載入因子數據
        self.load_ff_factors()

        # 2. 取得交易數據
        if trades is None:
            trades = self.get_backtest_trades()
        if trades.empty:
            print("[錯誤] 無可回測數據")
            return pd.DataFrame()

        # 3. 下載股價（需要更早的數據以覆蓋估計窗口）
        min_date = trades["filing_date"].min() - timedelta(days=400)  # 多抓 400 天
        max_date = pd.Timestamp.now() + timedelta(days=1)
        tickers = trades["ticker"].unique().tolist()
        self.download_prices(
            tickers,
            start=min_date.strftime("%Y-%m-%d"),
            end=max_date.strftime("%Y-%m-%d"),
        )

        # 3.5 用 SPY 延伸 FF 因子數據（彌補 Kenneth French 數據滯後）
        self.extend_ff_with_spy()

        # 4. 逐筆計算
        results = []
        total = len(trades)
        computed = 0

        for idx, row in trades.iterrows():
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

            betas_saved = False
            for w in windows:
                result = self.calculate_ff3_car(
                    row["ticker"], row["filing_date"], w, row["direction"]
                )
                if result is not None:
                    record[f"FF3_CAR_{w}d"] = result["ff3_car"]
                    record[f"MKT_CAR_{w}d"] = result["market_car"]
                    # 存第一個有效窗口的回歸參數（估計窗口相同，betas 不隨事件窗口變化）
                    if not betas_saved:
                        record["alpha_est"] = result["alpha_est"]
                        record["beta_mkt"] = result["beta_mkt"]
                        record["beta_smb"] = result["beta_smb"]
                        record["beta_hml"] = result["beta_hml"]
                        record["r_squared"] = result["r_squared"]
                        record["n_est"] = result["n_est"]
                        betas_saved = True
                else:
                    record[f"FF3_CAR_{w}d"] = None
                    record[f"MKT_CAR_{w}d"] = None

            results.append(record)
            computed += 1
            if computed % 50 == 0:
                print(f"  進度: {computed}/{total}")

        results_df = pd.DataFrame(results)

        # 統計
        for w in windows:
            ff3_valid = results_df[f"FF3_CAR_{w}d"].notna().sum()
            mkt_valid = results_df[f"MKT_CAR_{w}d"].notna().sum()
            print(f"[{w}d] FF3 有效: {ff3_valid}/{total}, MKT 有效: {mkt_valid}/{total}")

        return results_df

    # ── 比較分析 ──

    def comparison_analysis(
        self, results: pd.DataFrame, windows: Optional[List[int]] = None
    ) -> Dict:
        """比較 Market-Adjusted 與 FF3-Adjusted 的結果差異。"""
        if windows is None:
            windows = [5, 20, 60]

        from scipy import stats as sp_stats

        analysis = {}

        for w in windows:
            ff3_col = f"FF3_CAR_{w}d"
            mkt_col = f"MKT_CAR_{w}d"

            # 取兩者都有值的子集
            valid = results[[ff3_col, mkt_col]].dropna()
            n = len(valid)
            if n < 2:
                analysis[f"{w}d"] = {"n": n, "insufficient_data": True}
                continue

            ff3_vals = valid[ff3_col]
            mkt_vals = valid[mkt_col]

            # FF3 統計
            ff3_mean = float(ff3_vals.mean())
            ff3_median = float(ff3_vals.median())
            ff3_std = float(ff3_vals.std())
            ff3_t, ff3_p = sp_stats.ttest_1samp(ff3_vals, 0)
            ff3_hit = float((ff3_vals > 0).sum() / n)

            # Market 統計
            mkt_mean = float(mkt_vals.mean())
            mkt_median = float(mkt_vals.median())
            mkt_std = float(mkt_vals.std())
            mkt_t, mkt_p = sp_stats.ttest_1samp(mkt_vals, 0)
            mkt_hit = float((mkt_vals > 0).sum() / n)

            # 差異統計（配對 t 檢定）
            diff = ff3_vals - mkt_vals
            diff_mean = float(diff.mean())
            if diff.std() > 0:
                diff_t, diff_p = sp_stats.ttest_1samp(diff, 0)
            else:
                diff_t, diff_p = 0.0, 1.0

            analysis[f"{w}d"] = {
                "n": n,
                "ff3": {
                    "mean": ff3_mean, "median": ff3_median, "std": ff3_std,
                    "t_stat": float(ff3_t), "p_value": float(ff3_p),
                    "hit_rate": ff3_hit,
                },
                "market": {
                    "mean": mkt_mean, "median": mkt_median, "std": mkt_std,
                    "t_stat": float(mkt_t), "p_value": float(mkt_p),
                    "hit_rate": mkt_hit,
                },
                "diff": {
                    "mean": diff_mean,
                    "t_stat": float(diff_t),
                    "p_value": float(diff_p),
                },
            }

        return analysis

    def stratified_comparison(
        self, results: pd.DataFrame, windows: Optional[List[int]] = None
    ) -> Dict:
        """分層比較分析（方向、金額、院別等）。"""
        if windows is None:
            windows = [5, 20, 60]

        strata = {}

        # 全樣本
        strata["全樣本"] = self.comparison_analysis(results, windows)

        # 按方向
        for d in ["Buy", "Sale"]:
            subset = results[results["direction"] == d]
            if len(subset) >= 2:
                strata[f"方向: {d}"] = self.comparison_analysis(subset, windows)

        # 按金額
        high = results[results["amount_lower"] > 50000]
        low = results[results["amount_lower"] <= 50000]
        if len(high) >= 2:
            strata["金額 > $50K"] = self.comparison_analysis(high, windows)
        if len(low) >= 2:
            strata["金額 <= $50K"] = self.comparison_analysis(low, windows)

        # 按院別
        for ch in ["House", "Senate"]:
            subset = results[results["chamber"] == ch]
            if len(subset) >= 2:
                strata[f"院別: {ch}"] = self.comparison_analysis(subset, windows)

        # 按 Filing Lag
        fast = results[results["filing_lag"] < 15]
        slow = results[results["filing_lag"] >= 15]
        if len(fast) >= 2:
            strata["Filing Lag < 15天"] = self.comparison_analysis(fast, windows)
        if len(slow) >= 2:
            strata["Filing Lag >= 15天"] = self.comparison_analysis(slow, windows)

        return strata

    # ── 結果保存 ──

    def save_results(self, results: pd.DataFrame):
        """將結果保存到 SQLite fama_french_results 表。"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 建表
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS fama_french_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            politician_name TEXT,
            ticker TEXT,
            transaction_type TEXT,
            direction TEXT,
            transaction_date DATE,
            filing_date DATE,
            filing_lag INTEGER,
            amount_range TEXT,
            chamber TEXT,
            owner TEXT,
            ff3_car_5d REAL,
            ff3_car_20d REAL,
            ff3_car_60d REAL,
            mkt_car_5d REAL,
            mkt_car_20d REAL,
            mkt_car_60d REAL,
            alpha_est REAL,
            beta_mkt REAL,
            beta_smb REAL,
            beta_hml REAL,
            r_squared REAL,
            n_est INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # 清除舊結果
        cursor.execute("DELETE FROM fama_french_results")

        # 寫入
        for _, row in results.iterrows():
            cursor.execute("""
            INSERT INTO fama_french_results (
                politician_name, ticker, transaction_type, direction,
                transaction_date, filing_date, filing_lag, amount_range,
                chamber, owner,
                ff3_car_5d, ff3_car_20d, ff3_car_60d,
                mkt_car_5d, mkt_car_20d, mkt_car_60d,
                alpha_est, beta_mkt, beta_smb, beta_hml, r_squared, n_est
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                row.get("politician_name"),
                row.get("ticker"),
                row.get("transaction_type"),
                row.get("direction"),
                str(row.get("transaction_date"))[:10] if pd.notna(row.get("transaction_date")) else None,
                str(row.get("filing_date"))[:10] if pd.notna(row.get("filing_date")) else None,
                int(row["filing_lag"]) if pd.notna(row.get("filing_lag")) else None,
                row.get("amount_range"),
                row.get("chamber"),
                row.get("owner"),
                row.get("FF3_CAR_5d"),
                row.get("FF3_CAR_20d"),
                row.get("FF3_CAR_60d"),
                row.get("MKT_CAR_5d"),
                row.get("MKT_CAR_20d"),
                row.get("MKT_CAR_60d"),
                row.get("alpha_est"),
                row.get("beta_mkt"),
                row.get("beta_smb"),
                row.get("beta_hml"),
                row.get("r_squared"),
                int(row["n_est"]) if pd.notna(row.get("n_est")) else None,
            ))

        conn.commit()
        conn.close()
        print(f"[FF3] 已保存 {len(results)} 筆結果到 fama_french_results 表")

    # ── 報告生成 ──

    def generate_comparison_report(
        self, results: pd.DataFrame, output_path: str
    ) -> str:
        """生成 Market-Adjusted vs FF3-Adjusted 比較報告（Markdown）。"""
        strata = self.stratified_comparison(results)
        windows = [5, 20, 60]

        lines = []
        lines.append("# Fama-French 三因子 Alpha 比較報告")
        lines.append(f"日期: {datetime.now().strftime('%Y-%m-%d')}")
        lines.append("")

        # ── 方法論 ──
        lines.append("## 方法論")
        lines.append("")
        lines.append("| 參數 | Market-Adjusted | Fama-French 3-Factor |")
        lines.append("|------|-----------------|---------------------|")
        lines.append("| 模型 | AR = R_stock - R_SPY | R_i - R_f = a + b1(Mkt-RF) + b2*SMB + b3*HML |")
        lines.append(f"| 估計窗口 | N/A | [{EST_WINDOW_START}, {EST_WINDOW_END}] 交易日 |")
        lines.append("| 事件窗口 | [0, +W] | [0, +W] |")
        lines.append("| Benchmark | SPY | Mkt-RF, SMB, HML (Kenneth French) |")
        lines.append(f"| 最少估計觀測 | N/A | {MIN_EST_OBS} 天 |")
        lines.append("| Sale 方向 | CAR 取反 | CAR 取反 |")
        lines.append("")

        # ── 因子回歸摘要 ──
        if "beta_mkt" in results.columns:
            valid_betas = results[["beta_mkt", "beta_smb", "beta_hml", "r_squared"]].dropna()
            if len(valid_betas) > 0:
                lines.append("## 因子曝露摘要（估計窗口 OLS）")
                lines.append("")
                lines.append("| 統計量 | Beta(Mkt) | Beta(SMB) | Beta(HML) | R-squared |")
                lines.append("|--------|-----------|-----------|-----------|-----------|")
                lines.append(
                    f"| 平均值 | {valid_betas['beta_mkt'].mean():.3f} "
                    f"| {valid_betas['beta_smb'].mean():.3f} "
                    f"| {valid_betas['beta_hml'].mean():.3f} "
                    f"| {valid_betas['r_squared'].mean():.3f} |"
                )
                lines.append(
                    f"| 中位數 | {valid_betas['beta_mkt'].median():.3f} "
                    f"| {valid_betas['beta_smb'].median():.3f} "
                    f"| {valid_betas['beta_hml'].median():.3f} "
                    f"| {valid_betas['r_squared'].median():.3f} |"
                )
                lines.append(
                    f"| 標準差 | {valid_betas['beta_mkt'].std():.3f} "
                    f"| {valid_betas['beta_smb'].std():.3f} "
                    f"| {valid_betas['beta_hml'].std():.3f} "
                    f"| {valid_betas['r_squared'].std():.3f} |"
                )
                lines.append("")

        # ── 資料概覽 ──
        lines.append("## 資料概覽")
        lines.append("")
        lines.append(f"- 總交易筆數: {len(results)}")
        lines.append(f"- 標的數: {results['ticker'].nunique()}")
        lines.append(f"- 政治人物數: {results['politician_name'].nunique()}")

        buy_n = len(results[results["direction"] == "Buy"])
        sale_n = len(results[results["direction"] == "Sale"])
        lines.append(f"- Buy / Sale: {buy_n} / {sale_n}")

        if pd.notna(results["filing_date"].min()):
            lines.append(
                f"- 申報日期範圍: {results['filing_date'].min().strftime('%Y-%m-%d')} ~ "
                f"{results['filing_date'].max().strftime('%Y-%m-%d')}"
            )

        for w in windows:
            ff3_n = results[f"FF3_CAR_{w}d"].notna().sum()
            mkt_n = results[f"MKT_CAR_{w}d"].notna().sum()
            lines.append(f"- {w}日窗口有效: FF3={ff3_n}, MKT={mkt_n}")
        lines.append("")

        # ── 各分層比較結果 ──
        def _sig_marker(p):
            if p is None:
                return ""
            if p < 0.01:
                return " ***"
            if p < 0.05:
                return " **"
            if p < 0.10:
                return " *"
            return ""

        for group_name, group_data in strata.items():
            lines.append(f"## {group_name}")
            lines.append("")
            lines.append("| 窗口 | N | 模型 | 平均 CAR | 中位數 | Std | t-stat | p-value | Hit Rate |")
            lines.append("|------|---|------|---------|--------|-----|--------|---------|----------|")

            for w in windows:
                key = f"{w}d"
                s = group_data.get(key, {})
                if s.get("insufficient_data"):
                    lines.append(f"| {w}日 | {s.get('n', 0)} | - | 樣本不足 | - | - | - | - | - |")
                    continue

                n = s["n"]
                for model_key, model_label in [("market", "MKT"), ("ff3", "FF3")]:
                    m = s[model_key]
                    sig = _sig_marker(m["p_value"])
                    lines.append(
                        f"| {w}日 | {n} | {model_label} "
                        f"| {m['mean']:.4f}{sig} | {m['median']:.4f} "
                        f"| {m['std']:.4f} | {m['t_stat']:.3f} "
                        f"| {m['p_value']:.4f} | {m['hit_rate']:.1%} |"
                    )

                # 差異行
                d = s["diff"]
                diff_sig = _sig_marker(d["p_value"])
                lines.append(
                    f"| {w}日 | {n} | **Diff** "
                    f"| {d['mean']:.4f}{diff_sig} | - | - "
                    f"| {d['t_stat']:.3f} | {d['p_value']:.4f} | - |"
                )

            lines.append("")

        # ── 結論 ──
        lines.append("## 結論")
        lines.append("")

        # 自動生成結論
        full = strata.get("全樣本", {})
        for w in windows:
            key = f"{w}d"
            s = full.get(key, {})
            if s.get("insufficient_data"):
                continue

            ff3_mean = s["ff3"]["mean"]
            ff3_p = s["ff3"]["p_value"]
            mkt_mean = s["market"]["mean"]
            mkt_p = s["market"]["p_value"]
            diff_mean = s["diff"]["mean"]

            sig_ff3 = "顯著" if ff3_p < 0.05 else "不顯著"
            sig_mkt = "顯著" if mkt_p < 0.05 else "不顯著"

            lines.append(
                f"- **{w}日窗口**: FF3 CAR = {ff3_mean:+.4f} ({sig_ff3}, p={ff3_p:.4f}) vs "
                f"MKT CAR = {mkt_mean:+.4f} ({sig_mkt}, p={mkt_p:.4f}), "
                f"差異 = {diff_mean:+.4f}"
            )

            # 解讀
            if abs(diff_mean) > 0.005:
                if diff_mean > 0:
                    lines.append(
                        f"  → FF3 調整後 alpha 更高，表示簡單市場調整模型低估了真實 alpha"
                        f"（國會議員偏好小型/價值股，控制後 alpha 更大）"
                    )
                else:
                    lines.append(
                        f"  → FF3 調整後 alpha 更低，表示部分市場調整 CAR 可由 size/value 因子解釋"
                    )
            else:
                lines.append(
                    f"  → 兩種方法差異不大，size/value 因子對國會交易 alpha 影響有限"
                )

        lines.append("")
        lines.append("### 方法論備註")
        lines.append("")
        lines.append("- FF3 模型控制了市場風險 (Mkt-RF)、規模效應 (SMB)、價值效應 (HML)")
        lines.append("- 估計窗口 OLS 的 R-squared 反映因子模型對個股報酬的解釋力")
        lines.append("- 若 beta_smb 顯著正值 → 國會議員偏好小型股")
        lines.append("- 若 beta_hml 顯著正值 → 國會議員偏好價值股")
        lines.append("- 差異欄 (Diff) = FF3_CAR - MKT_CAR，正值表示 FF3 alpha 更大")
        lines.append("")
        lines.append("---")
        lines.append(
            f"*報告由 Political Alpha Monitor Fama-French 模組自動生成 — "
            f"{datetime.now().strftime('%Y-%m-%d %H:%M')}*"
        )
        lines.append("")

        # 寫入檔案
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("\n".join(lines), encoding="utf-8")

        print(f"\n[報告] 已生成: {output_path}")
        return output_path
