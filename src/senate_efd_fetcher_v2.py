from curl_cffi import requests
from bs4 import BeautifulSoup
import json
import logging
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def fetch_senate_data():
    base_url = "https://efdsearch.senate.gov"
    home_url = f"{base_url}/search/"
    agreement_url = f"{base_url}/search/home/"
    data_url = f"{base_url}/search/report/data/"
    
    session = requests.Session(impersonate="chrome")
    
    # 1. Get Home Page
    logger.info("Fetching home page...")
    resp = session.get(home_url)
    soup = BeautifulSoup(resp.text, "html.parser")
    csrf_token = soup.find("input", {"name": "csrfmiddlewaretoken"})["value"]
    
    # 2. Accept Agreement
    logger.info("Accepting agreement...")
    payload = {
        "csrfmiddlewaretoken": csrf_token,
        "prohibition_agreement": "1"
    }
    headers = {
        "Referer": home_url,
        "Origin": base_url,
        "X-CSRFToken": csrf_token,
    }
    session.post(agreement_url, data=payload, headers=headers)
    
    # 3. Get Search Page to "unlock" and get fresh CSRF
    resp = session.get(home_url)
    soup = BeautifulSoup(resp.text, "html.parser")
    csrf_token = soup.find("input", {"name": "csrfmiddlewaretoken"})["value"]
    
    # 4. Perform Search (Form Submit)
    logger.info("Performing form search...")
    form_payload = {
        "csrfmiddlewaretoken": csrf_token,
        "report_type": "11",
        "submitted_start_date": "12/01/2025",
        "submitted_end_date": "12/31/2025",
        "search_reports": "Search Reports"
    }
    resp = session.post(home_url, data=form_payload, headers=headers)
    logger.info(f"Form POST status: {resp.status_code}, URL: {resp.url}")
    
    with open("search_result_html.html", "w", encoding="utf-8") as f:
        f.write(resp.text)

    # Check if data is already in the HTML (sometimes it is for small results)
    if "filedReports" in resp.text:
        logger.info("Found 'filedReports' in search result HTML.")
        soup = BeautifulSoup(resp.text, "html.parser")
        table = soup.find("table", {"id": "filedReports"})
        if table:
            rows = table.find_all("tr")
            logger.info(f"Found table with {len(rows)} rows in HTML.")
    
    # 5. Fetch AJAX Data
    logger.info("Fetching AJAX data...")
    search_payload = {
        "csrfmiddlewaretoken": csrf_token,
        "start_date": "12/01/2025",
        "end_date": "12/31/2025",
        "report_types": "[11]",
        "filter_types": "[1,2,3]",
        "draw": "1",
        "start": "0",
        "length": "100",
        "order[0][column]": "4",
        "order[0][dir]": "desc",
    }
    for i in range(5):
        search_payload[f"columns[{i}][data]"] = str(i)
        search_payload[f"columns[{i}][searchable]"] = "true"
        search_payload[f"columns[{i}][orderable]"] = "true"
        search_payload[f"columns[{i}][search][value]"] = ""
        search_payload[f"columns[{i}][search][regex]"] = "false"

    ajax_headers = {
        "Referer": home_url,
        "X-Requested-With": "XMLHttpRequest",
        "X-CSRFToken": csrf_token,
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "en-US,en;q=0.9",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
    }
    
    resp = session.post(data_url, data=search_payload, headers=ajax_headers)
    
    if resp.status_code == 200:
        data = resp.json()
        logger.info(f"Success! Found {data.get('recordsTotal')} records.")
        return data
    else:
        logger.error(f"Failed with status {resp.status_code}")
        logger.error(f"Response: {resp.text[:500]}")

if __name__ == "__main__":
    result = fetch_senate_data()
    if result and 'data' in result:
        with open("data/processed/senate_dec_2025.json", "w") as f:
            json.dump(result['data'], f, indent=4)
        logger.info("Saved data to data/processed/senate_dec_2025.json")