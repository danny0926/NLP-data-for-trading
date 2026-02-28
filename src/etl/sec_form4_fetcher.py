"""
Extract 層 — SEC Form 4 Insider Trading Fetcher
從 SEC EDGAR 抓取 Form 4 (Insider Trading) 資料。

Form 4 揭露公司內部人（officer/director/10%+ owner）的股票交易。
與國會交易交叉比對可發現強力投資訊號。

SEC EDGAR API 規則:
- 必須包含 User-Agent header（含聯絡信箱）
- 速率限制: 最多 10 requests/second
- 資料來源: EDGAR Full-Text Search Index → Form 4 XML 解析

API 流程:
1. EFTS search-index 搜尋 Form 4 filings (回傳 accession + XML filename)
2. 從 _id 欄位取得 {accession}:{filename}，從 _source.ciks[0] 取得 CIK
3. 組合 URL: https://www.sec.gov/Archives/edgar/data/{CIK}/{accession_no_dashes}/{filename}
4. 下載並解析 Form 4 XML
"""

import logging
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Optional
from dataclasses import dataclass

import requests

logger = logging.getLogger("ETL.SECForm4Fetcher")

# SEC EDGAR 要求的 User-Agent
SEC_USER_AGENT = "Political Alpha Monitor research@example.com"

# Rate limiting: SEC 限制 10 req/sec，保守設為每秒 5 個
SEC_RATE_LIMIT_DELAY = 0.2  # 200ms between requests


@dataclass
class Form4Trade:
    """單筆 Form 4 交易紀錄"""
    accession_number: str
    filer_name: str
    filer_title: Optional[str]
    issuer_name: str
    ticker: Optional[str]
    transaction_type: str       # "P" = Purchase, "S" = Sale, "A" = Grant/Award, etc.
    transaction_date: str       # YYYY-MM-DD
    shares: Optional[float]
    price_per_share: Optional[float]
    total_value: Optional[float]
    ownership_type: str         # "D" = Direct, "I" = Indirect
    source_url: str


class SECForm4Fetcher:
    """
    從 SEC EDGAR 抓取 Form 4 insider trading 資料。

    流程:
    1. 用 EDGAR EFTS search-index API 搜尋最近的 Form 4 filings
    2. 從搜尋結果建構 XML 下載 URL
    3. 逐一下載 Form 4 XML 並解析交易明細
    """

    # EFTS search-index 每次最多回傳 100 筆
    EFTS_PAGE_SIZE = 100

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": SEC_USER_AGENT,
            "Accept": "application/json",
        })
        self._last_request_time = 0.0

    def _rate_limit(self):
        """遵守 SEC 速率限制"""
        elapsed = time.time() - self._last_request_time
        if elapsed < SEC_RATE_LIMIT_DELAY:
            time.sleep(SEC_RATE_LIMIT_DELAY - elapsed)
        self._last_request_time = time.time()

    def fetch(self, days: int = 7, max_filings: int = 50) -> list:
        """
        抓取最近 N 天的 Form 4 filings。

        Args:
            days: 回溯天數
            max_filings: 最大抓取數量

        Returns:
            list[Form4Trade]: 解析後的交易紀錄
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        logger.info(
            f"[SECForm4] 開始抓取 Form 4，範圍: "
            f"{start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')}"
        )

        # Step 1: 搜尋最近的 Form 4 filings
        filing_entries = self._search_filings(
            start_date=start_date.strftime("%Y-%m-%d"),
            end_date=end_date.strftime("%Y-%m-%d"),
            max_results=max_filings,
        )

        if not filing_entries:
            logger.warning("[SECForm4] 未找到任何 Form 4 filing")
            return []

        logger.info(f"[SECForm4] 找到 {len(filing_entries)} 筆 Form 4 filing")

        # Step 2: 逐一下載並解析 XML
        all_trades = self._download_and_parse(filing_entries)

        logger.info(
            f"[SECForm4] 完成: 共解析 {len(all_trades)} 筆交易 "
            f"(來自 {len(filing_entries)} 筆 filing)"
        )
        return all_trades

    def fetch_by_tickers(self, tickers: list, days: int = 30,
                         max_filings_per_ticker: int = 10) -> list:
        """
        針對特定 tickers 抓取 Form 4 insider trading 資料。

        使用 EDGAR EFTS search-index API，以公司 ticker 作為搜尋關鍵字。
        這能大幅提高與 congress_trades 的重疊率。

        Args:
            tickers: 要搜尋的 ticker 列表
            days: 回溯天數
            max_filings_per_ticker: 每個 ticker 最多抓取幾筆 filing

        Returns:
            list[Form4Trade]: 解析後的交易紀錄
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")

        logger.info(
            f"[SECForm4] 針對 {len(tickers)} 個 tickers 抓取 Form 4，"
            f"範圍: {start_str} ~ {end_str}"
        )

        all_trades = []
        for i, ticker in enumerate(tickers):
            logger.info(
                f"[SECForm4] ({i+1}/{len(tickers)}) 搜尋 {ticker} 的 Form 4..."
            )
            filing_entries = self._search_filings_by_ticker(
                ticker=ticker,
                start_date=start_str,
                end_date=end_str,
                max_results=max_filings_per_ticker,
            )

            if not filing_entries:
                logger.info(f"[SECForm4] {ticker}: 無 Form 4 filing")
                continue

            logger.info(
                f"[SECForm4] {ticker}: 找到 {len(filing_entries)} 筆 filing"
            )
            trades = self._download_and_parse(filing_entries)
            all_trades.extend(trades)

        logger.info(
            f"[SECForm4] 完成: 共解析 {len(all_trades)} 筆交易 "
            f"(來自 {len(tickers)} 個 tickers)"
        )
        return all_trades

    def _download_and_parse(self, filing_entries: list) -> list:
        """下載並解析 filing entries 為交易紀錄。"""
        all_trades = []
        for i, entry in enumerate(filing_entries):
            accession = entry["accession"]
            xml_url = entry["xml_url"]
            logger.info(
                f"[SECForm4] 處理 {i+1}/{len(filing_entries)}: "
                f"{accession} ({entry.get('display_name', '')})"
            )
            try:
                trades = self._fetch_and_parse_xml(accession, xml_url)
                all_trades.extend(trades)
            except Exception as e:
                logger.error(f"[SECForm4] 解析失敗 {accession}: {e}")
                continue
        return all_trades

    def _search_filings_by_ticker(self, ticker: str, start_date: str,
                                   end_date: str,
                                   max_results: int = 10) -> list:
        """
        使用 EDGAR EFTS search-index 搜尋特定公司的 Form 4 filings。

        以 ticker 作為搜尋關鍵字，EDGAR 會匹配 issuerTradingSymbol。
        """
        self._rate_limit()

        url = "https://efts.sec.gov/LATEST/search-index"
        params = {
            "q": f'"{ticker}"',
            "forms": "4",
            "dateRange": "custom",
            "startdt": start_date,
            "enddt": end_date,
            "from": 0,
            "size": min(max_results, self.EFTS_PAGE_SIZE),
        }

        try:
            resp = self.session.get(url, params=params, timeout=30)
            if resp.status_code != 200:
                logger.warning(
                    f"[SECForm4] EFTS 搜尋 {ticker} 回傳 {resp.status_code}"
                )
                return []

            data = resp.json()
            hits = data.get("hits", {}).get("hits", [])

            if not hits:
                return []

            return self._parse_efts_hits(hits, max_results)

        except Exception as e:
            logger.warning(f"[SECForm4] EFTS 搜尋 {ticker} 失敗: {e}")
            return []

    def _search_filings(self, start_date: str, end_date: str,
                        max_results: int = 50) -> list:
        """
        使用 EDGAR EFTS search-index API 搜尋 Form 4 filings。

        API 回傳格式:
        {
            "hits": {
                "hits": [
                    {
                        "_id": "0001832612-26-000006:form4-02262026_040207.xml",
                        "_source": {
                            "adsh": "0001832612-26-000006",
                            "ciks": ["0001832612", "0001792789"],
                            "display_names": ["Adarkar Prabir  (CIK ...)", "DoorDash..."],
                            "form": "4",
                            "file_date": "2026-02-26"
                        }
                    }
                ]
            }
        }

        Returns:
            list[dict]: [{"accession": str, "xml_url": str, "display_name": str}, ...]
        """
        self._rate_limit()

        url = "https://efts.sec.gov/LATEST/search-index"
        params = {
            "q": "\"form 4\"",
            "forms": "4",
            "dateRange": "custom",
            "startdt": start_date,
            "enddt": end_date,
            "from": 0,
            "size": min(max_results, self.EFTS_PAGE_SIZE),
        }

        try:
            resp = self.session.get(url, params=params, timeout=30)
            if resp.status_code != 200:
                logger.warning(
                    f"[SECForm4] EFTS 搜尋回傳 {resp.status_code}，"
                    f"改用 RSS feed fallback"
                )
                return self._search_filings_rss(max_results)

            data = resp.json()
            hits = data.get("hits", {}).get("hits", [])
            total = data.get("hits", {}).get("total", {}).get("value", 0)
            logger.info(f"[SECForm4] EFTS 搜尋: 總共 {total} 筆，本頁 {len(hits)} 筆")

            if not hits:
                logger.warning("[SECForm4] EFTS 無結果，改用 RSS feed fallback")
                return self._search_filings_rss(max_results)

            return self._parse_efts_hits(hits, max_results)

        except Exception as e:
            logger.warning(f"[SECForm4] EFTS 搜尋失敗: {e}，改用 RSS feed fallback")
            return self._search_filings_rss(max_results)

    def _parse_efts_hits(self, hits: list, max_results: int) -> list:
        """
        從 EFTS search-index 結果建構 XML 下載 URL。

        _id 格式: "{accession}:{filename}"
        URL 格式: https://www.sec.gov/Archives/edgar/data/{CIK}/{accession_no_dashes}/{filename}
        """
        results = []

        for hit in hits[:max_results]:
            hit_id = hit.get("_id", "")
            source = hit.get("_source", {})
            ciks = source.get("ciks", [])
            adsh = source.get("adsh", "")
            display_names = source.get("display_names", [])

            if ":" not in hit_id or not ciks:
                continue

            # 從 _id 取得 filename
            parts = hit_id.split(":", 1)
            filename = parts[1] if len(parts) > 1 else ""

            if not filename or not adsh:
                continue

            # 第一個 CIK 是 reporting owner (filer)
            cik = ciks[0]
            accession_no_dashes = adsh.replace("-", "")

            xml_url = (
                f"https://www.sec.gov/Archives/edgar/data/"
                f"{cik}/{accession_no_dashes}/{filename}"
            )

            display_name = display_names[0] if display_names else ""

            results.append({
                "accession": adsh,
                "xml_url": xml_url,
                "display_name": display_name,
            })

        return results

    def _search_filings_rss(self, max_results: int = 50) -> list:
        """
        Fallback: 使用 EDGAR RSS feed (getcurrent) 抓取最新 Form 4。
        最穩定的方式，但無法指定日期範圍，只回傳最新的 filing。
        """
        self._rate_limit()

        url = "https://www.sec.gov/cgi-bin/browse-edgar"
        params = {
            "action": "getcurrent",
            "type": "4",
            "dateb": "",
            "owner": "include",
            "count": min(max_results, 40),
            "output": "atom",
        }

        try:
            resp = self.session.get(url, params=params, timeout=60)
            if resp.status_code != 200:
                logger.error(f"[SECForm4] RSS feed 失敗: {resp.status_code}")
                return []

            return self._parse_rss_feed(resp.text, max_results)
        except Exception as e:
            logger.error(f"[SECForm4] RSS feed 異常: {e}")
            return []

    def _parse_rss_feed(self, xml_text: str, max_results: int) -> list:
        """
        解析 EDGAR Atom feed，萃取 Form 4 filing URLs。
        RSS 回傳 index page URL，需要額外一步找到 XML。
        """
        results = []
        try:
            root = ET.fromstring(xml_text)
            ns = {"atom": "http://www.w3.org/2005/Atom"}

            entries = root.findall("atom:entry", ns)
            for entry in entries[:max_results]:
                title_el = entry.find("atom:title", ns)
                link_el = entry.find("atom:link", ns)

                if link_el is None:
                    continue

                title = title_el.text if title_el is not None else ""
                # 只保留 Form 4（排除 4/A 等）
                if not title.startswith("4 ") and title != "4":
                    continue

                href = link_el.get("href", "")
                if not href:
                    continue

                # 從 URL 萃取 accession
                # 格式: /Archives/edgar/data/{CIK}/{accession-no-dashes}/{filename}-index.htm
                accession = href.split("/")[-1].replace("-index.htm", "") if href else ""

                # RSS 回傳的是 index page，需要下載後找 XML
                full_url = href if href.startswith("http") else f"https://www.sec.gov{href}"

                results.append({
                    "accession": accession,
                    "xml_url": full_url,  # 這是 index page，_fetch_and_parse_xml 會處理
                    "display_name": title,
                })

        except ET.ParseError as e:
            logger.error(f"[SECForm4] RSS XML 解析失敗: {e}")

        logger.info(f"[SECForm4] RSS feed 找到 {len(results)} 筆 Form 4 filing")
        return results

    def _fetch_and_parse_xml(self, accession: str, xml_url: str) -> list:
        """
        下載 Form 4 XML 並解析交易明細。
        如果 URL 是 index page（HTML），先找到 XML 連結再下載。
        """
        self._rate_limit()

        resp = self.session.get(xml_url, timeout=30)
        if resp.status_code != 200:
            logger.warning(f"下載失敗 ({resp.status_code}): {xml_url}")
            return []

        content = resp.text

        # 如果直接是 Form 4 XML
        if "<ownershipDocument" in content:
            return self._parse_form4_xml(content, accession, xml_url)

        # 如果是 HTML index page，找 XML 連結
        xml_link = self._find_xml_url_in_index(content, xml_url)
        if not xml_link:
            logger.warning(f"Index page 中找不到 XML 連結: {xml_url}")
            return []

        self._rate_limit()
        xml_resp = self.session.get(xml_link, timeout=30)
        if xml_resp.status_code != 200:
            logger.warning(f"XML 下載失敗 ({xml_resp.status_code}): {xml_link}")
            return []

        return self._parse_form4_xml(xml_resp.text, accession, xml_link)

    def _find_xml_url_in_index(self, html: str, base_url: str) -> Optional[str]:
        """從 filing index HTML 找到 Form 4 XML 檔案 URL"""
        pattern = r'href="([^"]*\.xml)"'
        matches = re.findall(pattern, html)

        for match in matches:
            lower = match.lower()
            # 排除 XBRL 和非 Form 4 相關 XML
            if any(skip in lower for skip in ("r2.xml", "r1.xml", "financial", "xbrl")):
                continue
            if match.startswith("/"):
                return f"https://www.sec.gov{match}"
            elif match.startswith("http"):
                return match
            else:
                base = "/".join(base_url.split("/")[:-1])
                return f"{base}/{match}"

        return None

    def _parse_form4_xml(self, xml_text: str, accession: str,
                         source_url: str) -> list:
        """
        解析 Form 4 XML 文件，萃取交易明細。

        Form 4 XML 結構:
        <ownershipDocument>
            <issuer>
                <issuerName/> <issuerTradingSymbol/>
            </issuer>
            <reportingOwner>
                <reportingOwnerId><rptOwnerName/></reportingOwnerId>
                <reportingOwnerRelationship><officerTitle/></reportingOwnerRelationship>
            </reportingOwner>
            <nonDerivativeTable>
                <nonDerivativeTransaction>
                    <transactionDate><value/></transactionDate>
                    <transactionCoding><transactionCode/></transactionCoding>
                    <transactionAmounts>
                        <transactionShares><value/></transactionShares>
                        <transactionPricePerShare><value/></transactionPricePerShare>
                    </transactionAmounts>
                    <ownershipNature>
                        <directOrIndirectOwnership><value/></directOrIndirectOwnership>
                    </ownershipNature>
                </nonDerivativeTransaction>
            </nonDerivativeTable>
        </ownershipDocument>
        """
        trades = []

        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as e:
            logger.error(f"[SECForm4] XML 解析錯誤: {e}")
            return []

        # 萃取 issuer 資訊
        issuer_name = self._get_text(root, ".//issuer/issuerName")
        ticker = self._get_text(root, ".//issuer/issuerTradingSymbol")

        # 萃取 reporting owner 資訊
        filer_name = self._get_text(
            root, ".//reportingOwner/reportingOwnerId/rptOwnerName"
        )
        filer_title = self._get_text(
            root,
            ".//reportingOwner/reportingOwnerRelationship/officerTitle"
        )

        if not filer_name:
            logger.warning(f"[SECForm4] 找不到 filer name: {accession}")
            return []

        # 解析 non-derivative transactions（一般股票交易）
        for txn in root.findall(".//nonDerivativeTable/nonDerivativeTransaction"):
            trade = self._parse_transaction(
                txn, accession, filer_name, filer_title,
                issuer_name, ticker, source_url
            )
            if trade:
                trades.append(trade)

        # 解析 derivative transactions（選擇權、RSU 等）
        for txn in root.findall(".//derivativeTable/derivativeTransaction"):
            trade = self._parse_transaction(
                txn, accession, filer_name, filer_title,
                issuer_name, ticker, source_url,
                is_derivative=True,
            )
            if trade:
                trades.append(trade)

        return trades

    def _parse_transaction(self, txn_el, accession: str, filer_name: str,
                           filer_title: Optional[str], issuer_name: str,
                           ticker: Optional[str], source_url: str,
                           is_derivative: bool = False) -> Optional[Form4Trade]:
        """解析單筆交易 XML element"""
        txn_date = self._get_text(txn_el, ".//transactionDate/value")
        txn_code = self._get_text(txn_el, ".//transactionCoding/transactionCode")

        shares_text = self._get_text(
            txn_el, ".//transactionAmounts/transactionShares/value"
        )
        price_text = self._get_text(
            txn_el, ".//transactionAmounts/transactionPricePerShare/value"
        )

        ownership = self._get_text(
            txn_el,
            ".//ownershipNature/directOrIndirectOwnership/value"
        )

        shares = self._parse_float(shares_text)
        price = self._parse_float(price_text)
        total_value = None
        if shares is not None and price is not None:
            total_value = round(shares * price, 2)

        if not txn_date or not txn_code:
            return None

        # 為衍生品交易加上標記
        if is_derivative:
            txn_code = f"{txn_code}(D)"

        return Form4Trade(
            accession_number=accession,
            filer_name=filer_name,
            filer_title=filer_title,
            issuer_name=issuer_name or "",
            ticker=ticker.upper().strip() if ticker else None,
            transaction_type=txn_code,
            transaction_date=txn_date,
            shares=shares,
            price_per_share=price,
            total_value=total_value,
            ownership_type=ownership or "D",
            source_url=source_url,
        )

    @staticmethod
    def _get_text(element, xpath: str) -> Optional[str]:
        """安全地從 XML element 取得文字"""
        el = element.find(xpath)
        if el is not None and el.text:
            return el.text.strip()
        return None

    @staticmethod
    def _parse_float(text: Optional[str]) -> Optional[float]:
        """安全地將文字轉為 float"""
        if text is None:
            return None
        try:
            return float(text.replace(",", ""))
        except (ValueError, TypeError):
            return None
