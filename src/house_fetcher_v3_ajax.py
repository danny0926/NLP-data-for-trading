from curl_cffi import requests
from bs4 import BeautifulSoup
import logging
import sqlite3
import json
import re

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class HouseAjaxFetcher:
    def __init__(self, db_path="data/data.db"):
        self.db_path = db_path
        self.base_url = "https://disclosures-clerk.house.gov"
        self.init_db()

    def init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS house_reports (
                doc_id TEXT PRIMARY KEY,
                last_name TEXT,
                first_name TEXT,
                filing_type TEXT,
                state_dist TEXT,
                filing_date TEXT,
                year INTEGER,
                pdf_url TEXT,
                is_processed INTEGER DEFAULT 0
            )
        ''')
        conn.commit()
        conn.close()

    def fetch_latest(self):
        # 1. Start Session
        session = requests.Session(impersonate="chrome")
        
        # 2. Get Search Page to get cookies
        search_page_url = f"{self.base_url}/PublicReporting/FinancialDisclosure#Search"
        logger.info(f"Getting search page: {search_page_url}")
        resp = session.get(search_page_url)
        
        # 3. Fetch AJAX data
        # Based on search_page_actual.html line 178
        ajax_url = f"{self.base_url}/search/report/data/"
        
        payload = {
            "draw": "1",
            "start": "0",
            "length": "100",
            "report_type": "P", # Periodic Transaction Report
            "filing_year": "2025",
        }
        
        # Add required DataTable columns
        for i in range(5):
            payload[f"columns[{i}][data]"] = str(i)
            payload[f"columns[{i}][searchable]"] = "true"
            payload[f"columns[{i}][orderable]"] = "true"
            payload[f"columns[{i}][search][value]"] = ""
            payload[f"columns[{i}][search][regex]"] = "false"

        headers = {
            "Referer": search_page_url,
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        }
        
        logger.info(f"Fetching AJAX data from {ajax_url}...")
        resp = session.post(ajax_url, data=payload, headers=headers)
        
        if resp.status_code == 200:
            try:
                data = resp.json()
                logger.info(f"Success! Found {data.get('recordsTotal')} total records.")
                self.process_results(data.get('data', []), 2025)
            except Exception as e:
                logger.error(f"Error parsing AJAX JSON: {e}")
                # Log a bit of response for debugging
                logger.error(f"Response snippet: {resp.text[:500]}")
        else:
            logger.error(f"AJAX request failed. Status: {resp.status_code}")
            # Try 2024 if 2025 fails or is empty
            logger.info("Retrying with Year 2024...")
            payload["FilingYear"] = "2024"
            resp = session.post(ajax_url, data=payload, headers=headers)
            if resp.status_code == 200:
                self.process_results(resp.json().get('data', []), 2024)

    def process_results(self, rows, year):
        reports = []
        for row in rows:
            # House AJAX row format is often a list: ["Name", "Office", "Year", "Date", "LinkHTML"]
            if len(row) >= 5:
                name_text = row[0]
                link_html = row[4]
                
                doc_id_match = re.search(r'/(\d+)\.pdf', link_html)
                doc_id = doc_id_match.group(1) if doc_id_match else ""
                
                reports.append({
                    'doc_id': doc_id,
                    'last_name': name_text.split(",")[0].strip() if "," in name_text else name_text,
                    'first_name': name_text.split(",")[1].strip() if "," in name_text else "",
                    'filing_type': 'PTR',
                    'state_dist': row[1],
                    'filing_date': row[3],
                    'year': year,
                    'pdf_url': f"https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/{year}/{doc_id}.pdf"
                })
        
        if reports:
            self.save_reports(reports)

    def save_reports(self, reports):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        new_count = 0
        for r in reports:
            if not r['doc_id']: continue
            try:
                cursor.execute('''
                    INSERT OR IGNORE INTO house_reports 
                    (doc_id, last_name, first_name, filing_type, state_dist, filing_date, year, pdf_url)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (r['doc_id'], r['last_name'], r['first_name'], r['filing_type'], 
                      r['state_dist'], r['filing_date'], r['year'], r['pdf_url']))
                if cursor.rowcount > 0:
                    new_count += 1
            except Exception as e:
                pass
        conn.commit()
        conn.close()
        logger.info(f"Saved {new_count} new House reports.")

if __name__ == "__main__":
    fetcher = HouseAjaxFetcher()
    fetcher.fetch_latest()
