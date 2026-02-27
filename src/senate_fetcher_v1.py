from curl_cffi import requests
from bs4 import BeautifulSoup
import json
import logging
import time
import os
import hashlib
from datetime import datetime, timedelta
import sqlite3
import sys

# Ensure src is in path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from database import DB_PATH, generate_hash

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("SenateFetcherV1")

class SenateFetcherV1:
    BASE_URL = "https://efdsearch.senate.gov"
    HOME_URL = f"{BASE_URL}/search/"
    AGREEMENT_URL = f"{BASE_URL}/search/home/"
    DATA_URL = f"{BASE_URL}/search/report/data/"

    def __init__(self):
        self.session = requests.Session(impersonate="chrome")
        self.csrf_token = None

    def _get_csrf_token(self):
        logger.info("Fetching CSRF token...")
        resp = self.session.get(self.HOME_URL)
        soup = BeautifulSoup(resp.text, "html.parser")
        token_input = soup.find("input", {"name": "csrfmiddlewaretoken"})
        if token_input:
            self.csrf_token = token_input["value"]
            return self.csrf_token
        return None

    def _accept_agreement(self):
        if not self.csrf_token:
            self._get_csrf_token()
        
        logger.info("Accepting agreement...")
        payload = {
            "csrfmiddlewaretoken": self.csrf_token,
            "prohibition_agreement": "1"
        }
        headers = {
            "Referer": self.HOME_URL,
            "X-CSRFToken": self.csrf_token,
        }
        self.session.post(self.AGREEMENT_URL, data=payload, headers=headers)
        
        # Refresh home page to ensure search is unlocked
        resp = self.session.get(self.HOME_URL)
        soup = BeautifulSoup(resp.text, "html.parser")
        token_input = soup.find("input", {"name": "csrfmiddlewaretoken"})
        if token_input:
            self.csrf_token = token_input["value"]
        
        return True

    def fetch_report_list(self, start_date, end_date):
        """
        Fetches the list of reports for the given date range.
        Dates should be MM/DD/YYYY.
        """
        if not self.csrf_token:
            self._accept_agreement()

        logger.info(f"Fetching report list from {start_date} to {end_date}...")
        
        # 1. Perform a dummy form search to initialize session state for the AJAX endpoint
        form_payload = {
            "csrfmiddlewaretoken": self.csrf_token,
            "report_type": "11", # Periodic Transaction Report
            "submitted_start_date": start_date,
            "submitted_end_date": end_date,
            "search_reports": "Search Reports"
        }
        headers = {
            "Referer": self.HOME_URL,
            "X-CSRFToken": self.csrf_token,
        }
        self.session.post(self.HOME_URL, data=form_payload, headers=headers)

        # 2. Call the AJAX data endpoint
        search_payload = {
            "csrfmiddlewaretoken": self.csrf_token,
            "draw": "1",
            "start": "0",
            "length": "100",
            "report_types": "[11]",
            "filter_types": "[1,2,3]",
            "start_date": start_date,
            "end_date": end_date,
            "order[0][column]": "4",
            "order[0][dir]": "desc",
        }
        # Add column definitions (required by DataTables)
        for i in range(5):
            search_payload[f"columns[{i}][data]"] = str(i)
            search_payload[f"columns[{i}][searchable]"] = "true"
            search_payload[f"columns[{i}][orderable]"] = "true"
            search_payload[f"columns[{i}][search][value]"] = ""
            search_payload[f"columns[{i}][search][regex]"] = "false"

        ajax_headers = {
            "Referer": self.HOME_URL,
            "X-Requested-With": "XMLHttpRequest",
            "X-CSRFToken": self.csrf_token,
        }
        
        resp = self.session.post(self.DATA_URL, data=search_payload, headers=ajax_headers)
        if resp.status_code == 200:
            return resp.json().get('data', [])
        else:
            logger.error(f"Failed to fetch report list: {resp.status_code}")
            return []

    def parse_report_page(self, report_url, first_name, last_name, filing_date):
        """
        Parses an individual report page (Electronic Filing).
        """
        full_url = f"{self.BASE_URL}{report_url}"
        logger.info(f"Parsing report: {full_url}")
        
        try:
            resp = self.session.get(full_url)
            if resp.status_code != 200:
                logger.error(f"Failed to fetch report page: {full_url}")
                return []
            
            soup = BeautifulSoup(resp.text, "html.parser")
            
            # Look for the transactions table
            table = soup.find("table", {"class": "table-striped"})
            if not table:
                # Some reports might have different table classes
                table = soup.find("table", {"id": "v3-transactions-table"})
            
            if not table:
                logger.warning(f"No transactions table found in {full_url}")
                return []
            
            trades = []
            rows = table.find("tbody").find_all("tr") if table.find("tbody") else table.find_all("tr")[1:]
            
            for row in rows:
                cols = row.find_all("td")
                if len(cols) < 8:
                    continue
                
                # Column indices based on common structure:
                # 0: #
                # 1: Transaction Date
                # 2: Owner
                # 3: Ticker
                # 4: Asset Name
                # 5: Asset Type
                # 6: Type (Purchase/Sale)
                # 7: Amount
                # 8: Comment
                
                trans_date_str = cols[1].get_text(strip=True)
                ticker = cols[3].get_text(strip=True)
                asset_name = cols[4].get_text(strip=True)
                asset_type = cols[5].get_text(strip=True)
                trans_type = cols[6].get_text(strip=True)
                amount_range = cols[7].get_text(strip=True)
                
                # Clean ticker
                if ticker == "--" or not ticker:
                    # Try to extract ticker from asset name if possible, or leave as None
                    ticker = None
                
                # Convert date format if needed (usually MM/DD/YYYY)
                try:
                    dt = datetime.strptime(trans_date_str, "%m/%d/%Y")
                    trans_date = dt.strftime("%Y-%m-%d")
                except:
                    trans_date = trans_date_str

                trades.append({
                    "politician_name": f"{first_name} {last_name}",
                    "filing_date": filing_date,
                    "transaction_date": trans_date,
                    "ticker": ticker,
                    "asset_type": asset_type,
                    "transaction_type": trans_type,
                    "amount_range": amount_range,
                    "ptr_link": full_url,
                    "is_paper": False
                })
            
            return trades
        except Exception as e:
            logger.error(f"Error parsing report page {full_url}: {e}")
            return []

    def save_to_db(self, trades):
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        new_count = 0
        updated_count = 0
        
        for trade in trades:
            # Generate data hash for deduplication
            # Using (politician_name, transaction_date, ticker, amount_range, transaction_type)
            data_tuple = (
                trade['politician_name'],
                trade['transaction_date'],
                trade['ticker'] or "",
                trade['amount_range'],
                trade['transaction_type']
            )
            data_hash = generate_hash(data_tuple)
            
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            try:
                cursor.execute('''
                INSERT INTO senate_trades (
                    id, filing_date, transaction_date, politician_name, ticker, 
                    asset_type, transaction_type, amount_range, ptr_link, 
                    is_paper, created_at, updated_at, data_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    str(hashlib.md5(data_hash.encode()).hexdigest()),
                    trade['filing_date'],
                    trade['transaction_date'],
                    trade['politician_name'],
                    trade['ticker'],
                    trade['asset_type'],
                    trade['transaction_type'],
                    trade['amount_range'],
                    trade['ptr_link'],
                    trade['is_paper'],
                    now,
                    now,
                    data_hash
                ))
                new_count += 1
            except sqlite3.IntegrityError:
                # Already exists, could update if needed
                updated_count += 1
        
        conn.commit()
        conn.close()
        return new_count, updated_count

    def run(self, days=7):
        """
        Full run for the last N days.
        """
        end_date_dt = datetime.now()
        start_date_dt = end_date_dt - timedelta(days=days)
        
        start_date = start_date_dt.strftime("%m/%d/%Y")
        end_date = end_date_dt.strftime("%m/%d/%Y")
        
        reports = self.fetch_report_list(start_date, end_date)
        logger.info(f"Found {len(reports)} reports in the list.")
        
        all_trades = []
        for report in reports:
            # report structure: [first_name_html, last_name, office, report_type, date_received]
            first_name_html = report[0]
            last_name = report[1]
            office = report[2]
            report_type = report[3]
            date_received = report[4]
            
            # Extract link and first name from HTML
            soup = BeautifulSoup(first_name_html, "html.parser")
            a_tag = soup.find("a")
            if not a_tag:
                continue
            
            report_link = a_tag["href"]
            first_name = a_tag.get_text(strip=True)
            
            # Standardize filing date
            try:
                fd_dt = datetime.strptime(date_received, "%m/%d/%Y")
                filing_date = fd_dt.strftime("%Y-%m-%d")
            except:
                filing_date = date_received

            if "/search/view/ptr/" in report_link:
                # Electronic Filing
                trades = self.parse_report_page(report_link, first_name, last_name, filing_date)
                all_trades.extend(trades)
            elif "/search/view/paper/" in report_link:
                # Paper Filing
                all_trades.append({
                    "politician_name": f"{first_name} {last_name}",
                    "filing_date": filing_date,
                    "transaction_date": filing_date, # Placeholder
                    "ticker": None,
                    "asset_type": "Unknown (Paper)",
                    "transaction_type": "Unknown (Paper)",
                    "amount_range": "Unknown (Paper)",
                    "ptr_link": f"{self.BASE_URL}{report_link}",
                    "is_paper": True
                })
        
        if all_trades:
            new, updated = self.save_to_db(all_trades)
            logger.info(f"Run complete. New trades: {new}, Already existed: {updated}")
            return new, updated
        else:
            logger.info("No trades found to save.")
            return 0, 0

if __name__ == "__main__":
    fetcher = SenateFetcherV1()
    # For testing, let's look at the last 30 days
    fetcher.run(days=30)