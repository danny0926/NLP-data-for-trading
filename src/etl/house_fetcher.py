"""
Extract 層 — House Fetcher
透過 curl_cffi 抓取 House FinancialDisclosure 報告列表 (HTML)，下載 PDF 檔案。
輸出 FetchResult (PDF bytes) 供 Transform 層的 Gemini Vision 解析。

House 網站 endpoint (2025~):
  POST /FinancialDisclosure/ViewMemberSearchResult
  回傳 HTML 表格，欄位: Name | Office | Filing Year | Filing (含 PDF 連結)
"""

import logging
import re
import time
from datetime import datetime

from bs4 import BeautifulSoup
from curl_cffi import requests

from .base_fetcher import BaseFetcher, FetchResult, SourceType

logger = logging.getLogger("ETL.HouseFetcher")


class HouseFetcher(BaseFetcher):
    BASE_URL = "https://disclosures-clerk.house.gov"
    DISCLOSURE_URL = f"{BASE_URL}/FinancialDisclosure"
    SEARCH_URL = f"{BASE_URL}/FinancialDisclosure/ViewMemberSearchResult"

    def __init__(self):
        self.session = requests.Session(impersonate="chrome")

    def _parse_name(self, raw_name: str) -> str:
        """
        解析 House 姓名格式。
        輸入: "Pelosi, Hon.. Nancy"  → 輸出: "Nancy Pelosi"
        輸入: "Allen, Hon.. Richard W." → 輸出: "Richard W. Allen"
        """
        # 移除 "Hon.." 或 "Hon." 前綴
        cleaned = re.sub(r'\bHon\.+\s*', '', raw_name).strip()

        if "," in cleaned:
            parts = cleaned.split(",", 1)
            last_name = parts[0].strip()
            first_name = parts[1].strip()
            return f"{first_name} {last_name}"
        return cleaned

    def _fetch_report_list(self, filing_year: int) -> list[dict]:
        """取得報告列表，解析 HTML 表格，回傳報告 metadata。"""
        # 先訪問主頁取得 cookies / session
        logger.info("取得搜尋頁面 cookies...")
        self.session.get(self.DISCLOSURE_URL)

        # POST 搜尋請求
        payload = {"FilingYear": str(filing_year)}
        headers = {
            "Referer": self.DISCLOSURE_URL,
            "X-Requested-With": "XMLHttpRequest",
        }

        logger.info(f"取得 {filing_year} 年 House 報告列表...")
        resp = self.session.post(self.SEARCH_URL, data=payload, headers=headers)

        if resp.status_code != 200:
            logger.error(f"搜尋請求失敗: {resp.status_code}")
            return []

        # 解析 HTML 表格
        soup = BeautifulSoup(resp.text, "html.parser")
        tbody = soup.find("tbody")
        if not tbody:
            logger.error("回傳 HTML 中找不到表格")
            return []

        rows = tbody.find_all("tr")
        logger.info(f"找到 {len(rows)} 筆報告")

        reports = []
        for row in rows:
            cols = row.find_all("td")
            if len(cols) < 4:
                continue

            # 欄位: Name (含 PDF link) | Office | Filing Year | Filing Type
            raw_name = cols[0].get_text(strip=True)
            state_dist = cols[1].get_text(strip=True)
            filing_type = cols[3].get_text(strip=True)

            # 只取 PTR (Periodic Transaction Report)
            if "PTR" not in filing_type:
                continue

            # PDF 連結在 Name 欄位 (cols[0]) 裡
            link = cols[0].find("a", href=True)
            if not link:
                continue

            href = link["href"]  # e.g. "public_disc/ptr-pdfs/2025/20032062.pdf"
            if ".pdf" not in href:
                continue

            doc_id_match = re.search(r'/(\d+)\.pdf', href)
            if not doc_id_match:
                continue
            doc_id = doc_id_match.group(1)

            # 組合完整 PDF URL
            pdf_url = f"{self.BASE_URL}/{href.lstrip('/')}"

            reports.append({
                "doc_id": doc_id,
                "politician_name": self._parse_name(raw_name),
                "state_dist": state_dist,
                "filing_type": filing_type,
                "pdf_url": pdf_url,
            })

        ptr_count = len(reports)
        logger.info(f"其中 PTR 報告: {ptr_count} 筆")
        return reports

    def _download_pdf(self, pdf_url: str) -> bytes:
        """下載 PDF 檔案，回傳 bytes。"""
        try:
            resp = self.session.get(pdf_url)
            if resp.status_code == 200 and len(resp.content) > 100:
                return resp.content
            logger.warning(f"PDF 下載異常: {pdf_url} (status={resp.status_code}, size={len(resp.content)})")
        except Exception as e:
            logger.error(f"PDF 下載失敗: {pdf_url} — {e}")
        return b""

    def fetch(self, filing_year: int = None, max_reports: int = 50) -> list[FetchResult]:
        """
        抓取 House 交易報告。
        取得報告列表後下載 PDF，回傳 FetchResult (PDF bytes)。
        """
        if filing_year is None:
            filing_year = datetime.now().year

        reports = self._fetch_report_list(filing_year)
        download_count = min(len(reports), max_reports)
        logger.info(f"準備下載 {download_count} 份 PDF")

        results = []
        for i, report in enumerate(reports[:max_reports]):
            pdf_url = report["pdf_url"]
            logger.info(f"[{i+1}/{download_count}] 下載: {report['politician_name']} — {pdf_url}")

            pdf_bytes = self._download_pdf(pdf_url)
            if not pdf_bytes:
                continue

            results.append(FetchResult(
                source_type=SourceType.HOUSE_PDF,
                content=pdf_bytes,
                content_type="application/pdf",
                source_url=pdf_url,
                metadata={
                    "politician_name": report["politician_name"],
                    "filing_date": str(datetime.now().date()),  # House 列表不提供 filing date
                    "chamber": "House",
                    "doc_id": report["doc_id"],
                    "state_dist": report.get("state_dist", ""),
                }
            ))

            # 禮貌延遲，避免觸發 rate limit
            time.sleep(0.5)

        logger.info(f"共下載 {len(results)} 份 PDF")
        return results
