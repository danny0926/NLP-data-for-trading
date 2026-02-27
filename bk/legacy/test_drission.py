from DrissionPage import ChromiumPage, ChromiumOptions
import time
import json

def test_senate_drission():
    co = ChromiumOptions()
    co.headless(True)
    # Adding some common arguments for headless stability
    co.set_argument('--no-sandbox')
    co.set_argument('--disable-gpu')
    
    page = ChromiumPage(co)
    try:
        url = "https://efdsearch.senate.gov/search/"
        page.get(url)
        
        # 1. Accept agreement if present
        if page.ele("@name=prohibition_agreement"):
            print("Accepting agreement...")
            page.ele("@name=prohibition_agreement").click()
            page.ele("@type=submit").click()
            time.sleep(2)
        
        # 2. Fill search form
        print("Filling search form...")
        # Select Report Type: Periodic Transaction Report
        # The checkbox has name 'report_type' and value '11'
        page.ele("@value=11").click()
        
        # Dates
        page.ele("@id=id_submitted_start_date").input("12/01/2025")
        page.ele("@id=id_submitted_end_date").input("01/17/2026")
        
        page.ele("@type=submit").click()
        time.sleep(3)
        
        # 3. Check if table is loaded
        if page.ele("#filedReports"):
            print("Table found!")
            # The table uses DataTables AJAX, so we wait for rows
            time.sleep(2)
            rows = page.eles("#filedReports tbody tr")
            print(f"Found {len(rows)} rows in the table.")
            
            for row in rows[:5]:
                print(row.text.replace("\n", " | "))
                
        else:
            print("Table not found or maintenance page shown.")
            print(page.html[:500])
            
    finally:
        page.quit()

if __name__ == "__main__":
    test_senate_drission()
