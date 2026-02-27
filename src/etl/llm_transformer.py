"""
Transform 層 — LLM 解析核心
根據 source_type 選擇專用 prompt，呼叫 Gemini API 萃取結構化資料，
Pydantic 驗證失敗時附錯誤訊息自動重試。
"""

import json
import logging
import os
import re
from datetime import date, timedelta
from typing import Optional

from google import genai
from google.genai import types as genai_types

from .base_fetcher import FetchResult, SourceType
from .schemas import ExtractionResult

logger = logging.getLogger("ETL.LLMTransformer")


# ──────────────────────── Prompt 定義 ────────────────────────

SENATE_HTML_PROMPT = """你是金融資料萃取專家。以下是美國參議院議員的交易揭露報告 HTML 內容。

議員資訊（已知）：
- 姓名：{politician_name}
- 申報日期：{filing_date}
- 院別：Senate

請萃取所有交易紀錄，輸出為 JSON。每筆紀錄需包含：
- politician_name: 議員全名（使用上方提供的姓名）
- chamber: "Senate"
- transaction_date: 交易日期 (YYYY-MM-DD)
- filing_date: 申報日期 (YYYY-MM-DD，使用上方提供的日期)
- ticker: 股票代號 (無則為 null)
- asset_name: 資產名稱
- asset_type: 資產類型 (Stock, Bond, Option, 等)
- transaction_type: "Buy" / "Sale" / "Exchange"
- amount_range: 金額區間 (保留原始格式，如 "$1,001 - $15,000")
- owner: 持有人 (Self/Spouse/Child/Joint，無則為 null)
- comment: 備註 (無則為 null)
- source_url: "{source_url}"

輸出格式：
{{
  "trades": [...],
  "source_format": "senate_html",
  "confidence": 0.95,
  "raw_record_count": <你在原始 HTML 中看到的交易紀錄總數>
}}

重要規則：
- 只萃取實際存在的資料，絕不捏造
- ticker 若為 "--" 或不存在，設為 null
- 日期必須轉為 YYYY-MM-DD 格式
- transaction_type 必須是 "Buy"、"Sale" 或 "Exchange" 之一
  - Purchase、Buy → "Buy"
  - Sale、Sale (Full)、Sale (Partial) → "Sale"
  - Exchange → "Exchange"
- amount_range 保留原始格式（含 $ 符號）
- confidence 反映你對萃取品質的信心 (0.0-1.0)
- raw_record_count 必須等於 HTML 中的實際紀錄數

HTML 內容：
{html_content}
"""

HOUSE_PDF_PROMPT = """你是金融資料萃取專家。以下是美國眾議院議員的交易揭露報告 PDF 圖片。

議員資訊（已知）：
- 姓名：{politician_name}
- 申報日期：{filing_date}
- 院別：House

請仔細閱讀圖片中的交易表格，萃取所有交易紀錄，輸出為 JSON。每筆紀錄需包含：
- politician_name: 議員全名（使用上方提供的姓名）
- chamber: "House"
- transaction_date: 交易日期 (YYYY-MM-DD)
- filing_date: 申報日期 (YYYY-MM-DD，使用上方提供的日期)
- ticker: 股票代號 (無則為 null)
- asset_name: 資產名稱
- asset_type: 資產類型 (Stock, Bond, Option, 等)
- transaction_type: "Buy" / "Sale" / "Exchange"
  - P、Purchase → "Buy"
  - S、Sale → "Sale"
  - E、Exchange → "Exchange"
- amount_range: 金額區間 (保留原始格式，如 "$1,001 - $15,000")
- owner: 持有人 (SP=Spouse, JT=Joint, DC=Child, Self，無則為 null)
- comment: 備註 (無則為 null)
- source_url: "{source_url}"

輸出格式：
{{
  "trades": [...],
  "source_format": "house_pdf",
  "confidence": 0.95,
  "raw_record_count": <你在 PDF 中看到的交易紀錄總數>
}}

重要規則：
- 只萃取實際存在的資料，絕不捏造
- ticker 若無法辨識，設為 null
- 日期必須轉為 YYYY-MM-DD 格式
- amount_range 保留原始格式（含 $ 符號）
- confidence 反映你對萃取品質的信心 (0.0-1.0)
- 若圖片模糊或欄位不清楚，降低 confidence
"""


CAPITOLTRADES_HTML_PROMPT = """你是金融資料萃取專家。以下是 Capitol Trades 網站的國會議員交易頁面 HTML。

頁面包含一個交易表格，欄位為: Politician | Traded Issuer | Published | Traded | Filed After | Owner | Type | Size | Price

請萃取所有交易紀錄，輸出為 JSON。每筆紀錄需包含：
- politician_name: 議員全名 (不含黨派和州份，例如 "Byron Donalds" 而非 "Byron DonaldsRepublicanHouseFL")
- chamber: "Senate" 或 "House" (從 Politician 欄位中的 Senate/House 判斷)
- transaction_date: 交易日期 (Traded 欄位，轉為 YYYY-MM-DD)
- filing_date: 申報日期 (Published 欄位，轉為 YYYY-MM-DD)
- ticker: 股票代碼 (從 Traded Issuer 萃取，格式如 $BTC 或 HWM:US → 取 HWM，無明確代碼則為 null)
- asset_name: 資產名稱 (Traded Issuer 的公司/資產名，不含 ticker 部分)
- asset_type: "Stock" (預設，如果是 Bond/Option/Fund 請標註)
- transaction_type: "Buy" 或 "Sale" (從 Type 欄位判斷: buy→Buy, sell→Sale)
- amount_range: 金額區間 (Size 欄位，轉為 "$X - $Y" 格式，例如 "1K–15K" → "$1,001 - $15,000")
- owner: 持有人 (Owner 欄位: Self/Spouse/Joint/Undisclosed，無則為 null)
- comment: null
- source_url: "{source_url}"

金額轉換規則：
- 1K–15K → "$1,001 - $15,000"
- 15K–50K → "$15,001 - $50,000"
- 50K–100K → "$50,001 - $100,000"
- 100K–250K → "$100,001 - $250,000"
- 250K–500K → "$250,001 - $500,000"
- 500K–1M → "$500,001 - $1,000,000"
- 1M–5M → "$1,000,001 - $5,000,000"
- 5M+ → "$5,000,001+"

輸出格式：
{{
  "trades": [...],
  "source_format": "capitoltrades_html",
  "confidence": 0.95,
  "raw_record_count": <表格中的交易紀錄總數>
}}

重要規則：
- 只萃取表格中實際存在的資料，絕不捏造
- 日期轉為 YYYY-MM-DD (今年是 {current_year})
- confidence 反映你對萃取品質的信心 (0.0-1.0)

HTML 內容：
{html_content}
"""


class TransformError(Exception):
    """Transform 層錯誤"""
    pass


class LLMTransformer:
    MAX_RETRIES = 3

    def __init__(self, model_name: str = "gemini-2.5-flash"):
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY 環境變數未設定")
        self.client = genai.Client(api_key=api_key)
        self.model_name = model_name

    def transform(self, fetch_result: FetchResult) -> ExtractionResult:
        """
        將 FetchResult 轉換為結構化的 ExtractionResult。
        根據 source_type + metadata 選擇處理路徑。
        """
        # Capitol Trades 來源 (metadata 標記)
        if fetch_result.metadata.get("source_site") == "capitoltrades.com":
            return self._transform_capitoltrades(fetch_result)
        elif fetch_result.source_type == SourceType.SENATE_HTML:
            return self._transform_senate_html(fetch_result)
        elif fetch_result.source_type == SourceType.HOUSE_PDF:
            return self._transform_house_pdf(fetch_result)
        else:
            raise TransformError(f"不支援的來源類型: {fetch_result.source_type}")

    def _transform_capitoltrades(self, fetch_result: FetchResult) -> ExtractionResult:
        """Capitol Trades HTML → 結構化交易資料"""
        html_content = fetch_result.content.decode("utf-8", errors="replace")
        html_content = self._trim_capitoltrades_html(html_content)

        from datetime import datetime
        prompt = CAPITOLTRADES_HTML_PROMPT.format(
            source_url=fetch_result.source_url,
            current_year=datetime.now().year,
            html_content=html_content,
        )

        result = self._call_and_validate(prompt)

        # Capitol Trades 的 source_format 標記
        if result.source_format not in ("capitoltrades_html", "senate_html", "house_pdf"):
            result = result.model_copy(update={"source_format": "capitoltrades_html"})

        return result

    def _transform_senate_html(self, fetch_result: FetchResult) -> ExtractionResult:
        """Senate HTML → 結構化交易資料"""
        html_content = fetch_result.content.decode("utf-8", errors="replace")

        # 截取關鍵部分以減少 token 用量
        html_content = self._trim_html(html_content)

        prompt = SENATE_HTML_PROMPT.format(
            politician_name=fetch_result.metadata.get("politician_name", "Unknown"),
            filing_date=fetch_result.metadata.get("filing_date", str(date.today())),
            source_url=fetch_result.source_url,
            html_content=html_content,
        )

        return self._call_and_validate(prompt)

    def _transform_house_pdf(self, fetch_result: FetchResult) -> ExtractionResult:
        """House PDF → 圖片 → Gemini Vision → 結構化交易資料"""
        try:
            import fitz  # PyMuPDF
        except ImportError:
            raise TransformError("PyMuPDF (fitz) 未安裝。請執行: pip install PyMuPDF")

        pdf_bytes = fetch_result.content

        # PDF 轉圖片
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        images = []
        for page_num in range(len(doc)):
            page = doc[page_num]
            pix = page.get_pixmap(dpi=200)
            images.append(pix.tobytes("png"))
        doc.close()

        if not images:
            raise TransformError("PDF 無頁面內容")

        prompt_text = HOUSE_PDF_PROMPT.format(
            politician_name=fetch_result.metadata.get("politician_name", "Unknown"),
            filing_date=fetch_result.metadata.get("filing_date", str(date.today())),
            source_url=fetch_result.source_url,
        )

        # 構建多模態內容 (文字 + 多張圖片)
        contents = [prompt_text]
        for img_bytes in images:
            contents.append(genai_types.Part.from_bytes(data=img_bytes, mime_type="image/png"))

        return self._call_and_validate_multimodal(contents)

    def _call_and_validate(self, prompt: str) -> ExtractionResult:
        """呼叫 LLM 並驗證輸出，失敗時附錯誤訊息重試。"""
        current_prompt = prompt
        last_error = None

        for attempt in range(self.MAX_RETRIES):
            if attempt > 0:
                logger.info(f"重試第 {attempt + 1} 次...")

            raw_output = self._call_llm(current_prompt)
            json_data = self._extract_json(raw_output)

            if json_data is None:
                last_error = "無法從 LLM 輸出中萃取 JSON"
                current_prompt = self._append_error_feedback(prompt, last_error)
                continue

            try:
                result = ExtractionResult(**json_data)
                result = self._validate_dates(result)
                if len(result.trades) < result.raw_record_count:
                    logger.warning(
                        f"遺漏紀錄: 萃取 {len(result.trades)}/{result.raw_record_count}"
                    )
                return result
            except Exception as e:
                last_error = str(e)
                logger.warning(f"驗證失敗 (attempt {attempt + 1}): {last_error}")
                current_prompt = self._append_error_feedback(prompt, last_error)

        raise TransformError(f"LLM 解析失敗 ({self.MAX_RETRIES} 次): {last_error}")

    def _call_and_validate_multimodal(self, contents: list) -> ExtractionResult:
        """多模態版本 (Vision)，呼叫 LLM 並驗證輸出。"""
        last_error = None

        for attempt in range(self.MAX_RETRIES):
            if attempt > 0:
                logger.info(f"重試第 {attempt + 1} 次...")
                # 重試時在文字 prompt 加入錯誤回饋
                error_note = f"\n\n[上次輸出有錯誤，請修正：{last_error}]"
                contents[0] = contents[0].rstrip() + error_note

            raw_output = self._call_llm_multimodal(contents)
            json_data = self._extract_json(raw_output)

            if json_data is None:
                last_error = "無法從 LLM 輸出中萃取 JSON"
                continue

            try:
                result = ExtractionResult(**json_data)
                result = self._validate_dates(result)
                if len(result.trades) < result.raw_record_count:
                    logger.warning(
                        f"遺漏紀錄: 萃取 {len(result.trades)}/{result.raw_record_count}"
                    )
                return result
            except Exception as e:
                last_error = str(e)
                logger.warning(f"驗證失敗 (attempt {attempt + 1}): {last_error}")

        raise TransformError(f"LLM Vision 解析失敗 ({self.MAX_RETRIES} 次): {last_error}")

    def _call_llm(self, prompt: str) -> str:
        """呼叫 Gemini API (文字模式)"""
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
            )
            return response.text or ""
        except Exception as e:
            logger.error(f"Gemini API 錯誤: {e}")
            return ""

    def _call_llm_multimodal(self, contents: list) -> str:
        """呼叫 Gemini API (多模態模式，用於 Vision)"""
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=contents,
            )
            return response.text or ""
        except Exception as e:
            logger.error(f"Gemini Vision API 錯誤: {e}")
            return ""

    def _extract_json(self, text: str) -> Optional[dict]:
        """
        從 LLM 輸出中萃取 JSON。
        沿用 discovery_engine_v4.py 的穩健邏輯。
        """
        if not text:
            return None

        # 移除 Markdown code blocks
        text = re.sub(r'```json\s*', '', text)
        text = re.sub(r'```\s*', '', text)

        # 搜尋 JSON object 或 array
        json_match = re.search(r'(\{.*\}|\[.*\])', text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                # 清理常見的 trailing comma 問題
                try:
                    cleaned = re.sub(r',\s*([\]}])', r'\1', json_match.group(0))
                    return json.loads(cleaned)
                except json.JSONDecodeError:
                    return None
        return None

    def _trim_html(self, html: str) -> str:
        """截取 HTML 中的關鍵部分 (交易表格)，減少 token 用量。"""
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")

        # 嘗試找到交易表格
        table = soup.find("table", {"class": "table-striped"})
        if not table:
            table = soup.find("table", {"id": "v3-transactions-table"})
        if not table:
            # 找不到特定表格，嘗試找所有 table
            tables = soup.find_all("table")
            if tables:
                table = max(tables, key=lambda t: len(t.find_all("tr")))

        if table:
            return str(table)

        # fallback: 回傳 body 內容 (截斷至 15000 字元避免 token 爆量)
        body = soup.find("body")
        content = str(body) if body else html
        return content[:15000]

    def _trim_capitoltrades_html(self, html: str) -> str:
        """Capitol Trades 專用：將 HTML 表格轉為精簡文字表格，大幅降低 token 用量。"""
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")

        table = soup.find("table")
        if not table:
            return html[:15000]

        rows = table.find_all("tr")
        if len(rows) < 2:
            return html[:15000]

        # 表頭
        lines = ["Politician | Traded Issuer | Published | Traded | Filed After | Owner | Type | Size | Price"]
        lines.append("-" * 100)

        for row in rows[1:]:  # 跳過 thead
            cells = row.find_all("td")
            if len(cells) < 9:
                continue
            # 萃取每個欄位的純文字
            vals = [c.get_text(separator=" ", strip=True) for c in cells[:9]]
            lines.append(" | ".join(vals))

        text_table = "\n".join(lines)
        logger.info(f"[CapitolTrades] HTML→文字表格: {len(html)} → {len(text_table)} chars")
        return text_table

    def _validate_dates(self, result: ExtractionResult) -> ExtractionResult:
        """
        日期合理性校驗：若 transaction_date 超過今天或超過 filing_date + 60 天，
        嘗試將年份減 1 修正。修正後更新 trades 列表。
        """
        today = date.today()
        updated_trades = []

        for trade in result.trades:
            td = trade.transaction_date
            fd = trade.filing_date
            corrected = False

            # 檢查 transaction_date 是否在未來
            if td > today:
                fixed_td = td.replace(year=td.year - 1)
                logger.warning(
                    f"未來交易日期偵測: {trade.politician_name} {trade.ticker} "
                    f"{td} → 修正為 {fixed_td}"
                )
                trade = trade.model_copy(update={"transaction_date": fixed_td})
                td = fixed_td
                corrected = True

            # 檢查 transaction_date 是否超過 filing_date + 60 天
            if fd and td > fd + timedelta(days=60):
                fixed_td = td.replace(year=td.year - 1)
                if not corrected:
                    logger.warning(
                        f"交易日期晚於申報日+60天: {trade.politician_name} {trade.ticker} "
                        f"交易={td} 申報={fd} → 修正為 {fixed_td}"
                    )
                    trade = trade.model_copy(update={"transaction_date": fixed_td})

            # 檢查 filing_date 是否在未來
            if fd > today:
                fixed_fd = fd.replace(year=fd.year - 1)
                logger.warning(
                    f"未來申報日期偵測: {trade.politician_name} {trade.ticker} "
                    f"{fd} → 修正為 {fixed_fd}"
                )
                trade = trade.model_copy(update={"filing_date": fixed_fd})

            updated_trades.append(trade)

        return result.model_copy(update={"trades": updated_trades})

    @staticmethod
    def _append_error_feedback(original_prompt: str, error: str) -> str:
        """將驗證錯誤附加到 prompt 尾部，引導 LLM 修正。"""
        return (
            original_prompt
            + f"\n\n[重要] 上次輸出驗證失敗，錯誤訊息如下，請修正後重新輸出：\n{error}"
        )
