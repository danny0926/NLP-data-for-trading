"""
Extract 層 — Senate Fetcher (Playwright 版)
使用真實 Chromium 瀏覽器繞過 Akamai WAF，
透過頁面原生 DataTable JS 發 AJAX 取得報告列表，
再逐一載入報告 HTML 給 Transform 層解析。
"""

import logging
import time
from datetime import datetime, timedelta

from bs4 import BeautifulSoup

from .base_fetcher import BaseFetcher, FetchResult, SourceType

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("ETL.SenateFetcher")


class SenateFetcher(BaseFetcher):
    BASE_URL = "https://efdsearch.senate.gov"

    def __init__(self, headless: bool = False):
        """
        Args:
            headless: True=無頭模式（可能被 Akamai 偵測），False=可見瀏覽器（穩定通過）
        """
        self.headless = headless

    def fetch(self, days: int = 7, max_reports: int = 25) -> list[FetchResult]:
        """
        抓取最近 N 天的 Senate 交易報告。

        Args:
            days: 回溯天數
            max_reports: 最大報告數量（避免過多頁面載入）
        """
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise RuntimeError(
                "Playwright 未安裝。請執行: pip install playwright && python -m playwright install chromium"
            )

        end_dt = datetime.now()
        start_dt = end_dt - timedelta(days=days)
        start_date = start_dt.strftime("%m/%d/%Y")
        end_date = end_dt.strftime("%m/%d/%Y")

        results = []

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=self.headless,
                args=["--disable-blink-features=AutomationControlled"],
            )
            context = browser.new_context(viewport={"width": 1920, "height": 1080})
            context.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
            )
            page = context.new_page()

            try:
                report_rows = self._get_report_list(page, start_date, end_date)
                if not report_rows:
                    return []

                results = self._fetch_reports(page, report_rows, max_reports)
            except Exception as e:
                logger.error(f"Playwright 抓取失敗: {e}")
            finally:
                browser.close()

        logger.info(f"共取得 {len(results)} 份 Senate 報告 HTML")
        return results

    def _get_report_list(self, page, start_date: str, end_date: str) -> list:
        """接受協議 → 填表 → 攔截 DataTable AJAX 回應 → 回傳報告列表。"""

        # Step 1: 接受使用者協議
        logger.info("載入 Senate EFD 首頁...")
        page.goto(f"{self.BASE_URL}/search/home/", wait_until="networkidle")

        logger.info("接受使用者協議...")
        with page.expect_navigation(timeout=15000):
            page.locator("#agree_statement").click()
        page.wait_for_load_state("networkidle")
        logger.info(f"協議已接受，導航至: {page.url}")

        # Step 2: 填寫搜尋表單
        logger.info(f"填寫搜尋表單: PTR, {start_date} ~ {end_date}")
        page.locator("input[value='11']").check()  # Periodic Transaction Report
        page.locator("input[name='submitted_start_date']").fill(start_date)
        page.locator("input[name='submitted_end_date']").fill(end_date)

        # Step 3: 提交並攔截 DataTable AJAX 回應
        logger.info("提交搜尋...")
        with page.expect_response(
            lambda r: "report/data" in r.url, timeout=30000
        ) as resp_info:
            page.locator("button[type='submit']").click()

        response = resp_info.value
        if response.status != 200:
            logger.error(f"AJAX 請求失敗: {response.status}")
            return []

        data = response.json()
        report_rows = data.get("data", [])
        total = data.get("recordsTotal", len(report_rows))
        logger.info(f"找到 {total} 份報告 (本頁 {len(report_rows)} 筆)")

        return report_rows

    def _fetch_reports(self, page, report_rows: list, max_reports: int) -> list[FetchResult]:
        """遍歷報告列表，逐一載入報告 HTML。"""
        results = []

        for i, row in enumerate(report_rows):
            if len(results) >= max_reports:
                logger.info(f"已達上限 {max_reports} 份，停止")
                break

            # 解析欄位: [first_name, last_name, office, report_html, date]
            first_name = row[0].strip()
            last_name = row[1].strip()
            report_html = row[3]
            date_received = row[4].strip()

            # 從 report 欄位萃取連結
            soup = BeautifulSoup(report_html, "html.parser")
            a_tag = soup.find("a")
            if not a_tag:
                continue

            report_link = a_tag["href"]
            politician_name = f"{first_name} {last_name}"

            # 標準化日期
            try:
                filing_date = datetime.strptime(date_received, "%m/%d/%Y").strftime("%Y-%m-%d")
            except ValueError:
                filing_date = date_received

            # 載入報告頁面
            full_url = f"{self.BASE_URL}{report_link}"
            logger.info(f"[{i+1}/{len(report_rows)}] 載入: {politician_name} ({filing_date})")

            try:
                page.goto(full_url, wait_until="networkidle", timeout=20000)
                html_content = page.content().encode("utf-8")
            except Exception as e:
                logger.error(f"載入失敗: {full_url} — {e}")
                continue

            if len(html_content) < 500:
                logger.warning(f"報告內容過短 ({len(html_content)} bytes)，跳過")
                continue

            results.append(FetchResult(
                source_type=SourceType.SENATE_HTML,
                content=html_content,
                content_type="text/html",
                source_url=full_url,
                metadata={
                    "politician_name": politician_name,
                    "filing_date": filing_date,
                    "chamber": "Senate",
                }
            ))

            time.sleep(0.3)  # 避免過快請求

        return results
