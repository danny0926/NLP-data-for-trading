import requests
from bs4 import BeautifulSoup
import json
import logging
from typing import Dict, List, Optional

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SenateEFDFetcher:
    BASE_URL = "https://efdsearch.senate.gov"
    HOME_URL = f"{BASE_URL}/search/"
    SEARCH_DATA_URL = f"{BASE_URL}/search/report/data/"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Referer": self.HOME_URL
        })
        self.csrf_token = None

    def initialize(self) -> bool:
        """
        Fetches the home page to get CSRF token and accepts the prohibition agreement.
        """
        try:
            # 1. Get Homepage to fetch CSRF Token
            logger.info("Fetching homepage to retrieve CSRF token...")
            response = self.session.get(self.HOME_URL)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, "html.parser")
            csrf_input = soup.find("input", {"name": "csrfmiddlewaretoken"})
            
            if not csrf_input:
                logger.error("Could not find CSRF token on the page.")
                return False
                
            self.csrf_token = csrf_input["value"]
            logger.info(f"CSRF Token retrieved: {self.csrf_token[:10]}...")

            # Ensure the csrftoken cookie is in the session
            if 'csrftoken' not in self.session.cookies:
                logger.warning("csrftoken cookie not found in session. Manually setting it if possible.")
                # Some sites set it via JavaScript or separate call, but usually it's in the GET response
            
            # 2. Accept Prohibition Agreement
            logger.info("Accepting prohibition agreement...")
            payload = {
                "csrfmiddlewaretoken": self.csrf_token,
                "prohibition_agreement": "1"
            }
            
            headers = {
                "Referer": self.HOME_URL,
                "X-CSRFToken": self.csrf_token
            }
            
            response = self.session.post(self.HOME_URL, data=payload, headers=headers)
            response.raise_for_status()
            
            logger.info("Agreement accepted.")
            # logger.info(f"Response after agreement: {response.text[:1000]}") # Debugging

            # Verify access to the search page (behind the wall)
            verify_response = self.session.get(self.HOME_URL)
            with open("search_page_dump.html", "w", encoding="utf-8") as f:
                f.write(verify_response.text)
            
            if "search_form" in verify_response.text or "datatable" in verify_response.text or "Search Reports" in verify_response.text:
                 if "prohibition_agreement" not in verify_response.text:
                     logger.info("Successfully verified access to search page content.")
                 else:
                     logger.warning("Still seeing agreement form in search page. Access might be restricted.")
            else:
                 logger.warning("Could not verify clear access to search page. Might still be on agreement page.")

            return True

        except Exception as e:
            logger.error(f"Initialization failed: {e}")
            return False

    def fetch_reports(self, start_date: str, end_date: str, offset: int = 0, limit: int = 100) -> Dict:
        """
        Fetches periodic transaction reports for a given date range.
        Dates should be in 'MM/DD/YYYY' format.
        """
        if not self.csrf_token:
            logger.error("Fetcher not initialized. Call initialize() first.")
            return {}

        payload = {
            "csrfmiddlewaretoken": self.csrf_token,
            "start_date": start_date,
            "end_date": end_date,
            "report_types": "[11]",  # 11 = Periodic Transactions
            "filter_types": "[1,2,3]", # Senators, Former Senators...
            "submitted_start_date": "",
            "submitted_end_date": "",
            "candidate_state": "",
            "senator_state": "",
            "lastName": "",
            "firstName": "",
            
            # DataTable parameters (required by the server usually)
            "draw": "1",
            "start": str(offset),
            "length": str(limit),
            "search[value]": "",
            "search[regex]": "false",
            
            # Order by Date Received (column 4) usually, descending
            "order[0][column]": "4", 
            "order[0][dir]": "desc"
        }

        # Add column definitions (boilerplate for DataTables)
        # 0: First Name, 1: Last Name, 2: Office, 3: Report Type, 4: Date Received
        columns = ["first_name", "last_name", "office", "report_type", "date_received"]
        for i, col in enumerate(columns):
            payload[f"columns[{i}][data]"] = str(i)
            payload[f"columns[{i}][name]"] = ""
            payload[f"columns[{i}][searchable]"] = "true"
            payload[f"columns[{i}][orderable]"] = "true"
            payload[f"columns[{i}][search][value]"] = ""
            payload[f"columns[{i}][search][regex]"] = "false"

        try:
            logger.info(f"Fetching reports from {start_date} to {end_date}...")
            # Add headers specifically for this AJAX request
            headers = {
                "Referer": self.HOME_URL,
                "X-Requested-With": "XMLHttpRequest",
                "X-CSRFToken": self.csrf_token,
                "Origin": self.BASE_URL
            }
            response = self.session.post(self.SEARCH_DATA_URL, data=payload, headers=headers)
            response.raise_for_status()
            
            return response.json()
            
        except Exception as e:
            logger.error(f"Failed to fetch reports: {e}")
            if 'response' in locals():
                logger.error(f"Response status: {response.status_code}")
                logger.error(f"Response content: {response.text[:500]}") # Log first 500 chars
            return {}

if __name__ == "__main__":
    fetcher = SenateEFDFetcher()
    if fetcher.initialize():
        # Test search for December 2025
        results = fetcher.fetch_reports("12/01/2025", "12/31/2025")
        if results and 'data' in results:
            print(f"Found {results['recordsTotal']} total records.")
            print(f"Returned {len(results['data'])} records.")
            if len(results['data']) > 0:
                print("Sample record:", results['data'][0])
        else:
            print("No data found or error occurred.")
