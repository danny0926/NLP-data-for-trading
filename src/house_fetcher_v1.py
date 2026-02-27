import os
import zipfile
import io
import xml.etree.ElementTree as ET
from curl_cffi import requests
import logging
import sqlite3
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class HouseFetcher:
    def __init__(self, db_path="data/data.db"):
        self.db_path = db_path
        self.base_url = "https://disclosures-clerk.house.gov/xml-and-data/"
        self.init_db()

    def init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        # Create a table for tracked reports if not exists
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

    def fetch_index(self, year):
        zip_url = f"{self.base_url}{year}FD.zip"
        logger.info(f"Fetching index for {year} from {zip_url}...")
        
        try:
            response = requests.get(zip_url, impersonate="chrome", timeout=30)
            if response.status_code != 200:
                logger.error(f"Failed to download index for {year}. Status: {response.status_code}")
                return []

            with zipfile.ZipFile(io.BytesIO(response.content)) as z:
                # The filename inside zip is typically {year}FD.xml
                xml_filename = f"{year}FD.xml"
                if xml_filename not in z.namelist():
                    # Try to find any .xml file if the name differs
                    xml_files = [f for f in z.namelist() if f.endswith('.xml')]
                    if not xml_files:
                        logger.error(f"No XML file found in {year}FD.zip")
                        return []
                    xml_filename = xml_files[0]
                
                with z.open(xml_filename) as f:
                    tree = ET.parse(f)
                    root = tree.getroot()
                    return self.parse_xml(root, year)
        except Exception as e:
            logger.error(f"Error fetching/parsing House index for {year}: {e}")
            return []

    def parse_xml(self, root, year):
        reports = []
        # House XML structure: <Member><Last>...</Last><FilingType>P</FilingType>...</Member>
        # FilingType 'P' stands for Periodic Transaction Report (PTR)
        for member in root.findall('Member'):
            filing_type = member.find('FilingType').text if member.find('FilingType') is not None else ""
            
            # We only care about Periodic Transaction Reports
            if filing_type == 'P':
                doc_id = member.find('DocID').text if member.find('DocID') is not None else ""
                last_name = member.find('Last').text if member.find('Last') is not None else ""
                first_name = member.find('First').text if member.find('First') is not None else ""
                filing_date = member.find('FilingDate').text if member.find('FilingDate') is not None else ""
                state_dist = member.find('StateDst').text if member.find('StateDst') is not None else ""
                
                # Construct PDF URL
                # Format: https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/{year}/{doc_id}.pdf
                pdf_url = f"https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/{year}/{doc_id}.pdf"
                
                reports.append({
                    'doc_id': doc_id,
                    'last_name': last_name,
                    'first_name': first_name,
                    'filing_type': 'PTR',
                    'state_dist': state_dist,
                    'filing_date': filing_date,
                    'year': year,
                    'pdf_url': pdf_url
                })
        
        logger.info(f"Parsed {len(reports)} PTR reports for {year}.")
        return reports

    def save_reports(self, reports):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        new_count = 0
        for r in reports:
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
        logger.info(f"Saved {new_count} new PTR reports to database.")
        return new_count

if __name__ == "__main__":
    fetcher = HouseFetcher()
    # Try fetching 2025 and 2026
    for year in [2025, 2026]:
        reports = fetcher.fetch_index(year)
        if reports:
            fetcher.save_reports(reports)
