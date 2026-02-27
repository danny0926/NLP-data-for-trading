#!/usr/bin/env python3
"""
Telegram Bot 入口 — Political Alpha Monitor
啟動 Telegram 機器人 polling loop

使用方式:
    python run_telegram_bot.py
    python run_telegram_bot.py --db data/data.db

需要 .env 設定:
    TELEGRAM_BOT_TOKEN=your_bot_token
    TELEGRAM_CHAT_ID=your_chat_id (optional, for legacy notifications)
"""

import argparse
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from src.config import DB_PATH, TELEGRAM_BOT_TOKEN


def main():
    parser = argparse.ArgumentParser(
        description="Political Alpha Monitor — Telegram Bot"
    )
    parser.add_argument("--db", type=str, default=DB_PATH,
                        help="Database path")
    parser.add_argument("--token", type=str, default='',
                        help="Bot token (default: from .env)")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    token = args.token or TELEGRAM_BOT_TOKEN
    if not token:
        print("ERROR: TELEGRAM_BOT_TOKEN not set.")
        print("Please add TELEGRAM_BOT_TOKEN to your .env file.")
        print("Create a bot via @BotFather on Telegram to get a token.")
        sys.exit(1)

    from src.telegram_bot import TelegramAlertBot

    bot = TelegramAlertBot(token=token, db_path=args.db)
    print("Starting Political Alpha Monitor Telegram Bot...")
    print("Press Ctrl+C to stop.")
    bot.run()


if __name__ == "__main__":
    main()
