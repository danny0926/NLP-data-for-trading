"""
Political Alpha Monitor — 全自動 Pipeline 一鍵執行
串接: ETL → AI Discovery → SQS 評分 → 收斂偵測 → 議員排名 → 信號生成 → 報告

使用方式:
    python run_full_pipeline.py                      # 完整 pipeline
    python run_full_pipeline.py --skip-etl           # 跳過 ETL（用已有資料）
    python run_full_pipeline.py --skip-discovery     # 跳過 AI Discovery
    python run_full_pipeline.py --analysis-only      # 只跑分析（SQS/收斂/排名/信號）
    python run_full_pipeline.py --days 14            # ETL 回溯 14 天
    python run_full_pipeline.py --report-only        # 只生成報告
"""

import argparse
import os
import sys
import time
import traceback
from datetime import datetime
from typing import Optional, List, Dict, Any

from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _timestamp() -> str:
    """返回當前時間戳。"""
    return datetime.now().strftime("%H:%M:%S")


def _safe_print(text: str) -> None:
    """安全列印，避免 Windows cp950 Unicode 編碼錯誤。"""
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode('ascii', 'replace').decode('ascii'))


def _divider(title: str) -> None:
    """印出分隔線。"""
    _safe_print(f"\n{'='*60}")
    _safe_print(f"  [{_timestamp()}] {title}")
    _safe_print(f"{'='*60}\n")


class PipelineOrchestrator:
    """統一 Pipeline 調度器，依序執行所有子系統。"""

    def __init__(self, days: int = 7, max_house: int = 20,
                 model: str = "gemini-2.5-flash",
                 senate_only: bool = False, house_only: bool = False):
        self.days = days
        self.max_house = max_house
        self.model = model
        self.senate_only = senate_only
        self.house_only = house_only
        self.results = {}  # type: Dict[str, Any]
        self.errors = []  # type: List[str]
        self.start_time = time.time()

    def run_etl(self) -> bool:
        """階段 1: ETL Pipeline — 抓取國會交易資料。"""
        _divider("階段 1/6: ETL Pipeline — 資料抓取")
        try:
            from src.config import DB_PATH, GEMINI_MODEL
            from src.database import init_db
            from src.etl.pipeline import CongressETLPipeline

            init_db()
            pipeline = CongressETLPipeline(
                db_path=DB_PATH,
                model_name=self.model
            )

            run_senate = not self.house_only
            run_house = not self.senate_only

            result = pipeline.run(
                days=self.days,
                run_senate=run_senate,
                run_house=run_house,
                max_house_reports=self.max_house
            )

            self.results['etl'] = {
                'senate_count': getattr(result, 'senate_count', 0) if result else 0,
                'house_count': getattr(result, 'house_count', 0) if result else 0,
                'status': 'success'
            }
            _safe_print("\n  [OK] ETL 完成")
            return True

        except Exception as e:
            self.errors.append(f"ETL: {str(e)}")
            self.results['etl'] = {'status': 'error', 'error': str(e)}
            _safe_print(f"\n  [FAIL] ETL: {e}")
            traceback.print_exc()
            return False

    def run_discovery(self) -> bool:
        """階段 2: AI Discovery — LLM 情報搜索。"""
        _divider("階段 2/6: AI Discovery — 情報搜索")
        try:
            from src.discovery_engine_v4 import DiscoveryEngineV4
            from src.targets import get_targets_by_tier

            engine = DiscoveryEngineV4(model_name=self.model)
            total_signals = 0
            total_errors = 0

            for tier in [1, 2]:
                targets = get_targets_by_tier(tier)
                print(f"  Tier {tier}: {len(targets)} 位議員")

                for target in targets:
                    try:
                        result = engine.run_discovery(
                            target_name=target['name'],
                            target_type='CONGRESS',
                            metadata={
                                'party': target['party'],
                                'state': target['state'],
                                'chamber': target['chamber']
                            }
                        )
                        if result:
                            signals = result.get('signals', []) if isinstance(result, dict) else []
                            total_signals += len(signals)
                        time.sleep(3)  # rate limit
                    except Exception as e:
                        total_errors += 1
                        _safe_print(f"    [FAIL] {target['name']}: {e}")

            self.results['discovery'] = {
                'signals': total_signals,
                'errors': total_errors,
                'status': 'success'
            }
            _safe_print(f"\n  [OK] Discovery: {total_signals} signals, {total_errors} errors")
            return True

        except Exception as e:
            self.errors.append(f"Discovery: {str(e)}")
            self.results['discovery'] = {'status': 'error', 'error': str(e)}
            _safe_print(f"\n  [FAIL] Discovery: {e}")
            return False

    def run_signal_scoring(self) -> bool:
        """階段 3: Signal Quality Score — 品質評分。"""
        _divider("Stage 3/6: Signal Quality Score")
        try:
            from src.signal_scorer import SignalScorer

            scorer = SignalScorer()
            scores = scorer.score_all_signals()
            scorer.save_scores(scores)

            self.results['sqs'] = {
                'scored': len(scores),
                'avg_score': sum(s.get('total_score', 0) for s in scores) / max(len(scores), 1),
                'status': 'success'
            }
            _safe_print(f"\n  [OK] SQS: {len(scores)} scored")
            return True

        except Exception as e:
            self.errors.append(f"SQS: {str(e)}")
            self.results['sqs'] = {'status': 'error', 'error': str(e)}
            _safe_print(f"\n  [FAIL] SQS: {e}")
            return False

    def run_convergence_detection(self) -> bool:
        """階段 4: Convergence Detection — 收斂信號偵測。"""
        _divider("Stage 4/6: Convergence Detection")
        try:
            from src.convergence_detector import ConvergenceDetector

            detector = ConvergenceDetector()
            events = detector.detect()
            detector.save_signals(events)

            self.results['convergence'] = {
                'events': len(events),
                'status': 'success'
            }
            _safe_print(f"\n  [OK] Convergence: {len(events)} events")
            return True

        except Exception as e:
            self.errors.append(f"Convergence: {str(e)}")
            self.results['convergence'] = {'status': 'error', 'error': str(e)}
            _safe_print(f"\n  [FAIL] Convergence: {e}")
            return False

    def run_politician_ranking(self) -> bool:
        """階段 5: Politician Ranking — 議員排名。"""
        _divider("Stage 5/6: Politician Ranking")
        try:
            from src.politician_ranking import PoliticianRanker
            from src.politician_ranking import print_ranking_table

            ranker = PoliticianRanker()
            rankings = ranker.rank()
            print_ranking_table(rankings[:10])

            self.results['ranking'] = {
                'ranked': len(rankings),
                'status': 'success'
            }
            _safe_print(f"\n  [OK] Ranking: {len(rankings)} politicians")
            return True

        except Exception as e:
            self.errors.append(f"Ranking: {str(e)}")
            self.results['ranking'] = {'status': 'error', 'error': str(e)}
            _safe_print(f"\n  [FAIL] Ranking: {e}")
            return False

    def run_report_generation(self) -> bool:
        """階段 6: Report Generation — 報告生成。"""
        _divider("Stage 6/6: Report Generation")
        try:
            # daily_report module
            try:
                from src.daily_report import generate_report
                from src.config import DB_PATH
                today = datetime.now().strftime("%Y-%m-%d")
                report_path = generate_report(DB_PATH, today)
                _safe_print(f"  [OK] Daily report: {report_path}")
            except ImportError:
                _safe_print("  [SKIP] src/daily_report.py not found")
            except Exception as e:
                _safe_print(f"  [WARN] Daily report error: {e}")

            # alpha signal generator module
            try:
                from src.alpha_signal_generator import AlphaSignalGenerator
                gen = AlphaSignalGenerator()
                signals = gen.generate_all()
                _safe_print(f"  [OK] Alpha signals: {len(signals)}")
            except ImportError:
                _safe_print("  [SKIP] src/alpha_signal_generator.py not found")
            except Exception as e:
                _safe_print(f"  [WARN] Alpha signal error: {e}")

            # portfolio optimizer module
            try:
                from src.portfolio_optimizer import run_portfolio_optimization
                run_portfolio_optimization()
                _safe_print(f"  [OK] Portfolio optimized")
            except ImportError:
                _safe_print("  [SKIP] src/portfolio_optimizer.py not found")
            except Exception as e:
                _safe_print(f"  [WARN] Portfolio error: {e}")

            self.results['report'] = {'status': 'success'}
            return True

        except Exception as e:
            self.errors.append(f"Report: {str(e)}")
            self.results['report'] = {'status': 'error', 'error': str(e)}
            _safe_print(f"\n  [FAIL] Report: {e}")
            return False

    def print_summary(self) -> None:
        """印出 pipeline 執行摘要。"""
        elapsed = time.time() - self.start_time
        minutes = int(elapsed // 60)
        seconds = int(elapsed % 60)

        _safe_print(f"\n{'='*60}")
        _safe_print(f"  Pipeline done -- {minutes}m {seconds}s")
        _safe_print(f"{'='*60}")

        for stage, result in self.results.items():
            status = result.get('status', 'unknown')
            icon = '[OK]' if status == 'success' else '[FAIL]'
            detail = ''
            if stage == 'etl':
                detail = f"Senate: {result.get('senate_count', '?')}, House: {result.get('house_count', '?')}"
            elif stage == 'discovery':
                detail = f"{result.get('signals', 0)} signals"
            elif stage == 'sqs':
                detail = f"{result.get('scored', 0)} scored"
            elif stage == 'convergence':
                detail = f"{result.get('events', 0)} events"
            elif stage == 'ranking':
                detail = f"{result.get('ranked', 0)} politicians"

            error_info = f" -- {result.get('error', '')}" if status == 'error' else ''
            _safe_print(f"  {icon} {stage}: {detail}{error_info}")

        if self.errors:
            _safe_print(f"\n  [WARN] {len(self.errors)} stages had errors")
        else:
            _safe_print(f"\n  [OK] All stages completed successfully")

        _safe_print(f"{'='*60}\n")

    def run(self, skip_etl: bool = False, skip_discovery: bool = False,
            analysis_only: bool = False, report_only: bool = False) -> None:
        """執行完整 pipeline。"""
        print(f"\n{'#'*60}")
        print(f"  Political Alpha Monitor — Full Pipeline")
        print(f"  啟動時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  模式: {'分析模式' if analysis_only else '報告模式' if report_only else '完整模式'}")
        print(f"{'#'*60}")

        if report_only:
            self.run_report_generation()
            self.print_summary()
            return

        if not analysis_only and not skip_etl:
            self.run_etl()

        if not analysis_only and not skip_discovery:
            self.run_discovery()

        # 分析階段（總是執行）
        self.run_signal_scoring()
        self.run_convergence_detection()
        self.run_politician_ranking()
        self.run_report_generation()

        # 告警檢查
        try:
            from src.smart_alerts import SmartAlertSystem
            alert_system = SmartAlertSystem(days=self.days)
            alerts = alert_system.run_all_checks()
            alert_system.print_summary()
            if alerts:
                alert_system.send_alerts()
        except Exception as e:
            _safe_print(f"  [WARN] Smart alerts: {e}")

        self.print_summary()


def main():
    parser = argparse.ArgumentParser(
        description="Political Alpha Monitor — Full Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
範例:
  python run_full_pipeline.py                  # 完整 pipeline
  python run_full_pipeline.py --skip-etl       # 跳過 ETL
  python run_full_pipeline.py --analysis-only  # 只跑分析
  python run_full_pipeline.py --days 14        # ETL 回溯 14 天
  python run_full_pipeline.py --report-only    # 只生成報告
        """
    )
    parser.add_argument("--days", type=int, default=7, help="ETL 回溯天數 (預設 7)")
    parser.add_argument("--max-house", type=int, default=20, help="House PDF 最大數 (預設 20)")
    parser.add_argument("--model", type=str, default="gemini-2.5-flash", help="Gemini model")
    parser.add_argument("--senate-only", action="store_true", help="只跑 Senate ETL")
    parser.add_argument("--house-only", action="store_true", help="只跑 House ETL")
    parser.add_argument("--skip-etl", action="store_true", help="跳過 ETL 階段")
    parser.add_argument("--skip-discovery", action="store_true", help="跳過 AI Discovery 階段")
    parser.add_argument("--analysis-only", action="store_true", help="只跑分析階段")
    parser.add_argument("--report-only", action="store_true", help="只生成報告")
    args = parser.parse_args()

    orchestrator = PipelineOrchestrator(
        days=args.days,
        max_house=args.max_house,
        model=args.model,
        senate_only=args.senate_only,
        house_only=args.house_only
    )

    orchestrator.run(
        skip_etl=args.skip_etl,
        skip_discovery=args.skip_discovery,
        analysis_only=args.analysis_only,
        report_only=args.report_only
    )


if __name__ == "__main__":
    main()
