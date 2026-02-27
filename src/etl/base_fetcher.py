"""
Extract 層 — BaseFetcher 抽象介面與 FetchResult 資料結構
每個資料來源只需實作 fetch() 方法，Transform / Load 層完全複用。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SourceType(Enum):
    SENATE_HTML = "senate_html"
    HOUSE_PDF = "house_pdf"
    THIRTEEN_F = "thirteenf_xml"


@dataclass
class FetchResult:
    """Extract 層的統一輸出"""
    source_type: SourceType
    content: bytes                      # 原始內容 (HTML bytes / PDF bytes / JSON bytes)
    content_type: str                   # "text/html" / "application/pdf" / "application/json"
    source_url: str                     # 來源 URL
    metadata: dict[str, Any] = field(default_factory=dict)  # 額外資訊 (議員姓名、filing ID 等)


class BaseFetcher(ABC):
    """所有 Fetcher 的抽象基底類別"""

    @abstractmethod
    def fetch(self, **kwargs) -> list[FetchResult]:
        """
        回傳原始內容列表。
        每個 FetchResult 代表一份需要 LLM 解析的文件。
        """
        ...
