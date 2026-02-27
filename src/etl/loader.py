"""
Load 層 — 驗證、去重、寫入 SQLite
純規則驅動，不涉及 LLM。
"""

import hashlib
import logging
import sqlite3
import uuid
from datetime import date, datetime

from .schemas import ExtractionResult
from src.config import DB_PATH, CONFIDENCE_THRESHOLD

logger = logging.getLogger("ETL.Loader")


class Loader:
    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = DB_PATH
        self.db_path = db_path

    def load(self, result: ExtractionResult, source_url: str = "") -> dict:
        """
        將 ExtractionResult 寫入 SQLite。
        回傳統計資訊：{"new": int, "skipped": int, "status": str}
        """
        log_id = str(uuid.uuid4())

        # 信心門檻檢查
        if result.confidence < CONFIDENCE_THRESHOLD:
            logger.warning(
                f"信心分數 {result.confidence:.2f} 低於門檻 {CONFIDENCE_THRESHOLD}，"
                f"進入人工審核佇列 ({len(result.trades)} 筆)"
            )
            self._write_extraction_log(
                log_id=log_id,
                source_type=result.source_format,
                source_url=source_url,
                confidence=result.confidence,
                raw_count=result.raw_record_count,
                extracted_count=len(result.trades),
                status="manual_review",
            )
            return {"new": 0, "skipped": len(result.trades), "status": "manual_review"}

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        new_count = 0
        skipped_count = 0
        has_anomaly = False

        for trade in result.trades:
            # 業務邏輯檢查（異常標記但不阻擋）
            anomalies = self._check_anomalies(trade)
            if anomalies:
                has_anomaly = True
                logger.warning(f"業務異常 ({trade.politician_name} {trade.ticker}): {anomalies}")

            # 計算去重 hash
            data_hash = self._generate_hash(
                trade.politician_name,
                str(trade.transaction_date),
                trade.ticker or "",
                trade.amount_range,
                trade.transaction_type,
            )

            # 寫入
            trade_id = str(uuid.uuid4())
            try:
                cursor.execute('''
                    INSERT INTO congress_trades (
                        id, chamber, politician_name, transaction_date, filing_date,
                        ticker, asset_name, asset_type, transaction_type, amount_range,
                        owner, comment, source_url, source_format, extraction_confidence,
                        data_hash
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    trade_id,
                    trade.chamber,
                    trade.politician_name,
                    str(trade.transaction_date),
                    str(trade.filing_date),
                    trade.ticker,
                    trade.asset_name,
                    trade.asset_type,
                    trade.transaction_type,
                    trade.amount_range,
                    trade.owner,
                    trade.comment,
                    trade.source_url,
                    result.source_format,
                    result.confidence,
                    data_hash,
                ))
                new_count += 1
            except sqlite3.IntegrityError:
                # data_hash 重複，已存在
                skipped_count += 1

        conn.commit()
        conn.close()

        status = "partial" if has_anomaly else "success"
        self._write_extraction_log(
            log_id=log_id,
            source_type=result.source_format,
            source_url=source_url,
            confidence=result.confidence,
            raw_count=result.raw_record_count,
            extracted_count=new_count + skipped_count,
            status=status,
        )

        logger.info(f"Load 完成: 新增 {new_count}, 跳過(重複) {skipped_count}, 狀態={status}")
        return {"new": new_count, "skipped": skipped_count, "status": status}

    def _check_anomalies(self, trade) -> list[str]:
        """業務邏輯檢查，回傳異常描述列表。"""
        anomalies = []
        today = date.today()

        if trade.transaction_date > today:
            anomalies.append(f"交易日期在未來: {trade.transaction_date}")

        if trade.filing_date > today:
            anomalies.append(f"申報日期在未來: {trade.filing_date}")

        return anomalies

    def _write_extraction_log(self, log_id: str, source_type: str, source_url: str,
                              confidence: float, raw_count: int, extracted_count: int,
                              status: str, error_message: str = None):
        """寫入 extraction_log 表。"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO extraction_log (
                id, source_type, source_url, confidence,
                raw_record_count, extracted_count, status, error_message
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (log_id, source_type, source_url, confidence,
              raw_count, extracted_count, status, error_message))
        conn.commit()
        conn.close()

    @staticmethod
    def _generate_hash(*fields) -> str:
        """SHA256 去重 hash"""
        data_str = "|".join(str(f) for f in fields)
        return hashlib.sha256(data_str.encode()).hexdigest()
