"""Ticker 補全模組 — 為 congress_trades 中缺失 ticker 的紀錄補全股票代號。

策略順序：
1. 靜態映射表（常見公司/ETF）
2. asset_name 本身就是 ticker 的模式偵測
3. yfinance 搜尋（公開上市公司）
4. 不可解析類型標記（municipal bond、Treasury、private fund）
"""

import logging
import re
import sqlite3
import time
from typing import Optional, Tuple

logger = logging.getLogger("TickerEnricher")

# ── 靜態映射：asset_name 關鍵字 → ticker ──
# 涵蓋常出現在國會交易中但 LLM 可能遺漏 ticker 的公司
STATIC_MAPPING = {
    # 大型科技股
    "apple inc": "AAPL",
    "microsoft": "MSFT",
    "alphabet": "GOOGL",
    "amazon.com": "AMZN",
    "amazon": "AMZN",
    "meta platforms": "META",
    "nvidia": "NVDA",
    "tesla": "TSLA",
    "broadcom": "AVGO",
    "oracle": "ORCL",
    "salesforce": "CRM",
    "adobe": "ADBE",
    "intel": "INTC",
    "cisco": "CSCO",
    "ibm": "IBM",
    "qualcomm": "QCOM",
    "advanced micro devices": "AMD",
    "texas instruments": "TXN",
    "netflix": "NFLX",
    "palantir": "PLTR",
    "snowflake": "SNOW",
    "servicenow": "NOW",
    "intuit": "INTU",
    "uber": "UBER",
    "airbnb": "ABNB",

    # 金融
    "jpmorgan": "JPM",
    "jp morgan": "JPM",
    "bank of america": "BAC",
    "wells fargo": "WFC",
    "goldman sachs": "GS",
    "morgan stanley": "MS",
    "citigroup": "C",
    "charles schwab": "SCHW",
    "blackrock": "BLK",
    "visa": "V",
    "mastercard": "MA",
    "american express": "AXP",
    "paypal": "PYPL",
    "ubs ag": "UBS",
    "ubs group": "UBS",
    "berkshire hathaway": "BRK.B",

    # 醫療
    "unitedhealth": "UNH",
    "johnson & johnson": "JNJ",
    "eli lilly": "LLY",
    "abbvie": "ABBV",
    "pfizer": "PFE",
    "merck": "MRK",
    "amgen": "AMGN",
    "gilead": "GILD",
    "biogen": "BIIB",
    "moderna": "MRNA",
    "regeneron": "REGN",
    "bristol-myers squibb": "BMY",
    "astrazeneca": "AZN",
    "novo nordisk": "NVO",

    # 能源
    "exxon mobil": "XOM",
    "exxonmobil": "XOM",
    "chevron": "CVX",
    "conocophillips": "COP",
    "pioneer natural resources": "PXD",
    "schlumberger": "SLB",
    "baker hughes": "BKR",

    # 工業 / 防禦
    "boeing": "BA",
    "lockheed martin": "LMT",
    "raytheon": "RTX",
    "general electric": "GE",
    "honeywell": "HON",
    "caterpillar": "CAT",
    "3m": "MMM",
    "deere": "DE",
    "northrop grumman": "NOC",
    "general dynamics": "GD",
    "l3harris": "LHX",

    # 通訊 / REIT
    "sba communications": "SBAC",
    "american tower": "AMT",
    "crown castle": "CCI",
    "disney": "DIS",
    "walt disney": "DIS",
    "comcast": "CMCSA",
    "verizon": "VZ",
    "at&t": "T",

    # 消費
    "walmart": "WMT",
    "costco": "COST",
    "procter & gamble": "PG",
    "coca-cola": "KO",
    "pepsico": "PEP",
    "mcdonald": "MCD",
    "starbucks": "SBUX",
    "home depot": "HD",
    "lowes": "LOW",
    "lowe's": "LOW",
    "target": "TGT",
    "nike": "NKE",

    # ETF
    "spdr s&p 500": "SPY",
    "ishares core s&p 500": "IVV",
    "vanguard s&p 500": "VOO",
    "invesco qqq": "QQQ",
    "ishares russell 2000": "IWM",
    "vanguard total stock": "VTI",

    # 加密貨幣相關
    "coinbase": "COIN",
}

# ── 不可解析類型的模式（municipal bond、Treasury、private fund） ──
NON_TICKER_PATTERNS = [
    # Municipal bonds
    re.compile(r'\b(ST|CNTY|CITY|DIST|AUTH)\b.*\d+\.\d+%', re.IGNORECASE),
    re.compile(r'\bGO\s+(BD|BOND)\b', re.IGNORECASE),
    re.compile(r'\b(GO|REV)\s*$', re.IGNORECASE),
    re.compile(r'\bMuni(cipal)?\s+Bond', re.IGNORECASE),
    re.compile(r'\b(OBLIG|TRANSN|INFRA)\b.*\b(REV|AUTH)\b', re.IGNORECASE),
    re.compile(r'\bGen\s+Oblig\b', re.IGNORECASE),
    re.compile(r'(?:ST|State)\s+(?:GO|REV|PUB)', re.IGNORECASE),
    re.compile(r'\bSCH\s+DIST\b', re.IGNORECASE),
    re.compile(r'\b\d+\.\d+%\s+(?:Due\s+)?\d', re.IGNORECASE),  # 3.5% Due Nov 2032
    re.compile(r'\b56042\w+\b'),  # CUSIP-like
    re.compile(r'\bGO\s+Bond', re.IGNORECASE),
    re.compile(r'\bGO\s+Ref', re.IGNORECASE),
    re.compile(r'\bGO\s+Promissory', re.IGNORECASE),
    re.compile(r'\bRev\.?\s+Bond', re.IGNORECASE),
    re.compile(r'\bSchool\s+District\b', re.IGNORECASE),
    re.compile(r'\bDept\.?\s+(?:of\s+)?W[at]', re.IGNORECASE),  # Dept. of Water
    re.compile(r',\s*(?:CA|NY|PA|TX|WI|AL|FL|OH|IL|NJ|MA)\b.*Bond', re.IGNORECASE),
    re.compile(r'\bCooperative\s+District\b', re.IGNORECASE),
    re.compile(r'\bFinancing\s+Authority\b', re.IGNORECASE),
    re.compile(r'\bFacilities\s+Auth', re.IGNORECASE),
    re.compile(r'\bIndl?\s+Dev\s+Auth', re.IGNORECASE),
    re.compile(r'\bPromissory\s+Notes?\b', re.IGNORECASE),
    re.compile(r'\bBDS\b.*\d+\.\d+%', re.IGNORECASE),

    # US Treasury
    re.compile(r'US\s+Treasury', re.IGNORECASE),
    re.compile(r'Treasury\s+(?:Note|Bond|Bill)', re.IGNORECASE),

    # Government-backed
    re.compile(r'Fannie\s+Mae', re.IGNORECASE),
    re.compile(r'Freddie\s+Mac', re.IGNORECASE),
    re.compile(r'Ginnie\s+Mae', re.IGNORECASE),

    # Private entities
    re.compile(r'\bLLC\b', re.IGNORECASE),
    re.compile(r'\bLP\b$', re.IGNORECASE),
    re.compile(r'\bL\.?P\.?\b$', re.IGNORECASE),
    re.compile(r'PRIVATE\s+FUND', re.IGNORECASE),
    re.compile(r'VENTURE\s+PARTNERS', re.IGNORECASE),

    # Stablecoins / crypto (非股票)
    re.compile(r'^usdc$', re.IGNORECASE),
    re.compile(r'^usdt$', re.IGNORECASE),
    re.compile(r'^tether$', re.IGNORECASE),
]

# ── ticker 格式：全大寫 1-5 字母（可含 .） ──
TICKER_PATTERN = re.compile(r'^[A-Z]{1,5}(\.[A-Z])?$')


def _is_non_tickerable(asset_name: str) -> bool:
    """判斷 asset_name 是否屬於不會有股票代號的類型。"""
    for pattern in NON_TICKER_PATTERNS:
        if pattern.search(asset_name):
            return True
    return False


def _looks_like_ticker(asset_name: str) -> bool:
    """判斷 asset_name 本身是否看起來就是 ticker（如 "SPYM"）。"""
    cleaned = asset_name.strip().upper()
    return bool(TICKER_PATTERN.match(cleaned))


def _static_lookup(asset_name: str) -> Optional[str]:
    """從靜態映射表查找 ticker。"""
    lower = asset_name.lower().strip()
    for keyword, ticker in STATIC_MAPPING.items():
        if keyword in lower:
            return ticker
    return None


def _yfinance_lookup(asset_name: str) -> Optional[str]:
    """使用 yfinance 搜尋 ticker。僅對看起來像公司名的查詢。"""
    # 跳過太短或太通用的名稱
    if len(asset_name.strip()) < 4:
        return None

    try:
        import yfinance as yf
        results = yf.Search(asset_name, max_results=5)
        quotes = results.quotes if hasattr(results, 'quotes') else []
        if not quotes:
            return None

        # 過濾出美股（不含 . 的 symbol，且 symbol 長度合理）
        us_quotes = [
            q for q in quotes
            if q.get('symbol') and '.' not in q['symbol'] and len(q['symbol']) <= 5
        ]
        if not us_quotes:
            return None

        # 驗證第一個結果的名字與查詢有相似性
        best = us_quotes[0]
        symbol = best['symbol'].upper()
        match_name = (best.get('shortname') or best.get('longname') or '').lower()
        query_lower = asset_name.lower()

        # 簡單相似度：查詢中的單字至少有一個出現在結果名字中
        query_words = [w for w in query_lower.split() if len(w) > 2]
        name_words = match_name.split()
        overlap = any(qw in match_name for qw in query_words)

        if overlap:
            return symbol

        return None
    except Exception as e:
        logger.warning(f"yfinance 搜尋失敗 ({asset_name}): {e}")
        return None


def _validate_ticker(ticker: str) -> bool:
    """驗證 ticker 是否存在（使用 yfinance）。"""
    try:
        import yfinance as yf
        t = yf.Ticker(ticker)
        info = t.info
        # 如果有 shortName 或 market，表示是有效的
        return bool(info.get('shortName') or info.get('regularMarketPrice'))
    except Exception:
        return False


def resolve_ticker(asset_name: str) -> Tuple[Optional[str], str]:
    """嘗試為 asset_name 解析出 ticker。

    Returns:
        (ticker_or_None, resolution_method)
        resolution_method: "static", "pattern", "yfinance", "non_tickerable", "unresolved"
    """
    if not asset_name or not asset_name.strip():
        return None, "empty"

    asset_name = asset_name.strip()

    # 1. 判斷是否不可解析類型
    if _is_non_tickerable(asset_name):
        return None, "non_tickerable"

    # 2. asset_name 本身就是 ticker
    if _looks_like_ticker(asset_name):
        upper = asset_name.upper()
        if _validate_ticker(upper):
            return upper, "pattern"
        return None, "unresolved"

    # 3. 靜態映射
    static_result = _static_lookup(asset_name)
    if static_result:
        return static_result, "static"

    # 4. yfinance 搜尋
    yf_result = _yfinance_lookup(asset_name)
    if yf_result:
        return yf_result, "yfinance"

    return None, "unresolved"


def enrich_missing_tickers(db_path: str = "data/data.db", dry_run: bool = False) -> dict:
    """掃描 congress_trades 中所有 ticker 為 NULL 的紀錄，嘗試補全。

    Args:
        db_path: SQLite 資料庫路徑
        dry_run: True 時只預覽不寫入

    Returns:
        統計資訊 {"total_missing", "enriched", "non_tickerable", "unresolved", "details"}
    """
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute(
        "SELECT id, asset_name, asset_type FROM congress_trades "
        "WHERE ticker IS NULL OR ticker = ''"
    )
    rows = cur.fetchall()

    stats = {
        "total_missing": len(rows),
        "enriched": 0,
        "non_tickerable": 0,
        "unresolved": 0,
        "details": [],
    }

    # 快取已查詢過的 asset_name → result，避免重複 API 呼叫
    cache = {}

    for row_id, asset_name, asset_type in rows:
        if asset_name in cache:
            ticker, method = cache[asset_name]
        else:
            ticker, method = resolve_ticker(asset_name)
            cache[asset_name] = (ticker, method)
            # yfinance API rate limit
            if method == "yfinance":
                time.sleep(0.3)

        detail = {
            "id": row_id,
            "asset_name": asset_name,
            "resolved_ticker": ticker,
            "method": method,
        }
        stats["details"].append(detail)

        if method == "non_tickerable":
            stats["non_tickerable"] += 1
            # 更新 asset_type 為更精確的類型
            if not dry_run:
                new_type = _classify_non_ticker_asset(asset_name)
                if new_type != asset_type:
                    cur.execute(
                        "UPDATE congress_trades SET asset_type = ? WHERE id = ?",
                        (new_type, row_id),
                    )
        elif ticker:
            stats["enriched"] += 1
            logger.info(f"補全 ticker: {asset_name} → {ticker} ({method})")
            if not dry_run:
                cur.execute(
                    "UPDATE congress_trades SET ticker = ? WHERE id = ?",
                    (ticker, row_id),
                )
        else:
            stats["unresolved"] += 1

    if not dry_run:
        conn.commit()
        logger.info(
            f"Ticker 補全完成: {stats['enriched']} 補全, "
            f"{stats['non_tickerable']} 不適用, "
            f"{stats['unresolved']} 無法解析 / {stats['total_missing']} 總缺失"
        )

    conn.close()
    return stats


def _classify_non_ticker_asset(asset_name: str) -> str:
    """為不可解析的資產分類出更精確的 asset_type。"""
    lower = asset_name.lower()

    if any(kw in lower for kw in ["treasury", "us treasury"]):
        return "Treasury"
    if any(kw in lower for kw in ["fannie mae", "freddie mac", "ginnie mae"]):
        return "Government Bond"
    if any(kw in lower for kw in ["llc", "lp", "private fund", "venture partners"]):
        return "Private Fund"
    if any(kw in lower for kw in ["usdc", "usdt", "tether"]):
        return "Cryptocurrency"
    if re.search(r'(?:GO|REV|BD|BOND|OBLIG|DIST|AUTH)', asset_name, re.IGNORECASE):
        return "Municipal Bond"
    if re.search(r'\d+\.\d+%', asset_name):
        return "Bond"

    return "Other"


# ── CLI 入口 ──
if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(name)s | %(message)s")

    db = "data/data.db"
    dry = "--dry-run" in sys.argv

    if dry:
        print("=== DRY RUN 模式（不寫入資料庫）===\n")

    stats = enrich_missing_tickers(db_path=db, dry_run=dry)

    print(f"\n{'='*60}")
    print(f"Ticker 補全統計：")
    print(f"  缺失 ticker 總數：{stats['total_missing']}")
    print(f"  成功補全：{stats['enriched']}")
    print(f"  不適用（債券/私募等）：{stats['non_tickerable']}")
    print(f"  無法解析：{stats['unresolved']}")
    print(f"{'='*60}\n")

    if stats['details']:
        print("詳細結果：")
        for d in stats['details']:
            status = d['resolved_ticker'] or f"({d['method']})"
            print(f"  {d['asset_name'][:50]:50s} → {status}")
