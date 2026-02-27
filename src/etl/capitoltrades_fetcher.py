"""
Extract 層 — Capitol Trades Fetcher
從 capitoltrades.com 抓取國會交易資料 (Senate / House)。
作為 Senate EFD Search 被封鎖時的替代來源。

Capitol Trades 是第三方聚合站，資料來自官方揭露。
回傳整頁 HTML 給 LLM Transform 層解析（保持架構一致性）。

URL 格式:
  https://www.capitoltrades.com/trades?chamber=senate&page=1
  https://www.capitoltrades.com/trades?chamber=house&page=1
"""

import logging
import time

from curl_cffi import requests

from .base_fetcher import BaseFetcher, FetchResult, SourceType

logger = logging.getLogger("ETL.CapitolTradesFetcher")


class SourceTypeExt:
    """擴充 SourceType，Capitol Trades 回傳 HTML 頁面"""
    CAPITOLTRADES_HTML = "capitoltrades_html"


class CapitolTradesFetcher(BaseFetcher):
    BASE_URL = "https://www.capitoltrades.com"
    TRADES_URL = f"{BASE_URL}/trades"

    def __init__(self):
        self.session = requests.Session(impersonate="chrome")

    def fetch(self, chamber: str = "senate", pages: int = 3) -> list[FetchResult]:
        """
        抓取 Capitol Trades 交易頁面。

        Args:
            chamber: "senate" 或 "house"
            pages: 要抓取的頁數 (每頁約 12 筆)
        """
        results = []

        for page in range(1, pages + 1):
            url = f"{self.TRADES_URL}?chamber={chamber}&page={page}"
            logger.info(f"[CapitolTrades] 抓取第 {page}/{pages} 頁: {url}")

            try:
                resp = self.session.get(url, timeout=15)
                if resp.status_code != 200:
                    logger.error(f"請求失敗: {resp.status_code}")
                    continue

                results.append(FetchResult(
                    source_type=SourceType.SENATE_HTML,  # 複用 SENATE_HTML type
                    content=resp.content,
                    content_type="text/html",
                    source_url=url,
                    metadata={
                        "chamber": chamber.capitalize(),
                        "page": page,
                        "source_site": "capitoltrades.com",
                    }
                ))
            except Exception as e:
                logger.error(f"抓取失敗: {e}")
                continue

            time.sleep(0.5)

        logger.info(f"共抓取 {len(results)} 頁")
        return results
