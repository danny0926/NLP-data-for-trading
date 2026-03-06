"""
Capitol Trades Bulk Importer — Direct HTML parsing (no LLM needed)

Parses the predictable HTML table structure from capitoltrades.com directly,
bypassing the LLM Transform step entirely. 100x faster and free.

Headers: Politician | Traded Issuer | Published | Traded | Filed After | Owner | Type | Size | Price
"""

import hashlib
import logging
import re
import sqlite3
import time
from datetime import datetime, date
from typing import Optional

from bs4 import BeautifulSoup
from curl_cffi import requests as cf_requests

from src.config import DB_PATH

logger = logging.getLogger("ETL.CapitolTradesBulk")

# Amount range mapping
SIZE_MAP = {
    "1K–15K": "$1,001 - $15,000",
    "15K–50K": "$15,001 - $50,000",
    "50K–100K": "$50,001 - $100,000",
    "100K–250K": "$100,001 - $250,000",
    "250K–500K": "$250,001 - $500,000",
    "500K–1M": "$500,001 - $1,000,000",
    "1M–5M": "$1,000,001 - $5,000,000",
    "5M–25M": "$5,000,001 - $25,000,000",
    "25M–50M": "$25,000,001 - $50,000,000",
    "Over 50M": "Over $50,000,000",
}

# Transaction type normalization
TYPE_MAP = {
    "buy": "Buy",
    "sale": "Sale",
    "sale_full": "Sale",
    "sale_partial": "Sale",
    "exchange": "Exchange",
    "receive": "Buy",
}

# Chamber detection from HTML
CHAMBER_MAP = {
    "House": "House",
    "Senate": "Senate",
}


def _compute_hash(politician: str, tx_date: str, ticker: str,
                  amount: str, tx_type: str) -> str:
    raw = f"{politician}|{tx_date}|{ticker}|{amount}|{tx_type}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _parse_trade_date(raw: str) -> Optional[str]:
    """Parse dates like '9 Feb2026' or '28 Jan2026' into YYYY-MM-DD."""
    raw = raw.strip()
    # Pattern: day month_abbr year
    m = re.match(r'(\d{1,2})\s*([A-Za-z]{3})(\d{4})', raw)
    if m:
        day, month, year = m.groups()
        try:
            dt = datetime.strptime(f"{day} {month} {year}", "%d %b %Y")
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            pass
    return None


def _parse_politician_cell(cell_text: str) -> dict:
    """Parse politician cell: 'Kevin HernRepublicanHouseOK' -> name, chamber, party."""
    # Capitol Trades puts name + party + chamber + state all concatenated
    # Try to extract chamber
    chamber = None
    for ch in ["House", "Senate"]:
        if ch in cell_text:
            chamber = ch
            break

    # Extract party (must check "Other" too for independents like Angus King)
    party = None
    for p in ["Republican", "Democrat", "Independent", "Other"]:
        if p in cell_text:
            party = p
            break

    # Extract name (everything before party)
    name = cell_text
    if party:
        name = cell_text.split(party)[0].strip()

    # Clean up name
    name = re.sub(r'\s+', ' ', name).strip()

    return {"name": name, "chamber": chamber or "Unknown", "party": party}


def _parse_issuer_cell(cell_text: str) -> dict:
    """Parse issuer cell: 'Waters CorpWAT:US' -> asset_name, ticker."""
    # Pattern: company name followed by TICKER:EXCHANGE or N/A
    m = re.search(r'([A-Z0-9.]+):(?:US|NYSE|NASDAQ|AMEX)\s*$', cell_text)
    if m:
        ticker = m.group(1)
        asset_name = cell_text[:m.start()].strip()
        return {"ticker": ticker, "asset_name": asset_name}

    # N/A ticker
    if "N/A" in cell_text:
        asset_name = cell_text.replace("N/A", "").strip()
        return {"ticker": None, "asset_name": asset_name}

    return {"ticker": None, "asset_name": cell_text.strip()}


def fetch_and_parse_page(session, page: int, chamber: str = "") -> list:
    """Fetch and parse a single page from Capitol Trades."""
    url = f"https://www.capitoltrades.com/trades?page={page}"
    if chamber:
        url += f"&chamber={chamber}"

    resp = session.get(url, timeout=20)
    if resp.status_code != 200:
        logger.warning(f"HTTP {resp.status_code} for {url}")
        return []

    soup = BeautifulSoup(resp.content, "html.parser")
    table = soup.find("table")
    if not table:
        return []

    rows = table.find_all("tr")[1:]  # Skip header
    trades = []

    for row in rows:
        cells = row.find_all("td")
        if len(cells) < 8:
            continue

        try:
            pol = _parse_politician_cell(cells[0].get_text(strip=True))
            issuer = _parse_issuer_cell(cells[1].get_text(strip=True))
            trade_date_raw = cells[3].get_text(strip=True)
            owner_raw = cells[5].get_text(strip=True)
            type_raw = cells[6].get_text(strip=True).lower()
            size_raw = cells[7].get_text(strip=True)

            trade_date = _parse_trade_date(trade_date_raw)
            tx_type = TYPE_MAP.get(type_raw, "Buy")
            amount = SIZE_MAP.get(size_raw, size_raw)

            if not pol["name"]:
                continue

            trade = {
                "politician_name": pol["name"],
                "chamber": pol["chamber"],
                "ticker": issuer["ticker"],
                "asset_name": issuer["asset_name"],
                "transaction_date": trade_date,
                "filing_date": None,  # Not reliably available from table
                "transaction_type": tx_type,
                "amount_range": amount,
                "owner": owner_raw if owner_raw else "Self",
                "asset_type": "Stock",
                "source_url": url,
            }
            trades.append(trade)
        except Exception as e:
            logger.debug(f"Parse error on row: {e}")
            continue

    return trades


def bulk_import(max_pages: int = 50, chamber: str = "",
                db_path: str = None) -> dict:
    """
    Bulk import trades from Capitol Trades via direct HTML parsing.

    Args:
        max_pages: Maximum pages to fetch (each has ~12 trades)
        chamber: 'senate', 'house', or '' for both
        db_path: Database path

    Returns:
        dict with new, skipped, total counts
    """
    if db_path is None:
        db_path = DB_PATH

    session = cf_requests.Session(impersonate="chrome")
    conn = sqlite3.connect(db_path)

    total_new = 0
    total_skipped = 0
    total_parsed = 0
    empty_pages = 0

    logger.info(f"Capitol Trades Bulk Import: up to {max_pages} pages, chamber={chamber or 'all'}")

    for page in range(1, max_pages + 1):
        trades = fetch_and_parse_page(session, page, chamber)

        if not trades:
            empty_pages += 1
            if empty_pages >= 3:
                logger.info(f"3 consecutive empty pages at page {page}, stopping")
                break
            continue
        else:
            empty_pages = 0

        total_parsed += len(trades)

        for trade in trades:
            ticker = trade["ticker"] or ""
            data_hash = _compute_hash(
                trade["politician_name"],
                trade["transaction_date"] or "",
                ticker,
                trade["amount_range"] or "",
                trade["transaction_type"],
            )

            # Check dedup
            existing = conn.execute(
                "SELECT 1 FROM congress_trades WHERE data_hash = ?", (data_hash,)
            ).fetchone()

            if existing:
                total_skipped += 1
                continue

            try:
                conn.execute("""
                    INSERT INTO congress_trades
                    (chamber, politician_name, transaction_date, filing_date,
                     ticker, asset_name, asset_type, transaction_type,
                     amount_range, owner, source_url, source_format,
                     extraction_confidence, data_hash, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    trade["chamber"],
                    trade["politician_name"],
                    trade["transaction_date"],
                    trade["filing_date"],
                    trade["ticker"],
                    trade["asset_name"],
                    trade["asset_type"],
                    trade["transaction_type"],
                    trade["amount_range"],
                    trade["owner"],
                    trade["source_url"],
                    "capitoltrades_bulk",
                    0.85,  # Direct parse confidence
                    data_hash,
                    datetime.now().isoformat(),
                ))
                total_new += 1
            except sqlite3.IntegrityError:
                total_skipped += 1

        conn.commit()

        if page % 5 == 0:
            logger.info(f"  Page {page}: parsed={total_parsed}, new={total_new}, skipped={total_skipped}")

        time.sleep(0.5)  # Be polite

    conn.close()

    result = {
        "pages_fetched": page,
        "total_parsed": total_parsed,
        "new": total_new,
        "skipped": total_skipped,
    }
    logger.info(f"Bulk import complete: {result}")
    return result


if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

    parser = argparse.ArgumentParser(description="Capitol Trades Bulk Importer")
    parser.add_argument("--pages", type=int, default=50, help="Max pages to fetch")
    parser.add_argument("--chamber", type=str, default="", help="senate/house/empty for both")
    args = parser.parse_args()

    from src.database import init_db
    init_db()

    result = bulk_import(max_pages=args.pages, chamber=args.chamber)
    print(f"\nResult: {result}")
