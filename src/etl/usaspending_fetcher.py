"""Extract layer -- USASpending.gov Government Contracts Fetcher (RB-009)"""

import hashlib, json, logging, time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
import requests

logger = logging.getLogger("ETL.USASpendingFetcher")

USA_SPENDING_AWARDS_URL = "https://api.usaspending.gov/api/v2/search/spending_by_award/"
CONTRACT_AWARD_CODES = ["A", "B", "C", "D"]
MIN_CONTRACT_AMOUNT = 100_000
CROSS_REF_WINDOW_DAYS = 90
PROJECT_ROOT = Path(__file__).parent.parent.parent
CONTRACTOR_MAP_PATH = PROJECT_ROOT / "data" / "contractor_tickers.json"
REQUEST_DELAY = 0.5


@dataclass
class GovernmentContract:
    award_id: str
    recipient_name: str
    ticker: str
    award_amount: float
    start_date: str
    end_date: str
    awarding_agency: str
    naics_code: str
    data_hash: str
    fetched_at: str


@dataclass
class ContractCrossRef:
    trade_id: str
    ticker: str
    politician_name: str
    transaction_type: str
    transaction_date: str
    award_id: str
    award_amount: float
    awarding_agency: str
    contract_start_date: str
    days_before_trade: int
    signal_type: str
    convergence_score: float


class USASpendingFetcher:
    """USASpending.gov fetcher for government contracts with congress_trades cross-reference.

    Usage:
        fetcher = USASpendingFetcher()
        contracts = fetcher.fetch_contracts_for_tickers(["AVAV", "MSFT", "ORCL"])
        cross_refs = fetcher.cross_reference_with_trades(contracts, congress_trades)
        fetcher.save_contracts_to_db(contracts, conn)
        fetcher.save_cross_refs_to_db(cross_refs, conn)
    """

    def __init__(self, contractor_map_path=None):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json", "Accept": "application/json"})
        self._last_request_time = 0.0
        map_path = contractor_map_path or str(CONTRACTOR_MAP_PATH)
        self.contractor_map = self._load_contractor_map(map_path)
        logger.info(f"[USASpending] loaded {len(self.contractor_map)} tickers from {map_path}")

    def _load_contractor_map(self, path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f).get("tickers", {})
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning(f"[USASpending] contractor map load failed: {e}")
            return {}

    def _rate_limit(self):
        elapsed = time.time() - self._last_request_time
        if elapsed < REQUEST_DELAY:
            time.sleep(REQUEST_DELAY - elapsed)
        self._last_request_time = time.time()

    def fetch_contracts_for_tickers(self, tickers, start_date=None, end_date=None, min_amount=MIN_CONTRACT_AMOUNT):
        """Batch query government contracts for multiple tickers.

        Args:
            tickers: list of tickers to query
            start_date: YYYY-MM-DD (default: 2 years ago)
            end_date: YYYY-MM-DD (default: today)
            min_amount: minimum contract amount filter

        Returns:
            list[GovernmentContract]
        """
        if not start_date:
            start_date = (datetime.now() - timedelta(days=730)).strftime("%Y-%m-%d")
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")
        all_contracts = []
        skipped = 0
        for ticker in tickers:
            if ticker not in self.contractor_map:
                skipped += 1
                continue
            info = self.contractor_map[ticker]
            search_terms = info.get("search_terms", [info.get("company", ticker)])
            contracts = self._fetch_for_company(ticker, search_terms, start_date, end_date, min_amount)
            all_contracts.extend(contracts)
            logger.info(f"[USASpending] {ticker} ({info.get('company', '')}): {len(contracts)} contracts")
        logger.info(f"[USASpending] done: {len(all_contracts)} contracts ({len(tickers)-skipped}/{len(tickers)} tickers mapped)")
        return all_contracts

    def _fetch_for_company(self, ticker, search_terms, start_date, end_date, min_amount, max_results=50):
        """Query contracts for one company (up to 2 search_terms, dedup by award_id)."""
        all_contracts = []
        seen_award_ids = set()
        for term in search_terms[:2]:
            self._rate_limit()
            payload = {
                "filters": {
                    "recipient_search_text": [term],
                    "time_period": [{"start_date": start_date, "end_date": end_date}],
                    "award_type_codes": CONTRACT_AWARD_CODES,
                    "award_amounts": [{"lower_bound": min_amount}],
                },
                "fields": ["Award ID", "Recipient Name", "Award Amount", "Start Date", "End Date", "Awarding Agency"],
                "limit": min(max_results, 100),
                "page": 1,
                "sort": "Award Amount",
                "order": "desc",
            }
            try:
                resp = self.session.post(USA_SPENDING_AWARDS_URL, json=payload, timeout=30)
                if resp.status_code != 200:
                    logger.warning(f"[USASpending] {ticker}/{term}: HTTP {resp.status_code}")
                    continue
                for r in resp.json().get("results", []):
                    award_id = r.get("Award ID", "")
                    if award_id in seen_award_ids:
                        continue
                    seen_award_ids.add(award_id)
                    amount = float(r.get("Award Amount") or 0.0)
                    start = r.get("Start Date") or ""
                    data_hash = hashlib.sha256(f"{award_id}:{ticker}:{start}".encode()).hexdigest()[:16]
                    all_contracts.append(GovernmentContract(
                        award_id=award_id,
                        recipient_name=r.get("Recipient Name") or term,
                        ticker=ticker,
                        award_amount=amount,
                        start_date=start,
                        end_date=r.get("End Date") or "",
                        awarding_agency=r.get("Awarding Agency") or "",
                        naics_code="",
                        data_hash=data_hash,
                        fetched_at=datetime.now().isoformat(),
                    ))
            except requests.RequestException as e:
                logger.error(f"[USASpending] {ticker}/{term} failed: {e}")
        return all_contracts

    def cross_reference_with_trades(self, contracts, congress_trades, window_days=CROSS_REF_WINDOW_DAYS):
        contracts_by_ticker = {}
        for c in contracts:
            if c.ticker:
                contracts_by_ticker.setdefault(c.ticker, []).append(c)

        cross_refs = []
        for trade in congress_trades:
            ticker = trade.get("ticker")
            trade_date_str = trade.get("transaction_date")
            if not ticker or not trade_date_str:
                continue
            try:
                trade_dt = datetime.strptime(trade_date_str, "%Y-%m-%d")
            except ValueError:
                continue
            win_start = (trade_dt - timedelta(days=window_days)).strftime("%Y-%m-%d")
            win_end = (trade_dt + timedelta(days=window_days)).strftime("%Y-%m-%d")
            nearby = [c for c in contracts_by_ticker.get(ticker, [])
                      if c.start_date and win_start <= c.start_date <= win_end]
            for contract in nearby:
                try:
                    contract_dt = datetime.strptime(contract.start_date, "%Y-%m-%d")
                except ValueError:
                    continue
                days_diff = (trade_dt - contract_dt).days
                tx_type = (trade.get("transaction_type") or "").lower()
                is_buy = any(kw in tx_type for kw in ["buy", "purchase"])
                if is_buy and 0 < days_diff <= 90:
                    signal_type = "PRE_CONTRACT_BUY"
                elif is_buy and -30 <= days_diff <= 0:
                    signal_type = "AHEAD_OF_CONTRACT_BUY"
                elif is_buy:
                    signal_type = "CONTRACT_BUY"
                else:
                    signal_type = "CONTRACT_SELL"
                score = 0.0
                if is_buy: score += 0.3
                if contract.award_amount >= 100_000_000: score += 0.3
                elif contract.award_amount >= 10_000_000: score += 0.1
                if signal_type in ("PRE_CONTRACT_BUY", "AHEAD_OF_CONTRACT_BUY"): score += 0.3
                if "Department of Defense" in contract.awarding_agency: score += 0.1
                score = min(score, 1.0)
                cross_refs.append(ContractCrossRef(
                    trade_id=trade.get("id", ""), ticker=ticker,
                    politician_name=trade.get("politician_name", ""),
                    transaction_type=trade.get("transaction_type", ""),
                    transaction_date=trade_date_str, award_id=contract.award_id,
                    award_amount=contract.award_amount, awarding_agency=contract.awarding_agency,
                    contract_start_date=contract.start_date, days_before_trade=days_diff,
                    signal_type=signal_type, convergence_score=round(score, 2),
                ))
        logger.info(f"[USASpending] cross-ref: {len(cross_refs)} pairs")
        return cross_refs

    def save_contracts_to_db(self, contracts, conn):
        conn.execute(
            "CREATE TABLE IF NOT EXISTS government_contracts ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "award_id TEXT NOT NULL, recipient_name TEXT NOT NULL, ticker TEXT, "
            "award_amount REAL, start_date TEXT, end_date TEXT, awarding_agency TEXT, "
            "naics_code TEXT, data_hash TEXT UNIQUE, "
            "fetched_at TEXT DEFAULT (datetime('now')))"
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_gov_contracts_ticker ON government_contracts(ticker)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_gov_contracts_date ON government_contracts(start_date)")
        inserted = 0
        for c in contracts:
            try:
                conn.execute(
                    "INSERT OR IGNORE INTO government_contracts "
                    "(award_id, recipient_name, ticker, award_amount, start_date, "
                    "end_date, awarding_agency, naics_code, data_hash, fetched_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (c.award_id, c.recipient_name, c.ticker, c.award_amount, c.start_date,
                     c.end_date, c.awarding_agency, c.naics_code, c.data_hash, c.fetched_at),
                )
                inserted += 1
            except Exception as e:
                logger.warning(f"[USASpending] DB insert failed {c.award_id}: {e}")
        logger.info(f"[USASpending] saved {inserted}/{len(contracts)} contracts")
        return inserted

    def save_cross_refs_to_db(self, cross_refs, conn):
        conn.execute(
            "CREATE TABLE IF NOT EXISTS contract_cross_refs ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "trade_id TEXT NOT NULL, ticker TEXT NOT NULL, politician_name TEXT, "
            "transaction_type TEXT, transaction_date TEXT, award_id TEXT, "
            "award_amount REAL, awarding_agency TEXT, contract_start_date TEXT, "
            "days_before_trade INTEGER, signal_type TEXT, convergence_score REAL, "
            "created_at TEXT DEFAULT (datetime('now')))"
        )
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_cross_refs_uniq "
            "ON contract_cross_refs(trade_id, award_id)"
        )
        inserted = 0
        for cr in cross_refs:
            try:
                conn.execute(
                    "INSERT OR IGNORE INTO contract_cross_refs "
                    "(trade_id, ticker, politician_name, transaction_type, transaction_date, "
                    "award_id, award_amount, awarding_agency, contract_start_date, "
                    "days_before_trade, signal_type, convergence_score) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (cr.trade_id, cr.ticker, cr.politician_name, cr.transaction_type,
                     cr.transaction_date, cr.award_id, cr.award_amount, cr.awarding_agency,
                     cr.contract_start_date, cr.days_before_trade, cr.signal_type,
                     cr.convergence_score),
                )
                inserted += 1
            except Exception as e:
                logger.warning(f"[USASpending] cross_ref insert failed: {e}")
        logger.info(f"[USASpending] saved {inserted}/{len(cross_refs)} cross-refs")
        return inserted
