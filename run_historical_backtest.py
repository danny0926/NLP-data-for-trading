"""歷史國會交易 Alpha 回測 — 擴展版

資料來源：
1. Capitol Trades (capitoltrades.com) — 最近 12 個月的兩院交易
2. Senate Stock Watcher (GitHub) — 2019-2020 歷史 Senate 交易

方法論：Event Study，以 disclosure_date 為事件日，
計算 5/20/60 交易日 CAR（市場調整模型，benchmark = SPY）。
"""

import io
import re
import sys
import time
import sqlite3
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

# ── 資料來源 ──
SENATE_NESTED_URL = (
    "https://raw.githubusercontent.com/timothycarambat/senate-stock-watcher-data"
    "/master/aggregate/all_daily_summaries.json"
)

# ── 路徑 ──
PROJECT_ROOT = Path(__file__).parent
DB_PATH = PROJECT_ROOT / "data" / "data.db"

# ── 回測參數 ──
WINDOWS = [5, 20, 60]
MIN_SAMPLES_FOR_STATS = 5
CAPITOL_MAX_PAGES = 40  # Capitol Trades 頁數上限
CAPITOL_LOOKBACK_MONTHS = 12


# ════════════════════════════════════════════════════════════════
# 1A. Capitol Trades 資料下載（最近 12 個月）
# ════════════════════════════════════════════════════════════════

def fetch_capitol_trades() -> pd.DataFrame:
    """從 Capitol Trades 抓取歷史交易數據。"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    all_trades = []
    cutoff = datetime.now() - timedelta(days=CAPITOL_LOOKBACK_MONTHS * 30)

    for page in range(1, CAPITOL_MAX_PAGES + 1):
        url = "https://www.capitoltrades.com/trades?page=%d&pageSize=100" % page
        try:
            resp = requests.get(url, headers=headers, timeout=30)
            resp.raise_for_status()
        except Exception as e:
            logger.warning("Page %d 下載失敗: %s" % (page, e))
            break

        soup = BeautifulSoup(resp.text, "html.parser")
        rows = soup.select("table tbody tr")
        if not rows:
            logger.info("Page %d: 無更多資料" % page)
            break

        page_trades = []
        oldest_on_page = None

        for row in rows:
            cells = row.find_all("td")
            if len(cells) < 9:
                continue

            try:
                # [0] Politician + chamber
                pol_cell = cells[0]
                pol_link = pol_cell.find("a")
                politician_name = pol_link.get_text(strip=True) if pol_link else pol_cell.get_text(strip=True)
                # 清理名字（移除黨派和州名後綴）
                politician_name = _clean_politician_name(politician_name)

                pol_text = pol_cell.get_text(strip=True)
                chamber = "House" if "House" in pol_text else ("Senate" if "Senate" in pol_text else "")

                # [1] Asset + ticker — 使用 CSS selector 提取 ticker
                asset_cell = cells[1]
                ticker_el = asset_cell.select_one(".q-field.issuer-ticker")
                ticker_raw = ticker_el.get_text(strip=True) if ticker_el else "N/A"
                # 格式: "AMD:US" → "AMD"
                ticker = ticker_raw.split(":")[0].strip().upper() if ticker_raw != "N/A" else ""

                if not ticker or ticker == "N/A":
                    continue

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

                if not transaction_date:
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
                    "ticker": ticker,
                    "chamber": chamber,
                    "transaction_date": transaction_date,
                    "disclosure_date": disclosure_date or (transaction_date + timedelta(days=30)),
                    "direction": direction,
                    "amount": amount,
                    "owner": owner,
                    "source": "CapitolTrades",
                }
                page_trades.append(trade)

                if oldest_on_page is None or (disclosure_date and disclosure_date < oldest_on_page):
                    oldest_on_page = disclosure_date or transaction_date

            except Exception:
                continue

        all_trades.extend(page_trades)
        logger.info("Page %d: %d 有效交易（累計 %d）" % (page, len(page_trades), len(all_trades)))

        if oldest_on_page and oldest_on_page < cutoff:
            logger.info("已達回溯期限，停止抓取")
            break

        time.sleep(0.5)

    if not all_trades:
        return pd.DataFrame()

    df = pd.DataFrame(all_trades)
    df["ticker"] = df["ticker"].str.replace(".", "-", regex=False)
    df = df[df["ticker"].str.len().between(1, 5)]

    # 日期篩選
    df = df[df["disclosure_date"] >= cutoff]
    df = df[df["disclosure_date"] <= datetime.now() + timedelta(days=1)]

    df["filing_lag"] = (df["disclosure_date"] - df["transaction_date"]).dt.days
    df["amount_lower"] = df["amount"].apply(parse_amount_lower)

    logger.info("Capitol Trades: %d 筆有效（Buy: %d, Sale: %d, 標的: %d）" % (
        len(df), (df["direction"] == "Buy").sum(), (df["direction"] == "Sale").sum(),
        df["ticker"].nunique(),
    ))
    return df


def _clean_politician_name(raw_name):
    """從 'Scott PetersDemocratHouseCA' 提取 'Scott Peters'。"""
    # 常見黨派/院別/州名需移除
    for suffix in ["Democrat", "Republican", "Independent",
                    "House", "Senate"]:
        idx = raw_name.find(suffix)
        if idx > 0:
            raw_name = raw_name[:idx]
            break
    return raw_name.strip()


def _parse_capitol_date(text):
    # type: (str) -> Optional[datetime]
    """解析 Capitol Trades 日期。"""
    text = text.strip()
    if "Yesterday" in text or "Today" in text or "ago" in text:
        return datetime.now() - timedelta(days=1)

    # "25 Feb2026" → "25 Feb 2026"
    text = re.sub(r"(\d{1,2})\s*([A-Za-z]{3})\s*(\d{4})", r"\1 \2 \3", text)

    for fmt in ["%d %b %Y", "%d %B %Y", "%Y-%m-%d", "%m/%d/%Y"]:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue

    match = re.search(r"(\d{1,2})\s*([A-Za-z]+)\s*(\d{4})", text)
    if match:
        try:
            return datetime.strptime(
                "%s %s %s" % (match.group(1), match.group(2), match.group(3)),
                "%d %b %Y",
            )
        except ValueError:
            pass
    return None


# ════════════════════════════════════════════════════════════════
# 1B. Senate Stock Watcher 資料（2019-2020 歷史）
# ════════════════════════════════════════════════════════════════

def fetch_senate_historical() -> pd.DataFrame:
    """從 GitHub 下載 Senate 歷史交易（nested JSON with disclosure dates）。"""
    logger.info("正在下載 Senate Stock Watcher 歷史數據 ...")
    resp = requests.get(SENATE_NESTED_URL, timeout=120)
    resp.raise_for_status()
    filings = resp.json()
    logger.info("  共 %d 筆 filing 記錄" % len(filings))

    rows = []
    for filing in filings:
        disc_str = filing.get("date_recieved", "")
        name = "%s %s" % (
            filing.get("first_name", "").strip(),
            filing.get("last_name", "").strip(),
        )
        name = name.strip()

        for tx in filing.get("transactions", []):
            ticker_raw = tx.get("ticker", "").strip()
            if not ticker_raw or ticker_raw == "--" or ticker_raw == "N/A":
                continue

            # ticker 可能是 HTML: <a href="...?s=BA" ...>BA</a>
            ticker = _extract_ticker_from_html(ticker_raw)
            if not ticker:
                continue

            tx_type = tx.get("type", "")
            direction = None
            tx_lower = tx_type.lower()
            if "purchase" in tx_lower or "buy" in tx_lower:
                direction = "Buy"
            elif "sale" in tx_lower or "sell" in tx_lower:
                direction = "Sale"
            if not direction:
                continue

            rows.append({
                "politician_name": name,
                "ticker": ticker.upper(),
                "transaction_type": tx_type,
                "direction": direction,
                "amount": tx.get("amount", ""),
                "owner": tx.get("owner", ""),
                "transaction_date_str": tx.get("transaction_date", ""),
                "disclosure_date_str": disc_str,
                "chamber": "Senate",
                "source": "SenateStockWatcher",
            })

    df = pd.DataFrame(rows)
    logger.info("  展開後 %d 筆有效交易" % len(df))

    df["transaction_date"] = pd.to_datetime(df["transaction_date_str"], format="%m/%d/%Y", errors="coerce")
    df["disclosure_date"] = pd.to_datetime(df["disclosure_date_str"], format="%m/%d/%Y", errors="coerce")

    # 過濾 2019-2020
    df = df[df["disclosure_date"] >= "2019-01-01"]
    df = df[df["disclosure_date"] <= "2020-12-31"]
    df = df.dropna(subset=["transaction_date"])

    # 清理 ticker
    df["ticker"] = df["ticker"].str.replace(".", "-", regex=False)
    df = df[df["ticker"].str.len().between(1, 5)]

    df["filing_lag"] = (df["disclosure_date"] - df["transaction_date"]).dt.days
    df["amount_lower"] = df["amount"].apply(parse_amount_lower)

    logger.info("Senate Stock Watcher (2019-2020): %d 筆有效" % len(df))
    return df


# ════════════════════════════════════════════════════════════════
# 1C. ETL 資料庫
# ════════════════════════════════════════════════════════════════

def fetch_etl_data() -> pd.DataFrame:
    """從本地 ETL 資料庫取得交易數據。"""
    if not DB_PATH.exists():
        logger.warning("ETL 資料庫不存在: %s" % DB_PATH)
        return pd.DataFrame()

    conn = sqlite3.connect(str(DB_PATH))
    query = """
    SELECT politician_name, ticker, transaction_type, transaction_date,
           filing_date AS disclosure_date, amount_range AS amount,
           chamber, owner
    FROM congress_trades
    WHERE ticker IS NOT NULL AND ticker != ''
    """
    df = pd.read_sql_query(query, conn)
    conn.close()

    df["transaction_date"] = pd.to_datetime(df["transaction_date"], errors="coerce")
    df["disclosure_date"] = pd.to_datetime(df["disclosure_date"], errors="coerce")
    df = df.dropna(subset=["transaction_date", "disclosure_date"])

    df["ticker"] = df["ticker"].str.replace(".", "-", regex=False).str.upper().str.strip()
    df = df[df["ticker"].str.len().between(1, 5)]

    # 方向分類
    def classify(tx):
        if not isinstance(tx, str):
            return None
        t = tx.lower()
        if "buy" in t or "purchase" in t:
            return "Buy"
        if "sale" in t or "sell" in t:
            return "Sale"
        return None

    df["direction"] = df["transaction_type"].apply(classify)
    df = df.dropna(subset=["direction"])
    df["filing_lag"] = (df["disclosure_date"] - df["transaction_date"]).dt.days
    df["amount_lower"] = df["amount"].apply(parse_amount_lower)
    df["source"] = "ETL"

    logger.info("ETL 資料: %d 筆" % len(df))
    return df


def parse_amount_lower(amount_str):
    """解析金額範圍字串，回傳下限。"""
    if not isinstance(amount_str, str):
        return 0.0
    cleaned = amount_str.replace("$", "").replace(",", "").replace("\u2013", "-").strip()
    # 處理 "15K" 等格式
    cleaned = re.sub(r"(\d+)K", lambda m: str(int(m.group(1)) * 1000), cleaned)
    cleaned = re.sub(r"(\d+)M", lambda m: str(int(m.group(1)) * 1000000), cleaned)
    numbers = re.findall(r"[\d]+(?:\.[\d]+)?", cleaned)
    if numbers:
        return float(numbers[0])
    return 0.0


# ════════════════════════════════════════════════════════════════
# 2. 股價下載
# ════════════════════════════════════════════════════════════════

def download_prices(tickers, start, end):
    # type: (List[str], str, str) -> Dict[str, pd.DataFrame]
    """批量下載股價。"""
    import yfinance as yf

    all_tickers = list(set(tickers + ["SPY"]))
    logger.info("正在下載 %d 個標的的股價（%s ~ %s）..." % (len(all_tickers), start, end))

    price_cache = {}  # type: Dict[str, pd.DataFrame]
    failed = []

    batch_size = 200
    for i in range(0, len(all_tickers), batch_size):
        batch = all_tickers[i:i + batch_size]
        logger.info("  批次 %d/%d: %d 個標的" % (
            i // batch_size + 1, (len(all_tickers) - 1) // batch_size + 1, len(batch)
        ))
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
            logger.warning("  批次下載失敗: %s" % e)
            failed.extend(batch)

    if failed:
        logger.warning("  %d 個標的無法下載" % len(failed))
    logger.info("  成功下載: %d / %d" % (len(price_cache), len(all_tickers)))
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
    logger.info("開始計算 CAR（共 %d 筆交易，窗口: %s）..." % (total, WINDOWS))

    for idx, (_, row) in enumerate(df.iterrows()):
        if (idx + 1) % 500 == 0:
            logger.info("  進度: %d/%d" % (idx + 1, total))

        record = {
            "politician_name": row["politician_name"],
            "ticker": row["ticker"],
            "direction": row["direction"],
            "transaction_date": row["transaction_date"],
            "disclosure_date": row["disclosure_date"],
            "filing_lag": row.get("filing_lag", None),
            "amount": row.get("amount", ""),
            "amount_lower": row.get("amount_lower", 0),
            "chamber": row.get("chamber", ""),
            "source": row.get("source", ""),
        }

        for w in WINDOWS:
            car = calculate_car(price_cache, row["ticker"], row["disclosure_date"], w, row["direction"])
            record["CAR_%dd" % w] = car

        results.append(record)

    results_df = pd.DataFrame(results)
    for w in WINDOWS:
        col = "CAR_%dd" % w
        valid = results_df[col].notna().sum()
        logger.info("  CAR %dd 有效: %d/%d" % (w, valid, total))

    return results_df


# ════════════════════════════════════════════════════════════════
# 4. 分析
# ════════════════════════════════════════════════════════════════

def compute_stats(df, car_cols):
    result = {}
    for col in car_cols:
        valid = df[col].dropna()
        n = len(valid)
        if n < MIN_SAMPLES_FOR_STATS:
            result[col] = {
                "n": n,
                "mean": float(valid.mean()) if n > 0 else None,
                "median": float(valid.median()) if n > 0 else None,
                "std": None, "t_stat": None, "p_value": None,
                "hit_rate": float((valid > 0).sum() / n) if n > 0 else None,
            }
            continue
        mean_car = float(valid.mean())
        median_car = float(valid.median())
        std_car = float(valid.std())
        t_stat, p_value = stats.ttest_1samp(valid, 0)
        hit_rate = float((valid > 0).sum() / n)
        result[col] = {
            "n": n, "mean": mean_car, "median": median_car, "std": std_car,
            "t_stat": float(t_stat), "p_value": float(p_value), "hit_rate": hit_rate,
        }
    return result


def stratified_analysis(results):
    car_cols = ["CAR_%dd" % w for w in WINDOWS]
    analysis = {}

    analysis["全樣本"] = compute_stats(results, car_cols)

    for d in ["Buy", "Sale"]:
        sub = results[results["direction"] == d]
        if len(sub) > 0:
            analysis["交易方向: %s" % d] = compute_stats(sub, car_cols)

    tiers = [
        ("$1K-$15K", 1000, 15001),
        ("$15K-$50K", 15001, 50001),
        ("$50K-$100K", 50001, 100001),
        ("$100K+", 100001, float("inf")),
    ]
    for label, lo, hi in tiers:
        sub = results[(results["amount_lower"] >= lo) & (results["amount_lower"] < hi)]
        if len(sub) > 0:
            analysis["金額: %s" % label] = compute_stats(sub, car_cols)

    for chamber in ["House", "Senate"]:
        sub = results[results["chamber"] == chamber]
        if len(sub) > 0:
            analysis["院別: %s" % chamber] = compute_stats(sub, car_cols)

    valid_lag = results.dropna(subset=["filing_lag"])
    for label, lo, hi in [("< 15 天", 0, 15), ("15-44 天", 15, 45), (">= 45 天", 45, 9999)]:
        sub = valid_lag[(valid_lag["filing_lag"] >= lo) & (valid_lag["filing_lag"] < hi)]
        if len(sub) > 0:
            analysis["Filing Lag %s" % label] = compute_stats(sub, car_cols)

    return analysis


def top_politicians_analysis(results, top_n=20):
    rows = []
    for name, group in results.groupby("politician_name"):
        car5 = group["CAR_5d"].dropna()
        if len(car5) < 5:
            continue
        car20 = group["CAR_20d"].dropna()
        car60 = group["CAR_60d"].dropna()
        rows.append({
            "politician_name": name,
            "n_trades": len(group),
            "n_buy": int((group["direction"] == "Buy").sum()),
            "n_sale": int((group["direction"] == "Sale").sum()),
            "chamber": group["chamber"].mode().iloc[0] if not group["chamber"].mode().empty else "",
            "CAR_5d_mean": float(car5.mean()),
            "CAR_5d_n": len(car5),
            "CAR_5d_hit": float((car5 > 0).sum() / len(car5)),
            "CAR_20d_mean": float(car20.mean()) if len(car20) > 0 else None,
            "CAR_20d_n": len(car20),
            "CAR_60d_mean": float(car60.mean()) if len(car60) > 0 else None,
            "CAR_60d_n": len(car60),
        })
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values("CAR_5d_mean", ascending=False).head(top_n)


# ════════════════════════════════════════════════════════════════
# 5. 報告
# ════════════════════════════════════════════════════════════════

def _sig(p):
    if p is None: return ""
    if p < 0.01: return " ***"
    if p < 0.05: return " **"
    if p < 0.10: return " *"
    return ""


def _f(v, fmt=".4f"):
    if v is None: return "N/A"
    return ("{:" + fmt + "}").format(v)


def _write_stats_table(L, group_stats):
    L.append("| 窗口 | 樣本數 | 平均 CAR | 中位數 CAR | 標準差 | t-stat | p-value | Hit Rate |")
    L.append("|------|--------|---------|-----------|--------|--------|---------|----------|")
    for col, s in group_stats.items():
        wl = col.replace("CAR_", "").replace("d", " 日")
        sig = _sig(s.get("p_value"))
        hr = ("%.1f%%" % (s["hit_rate"] * 100)) if s.get("hit_rate") is not None else "N/A"
        L.append("| %s | %d | %s%s | %s | %s | %s | %s | %s |" % (
            wl, s["n"], _f(s["mean"]), sig, _f(s["median"]),
            _f(s["std"]), _f(s.get("t_stat"), ".3f"),
            _f(s.get("p_value")), hr,
        ))


def generate_report(results, analysis, pol_df, hist_results, hist_analysis, output_path):
    L = []

    L.append("# Alpha 回測報告（擴展版 — 歷史數據）")
    L.append("日期: %s" % datetime.now().strftime("%Y-%m-%d"))
    L.append("")

    # ── 方法論 ──
    L.append("## 方法論")
    L.append("")
    L.append("| 參數 | 設定 |")
    L.append("|------|------|")
    L.append("| 事件日 | Disclosure Date（揭露日 / Filing Date） |")
    L.append("| 事件窗口 | [0, +5], [0, +20], [0, +60] 交易日 |")
    L.append("| Benchmark | SPY (S&P 500 ETF) |")
    L.append("| 異常報酬 | AR = R_stock - R_SPY |")
    L.append("| 累積異常報酬 | CAR = sum(AR) |")
    L.append("| Sale 方向 | CAR 取反（股價下跌 = 正 alpha） |")
    L.append("| 統計檢定 | 單樣本 t-test (H0: CAR = 0)，最少 %d 筆 |" % MIN_SAMPLES_FOR_STATS)
    L.append("")

    # ════════════ Part A: Capitol Trades ════════════
    L.append("---")
    L.append("")
    L.append("# Part A: Capitol Trades 回測（最近 %d 個月）" % CAPITOL_LOOKBACK_MONTHS)
    L.append("")

    # 資料概覽
    L.append("## 資料概覽")
    L.append("")
    L.append("- 總交易筆數: %d" % len(results))
    L.append("- 唯一標的數: %d" % results["ticker"].nunique())
    L.append("- 唯一政治人物: %d" % results["politician_name"].nunique())
    tx_min = results["transaction_date"].min()
    tx_max = results["transaction_date"].max()
    dd_min = results["disclosure_date"].min()
    dd_max = results["disclosure_date"].max()
    L.append("- 交易日期範圍: %s ~ %s" % (
        tx_min.strftime("%Y-%m-%d") if pd.notna(tx_min) else "N/A",
        tx_max.strftime("%Y-%m-%d") if pd.notna(tx_max) else "N/A",
    ))
    L.append("- 揭露日期範圍: %s ~ %s" % (
        dd_min.strftime("%Y-%m-%d") if pd.notna(dd_min) else "N/A",
        dd_max.strftime("%Y-%m-%d") if pd.notna(dd_max) else "N/A",
    ))
    buy_n = int((results["direction"] == "Buy").sum())
    sale_n = int((results["direction"] == "Sale").sum())
    L.append("- Buy / Sale: %d / %d" % (buy_n, sale_n))
    valid_lag = results["filing_lag"].dropna()
    if len(valid_lag) > 0:
        L.append("- 中位數 Filing Lag: %.0f 天" % valid_lag.median())
    for w in WINDOWS:
        v = results["CAR_%dd" % w].notna().sum()
        L.append("- CAR %dd 有效樣本: %d" % (w, v))
    L.append("")

    # 分層結果
    for gname, gstats in analysis.items():
        L.append("## %s" % gname)
        L.append("")
        _write_stats_table(L, gstats)
        L.append("")

    # 議員排行榜
    if pol_df is not None and not pol_df.empty:
        L.append("## 議員 Alpha 排行榜（按 5 日 CAR 排序，至少 5 筆有效交易）")
        L.append("")
        L.append("| 排名 | 議員 | 院別 | 交易數 | Buy/Sale | 5d CAR | 5d Hit | 20d CAR | 60d CAR |")
        L.append("|------|------|------|--------|----------|--------|--------|---------|---------|")
        for rank, (_, row) in enumerate(pol_df.iterrows(), 1):
            hr5 = ("%.1f%%" % (row["CAR_5d_hit"] * 100)) if row.get("CAR_5d_hit") is not None else "N/A"
            L.append("| %d | %s | %s | %d | %d/%d | %s | %s | %s | %s |" % (
                rank, row["politician_name"], row["chamber"],
                row["n_trades"], row["n_buy"], row["n_sale"],
                _f(row["CAR_5d_mean"]), hr5,
                _f(row["CAR_20d_mean"]), _f(row["CAR_60d_mean"]),
            ))
        L.append("")

    # Sale 訊號驗證
    L.append("## Sale 訊號深入分析")
    L.append("")
    L.append("初步回測（ETL 數據 38 筆）發現 Sale 信號 CAR_5d = -5.29%（p=0.032），")
    L.append("意味議員賣出後股價反而上漲。以下以 Capitol Trades 大樣本驗證：")
    L.append("")
    sale_df = results[results["direction"] == "Sale"]
    for w in WINDOWS:
        col = "CAR_%dd" % w
        valid = sale_df[col].dropna()
        n = len(valid)
        if n >= MIN_SAMPLES_FOR_STATS:
            mean = float(valid.mean())
            t, p = stats.ttest_1samp(valid, 0)
            hit = float((valid > 0).sum() / n)
            sig = _sig(p)
            L.append("- **Sale CAR %dd**: mean = %.4f%s, n = %d, p = %.4f, hit = %.1f%%" % (
                w, mean, sig, n, p, hit * 100
            ))
            if mean < 0:
                L.append("  - 負 CAR = 議員賣出後股價上漲（反向訊號）")
            else:
                L.append("  - 正 CAR = 議員賣出後股價下跌（訊號有效）")
        elif n > 0:
            L.append("- **Sale CAR %dd**: mean = %.4f, n = %d（樣本不足）" % (w, float(valid.mean()), n))
    L.append("")

    # ════════════ Part B: 歷史 Senate (2019-2020) ════════════
    if hist_results is not None and not hist_results.empty and hist_analysis:
        L.append("---")
        L.append("")
        L.append("# Part B: Senate Stock Watcher 歷史回測 (2019-2020)")
        L.append("")
        L.append("## 資料概覽")
        L.append("")
        L.append("- 總交易筆數: %d" % len(hist_results))
        L.append("- 唯一標的數: %d" % hist_results["ticker"].nunique())
        L.append("- 唯一政治人物: %d" % hist_results["politician_name"].nunique())
        L.append("- 交易日期範圍: %s ~ %s" % (
            hist_results["transaction_date"].min().strftime("%Y-%m-%d"),
            hist_results["transaction_date"].max().strftime("%Y-%m-%d"),
        ))
        for w in WINDOWS:
            v = hist_results["CAR_%dd" % w].notna().sum()
            L.append("- CAR %dd 有效樣本: %d" % (w, v))
        L.append("")

        for gname, gstats in hist_analysis.items():
            L.append("## %s" % gname)
            L.append("")
            _write_stats_table(L, gstats)
            L.append("")

    # ════════════ 結論 ════════════
    L.append("---")
    L.append("")
    L.append("## 總結論與建議")
    L.append("")

    full = analysis.get("全樣本", {})
    for w in WINDOWS:
        col = "CAR_%dd" % w
        s = full.get(col, {})
        if s.get("mean") is not None:
            sig_text = "統計顯著" if s.get("p_value") is not None and s["p_value"] < 0.05 else "統計不顯著"
            hr = ("%.1f%%" % (s["hit_rate"] * 100)) if s.get("hit_rate") is not None else "N/A"
            L.append("- **Capitol Trades %d 日 CAR**: %.4f，%s（p = %s），Hit Rate = %s" % (
                w, s["mean"], sig_text, _f(s.get("p_value")), hr,
            ))

    if hist_analysis:
        hist_full = hist_analysis.get("全樣本", {})
        for w in WINDOWS:
            col = "CAR_%dd" % w
            s = hist_full.get(col, {})
            if s.get("mean") is not None:
                sig_text = "統計顯著" if s.get("p_value") is not None and s["p_value"] < 0.05 else "統計不顯著"
                L.append("- **歷史 Senate %d 日 CAR**: %.4f，%s（p = %s）" % (
                    w, s["mean"], sig_text, _f(s.get("p_value")),
                ))

    L.append("")
    L.append("### 限制與後續方向")
    L.append("")
    L.append("- Capitol Trades 頁面結構可能變動，ticker 提取率約 65%（非 N/A 部分）")
    L.append("- 歷史數據（2019-2020）含 COVID-19 大波動，可能放大異常報酬")
    L.append("- Market-Adjusted Model 較簡化，後續可用 CAPM 或 Fama-French 三因子")
    L.append("- 部分 ticker 無法在 yfinance 取得（已下市、非美股等），已排除")
    L.append("- 多重檢定問題：大量分層比較可能產生假陽性")
    L.append("- 未考慮交易成本與市場衝擊")
    L.append("")
    L.append("---")
    L.append("*報告由 Political Alpha Monitor 自動生成 — %s*" % datetime.now().strftime("%Y-%m-%d %H:%M"))
    L.append("")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text("\n".join(L), encoding="utf-8")
    logger.info("報告已生成: %s" % output_path)


# ════════════════════════════════════════════════════════════════
# 6. 主程式
# ════════════════════════════════════════════════════════════════

def main():
    logger.info("=" * 60)
    logger.info("  歷史國會交易 Alpha 回測 — 擴展版")
    logger.info("=" * 60)

    # ── Part A: Capitol Trades（最近 12 個月）──
    logger.info("")
    logger.info("=== Part A: Capitol Trades ===")
    cap_df = fetch_capitol_trades()
    if cap_df.empty or len(cap_df) < 20:
        logger.error("Capitol Trades 數據不足，無法回測")
        sys.exit(1)

    cap_tickers = cap_df["ticker"].unique().tolist()
    cap_min = cap_df["disclosure_date"].min() - timedelta(days=10)
    cap_max = pd.Timestamp.now() + timedelta(days=1)
    cap_prices = download_prices(cap_tickers, cap_min.strftime("%Y-%m-%d"), cap_max.strftime("%Y-%m-%d"))
    if "SPY" not in cap_prices:
        logger.error("無法下載 SPY 數據")
        sys.exit(1)

    cap_results = run_backtest(cap_df, cap_prices)
    cap_analysis = stratified_analysis(cap_results)
    cap_pol = top_politicians_analysis(cap_results)

    # ── Part B: Senate Stock Watcher (2019-2020) ──
    logger.info("")
    logger.info("=== Part B: Senate Stock Watcher (2019-2020) ===")
    hist_results = None
    hist_analysis = None
    try:
        hist_df = fetch_senate_historical()
        if not hist_df.empty and len(hist_df) >= 20:
            hist_tickers = hist_df["ticker"].unique().tolist()
            hist_prices = download_prices(hist_tickers, "2018-12-01", "2021-06-01")
            if "SPY" in hist_prices:
                hist_results = run_backtest(hist_df, hist_prices)
                hist_analysis = stratified_analysis(hist_results)
    except Exception as e:
        logger.warning("歷史 Senate 數據處理失敗: %s" % e)

    # ── 報告 ──
    report_path = "docs/reports/Alpha_Backtest_Extended_2026-02-27.md"
    generate_report(cap_results, cap_analysis, cap_pol, hist_results, hist_analysis, report_path)

    # ── 摘要 ──
    print("\n" + "=" * 70)
    print("  Alpha 回測摘要（擴展版）")
    print("=" * 70)
    print("\n=== Capitol Trades (最近 %d 個月) ===" % CAPITOL_LOOKBACK_MONTHS)
    for gn, gs in cap_analysis.items():
        print("\n--- %s ---" % gn)
        for col, s in gs.items():
            w = col.replace("CAR_", "").replace("d", "")
            n = s["n"]
            if n < MIN_SAMPLES_FOR_STATS:
                print("  %sd: n=%d, 樣本不足" % (w, n))
                continue
            print("  %sd: n=%d, mean=%+.4f, p=%.4f%s, hit=%.1f%%" % (
                w, n, s["mean"], s["p_value"], _sig(s["p_value"]), s["hit_rate"] * 100
            ))

    if cap_pol is not None and not cap_pol.empty:
        print("\n--- 議員 Alpha 排行榜 (Top %d) ---" % len(cap_pol))
        for _, row in cap_pol.iterrows():
            print("  %s (%s): n=%d, 5d=%+.4f, hit=%.0f%%" % (
                row["politician_name"], row["chamber"],
                row["n_trades"], row["CAR_5d_mean"], row["CAR_5d_hit"] * 100,
            ))

    if hist_analysis:
        print("\n=== Senate Stock Watcher (2019-2020) ===")
        for gn, gs in hist_analysis.items():
            print("\n--- %s ---" % gn)
            for col, s in gs.items():
                w = col.replace("CAR_", "").replace("d", "")
                n = s["n"]
                if n < MIN_SAMPLES_FOR_STATS:
                    print("  %sd: n=%d, 樣本不足" % (w, n))
                    continue
                print("  %sd: n=%d, mean=%+.4f, p=%.4f%s, hit=%.1f%%" % (
                    w, n, s["mean"], s["p_value"], _sig(s["p_value"]), s["hit_rate"] * 100
                ))


if __name__ == "__main__":
    main()
