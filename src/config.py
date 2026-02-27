"""統一配置管理 — Political Alpha Monitor

所有可配置的參數集中在此。優先讀取環境變數，否則使用預設值。
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── 路徑 ──
PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = os.getenv("DATABASE_URL", str(PROJECT_ROOT / "data" / "data.db"))
LOG_DIR = os.getenv("LOG_DIR", str(PROJECT_ROOT / "data" / "logs"))

# ── LLM ──
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")

# ── ETL ──
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.7"))
MAX_RETRY = int(os.getenv("MAX_RETRY", "3"))

# ── Telegram ──
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
