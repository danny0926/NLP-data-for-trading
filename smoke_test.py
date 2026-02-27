"""
Political Alpha Monitor — Smoke Test
系統健康檢查：驗證所有模組可正常載入和執行

使用方式:
    python smoke_test.py
"""

import os
import sys
import sqlite3
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PASS = "[PASS]"
FAIL = "[FAIL]"
WARN = "[WARN]"


def check(name, fn):
    """執行一項檢查。"""
    try:
        result = fn()
        if result:
            print(f"  {PASS} {name}: {result}")
            return True
        else:
            print(f"  {FAIL} {name}: returned falsy")
            return False
    except Exception as e:
        print(f"  {FAIL} {name}: {e}")
        return False


def main():
    print(f"\n{'='*60}")
    print(f"  Political Alpha Monitor — Smoke Test")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

    passed = 0
    failed = 0

    # ── 環境檢查 ──
    print("  --- Environment ---")

    def check_env():
        from dotenv import load_dotenv
        load_dotenv()
        key = os.getenv("GOOGLE_API_KEY")
        return f"GOOGLE_API_KEY={'set' if key else 'MISSING'}"
    if check("Environment", check_env): passed += 1
    else: failed += 1

    def check_db():
        from src.config import DB_PATH
        if not os.path.exists(DB_PATH):
            return None
        conn = sqlite3.connect(DB_PATH)
        tables = conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'").fetchone()[0]
        conn.close()
        return f"{DB_PATH} ({tables} tables)"
    if check("Database", check_db): passed += 1
    else: failed += 1

    # ── 模組載入 ──
    print("\n  --- Module Imports ---")

    modules = [
        ("src.config", "Config"),
        ("src.database", "Database"),
        ("src.logging_config", "Logging"),
        ("src.notifications", "Notifications"),
        ("src.targets", "Targets"),
        ("src.signal_scorer", "Signal Scorer"),
        ("src.convergence_detector", "Convergence Detector"),
        ("src.politician_ranking", "Politician Ranking"),
        ("src.alpha_signal_generator", "Alpha Signal Generator"),
        ("src.portfolio_optimizer", "Portfolio Optimizer"),
        ("src.daily_report", "Daily Report"),
        ("src.smart_alerts", "Smart Alerts"),
        ("src.name_mapping", "Name Mapping"),
        ("src.alpha_backtest", "Alpha Backtest"),
        ("src.signal_tracker", "Signal Tracker"),
        ("src.discovery_engine_v4", "Discovery Engine"),
        ("src.fama_french", "Fama-French Model"),
        ("src.ticker_enricher", "Ticker Enricher"),
        ("src.risk_manager", "Risk Manager"),
        ("src.portfolio_simulator", "Portfolio Simulator"),
        ("src.telegram_bot", "Telegram Bot"),
        ("src.ml_signal_model", "ML Signal Model"),
    ]

    for mod_path, name in modules:
        def make_check(mp):
            def inner():
                __import__(mp)
                return "OK"
            return inner
        if check(name, make_check(mod_path)): passed += 1
        else: failed += 1

    # ── Root-level 模組 ──
    print("\n  --- Root-level Modules ---")

    root_modules = [
        ("api_server", "API Server"),
    ]

    for mod_path, name in root_modules:
        def make_check(mp):
            def inner():
                __import__(mp)
                return "OK"
            return inner
        if check(name, make_check(mod_path)): passed += 1
        else: failed += 1

    # ── ETL 模組 ──
    print("\n  --- ETL Modules ---")

    etl_modules = [
        ("src.etl.pipeline", "ETL Pipeline"),
        ("src.etl.schemas", "ETL Schemas"),
        ("src.etl.senate_fetcher", "Senate Fetcher"),
        ("src.etl.house_fetcher", "House Fetcher"),
        ("src.etl.capitoltrades_fetcher", "Capitol Trades Fetcher"),
        ("src.etl.llm_transformer", "LLM Transformer"),
        ("src.etl.loader", "Loader"),
        ("src.etl.sec_form4_fetcher", "SEC Form 4 Fetcher"),
    ]

    for mod_path, name in etl_modules:
        def make_check(mp):
            def inner():
                __import__(mp)
                return "OK"
            return inner
        if check(name, make_check(mod_path)): passed += 1
        else: failed += 1

    # ── 資料完整性 ──
    print("\n  --- Data Integrity ---")

    def check_congress_trades():
        conn = sqlite3.connect('data/data.db')
        count = conn.execute("SELECT COUNT(*) FROM congress_trades").fetchone()[0]
        conn.close()
        return f"{count} rows" if count > 0 else None
    if check("congress_trades", check_congress_trades): passed += 1
    else: failed += 1

    def check_signals():
        conn = sqlite3.connect('data/data.db')
        count = conn.execute("SELECT COUNT(*) FROM ai_intelligence_signals").fetchone()[0]
        conn.close()
        return f"{count} rows" if count > 0 else None
    if check("ai_intelligence_signals", check_signals): passed += 1
    else: failed += 1

    def check_sqs():
        conn = sqlite3.connect('data/data.db')
        count = conn.execute("SELECT COUNT(*) FROM signal_quality_scores").fetchone()[0]
        conn.close()
        return f"{count} rows" if count > 0 else None
    if check("signal_quality_scores", check_sqs): passed += 1
    else: failed += 1

    def check_alpha():
        conn = sqlite3.connect('data/data.db')
        count = conn.execute("SELECT COUNT(*) FROM alpha_signals").fetchone()[0]
        conn.close()
        return f"{count} rows" if count > 0 else None
    if check("alpha_signals", check_alpha): passed += 1
    else: failed += 1

    def check_portfolio():
        conn = sqlite3.connect('data/data.db')
        count = conn.execute("SELECT COUNT(*) FROM portfolio_positions").fetchone()[0]
        conn.close()
        return f"{count} rows" if count > 0 else None
    if check("portfolio_positions", check_portfolio): passed += 1
    else: failed += 1

    def check_sectors():
        path = 'data/ticker_sectors.json'
        if os.path.exists(path):
            import json
            with open(path) as f:
                data = json.load(f)
            return f"{len(data.get('sector_map', {}))} tickers"
        return None
    if check("ticker_sectors.json", check_sectors): passed += 1
    else: failed += 1

    def check_fama_french():
        conn = sqlite3.connect('data/data.db')
        try:
            count = conn.execute("SELECT COUNT(*) FROM fama_french_results").fetchone()[0]
            conn.close()
            return f"{count} rows" if count > 0 else None
        except Exception:
            conn.close()
            return None
    if check("fama_french_results", check_fama_french): passed += 1
    else: failed += 1

    def check_sec_form4():
        conn = sqlite3.connect('data/data.db')
        try:
            count = conn.execute("SELECT COUNT(*) FROM sec_form4_trades").fetchone()[0]
            conn.close()
            return f"{count} rows" if count > 0 else None
        except Exception:
            conn.close()
            return None
    if check("sec_form4_trades", check_sec_form4): passed += 1
    else: failed += 1

    def check_risk_assessments():
        conn = sqlite3.connect('data/data.db')
        try:
            count = conn.execute("SELECT COUNT(*) FROM risk_assessments").fetchone()[0]
            conn.close()
            return f"{count} rows" if count > 0 else None
        except Exception:
            conn.close()
            return None
    if check("risk_assessments", check_risk_assessments): passed += 1
    else: failed += 1

    def check_portfolio_simulation():
        conn = sqlite3.connect('data/data.db')
        try:
            count = conn.execute("SELECT COUNT(*) FROM portfolio_simulation").fetchone()[0]
            conn.close()
            return f"{count} rows" if count > 0 else None
        except Exception:
            conn.close()
            return None
    if check("portfolio_simulation", check_portfolio_simulation): passed += 1
    else: failed += 1

    def check_simulation_trades():
        conn = sqlite3.connect('data/data.db')
        try:
            count = conn.execute("SELECT COUNT(*) FROM simulation_trades").fetchone()[0]
            conn.close()
            return f"{count} rows" if count > 0 else None
        except Exception:
            conn.close()
            return None
    if check("simulation_trades", check_simulation_trades): passed += 1
    else: failed += 1

    def check_ml_predictions():
        conn = sqlite3.connect('data/data.db')
        try:
            count = conn.execute("SELECT COUNT(*) FROM ml_predictions").fetchone()[0]
            conn.close()
            return f"{count} rows" if count > 0 else None
        except Exception:
            conn.close()
            return None
    if check("ml_predictions", check_ml_predictions): passed += 1
    else: failed += 1

    def check_telegram_subscribers():
        conn = sqlite3.connect('data/data.db')
        try:
            exists = conn.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='telegram_subscribers'"
            ).fetchone()[0]
            if exists:
                count = conn.execute("SELECT COUNT(*) FROM telegram_subscribers").fetchone()[0]
                conn.close()
                return f"{count} subscribers"
            else:
                conn.close()
                return "table created on first bot use (OK)"
        except Exception:
            conn.close()
            return None
    if check("telegram_subscribers", check_telegram_subscribers): passed += 1
    else: failed += 1

    # ── 摘要 ──
    total = passed + failed
    print(f"\n{'='*60}")
    print(f"  Results: {passed}/{total} passed, {failed} failed")
    if failed == 0:
        print(f"  Status: ALL SYSTEMS OPERATIONAL")
    else:
        print(f"  Status: {failed} ISSUES DETECTED")
    print(f"{'='*60}\n")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
