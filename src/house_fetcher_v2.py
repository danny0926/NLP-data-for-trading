from curl_cffi import requests
from bs4 import BeautifulSoup
import logging
import sqlite3
import re
import json

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class HouseFetcherV2:
    def __init__(self, db_path="data/data.db"):
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        # Ensure the reports table exists
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

    def fetch_ptr_list(self, year):
        # The PTR specific list page for a given year
        url = f"https://disclosures-clerk.house.gov/PublicReporting/FinancialDisclosure/PTR?Year={year}"
        logger.info(f"Fetching House PTR list for {year} from {url}...")
        
        try:
            # House website is sensitive to TLS fingerprints, using curl_cffi chrome impersonation
            response = requests.get(url, impersonate="chrome", timeout=30)
            if response.status_code != 200:
                logger.error(f"Failed to fetch PTR list for {year}. Status: {response.status_code}")
                return []

            soup = BeautifulSoup(response.text, 'html.parser')
            # The reports are usually in a table with id 'ptrReports'
            table = soup.find('table', {'id': 'ptrReports'})
            if not table:
                # Fallback: check if they use AJAX for this page too
                logger.warning(f"No table 'ptrReports' found in HTML for {year}. Trying to find DataTables script...")
                return self.parse_from_scripts(response.text, year)

            return self.parse_table(table, year)
        except Exception as e:
            logger.error(f"Error fetching House PTR list for {year}: {e}")
            return []

    def parse_table(self, table, year):
        reports = []
        rows = table.find('tbody').find_all('tr') if table.find('tbody') else table.find_all('tr')
        
        for row in rows:
            cols = row.find_all('td')
            if len(cols) < 5:
                continue
            
            # Typical cols: Name, Office, Filing Year, Filing Date, Document Link
            name_text = cols[0].get_text(strip=True)
            # Split "Last, First"
            if "," in name_text:
                last_name, first_name = [x.strip() for x in name_text.split(",", 1)]
            else:
                last_name, first_name = name_text, ""
            
            office = cols[1].get_text(strip=True)
            filing_date = cols[3].get_text(strip=True)
            
            # Find PDF link
            link_tag = cols[4].find('a')
            if link_tag and 'href' in link_tag.attrs:
                href = link_tag['href']
                # Link is often like /public_disc/ptr-pdfs/2025/12345678.pdf
                # We extract the DocID from it
                doc_id_match = re.search(r'/(\d+)\.pdf', href)
                doc_id = doc_id_match.group(1) if doc_id_match else ""
                
                pdf_url = f"https://disclosures-clerk.house.gov{href}" if href.startswith('/') else href
                
                reports.append({
                    'doc_id': doc_id,
                    'last_name': last_name,
                    'first_name': first_name,
                    'filing_type': 'PTR',
                    'state_dist': office,
                    'filing_date': filing_date,
                    'year': year,
                    'pdf_url': pdf_url
                })
        
        logger.info(f"Parsed {len(reports)} reports from table for {year}.")
        return reports

    def parse_from_scripts(self, html, year):
        # Sometimes DataTables data is embedded in a script as a JSON object
        logger.info("Attempting to parse DataTables data from scripts...")
        reports = []
        # Look for something like var data = [...];
        match = re.search(r'var\s+data\s*=\s*(\[.*?\]);', html, re.DOTALL)
        if match:
            try:
                raw_data = json.loads(match.group(1))
                for item in raw_data:
                    # Map the JSON fields to our report structure
                    # Example item: ["Name", "Office", "Year", "Date", "LinkHTML"]
                    # Note: We'd need to parse the LinkHTML for docID
                    name_text = item[0]
                    # Simple split logic
                    if "," in name_text:
                        last_name, first_name = [x.strip() for x in name_text.split(",", 1)]
                    else:
                        last_name, first_name = name_text, ""
                    
                    link_html = item[4]
                    doc_id_match = re.search(r'/(\d+)\.pdf', link_html)
                    doc_id = doc_id_match.group(1) if doc_id_match else ""
                    
                    reports.append({
                        'doc_id': doc_id,
                        'last_name': last_name,
                        'first_name': first_name,
                        'filing_type': 'PTR',
                        'state_dist': item[1],
                        'filing_date': item[3],
                        'year': year,
                        'pdf_url': f"https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/{year}/{doc_id}.pdf"
                    })
                logger.info(f"Parsed {len(reports)} reports from script for {year}.")
            except Exception as e:
                logger.error(f"Error parsing script JSON: {e}")
        return reports

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
                logger.error(f"Error saving report {r['doc_id']}: {e}")
        
        conn.commit()
        conn.close()
        logger.info(f"Saved {new_count} new House PTR reports to database.")
        return new_count

if __name__ == "__main__":
    fetcher = HouseFetcherV2()
    # Fetch latest 2 years
    for year in [2024, 2025]:
        reports = fetcher.fetch_ptr_list(year)
        if reports:
            fetcher.save_reports(reports)
