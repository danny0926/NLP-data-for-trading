"""
Pipeline Orchestrator — 串接 Extract → Transform → Load
調度、監控、錯誤處理。
"""

import logging
import time
from datetime import datetime

from .base_fetcher import FetchResult
from .senate_fetcher import SenateFetcher
from .house_fetcher import HouseFetcher
from .capitoltrades_fetcher import CapitolTradesFetcher
from .llm_transformer import LLMTransformer, TransformError
from .loader import Loader

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("ETL.Pipeline")


class CongressETLPipeline:
    def __init__(self, db_path: str = "data/data.db", model_name: str = "gemini-2.5-flash"):
        self.db_path = db_path
        self.transformer = LLMTransformer(model_name=model_name)
        self.loader = Loader(db_path=db_path)

    def run(self, days: int = 7, filing_year: int = None,
            run_senate: bool = True, run_house: bool = True,
            max_house_reports: int = 20):
        """
        執行完整 ETL pipeline。

        Args:
            days: Senate 回溯天數
            filing_year: House 報告年份 (預設為今年)
            run_senate: 是否執行 Senate 路徑
            run_house: 是否執行 House 路徑
            max_house_reports: House PDF 最大下載數量
        """
        start_time = time.time()
        logger.info("=" * 60)
        logger.info("Congressional ETL Pipeline 啟動")
        logger.info(f"時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 60)

        total_stats = {"new": 0, "skipped": 0, "failed": 0, "sources_processed": 0}

        # ── Senate 路徑 ──
        if run_senate:
            senate_stats = self._run_senate(days)
            self._merge_stats(total_stats, senate_stats)

        # ── House 路徑 ──
        if run_house:
            house_stats = self._run_house(filing_year, max_house_reports)
            self._merge_stats(total_stats, house_stats)

        # ── 總結 ──
        elapsed = time.time() - start_time
        logger.info("=" * 60)
        logger.info("Pipeline 執行完成")
        logger.info(f"  來源處理: {total_stats['sources_processed']}")
        logger.info(f"  新增紀錄: {total_stats['new']}")
        logger.info(f"  跳過(重複): {total_stats['skipped']}")
        logger.info(f"  失敗: {total_stats['failed']}")
        logger.info(f"  耗時: {elapsed:.1f} 秒")
        logger.info("=" * 60)

        return total_stats

    def _run_senate(self, days: int) -> dict:
        """執行 Senate ETL 路徑。EFD Search 失敗時自動 fallback 至 Capitol Trades。"""
        logger.info("-" * 40)
        logger.info(f"[Senate] 開始抓取最近 {days} 天的報告")
        stats = {"new": 0, "skipped": 0, "failed": 0, "sources_processed": 0}

        try:
            fetcher = SenateFetcher()
            fetch_results = fetcher.fetch(days=days)
            logger.info(f"[Senate] Extract 完成: {len(fetch_results)} 份報告")
        except Exception as e:
            logger.error(f"[Senate] Extract 失敗: {e}")
            fetch_results = []

        # Fallback: EFD Search 無結果時，改用 Capitol Trades
        if not fetch_results:
            logger.info("[Senate] EFD Search 無結果，切換至 Capitol Trades fallback")
            try:
                ct_fetcher = CapitolTradesFetcher()
                pages = max(1, days // 3)  # 粗估：每頁約 12 筆，涵蓋數天
                fetch_results = ct_fetcher.fetch(chamber="senate", pages=pages)
                logger.info(f"[Senate/CapitolTrades] Extract 完成: {len(fetch_results)} 頁")
            except Exception as e:
                logger.error(f"[Senate/CapitolTrades] Extract 也失敗: {e}")
                return stats

        for i, fetch_result in enumerate(fetch_results):
            name = fetch_result.metadata.get("politician_name", "Unknown")
            logger.info(f"[Senate] Transform {i+1}/{len(fetch_results)}: {name}")

            try:
                extraction = self.transformer.transform(fetch_result)
                load_result = self.loader.load(extraction, source_url=fetch_result.source_url)
                stats["new"] += load_result["new"]
                stats["skipped"] += load_result["skipped"]
                stats["sources_processed"] += 1
                logger.info(
                    f"[Senate] {name}: {load_result['new']} 新, "
                    f"{load_result['skipped']} 重複 (confidence={extraction.confidence:.2f})"
                )
            except TransformError as e:
                stats["failed"] += 1
                logger.error(f"[Senate] Transform 失敗 ({name}): {e}")
            except Exception as e:
                stats["failed"] += 1
                logger.error(f"[Senate] 未預期錯誤 ({name}): {e}")

        logger.info(f"[Senate] 完成: new={stats['new']}, skipped={stats['skipped']}, failed={stats['failed']}")
        return stats

    def _run_house(self, filing_year: int = None, max_reports: int = 20) -> dict:
        """執行 House ETL 路徑。"""
        if filing_year is None:
            filing_year = datetime.now().year

        logger.info("-" * 40)
        logger.info(f"[House] 開始抓取 {filing_year} 年報告 (最多 {max_reports} 份)")
        stats = {"new": 0, "skipped": 0, "failed": 0, "sources_processed": 0}

        try:
            fetcher = HouseFetcher()
            fetch_results = fetcher.fetch(filing_year=filing_year, max_reports=max_reports)
            logger.info(f"[House] Extract 完成: {len(fetch_results)} 份 PDF")
        except Exception as e:
            logger.error(f"[House] Extract 失敗: {e}")
            return stats

        for i, fetch_result in enumerate(fetch_results):
            name = fetch_result.metadata.get("politician_name", "Unknown")
            logger.info(f"[House] Transform {i+1}/{len(fetch_results)}: {name}")

            try:
                extraction = self.transformer.transform(fetch_result)
                load_result = self.loader.load(extraction, source_url=fetch_result.source_url)
                stats["new"] += load_result["new"]
                stats["skipped"] += load_result["skipped"]
                stats["sources_processed"] += 1
                logger.info(
                    f"[House] {name}: {load_result['new']} 新, "
                    f"{load_result['skipped']} 重複 (confidence={extraction.confidence:.2f})"
                )
            except TransformError as e:
                stats["failed"] += 1
                logger.error(f"[House] Transform 失敗 ({name}): {e}")
            except Exception as e:
                stats["failed"] += 1
                logger.error(f"[House] 未預期錯誤 ({name}): {e}")

        logger.info(f"[House] 完成: new={stats['new']}, skipped={stats['skipped']}, failed={stats['failed']}")
        return stats

    @staticmethod
    def _merge_stats(total: dict, source: dict):
        """合併統計數據。"""
        for key in ("new", "skipped", "failed", "sources_processed"):
            total[key] += source.get(key, 0)
