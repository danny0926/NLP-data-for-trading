"""PAM 統一異常體系 — Political Alpha Monitor

所有模組的自定義異常集中在此。
使用指南: from src.exceptions import ETLError, LLMError, ...
"""


class PAMBaseError(Exception):
    """所有 PAM 自定義異常的基底類。"""
    pass


class ETLError(PAMBaseError):
    """ETL Pipeline 相關錯誤 (抓取、轉換、載入)。"""
    pass


class FetchError(ETLError):
    """資料抓取失敗 (網路、WAF、端點變更)。"""
    pass


class TransformError(ETLError):
    """LLM 轉換 / Pydantic 驗證失敗。"""
    pass


class LoadError(ETLError):
    """資料載入 DB 失敗 (重複、schema 不符)。"""
    pass


class LLMError(PAMBaseError):
    """LLM 呼叫或回應解析相關錯誤。"""
    pass


class JSONExtractionError(LLMError):
    """無法從 LLM 輸出中提取有效 JSON。"""
    pass


class DBError(PAMBaseError):
    """資料庫操作相關錯誤。"""
    pass


class SignalError(PAMBaseError):
    """信號計算或評分相關錯誤。"""
    pass


class ConfigError(PAMBaseError):
    """配置缺失或無效 (API key, DB path, etc.)。"""
    pass
