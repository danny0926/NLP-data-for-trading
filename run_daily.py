"""
Political Alpha Monitor — 每日自動排程執行器
統一執行所有子系統: Smoke Test → ETL → AI Discovery → 分析 → Dashboard → 驗證

使用方式:
    python run_daily.py                          # 完整每日流程
    python run_daily.py --skip-etl               # 跳過 ETL（用既有資料）
    python run_daily.py --skip-discovery         # 跳過 AI Discovery
    python run_daily.py --skip-social            # 跳過社群媒體抓取分析
    python run_daily.py --analysis-only          # 只跑分析 + Dashboard
    python run_daily.py --days 7                 # ETL 回溯天數（預設 3）
"""

import argparse
import glob
import logging
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

# 確保從專案根目錄載入模組
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_DIR)
os.chdir(PROJECT_DIR)

from dotenv import load_dotenv
load_dotenv()


# ============================================================
# 日誌設定
# ============================================================

def setup_daily_logging(log_dir: str = "logs") -> logging.Logger:
    """設定每日日誌：同時輸出到檔案和 console。"""
    os.makedirs(log_dir, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    log_path = os.path.join(log_dir, f"daily_{today}.log")

    logger = logging.getLogger("daily_runner")
    logger.setLevel(logging.INFO)

    # 避免重複 handler
    if logger.handlers:
        logger.handlers.clear()

    # 檔案 handler
    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setLevel(logging.INFO)
    fh.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    ))
    logger.addHandler(fh)

    # Console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter(
        "[%(asctime)s] %(message)s",
        datefmt="%H:%M:%S"
    ))
    logger.addHandler(ch)

    return logger


def rotate_logs(log_dir: str = "logs", keep_days: int = 30) -> int:
    """清理超過 keep_days 天的日誌檔。回傳刪除的檔案數。"""
    cutoff = datetime.now() - timedelta(days=keep_days)
    removed = 0
    for f in glob.glob(os.path.join(log_dir, "daily_*.log")):
        try:
            # 從檔名解析日期: daily_YYYY-MM-DD.log
            basename = os.path.basename(f)
            date_str = basename.replace("daily_", "").replace(".log", "")
            file_date = datetime.strptime(date_str, "%Y-%m-%d")
            if file_date < cutoff:
                os.remove(f)
                removed += 1
        except (ValueError, OSError):
            pass
    return removed


# ============================================================
# 步驟執行器
# ============================================================

class StepResult:
    """單一步驟的執行結果。"""
    def __init__(self, name: str):
        self.name = name
        self.success = False
        self.elapsed = 0.0
        self.detail = ""
        self.error = ""


class DailyRunner:
    """每日 Pipeline 統一調度器。"""

    def __init__(self, days: int = 3, skip_etl: bool = False,
                 skip_discovery: bool = False, skip_social: bool = False,
                 analysis_only: bool = False):
        self.days = days
        self.skip_etl = skip_etl
        self.skip_discovery = skip_discovery
        self.skip_social = skip_social
        self.analysis_only = analysis_only
        self.results = []  # type: List[StepResult]
        self.logger = setup_daily_logging()
        self.start_time = time.time()

    def _run_step(self, name: str, fn) -> StepResult:
        """安全執行一個步驟，捕捉所有例外。"""
        result = StepResult(name)
        self.logger.info(f"{'='*50}")
        self.logger.info(f"開始: {name}")
        self.logger.info(f"{'='*50}")

        t0 = time.time()
        try:
            detail = fn()
            result.success = True
            result.detail = str(detail) if detail else "OK"
            self.logger.info(f"[PASS] {name}: {result.detail}")
        except Exception as e:
            result.success = False
            result.error = str(e)
            self.logger.error(f"[FAIL] {name}: {e}", exc_info=True)

        result.elapsed = time.time() - t0
        self.logger.info(f"耗時: {result.elapsed:.1f}s")
        self.results.append(result)
        return result

    # ── Step 1: Pre-flight Smoke Test ──

    def step_preflight(self):
        """Pre-flight 健康檢查。"""
        from smoke_test import main as smoke_main
        exit_code = smoke_main()
        if exit_code != 0:
            self.logger.warning("Pre-flight 有部分檢查未通過，繼續執行...")
        return f"exit_code={exit_code}"

    # ── Step 2: ETL Pipeline ──

    def step_etl(self):
        """執行 ETL Pipeline 抓取國會交易資料。"""
        from src.config import DB_PATH, GEMINI_MODEL
        from src.database import init_db
        from src.etl.pipeline import CongressETLPipeline

        init_db()
        pipeline = CongressETLPipeline(db_path=DB_PATH, model_name=GEMINI_MODEL)
        stats = pipeline.run(
            days=self.days,
            run_senate=True,
            run_house=True,
            max_house_reports=20
        )
        new = stats.get("new", 0)
        skipped = stats.get("skipped", 0)
        failed = stats.get("failed", 0)
        return f"new={new}, skipped={skipped}, failed={failed}"

    # ── Step 3: AI Discovery ──

    def step_discovery(self):
        """執行 AI Discovery 情報搜索。"""
        from src.discovery_engine_v4 import DiscoveryEngineV4
        from src.targets import get_targets_by_tier

        engine = DiscoveryEngineV4(model_name="gemini-2.5-flash")
        total_signals = 0
        total_errors = 0

        for tier in [1, 2]:
            targets = get_targets_by_tier(tier)
            for target in targets:
                try:
                    result = engine.monitor_target("CONGRESS", target["name"])
                    if result:
                        total_signals += 1
                    time.sleep(3)
                except Exception as e:
                    total_errors += 1
                    self.logger.warning(f"Discovery {target['name']}: {e}")

        return f"signals={total_signals}, errors={total_errors}"

    # ── Step 2.5: Social Media Intelligence ──

    def step_social_intelligence(self):
        """抓取社群媒體 + NLP 分析 + 交叉比對國會交易。"""
        from src.database import init_db
        from src.etl.social_fetcher import SocialFetcher
        from src.social_analyzer import SocialAnalyzer

        init_db()

        # 抓取（過去 24 小時）
        fetcher = SocialFetcher()
        posts = fetcher.fetch_all_targets(hours=24)
        fetch_count = len(posts)

        # 分析 + 交叉比對 + alpha 信號
        analyzer = SocialAnalyzer()
        stats = analyzer.analyze_batch(hours=24)

        return (
            f"fetched={fetch_count}, signals={stats['signals']}, "
            f"alpha={stats.get('alpha_signals', 0)}, "
            f"consistent={stats['consistent']}, contradictory={stats['contradictory']}"
        )

    # ── Step 4: Analysis Pipeline ──

    def step_analysis(self):
        """執行分析 Pipeline: SQS + 收斂 + 排名 + Alpha + 投資組合。"""
        sub_results = []

        # SQS 評分
        try:
            from src.signal_scorer import SignalScorer
            scorer = SignalScorer()
            scores = scorer.score_all_signals()
            scorer.save_scores(scores)
            sub_results.append(f"SQS={len(scores)}")
        except Exception as e:
            sub_results.append(f"SQS:FAIL({e})")
            self.logger.warning(f"SQS 評分失敗: {e}")

        # 收斂偵測
        try:
            from src.convergence_detector import ConvergenceDetector
            detector = ConvergenceDetector()
            events = detector.detect()
            detector.save_signals(events)
            sub_results.append(f"convergence={len(events)}")
        except Exception as e:
            sub_results.append(f"convergence:FAIL({e})")
            self.logger.warning(f"收斂偵測失敗: {e}")

        # 議員排名
        try:
            from src.politician_ranking import PoliticianRanker
            ranker = PoliticianRanker()
            rankings = ranker.rank()
            sub_results.append(f"ranking={len(rankings)}")
        except Exception as e:
            sub_results.append(f"ranking:FAIL({e})")
            self.logger.warning(f"議員排名失敗: {e}")

        # Alpha 信號
        try:
            from src.alpha_signal_generator import AlphaSignalGenerator
            gen = AlphaSignalGenerator()
            signals = gen.generate_all()
            sub_results.append(f"alpha={len(signals)}")
        except Exception as e:
            sub_results.append(f"alpha:FAIL({e})")
            self.logger.warning(f"Alpha 信號失敗: {e}")

        # 投資組合優化
        try:
            from src.portfolio_optimizer import run_portfolio_optimization
            run_portfolio_optimization()
            sub_results.append("portfolio=OK")
        except Exception as e:
            sub_results.append(f"portfolio:FAIL({e})")
            self.logger.warning(f"投資組合優化失敗: {e}")

        # Smart Alerts
        try:
            from src.smart_alerts import SmartAlertSystem
            alert_system = SmartAlertSystem(days=self.days)
            alerts = alert_system.run_all_checks()
            if alerts:
                alert_system.send_alerts()
            sub_results.append(f"alerts={len(alerts)}")
        except Exception as e:
            sub_results.append(f"alerts:FAIL({e})")
            self.logger.warning(f"Smart Alerts 失敗: {e}")

        return ", ".join(sub_results)

    # ── Step 5: Dashboard ──

    def step_dashboard(self):
        """重新生成 HTML Dashboard。"""
        # 使用 subprocess 避免 import 衝突
        result = subprocess.run(
            [sys.executable, "generate_dashboard.py"],
            capture_output=True, text=True, timeout=120,
            cwd=PROJECT_DIR
        )
        if result.returncode != 0:
            raise RuntimeError(f"Dashboard 生成失敗: {result.stderr[:500]}")
        return "dashboard.html 已更新"

    # ── Step 6: Post-flight Smoke Test ──

    def step_postflight(self):
        """Post-flight 健康檢查，驗證 pipeline 結果。"""
        from smoke_test import main as smoke_main
        exit_code = smoke_main()
        if exit_code != 0:
            raise RuntimeError(f"Post-flight 檢查失敗 (exit_code={exit_code})")
        return f"exit_code={exit_code}"

    # ── 主流程 ──

    def run(self) -> int:
        """執行完整每日流程。回傳 exit code (0=全部通過, 1=有失敗)。"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        mode = "分析模式" if self.analysis_only else "完整模式"
        if self.skip_etl:
            mode += " (跳過 ETL)"
        if self.skip_discovery:
            mode += " (跳過 Discovery)"
        if self.skip_social:
            mode += " (跳過 Social)"

        self.logger.info(f"{'#'*60}")
        self.logger.info(f"  Political Alpha Monitor — 每日自動執行")
        self.logger.info(f"  啟動時間: {now}")
        self.logger.info(f"  模式: {mode}")
        self.logger.info(f"  ETL 回溯天數: {self.days}")
        self.logger.info(f"{'#'*60}")

        # 日誌輪轉
        removed = rotate_logs()
        if removed > 0:
            self.logger.info(f"已清理 {removed} 個過期日誌檔")

        # Step 1: Pre-flight
        self._run_step("Pre-flight Smoke Test", self.step_preflight)

        # Step 2: ETL
        if not self.analysis_only and not self.skip_etl:
            self._run_step("ETL Pipeline", self.step_etl)
        else:
            self.logger.info("[SKIP] ETL Pipeline")

        # Step 3: AI Discovery
        if not self.analysis_only and not self.skip_discovery:
            self._run_step("AI Discovery", self.step_discovery)
        else:
            self.logger.info("[SKIP] AI Discovery")

        # Step 3.5: Social Media Intelligence
        if not self.analysis_only and not self.skip_social:
            self._run_step("Social Media Intelligence", self.step_social_intelligence)
        else:
            self.logger.info("[SKIP] Social Media Intelligence")

        # Step 4: Analysis
        self._run_step("Analysis Pipeline", self.step_analysis)

        # Step 5: Dashboard
        self._run_step("Dashboard Generation", self.step_dashboard)

        # Step 6: Post-flight
        self._run_step("Post-flight Smoke Test", self.step_postflight)

        # ── 摘要 ──
        self._print_summary()

        # exit code
        has_failure = any(not r.success for r in self.results)
        return 1 if has_failure else 0

    def _print_summary(self):
        """印出執行摘要。"""
        total_elapsed = time.time() - self.start_time
        minutes = int(total_elapsed // 60)
        seconds = int(total_elapsed % 60)

        passed = sum(1 for r in self.results if r.success)
        failed = sum(1 for r in self.results if not r.success)
        total = len(self.results)

        self.logger.info("")
        self.logger.info(f"{'='*60}")
        self.logger.info(f"  每日執行摘要 — {datetime.now().strftime('%Y-%m-%d')}")
        self.logger.info(f"  總耗時: {minutes}m {seconds}s")
        self.logger.info(f"  結果: {passed}/{total} 通過, {failed} 失敗")
        self.logger.info(f"{'='*60}")

        for r in self.results:
            icon = "[PASS]" if r.success else "[FAIL]"
            elapsed_str = f"{r.elapsed:.1f}s"
            detail = r.detail if r.success else r.error
            # 截斷過長的 detail
            if len(detail) > 100:
                detail = detail[:97] + "..."
            self.logger.info(f"  {icon} {r.name:30s} ({elapsed_str:>8s}) {detail}")

        if failed > 0:
            self.logger.info(f"\n  [WARNING] 有 {failed} 個步驟失敗，請檢查日誌")
        else:
            self.logger.info(f"\n  [OK] 所有步驟執行成功")

        self.logger.info(f"{'='*60}")


# ============================================================
# CLI 入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Political Alpha Monitor — 每日自動排程執行器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
範例:
  python run_daily.py                          # 完整每日流程
  python run_daily.py --skip-etl               # 跳過 ETL
  python run_daily.py --skip-discovery         # 跳過 AI Discovery
  python run_daily.py --skip-social            # 跳過社群媒體抓取分析
  python run_daily.py --analysis-only          # 只跑分析 + Dashboard
  python run_daily.py --days 7                 # ETL 回溯 7 天
        """
    )
    parser.add_argument("--days", type=int, default=3,
                        help="ETL 回溯天數 (預設 3，捕捉延遲申報)")
    parser.add_argument("--skip-etl", action="store_true",
                        help="跳過 ETL 階段")
    parser.add_argument("--skip-discovery", action="store_true",
                        help="跳過 AI Discovery 階段")
    parser.add_argument("--skip-social", action="store_true",
                        help="跳過社群媒體抓取分析階段")
    parser.add_argument("--analysis-only", action="store_true",
                        help="只跑分析 + Dashboard（跳過 ETL/Discovery/Social）")
    args = parser.parse_args()

    runner = DailyRunner(
        days=args.days,
        skip_etl=args.skip_etl,
        skip_discovery=args.skip_discovery,
        skip_social=args.skip_social,
        analysis_only=args.analysis_only
    )

    exit_code = runner.run()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
