"""歷史國會交易 Alpha 回測 — 擴展版

使用 Capitol Trades 歷史數據做大樣本回測。
方法論：Event Study，以 disclosure_date 為事件日，
計算 5/20/60 交易日 CAR（市場調整模型，benchmark = SPY）。

資料來源：capitoltrades.com（公開歷史交易數據）
"""

import io
import re
import sys
import time
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict

import numpy as np
import pandas as pd
import requests
from bs4 import BeautifulSoup
from scipy import stats

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("HistoricalBacktest")

# ── 回測參數 ──
LOOKBACK_MONTHS = 12
WINDOWS = [5, 20, 60]
MIN_SAMPLES_FOR_STATS = 5
MAX_PAGES = 30  # Capitol Trades 頁數上限（100 trades/page）


# ════════════════════════════════════════════════════════════════
# 1. 資料下載（Capitol Trades）
# ════════════════════════════════════════════════════════════════

def fetch_historical_data() -> pd.DataFrame:
    """從 Capitol Trades 抓取歷史交易數據。"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    all_trades = []
    cutoff = datetime.now() - timedelta(days=LOOKBACK_MONTHS * 30)

    for page in range(1, MAX_PAGES + 1):
        url = f"https://www.capitoltrades.com/trades?page={page}&pageSize=100"
        try:
            resp = requests.get(url, headers=headers, timeout=30)
            resp.raise_for_status()
        except Exception as e:
            logger.warning(f"Page {page} 下載失敗: {e}")
            break

        soup = BeautifulSoup(resp.text, "html.parser")
        rows = soup.select("table tbody tr")
        if not rows:
            logger.info(f"Page {page}: 無更多資料")
            break

        page_trades = []
        oldest_date_on_page = None

        for row in rows:
            cells = row.find_all("td")
            if len(cells) < 9:
                continue

            try:
                # [0] Politician + chamber
                pol_cell = cells[0]
                politician_name = ""
                # 取 <a> 標籤的文字作為名字
                pol_link = pol_cell.find("a")
                if pol_link:
                    politician_name = pol_link.get_text(strip=True)
                else:
                    politician_name = pol_cell.get_text(strip=True)

                # 判斷 chamber
                pol_text = pol_cell.get_text(strip=True)
                chamber = "House" if "House" in pol_text else "Senate" if "Senate" in pol_text else ""

                # [1] Asset + ticker
                asset_cell = cells[1]
                asset_text = asset_cell.get_text(strip=True)
                # 嘗試從 issuer 頁面連結或文字取得 ticker
                ticker = _extract_ticker(asset_text, asset_cell)

                # [2] Filing date (disclosure date)
                filing_text = cells[2].get_text(strip=True)
                disclosure_date = _parse_capitol_date(filing_text)

                # [3] Transaction date
                tx_text = cells[3].get_text(strip=True)
                transaction_date = _parse_capitol_date(tx_text)

                # [5] Owner
                owner = cells[5].get_text(strip=True)

                # [6] Transaction type
                tx_type = cells[6].get_text(strip=True).lower()

                # [7] Amount
                amount = cells[7].get_text(strip=True)

                if not ticker or ticker == "N/A" or not transaction_date:
                    continue

                # 方向分類
                direction = None
                if "buy" in tx_type or "purchase" in tx_type:
                    direction = "Buy"
                elif "sell" in tx_type or "sale" in tx_type:
                    direction = "Sale"

                if not direction:
                    continue

                trade = {
                    "politician_name": politician_name,
                    "ticker": ticker.upper().strip(),
                    "chamber": chamber,
                    "transaction_date": transaction_date,
                    "disclosure_date": disclosure_date or transaction_date + timedelta(days=30),
                    "transaction_type": tx_type,
                    "direction": direction,
                    "amount": amount,
                    "owner": owner,
                }
                page_trades.append(trade)

                if oldest_date_on_page is None or (disclosure_date and disclosure_date < oldest_date_on_page):
                    oldest_date_on_page = disclosure_date or transaction_date

            except Exception:
                continue

        all_trades.extend(page_trades)
        logger.info(f"Page {page}: {len(page_trades)} 有效交易（累計 {len(all_trades)}）")

        # 如果最舊的日期已超過回溯期，停止
        if oldest_date_on_page and oldest_date_on_page < cutoff:
            logger.info(f"已達回溯期限 ({cutoff.strftime('%Y-%m-%d')})，停止抓取")
            break

        time.sleep(0.5)  # 禮貌性延遲

    if not all_trades:
        return pd.DataFrame()

    df = pd.DataFrame(all_trades)

    # 清理 ticker
    df["ticker"] = df["ticker"].str.replace(".", "-", regex=False)
    df = df[~df["ticker"].isin(["N/A", "--", ""])]

    # 過濾日期範圍
    df = df[df["disclosure_date"] >= cutoff]
    df = df[df["disclosure_date"] <= datetime.now() + timedelta(days=1)]

    # Filing lag
    df["filing_lag"] = (df["disclosure_date"] - df["transaction_date"]).dt.days

    # 金額解析
    df["amount_lower"] = df["amount"].apply(parse_amount_lower)

    logger.info(f"清洗後共 {len(df)} 筆有效交易")
    logger.info(f"  Buy: {(df['direction'] == 'Buy').sum()}, Sale: {(df['direction'] == 'Sale').sum()}")
    logger.info(f"  唯一標的: {df['ticker'].nunique()}, 唯一政治人物: {df['politician_name'].nunique()}")

    return df


def _extract_ticker(asset_text: str, cell) -> str:
    """從資產名稱提取 ticker。"""
    # Capitol Trades 格式通常是 "COMPANY NAME\nTICKER" 或 "COMPANY NAMETICKER"
    # ticker 通常是最後的大寫字母序列
    parts = asset_text.split("\n") if "\n" in asset_text else [asset_text]

    # 嘗試從文字中找到 ticker 模式（2-5 個大寫字母）
    for part in reversed(parts):
        part = part.strip()
        # 跳過 N/A
        if part == "N/A":
            continue
        # 完全匹配 ticker 模式
        if re.match(r"^[A-Z]{1,5}$", part):
            return part

    # 嘗試從末尾提取
    match = re.search(r"([A-Z]{1,5})(?:N/A)?$", asset_text)
    if match:
        candidate = match.group(1)
        if candidate not in ("N", "NA", "INC", "LLC", "LP", "LTD", "ETF", "CORP"):
            return candidate

    return "N/A"


def _parse_capitol_date(text: str) -> Optional[datetime]:
    """解析 Capitol Trades 日期格式（如 '25 Feb2026' 或 '11 Feb2026'）。"""
    text = text.strip()
    # 移除 "Yesterday", "Today" 等
    if "Yesterday" in text or "Today" in text or "ago" in text:
        return datetime.now() - timedelta(days=1)

    # 常見格式: "25 Feb2026" 或 "11 Feb 2026"
    # 加入空格
    text = re.sub(r"(\d{1,2})\s*([A-Za-z]{3})\s*(\d{4})", r"\1 \2 \3", text)

    for fmt in ["%d %b %Y", "%d %B %Y", "%Y-%m-%d", "%m/%d/%Y"]:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue

    # 嘗試提取數字和月份
    match = re.search(r"(\d{1,2})\s*([A-Za-z]+)\s*(\d{4})", text)
    if match:
        try:
            return datetime.strptime(f"{match.group(1)} {match.group(2)} {match.group(3)}", "%d %b %Y")
        except ValueError:
            pass

    return None


def parse_amount_lower(amount_str) -> float:
    """解析金額範圍字串，回傳下限。"""
    if not isinstance(amount_str, str):
        return 0.0
    cleaned = amount_str.replace("$", "").replace(",", "").replace("\u2013", "-").strip()
    numbers = re.findall(r"[\d]+(?:\.[\d]+)?", cleaned.replace("K", "000").replace("M", "000000"))
    if numbers:
        return float(numbers[0])
    # 嘗試解析 "15K" 格式
    match = re.search(r"(\d+)K", amount_str)
    if match:
        return float(match.group(1)) * 1000
    return 0.0


# ════════════════════════════════════════════════════════════════
# 2. 股價下載
# ════════════════════════════════════════════════════════════════

def download_prices(tickers: List[str], start: str, end: str) -> Dict[str, pd.DataFrame]:
    """批量下載股價。"""
    import yfinance as yf

    all_tickers = list(set(tickers + ["SPY"]))
    logger.info(f"正在下載 {len(all_tickers)} 個標的的股價（{start} ~ {end}）...")

    price_cache = {}
    failed = []

    batch_size = 200
    for i in range(0, len(all_tickers), batch_size):
        batch = all_tickers[i:i + batch_size]
        logger.info(f"  批次 {i // batch_size + 1}: {len(batch)} 個標的")
        try:
            data = yf.download(batch, start=start, end=end, auto_adjust=True, progress=False, threads=True)
            if data.empty:
                failed.extend(batch)
                continue

            for ticker in batch:
                try:
                    if len(batch) == 1:
                        prices = data[["Close"]].copy()
                    else:
                        prices = data["Close"][[ticker]].copy()
                        prices.columns = ["Close"]
                    prices = prices.dropna()
                    if len(prices) > 0:
                        price_cache[ticker] = prices
                    else:
                        failed.append(ticker)
                except (KeyError, TypeError):
                    failed.append(ticker)
        except Exception as e:
            logger.warning(f"  批次下載失敗: {e}")
            failed.extend(batch)

    if failed:
        logger.warning(f"  {len(failed)} 個標的無法下載（前 10 個: {failed[:10]}）")
    logger.info(f"  成功下載: {len(price_cache)} / {len(all_tickers)}")
    return price_cache


# ════════════════════════════════════════════════════════════════
# 3. CAR 計算
# ════════════════════════════════════════════════════════════════

def calculate_car(price_cache, ticker, event_date, window, direction):
    """計算單筆交易的 CAR。"""
    if ticker not in price_cache or "SPY" not in price_cache:
        return None

    stock_prices = price_cache[ticker]
    spy_prices = price_cache["SPY"]
    event_ts = pd.Timestamp(event_date)

    stock_after = stock_prices[stock_prices.index >= event_ts]
    spy_after = spy_prices[spy_prices.index >= event_ts]

    if len(stock_after) < window + 1 or len(spy_after) < window + 1:
        return None

    stock_window = stock_after.iloc[:window + 1]["Close"]
    spy_window = spy_after.iloc[:window + 1]["Close"]

    stock_returns = stock_window.pct_change().dropna()
    spy_returns = spy_window.pct_change().dropna()

    common_dates = stock_returns.index.intersection(spy_returns.index)
    if len(common_dates) < 1:
        return None

    ar = stock_returns.loc[common_dates].values - spy_returns.loc[common_dates].values
    car = float(np.sum(ar))

    if direction == "Sale":
        car = -car

    return car


def run_backtest(df, price_cache):
    """對所有交易計算 CAR。"""
    results = []
    total = len(df)
    logger.info(f"開始計算 CAR（共 {total} 筆交易，窗口: {WINDOWS}）...")

    for idx, (_, row) in enumerate(df.iterrows()):
        if (idx + 1) % 200 == 0:
            logger.info(f"  進度: {idx + 1}/{total}")

        record = {
            "politician_name": row["politician_name"],
            "ticker": row["ticker"],
            "direction": row["direction"],
            "transaction_date": row["transaction_date"],
            "disclosure_date": row["disclosure_date"],
            "filing_lag": row.get("filing_lag", None),
            "amount": row.get("amount", ""),
            "amount_lower": row.get("amount_lower", 0),
            "chamber": row["chamber"],
        }

        for w in WINDOWS:
            car = calculate_car(price_cache, row["ticker"], row["disclosure_date"], w, row["direction"])
            record[f"CAR_{w}d"] = car

        results.append(record)

    results_df = pd.DataFrame(results)
    for w in WINDOWS:
        col = f"CAR_{w}d"
        valid = results_df[col].notna().sum()
        logger.info(f"  CAR {w}d 有效: {valid}/{total}")

    return results_df


# ════════════════════════════════════════════════════════════════
# 4. 分析與報告
# ════════════════════════════════════════════════════════════════

def compute_stats(df, car_cols):
    result = {}
    for col in car_cols:
        valid = df[col].dropna()
        n = len(valid)
        if n < MIN_SAMPLES_FOR_STATS:
            result[col] = {"n": n, "mean": float(valid.mean()) if n > 0 else None,
                           "median": float(valid.median()) if n > 0 else None,
                           "std": None, "t_stat": None, "p_value": None,
                           "hit_rate": float((valid > 0).sum() / n) if n > 0 else None}
            continue
        mean_car = float(valid.mean())
        median_car = float(valid.median())
        std_car = float(valid.std())
        t_stat, p_value = stats.ttest_1samp(valid, 0)
        hit_rate = float((valid > 0).sum() / n)
        result[col] = {"n": n, "mean": mean_car, "median": median_car, "std": std_car,
                        "t_stat": float(t_stat), "p_value": float(p_value), "hit_rate": hit_rate}
    return result


def stratified_analysis(results):
    car_cols = [f"CAR_{w}d" for w in WINDOWS]
    analysis = {}
    analysis["全樣本"] = compute_stats(results, car_cols)

    for d in ["Buy", "Sale"]:
        sub = results[results["direction"] == d]
        if len(sub) > 0:
            analysis[f"交易方向: {d}"] = compute_stats(sub, car_cols)

    tiers = [("$1K-$15K", 1000, 15001), ("$15K-$50K", 15001, 50001),
             ("$50K-$100K", 50001, 100001), ("$100K+", 100001, float("inf"))]
    for label, lo, hi in tiers:
        sub = results[(results["amount_lower"] >= lo) & (results["amount_lower"] < hi)]
        if len(sub) > 0:
            analysis[f"金額: {label}"] = compute_stats(sub, car_cols)

    for chamber in ["House", "Senate"]:
        sub = results[results["chamber"] == chamber]
        if len(sub) > 0:
            analysis[f"院別: {chamber}"] = compute_stats(sub, car_cols)

    valid_lag = results.dropna(subset=["filing_lag"])
    for label, lo, hi in [("< 15 天", 0, 15), ("15-44 天", 15, 45), (">= 45 天", 45, 999)]:
        sub = valid_lag[(valid_lag["filing_lag"] >= lo) & (valid_lag["filing_lag"] < hi)]
        if len(sub) > 0:
            analysis[f"Filing Lag {label}"] = compute_stats(sub, car_cols)

    return analysis


def top_politicians_analysis(results, top_n=15):
    rows = []
    for name, group in results.groupby("politician_name"):
        car5_valid = group["CAR_5d"].dropna()
        if len(car5_valid) < 3:
            continue
        car20_valid = group["CAR_20d"].dropna()
        car60_valid = group["CAR_60d"].dropna()
        rows.append({
            "politician_name": name,
            "n_trades": len(group),
            "n_buy": int((group["direction"] == "Buy").sum()),
            "n_sale": int((group["direction"] == "Sale").sum()),
            "chamber": group["chamber"].mode().iloc[0] if not group["chamber"].mode().empty else "",
            "CAR_5d_mean": float(car5_valid.mean()),
            "CAR_5d_n": len(car5_valid),
            "CAR_5d_hit": float((car5_valid > 0).sum() / len(car5_valid)),
            "CAR_20d_mean": float(car20_valid.mean()) if len(car20_valid) > 0 else None,
            "CAR_20d_n": len(car20_valid),
            "CAR_60d_mean": float(car60_valid.mean()) if len(car60_valid) > 0 else None,
            "CAR_60d_n": len(car60_valid),
        })
    if not rows:
        return pd.DataFrame()
    pol_df = pd.DataFrame(rows).sort_values("CAR_5d_mean", ascending=False, na_position="last")
    return pol_df.head(top_n)


def _sig(p):
    if p is None: return ""
    if p < 0.01: return " ***"
    if p < 0.05: return " **"
    if p < 0.10: return " *"
    return ""


def _f(v, fmt=".4f"):
    return "N/A" if v is None else f"{v:{fmt}}"


def generate_report(results, analysis, pol_df, output_path):
    L = []
    L.append("# Alpha 回測報告（擴展版 — Capitol Trades 歷史數據）")
    L.append(f"日期: {datetime.now().strftime('%Y-%m-%d')}")
    L.append("")

    L.append("## 資料來源")
    L.append("")
    L.append("| 來源 | 說明 |")
    L.append("|------|------|")
    L.append("| Capitol Trades | capitoltrades.com 公開歷史交易列表 |")
    L.append(f"| 回溯期間 | 最近 {LOOKBACK_MONTHS} 個月 |")
    L.append(f"| 抓取頁數 | 最多 {MAX_PAGES} 頁（每頁 100 筆） |")
    L.append("")

    L.append("## 方法論")
    L.append("")
    L.append("| 參數 | 設定 |")
    L.append("|------|------|")
    L.append("| 事件日 | Disclosure Date（揭露日） |")
    L.append("| 事件窗口 | [0, +5], [0, +20], [0, +60] 交易日 |")
    L.append("| Benchmark | SPY (S&P 500 ETF) |")
    L.append("| 異常報酬 | AR = R_stock - R_SPY |")
    L.append("| 累積異常報酬 | CAR = sum(AR) |")
    L.append("| Sale 方向 | CAR 取反（股價下跌 = 正 alpha） |")
    L.append(f"| 最小樣本數 | {MIN_SAMPLES_FOR_STATS} |")
    L.append("")

    L.append("## 資料概覽")
    L.append("")
    L.append(f"- 總交易筆數: {len(results)}")
    L.append(f"- 唯一標的數: {results['ticker'].nunique()}")
    L.append(f"- 唯一政治人物: {results['politician_name'].nunique()}")
    tx_min, tx_max = results["transaction_date"].min(), results["transaction_date"].max()
    dd_min, dd_max = results["disclosure_date"].min(), results["disclosure_date"].max()
    L.append(f"- 交易日期範圍: {tx_min.strftime('%Y-%m-%d') if pd.notna(tx_min) else 'N/A'} ~ {tx_max.strftime('%Y-%m-%d') if pd.notna(tx_max) else 'N/A'}")
    L.append(f"- 揭露日期範圍: {dd_min.strftime('%Y-%m-%d') if pd.notna(dd_min) else 'N/A'} ~ {dd_max.strftime('%Y-%m-%d') if pd.notna(dd_max) else 'N/A'}")
    buy_n = (results["direction"] == "Buy").sum()
    sale_n = (results["direction"] == "Sale").sum()
    L.append(f"- Buy / Sale: {buy_n} / {sale_n}")
    valid_lag = results["filing_lag"].dropna()
    if len(valid_lag) > 0:
        L.append(f"- 中位數 Filing Lag: {valid_lag.median():.0f} 天")
    for w in WINDOWS:
        L.append(f"- CAR {w}d 有效樣本: {results[f'CAR_{w}d'].notna().sum()}")
    L.append("")

    for group_name, group_stats in analysis.items():
        L.append(f"## {group_name}")
        L.append("")
        L.append("| 窗口 | 樣本數 | 平均 CAR | 中位數 CAR | 標準差 | t-stat | p-value | Hit Rate |")
        L.append("|------|--------|---------|-----------|--------|--------|---------|----------|")
        for col, s in group_stats.items():
            wl = col.replace("CAR_", "").replace("d", " 日")
            sig = _sig(s.get("p_value"))
            hr = f"{s['hit_rate']:.1%}" if s.get("hit_rate") is not None else "N/A"
            L.append(f"| {wl} | {s['n']} | {_f(s['mean'])}{sig} | {_f(s['median'])} | "
                     f"{_f(s['std'])} | {_f(s.get('t_stat'), '.3f')} | {_f(s.get('p_value'))} | {hr} |")
        L.append("")

    if not pol_df.empty:
        L.append("## 議員 Alpha 排行榜（按 5 日 CAR 排序，至少 3 筆交易）")
        L.append("")
        L.append("| 排名 | 議員 | 院別 | 交易數 | Buy/Sale | 5d CAR | 5d Hit | 20d CAR | 60d CAR |")
        L.append("|------|------|------|--------|----------|--------|--------|---------|---------|")
        for rank, (_, row) in enumerate(pol_df.iterrows(), 1):
            hr5 = f"{row['CAR_5d_hit']:.1%}" if row.get("CAR_5d_hit") is not None else "N/A"
            L.append(f"| {rank} | {row['politician_name']} | {row['chamber']} | "
                     f"{row['n_trades']} | {row['n_buy']}/{row['n_sale']} | "
                     f"{_f(row['CAR_5d_mean'])} | {hr5} | "
                     f"{_f(row['CAR_20d_mean'])} | {_f(row['CAR_60d_mean'])} |")
        L.append("")

    # 結論
    L.append("## 結論與建議")
    L.append("")
    full = analysis.get("全樣本", {})
    for w in WINDOWS:
        col = f"CAR_{w}d"
        s = full.get(col, {})
        if s.get("mean") is not None:
            sig_text = "統計顯著" if s.get("p_value") is not None and s["p_value"] < 0.05 else "統計不顯著"
            hr = f"{s['hit_rate']:.1%}" if s.get("hit_rate") is not None else "N/A"
            L.append(f"- **{w} 日 CAR**: 平均 {s['mean']:.4f}，{sig_text}（p = {_f(s.get('p_value'))}），Hit Rate = {hr}")

    buy_s = analysis.get("交易方向: Buy", {}).get("CAR_5d", {})
    sale_s = analysis.get("交易方向: Sale", {}).get("CAR_5d", {})
    if buy_s.get("mean") is not None and sale_s.get("mean") is not None:
        L.append("")
        L.append("### Buy vs Sale 比較")
        L.append(f"- Buy 5d CAR = {buy_s['mean']:.4f}（n={buy_s['n']}），Sale 5d CAR = {sale_s['mean']:.4f}（n={sale_s['n']}）")

    L.append("")
    L.append("### 限制")
    L.append("- Capitol Trades 數據可能有延遲或遺漏")
    L.append("- Market-Adjusted Model 較簡化，未來可改用 CAPM / FF3")
    L.append("- 部分 ticker 無法在 yfinance 取得（已排除）")
    L.append("- 未考慮交易成本與市場衝擊")
    L.append("- 多重檢定可能產生假陽性")
    L.append("")
    L.append("---")
    L.append(f"*報告由 Political Alpha Monitor 自動生成 — {datetime.now().strftime('%Y-%m-%d %H:%M')}*")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text("\n".join(L), encoding="utf-8")
    logger.info(f"報告已生成: {output_path}")


# ════════════════════════════════════════════════════════════════
# Main
# ════════════════════════════════════════════════════════════════

def main():
    logger.info("=" * 60)
    logger.info("  歷史國會交易 Alpha 回測 — Capitol Trades 數據")
    logger.info("=" * 60)

    df = fetch_historical_data()
    if df.empty or len(df) < 10:
        logger.error("有效數據不足，無法回測")
        sys.exit(1)

    tickers = df["ticker"].unique().tolist()
    min_date = df["disclosure_date"].min() - timedelta(days=10)
    max_date = pd.Timestamp.now() + timedelta(days=1)
    price_cache = download_prices(tickers, min_date.strftime("%Y-%m-%d"), max_date.strftime("%Y-%m-%d"))

    if "SPY" not in price_cache:
        logger.error("無法下載 SPY 數據，回測中止")
        sys.exit(1)

    results = run_backtest(df, price_cache)
    if results.empty:
        logger.error("回測結果為空")
        sys.exit(1)

    analysis = stratified_analysis(results)
    pol_df = top_politicians_analysis(results)

    report_path = "docs/reports/Alpha_Backtest_Extended_2026-02-27.md"
    generate_report(results, analysis, pol_df, report_path)

    # 印出摘要
    print("\n" + "=" * 70)
    print("  Alpha 回測摘要（擴展版 — Capitol Trades）")
    print("=" * 70)
    for gn, gs in analysis.items():
        print(f"\n--- {gn} ---")
        for col, s in gs.items():
            w = col.replace("CAR_", "").replace("d", "")
            n = s["n"]
            if n < MIN_SAMPLES_FOR_STATS:
                print(f"  {w}d: n={n}, 樣本不足")
                continue
            print(f"  {w}d: n={n}, mean={s['mean']:+.4f}, p={s['p_value']:.4f}{_sig(s['p_value'])}, hit={s['hit_rate']:.1%}")


if __name__ == "__main__":
    main()
