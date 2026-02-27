from curl_cffi import requests
from bs4 import BeautifulSoup
import logging

logging.basicConfig(level=logging.INFO)

def debug_ajax():
    base_url = "https://efdsearch.senate.gov"
    home_url = f"{base_url}/search/"
    data_url = f"{base_url}/search/report/data/"
    
    session = requests.Session(impersonate="chrome")
    
    # 1. Get Home & Accept Agreement
    resp = session.get(home_url)
    soup = BeautifulSoup(resp.text, "html.parser")
    csrf_token = soup.find("input", {"name": "csrfmiddlewaretoken"})["value"]
    
    session.post(f"{base_url}/search/home/", data={
        "csrfmiddlewaretoken": csrf_token,
        "prohibition_agreement": "1"
    }, headers={"Referer": home_url})
    
    # 2. Search Form
    session.post(home_url, data={
        "csrfmiddlewaretoken": csrf_token,
        "report_type": "11",
        "submitted_start_date": "12/01/2025",
        "submitted_end_date": "01/17/2026",
        "search_reports": "Search Reports"
    }, headers={"Referer": home_url})
    
    # 3. Test AJAX with different variants
    variants = [
        {"report_types": "[11]", "filter_types": "[1,2,3]"},
        {"report_types": "11", "filter_types": "1,2,3"},
    ]
    
    for var in variants:
        print(f"\nTesting variant: {var}")
        payload = {
            "csrfmiddlewaretoken": csrf_token,
            "draw": "1",
            "start": "0",
            "length": "25",
            "start_date": "12/01/2025",
            "end_date": "01/17/2026",
        }
        payload.update(var)
        
        # Add columns
        for i in range(5):
            payload[f"columns[{i}][data]"] = str(i)
            payload[f"columns[{i}][searchable]"] = "true"
            payload[f"columns[{i}][orderable]"] = "true"
            payload[f"columns[{i}][search][value]"] = ""
            payload[f"columns[{i}][search][regex]"] = "false"
        
        resp = session.post(data_url, data=payload, headers={
            "Referer": home_url,
            "X-Requested-With": "XMLHttpRequest",
            "X-CSRFToken": csrf_token
        })
        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
            print(f"Success! Data keys: {resp.json().keys()}")
            break
        else:
            print(f"Response (first 200 chars): {resp.text[:200]}")

if __name__ == "__main__":
    debug_ajax()
