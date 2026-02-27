from DrissionPage import ChromiumPage, ChromiumOptions
import time
import sqlite3
import re
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class HouseDrissionFetcher:
    def __init__(self, db_path="data/data.db"):
        self.db_path = db_path
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

    def fetch_with_drission(self):
        co = ChromiumOptions()
        co.headless(True)
        co.set_argument('--no-sandbox')
        co.set_argument('--disable-gpu')
        
        page = ChromiumPage(co)
        try:
            url = "https://disclosures-clerk.house.gov/PublicReporting/FinancialDisclosure#Search"
            logger.info(f"Opening House Search page: {url}")
            page.get(url)
            time.sleep(3)

            # 1. Look for the "Search" or "Find Reports" button if needed
            # Based on search_page_actual.html, we might need to click "Search Options" 
            # but usually it's already there.
            
            # 2. Select Report Type: Periodic Transaction Report (PTR)
            # Find the checkbox for PTR. Usually name="FilingType" value="P"
            ptr_checkbox = page.ele("@value=P")
            if ptr_checkbox:
                logger.info("Selecting PTR checkbox...")
                ptr_checkbox.click()
            
            # 3. Select Year
            # The year dropdown might have id="FilingYear"
            year_select = page.ele("#FilingYear")
            if year_select:
                logger.info("Selecting Year 2025...")
                year_select.select("2025")
            
            # 4. Submit Search
            submit_btn = page.ele("@type=submit")
            if submit_btn:
                logger.info("Submitting search...")
                submit_btn.click()
                time.sleep(5) # Wait for DataTables to load

            # 5. Parse the table
            if page.ele("#search_options_retrieve"):
                logger.info("Table container found.")
                # DataTables might be in #searchForm results
                rows = page.eles("t:tr") # Get all table rows
                logger.info(f"Found {len(rows)} potential table rows.")
                
                reports = []
                for row in rows:
                    cells = row.eles("t:td")
                    if len(cells) >= 5:
                        name_text = cells[0].text
                        # Document link is in cell[4]
                        link_ele = cells[4].ele("t:a")
                        if link_ele:
                            href = link_ele.attr("href")
                            doc_id_match = re.search(r'/(\d+)\.pdf', href)
                            doc_id = doc_id_match.group(1) if doc_id_match else ""
                            
                            reports.append({
                                'doc_id': doc_id,
                                'last_name': name_text.split(",")[0].strip() if "," in name_text else name_text,
                                'first_name': name_text.split(",")[1].strip() if "," in name_text else "",
                                'filing_type': 'PTR',
                                'state_dist': cells[1].text,
                                'filing_date': cells[3].text,
                                'year': 2025,
                                'pdf_url': f"https://disclosures-clerk.house.gov{href}"
                            })
                
                if reports:
                    self.save_reports(reports)
                else:
                    logger.warning("No reports extracted. Maybe table was empty or not loaded.")
            else:
                logger.error("Search result table not found.")
                # Save screenshot for debugging
                page.get_screenshot("house_debug.png")

        finally:
            page.quit()

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
        logger.info(f"Saved {new_count} new House PTR reports.")

if __name__ == "__main__":
    fetcher = HouseDrissionFetcher()
    fetcher.fetch_with_drission()
