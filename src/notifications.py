"""Telegram 告警模組 — Political Alpha Monitor"""
import os
import logging
import requests
from typing import Optional

logger = logging.getLogger(__name__)


def send_telegram(message: str, parse_mode: str = "HTML") -> bool:
    """
    發送 Telegram 通知。
    需要 .env 中設定 TELEGRAM_BOT_TOKEN 和 TELEGRAM_CHAT_ID。
    """
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        logger.warning("Telegram 未設定 (TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID)，跳過通知")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": parse_mode
    }

    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        logger.info("Telegram 通知已發送")
        return True
    except Exception as e:
        logger.error(f"Telegram 通知失敗: {e}")
        return False


def format_etl_summary(
    senate_count: int = 0,
    house_count: int = 0,
    errors: Optional[list] = None
) -> str:
    """格式化 ETL 執行摘要為 Telegram 訊息。"""
    status = "✅ 成功" if not errors else "⚠️ 有錯誤"
    msg = (
        f"<b>📊 ETL Pipeline {status}</b>\n\n"
        f"Senate 交易: {senate_count} 筆\n"
        f"House 交易: {house_count} 筆\n"
    )
    if errors:
        msg += f"\n<b>錯誤 ({len(errors)}):</b>\n"
        for err in errors[:5]:
            msg += f"• {err}\n"
    return msg
