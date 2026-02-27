"""統一 logging 配置 — Political Alpha Monitor"""
import logging
import os
from datetime import datetime


def setup_logging(level=logging.INFO, log_dir="data/logs"):
    """
    設定全域 logging。
    - Console handler: INFO level, 簡潔格式
    - File handler: DEBUG level, JSON-like 格式, 寫到 data/logs/etl_{date}.log
    """
    os.makedirs(log_dir, exist_ok=True)

    log_file = os.path.join(log_dir, f"etl_{datetime.now().strftime('%Y%m%d')}.log")

    # Root logger
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    # 清除現有 handlers（避免重複）
    root.handlers.clear()

    # Console handler
    console = logging.StreamHandler()
    console.setLevel(level)
    console_fmt = logging.Formatter('[%(levelname)s] %(name)s: %(message)s')
    console.setFormatter(console_fmt)
    root.addHandler(console)

    # File handler
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_fmt = logging.Formatter(
        '{"time":"%(asctime)s","level":"%(levelname)s","module":"%(name)s","message":"%(message)s"}'
    )
    file_handler.setFormatter(file_fmt)
    root.addHandler(file_handler)

    logging.info(f"Logging initialized → {log_file}")
