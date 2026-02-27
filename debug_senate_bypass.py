"""嘗試多種策略繞過 Senate EFD Akamai 封鎖"""
import sys, os, time
sys.path.insert(0, os.path.dirname(__file__))

from curl_cffi import requests
from bs4 import BeautifulSoup

BASE = "https://efdsearch.senate.gov"


def try_impersonation(browser_type):
    """嘗試不同的瀏覽器指紋"""
    print(f"\n--- 嘗試 impersonate={browser_type} ---")
    try:
        session = requests.Session(impersonate=browser_type)

        # Step 1-3: Home → Agreement → Form search
        r1 = session.get(f"{BASE}/search/home/")
        soup = BeautifulSoup(r1.text, "html.parser")
        token_el = soup.find("input", {"name": "csrfmiddlewaretoken"})
        if not token_el:
            print(f"  [FAIL] 無法取得 CSRF token")
            return False
        csrf = token_el["value"]

        time.sleep(0.5)
        session.post(f"{BASE}/search/home/", data={
            "csrfmiddlewaretoken": csrf,
            "prohibition_agreement": "1",
        }, headers={"Referer": f"{BASE}/search/home/", "X-CSRFToken": csrf, "Origin": BASE})

        time.sleep(0.3)
        r3 = session.get(f"{BASE}/search/")
        soup3 = BeautifulSoup(r3.text, "html.parser")
        token3 = soup3.find("input", {"name": "csrfmiddlewaretoken"})
        csrf = token3["value"] if token3 else csrf

        time.sleep(0.3)
        session.post(f"{BASE}/search/", data={
            "csrfmiddlewaretoken": csrf,
            "report_type": "11",
            "submitted_start_date": "01/01/2026",
            "submitted_end_date": "02/14/2026",
            "search_reports": "Search Reports",
        }, headers={"Referer": f"{BASE}/search/", "X-CSRFToken": csrf, "Origin": BASE})

        # Step 4: AJAX
        time.sleep(0.5)
        payload = {
            "csrfmiddlewaretoken": csrf,
            "draw": "1", "start": "0", "length": "10",
            "report_types": "[11]", "filter_types": "[1,2,3]",
            "start_date": "01/01/2026", "end_date": "02/14/2026",
            "order[0][column]": "4", "order[0][dir]": "desc",
        }
        for i in range(5):
            payload[f"columns[{i}][data]"] = str(i)
            payload[f"columns[{i}][searchable]"] = "true"
            payload[f"columns[{i}][orderable]"] = "true"
            payload[f"columns[{i}][search][value]"] = ""
            payload[f"columns[{i}][search][regex]"] = "false"

        r5 = session.post(f"{BASE}/search/report/data/", data=payload, headers={
            "Referer": f"{BASE}/search/",
            "X-Requested-With": "XMLHttpRequest",
            "X-CSRFToken": csrf,
            "Origin": BASE,
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        })
        print(f"  Status: {r5.status_code} | Server: {r5.headers.get('server', 'N/A')}")
        if r5.status_code == 200:
            data = r5.json()
            print(f"  *** 成功! Records: {data.get('recordsTotal', 0)} ***")
            if data.get("data"):
                print(f"  First: {data['data'][0][:2]}")
            return True
        else:
            title = BeautifulSoup(r5.text, "html.parser").find("title")
            print(f"  Title: {title.get_text() if title else 'N/A'}")
            return False
    except Exception as e:
        print(f"  [ERROR] {e}")
        return False


# 策略 1: 不同瀏覽器指紋
print("=" * 60)
print("策略 1: 不同 curl_cffi 瀏覽器指紋")
print("=" * 60)

browsers = ["chrome", "chrome110", "chrome120", "chrome124", "safari", "safari_ios", "edge99", "edge101"]
for b in browsers:
    success = try_impersonation(b)
    if success:
        print(f"\n*** 成功的指紋: {b} ***")
        break
    time.sleep(1)

# 策略 2: 使用 httpx 替代 curl_cffi
print()
print("=" * 60)
print("策略 2: 使用 httpx (不同 TLS stack)")
print("=" * 60)

try:
    import httpx
    client = httpx.Client(follow_redirects=True, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    })

    r1 = client.get(f"{BASE}/search/home/")
    soup = BeautifulSoup(r1.text, "html.parser")
    token_el = soup.find("input", {"name": "csrfmiddlewaretoken"})
    csrf = token_el["value"] if token_el else None
    print(f"  CSRF: {csrf[:20] if csrf else 'NONE'}...")

    if csrf:
        client.post(f"{BASE}/search/home/", data={
            "csrfmiddlewaretoken": csrf,
            "prohibition_agreement": "1",
        }, headers={"Referer": f"{BASE}/search/home/", "X-CSRFToken": csrf, "Origin": BASE})

        r3 = client.get(f"{BASE}/search/")
        soup3 = BeautifulSoup(r3.text, "html.parser")
        token3 = soup3.find("input", {"name": "csrfmiddlewaretoken"})
        csrf = token3["value"] if token3 else csrf

        time.sleep(0.5)
        client.post(f"{BASE}/search/", data={
            "csrfmiddlewaretoken": csrf,
            "report_type": "11",
            "submitted_start_date": "01/01/2026",
            "submitted_end_date": "02/14/2026",
            "search_reports": "Search Reports",
        }, headers={"Referer": f"{BASE}/search/", "X-CSRFToken": csrf, "Origin": BASE})

        payload = {
            "csrfmiddlewaretoken": csrf,
            "draw": "1", "start": "0", "length": "10",
            "report_types": "[11]", "filter_types": "[1,2,3]",
            "start_date": "01/01/2026", "end_date": "02/14/2026",
            "order[0][column]": "4", "order[0][dir]": "desc",
        }
        for i in range(5):
            payload[f"columns[{i}][data]"] = str(i)
            payload[f"columns[{i}][searchable]"] = "true"
            payload[f"columns[{i}][orderable]"] = "true"
            payload[f"columns[{i}][search][value]"] = ""
            payload[f"columns[{i}][search][regex]"] = "false"

        time.sleep(0.5)
        r5 = client.post(f"{BASE}/search/report/data/", data=payload, headers={
            "Referer": f"{BASE}/search/",
            "X-Requested-With": "XMLHttpRequest",
            "X-CSRFToken": csrf,
            "Origin": BASE,
            "Accept": "application/json, text/javascript, */*; q=0.01",
        })
        print(f"  Status: {r5.status_code} | Server: {r5.headers.get('server', 'N/A')}")
        if r5.status_code == 200:
            data = r5.json()
            print(f"  *** 成功! Records: {data.get('recordsTotal', 0)} ***")
        else:
            title = BeautifulSoup(r5.text, "html.parser").find("title")
            print(f"  Title: {title.get_text() if title else 'N/A'}")
except Exception as e:
    print(f"  [ERROR] {e}")

# 策略 3: 檢查替代資料來源
print()
print("=" * 60)
print("策略 3: 替代資料來源檢查")
print("=" * 60)

alt_sources = [
    ("Senate.gov PTR 列表", "https://www.senate.gov/legislative/public_disclosure/ptr.htm"),
    ("Senate.gov 揭露頁面", "https://www.senate.gov/pagelayout/legislative/g_three_sections_with_teasers/ethics.htm"),
]

session_alt = requests.Session(impersonate="chrome")
for name, url in alt_sources:
    try:
        r = session_alt.get(url, timeout=10)
        print(f"  {name}: {r.status_code}")
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            # 找 efdsearch 或相關連結
            links = soup.find_all("a", href=True)
            efd_links = [l for l in links if "efd" in l["href"].lower() or "disclosure" in l["href"].lower() or "ptr" in l["href"].lower()]
            if efd_links:
                for el in efd_links[:5]:
                    print(f"    -> {el['href']} ({el.get_text(strip=True)[:60]})")
    except Exception as e:
        print(f"  {name}: ERROR {e}")
