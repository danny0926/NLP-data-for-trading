"""
Pydantic schemas — 統一資料合約
所有來源 (Senate HTML / House PDF / 13F) 經 LLM Transform 後都必須符合這些 schema。
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, Literal
from datetime import date


class CongressTrade(BaseModel):
    """統一的國會交易紀錄 schema"""
    politician_name: str = Field(..., description="議員全名")
    chamber: Literal["Senate", "House"]
    transaction_date: date
    filing_date: date
    ticker: Optional[str] = Field(None, max_length=10)
    asset_name: str = Field(..., description="資產名稱")
    asset_type: str = Field(default="Stock")
    transaction_type: Literal["Buy", "Sale", "Exchange"]
    amount_range: str = Field(..., description="金額區間，如 $1,001 - $15,000")
    owner: Optional[str] = Field(None, description="Owner: Self/Spouse/Child/Joint")
    comment: Optional[str] = None
    source_url: str = Field(..., description="原始揭露頁面 URL")

    @field_validator('ticker')
    @classmethod
    def clean_ticker(cls, v):
        if v is None:
            return None
        if v.strip() in ('--', 'N/A', '', 'n/a', 'None', 'null'):
            return None
        return v.upper().strip()

    @field_validator('amount_range')
    @classmethod
    def validate_amount(cls, v):
        if '$' not in v:
            raise ValueError(f"金額區間格式異常: {v}")
        return v


class ExtractionResult(BaseModel):
    """LLM 萃取結果的包裝"""
    trades: list[CongressTrade]
    source_format: Literal["senate_html", "house_pdf", "capitoltrades_html", "thirteenf_xml", "unknown"]
    confidence: float = Field(..., ge=0.0, le=1.0, description="LLM 自評信心分數")
    raw_record_count: int = Field(..., ge=0, description="原始資料中的紀錄數，用於比對是否遺漏")
