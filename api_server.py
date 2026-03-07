"""Political Alpha Monitor — REST API Server

提供國會交易情報系統的 RESTful API，包含 Alpha 訊號、政治人物排名、
國會交易、SEC Form 4 內部人交易、收斂訊號、投資組合等端點。

啟動方式:
    uvicorn api_server:app --reload --port 8000
"""

import logging
import os
import sqlite3
import time
from collections import defaultdict
from datetime import datetime
from typing import Optional, List, Any, Dict

from fastapi import FastAPI, Query, Path, HTTPException, Depends, Security, Request
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("PAM.API")

# ── 設定 ──
DB_PATH = os.getenv("DATABASE_URL", os.path.join(os.path.dirname(__file__), "data", "data.db"))
API_KEY = os.getenv("API_SERVER_KEY", "")
RATE_LIMIT = int(os.getenv("API_RATE_LIMIT", "60"))  # requests per minute
_START_TIME = time.time()

LEGAL_DISCLAIMER = (
    "DISCLAIMER: Political Alpha Monitor (PAM) is a research tool for informational purposes only. "
    "It does NOT constitute investment advice, solicitation, or recommendation to buy or sell any securities. "
    "All signals, scores, and portfolio suggestions are algorithmically generated and have not been verified "
    "by a registered investment adviser (RIA). Past performance does not guarantee future returns. "
    "Congressional trading data has an inherent filing delay of 30-45 days. "
    "Users bear full responsibility for any investment decisions."
)

app = FastAPI(
    title="Political Alpha Monitor API",
    description=(
        "國會交易情報系統 REST API — 提供 Alpha 訊號、PACS 增強訊號、"
        "政治人物排名、國會交易、SEC Form 4 內部人交易、"
        "收斂訊號、板塊輪動、投資組合等端點。\n\n"
        "認證：設定 `X-API-Key` header（若伺服器啟用 API_SERVER_KEY）\n\n"
        f"⚠ {LEGAL_DISCLAIMER}"
    ),
    version="2.5.0",
    openapi_tags=[
        {"name": "Signals", "description": "Alpha 訊號與增強訊號"},
        {"name": "Portfolio", "description": "投資組合與板塊輪動"},
        {"name": "Politicians", "description": "政治人物排名與交易"},
        {"name": "Trades", "description": "國會交易與 SEC Form 4"},
        {"name": "System", "description": "系統狀態與健康檢查"},
    ],
)

# ── CORS ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Disclaimer Header Middleware ──
@app.middleware("http")
async def add_disclaimer_header(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Disclaimer"] = "Research tool only. Not investment advice."
    return response


# ── Rate Limiter (in-memory, per-IP) ──
_rate_buckets: Dict[str, list] = defaultdict(list)


async def rate_limit(request: Request):
    """Simple per-IP rate limiter: RATE_LIMIT requests/minute."""
    if not RATE_LIMIT:
        return
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    bucket = _rate_buckets[client_ip]
    # Remove entries older than 60s
    _rate_buckets[client_ip] = [t for t in bucket if now - t < 60]
    if len(_rate_buckets[client_ip]) >= RATE_LIMIT:
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Try again later.")
    _rate_buckets[client_ip].append(now)


# ── Global exception handler ──
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error on {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )

# ── API Key 認證 (可選) ──
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(api_key: Optional[str] = Security(api_key_header)):
    """若 .env 設有 API_SERVER_KEY 則驗證，否則跳過"""
    if not API_KEY:
        return None
    if api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return api_key


# ── DB 工具 ──
def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def paginated_response(rows: List[Dict[str, Any]], total: int, limit: int, offset: int) -> dict:
    return {"data": rows, "total": total, "limit": limit, "offset": offset}


def clamp_limit(limit: int) -> int:
    return max(1, min(limit, 200))


def rows_to_dicts(rows) -> List[dict]:
    return [dict(r) for r in rows]


# ── 1. GET /api/signals — Alpha 訊號 ──
@app.get("/api/signals", dependencies=[Depends(rate_limit), Depends(verify_api_key)], tags=["Signals"])
def list_signals(
    ticker: Optional[str] = Query(None, description="篩選股票代號"),
    direction: Optional[str] = Query(None, description="方向 (LONG/SHORT)"),
    min_strength: Optional[float] = Query(None, description="最低訊號強度"),
    chamber: Optional[str] = Query(None, description="院別 (Senate/House)"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    conn = get_db()
    try:
        where, params = [], []
        if ticker:
            where.append("ticker = ?")
            params.append(ticker.upper())
        if direction:
            where.append("direction = ?")
            params.append(direction.upper())
        if min_strength is not None:
            where.append("signal_strength >= ?")
            params.append(min_strength)
        if chamber:
            where.append("chamber = ?")
            params.append(chamber)

        clause = (" WHERE " + " AND ".join(where)) if where else ""

        total = conn.execute(f"SELECT COUNT(*) FROM alpha_signals{clause}", params).fetchone()[0]
        rows = conn.execute(
            f"SELECT * FROM alpha_signals{clause} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            params + [clamp_limit(limit), offset],
        ).fetchall()
        return paginated_response(rows_to_dicts(rows), total, clamp_limit(limit), offset)
    finally:
        conn.close()


# ── 1b. GET /api/signals/aging — 訊號新鮮度分析 (must be before {signal_id}) ──
@app.get("/api/signals/aging", dependencies=[Depends(rate_limit), Depends(verify_api_key)], tags=["Signals"])
def signal_aging_summary():
    """訊號新鮮度分析 — FRESH/DECAYING/EXPIRED 分類"""
    conn = get_db()
    try:
        rows = conn.execute("""
            SELECT a.id, a.ticker, a.politician_name, a.direction, a.signal_strength,
                   a.created_at,
                   ct.filing_date,
                   CAST(julianday('now') - julianday(ct.filing_date) AS INTEGER) as days_since_filing,
                   CASE
                       WHEN julianday('now') - julianday(ct.filing_date) <= 20 THEN 'FRESH'
                       WHEN julianday('now') - julianday(ct.filing_date) <= 40 THEN 'DECAYING'
                       ELSE 'EXPIRED'
                   END as freshness
            FROM alpha_signals a
            LEFT JOIN congress_trades ct ON a.trade_id = ct.id
            WHERE ct.filing_date IS NOT NULL
            ORDER BY ct.filing_date DESC
        """).fetchall()

        signals = rows_to_dicts(rows)
        summary = {"FRESH": 0, "DECAYING": 0, "EXPIRED": 0}
        for s in signals:
            tier = s.get("freshness", "EXPIRED")
            summary[tier] = summary.get(tier, 0) + 1

        return {
            "summary": summary,
            "total": len(signals),
            "fresh_pct": round(summary["FRESH"] / max(len(signals), 1) * 100, 1),
            "signals": signals[:50],
        }
    finally:
        conn.close()


# ── 1c. GET /api/signals/distribution — 信號分布統計 (must be before {signal_id}) ──
@app.get("/api/signals/distribution", dependencies=[Depends(rate_limit), Depends(verify_api_key)], tags=["Signals"])
def signal_distribution():
    """信號分布統計 — signal_strength, confidence, sqs_score 的直方圖數據"""
    conn = get_db()
    try:
        import numpy as np
        result = {}
        for field, table in [
            ("signal_strength", "alpha_signals"),
            ("confidence", "alpha_signals"),
            ("sqs_score", "alpha_signals"),
            ("pacs_score", "enhanced_signals"),
        ]:
            vals = [r[0] for r in conn.execute(
                f"SELECT {field} FROM {table} WHERE {field} IS NOT NULL"
            ).fetchall()]
            if vals:
                arr = np.array(vals)
                hist, bin_edges = np.histogram(arr, bins=20)
                result[field] = {
                    "n": len(vals),
                    "mean": round(float(np.mean(arr)), 4),
                    "std": round(float(np.std(arr)), 4),
                    "min": round(float(np.min(arr)), 4),
                    "max": round(float(np.max(arr)), 4),
                    "q25": round(float(np.percentile(arr, 25)), 4),
                    "q50": round(float(np.percentile(arr, 50)), 4),
                    "q75": round(float(np.percentile(arr, 75)), 4),
                    "histogram": {
                        "counts": hist.tolist(),
                        "bin_edges": [round(float(b), 4) for b in bin_edges],
                    },
                }
        return result
    finally:
        conn.close()


# ── 2. GET /api/signals/{id} — 單一訊號 ──
@app.get("/api/signals/{signal_id}", dependencies=[Depends(rate_limit), Depends(verify_api_key)], tags=["Signals"])
def get_signal(signal_id: str = Path(..., description="訊號 ID")):
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM alpha_signals WHERE id = ?", (signal_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Signal not found")
        return {"data": dict(row)}
    finally:
        conn.close()


# ── 3. GET /api/portfolio — 投資組合 ──
@app.get("/api/portfolio", dependencies=[Depends(rate_limit), Depends(verify_api_key)], tags=["Portfolio"])
def list_portfolio(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    conn = get_db()
    try:
        total = conn.execute("SELECT COUNT(*) FROM portfolio_positions").fetchone()[0]
        rows = conn.execute(
            "SELECT * FROM portfolio_positions ORDER BY conviction_score DESC LIMIT ? OFFSET ?",
            (clamp_limit(limit), offset),
        ).fetchall()
        return paginated_response(rows_to_dicts(rows), total, clamp_limit(limit), offset)
    finally:
        conn.close()


# ── 4. GET /api/politicians — 政治人物排名 ──
@app.get("/api/politicians", dependencies=[Depends(rate_limit), Depends(verify_api_key)], tags=["Politicians"])
def list_politicians(
    chamber: Optional[str] = Query(None, description="院別 (Senate/House)"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    conn = get_db()
    try:
        where, params = [], []
        if chamber:
            where.append("chamber = ?")
            params.append(chamber)

        clause = (" WHERE " + " AND ".join(where)) if where else ""

        total = conn.execute(f"SELECT COUNT(*) FROM politician_rankings{clause}", params).fetchone()[0]
        rows = conn.execute(
            f"SELECT * FROM politician_rankings{clause} ORDER BY pis_total DESC LIMIT ? OFFSET ?",
            params + [clamp_limit(limit), offset],
        ).fetchall()
        return paginated_response(rows_to_dicts(rows), total, clamp_limit(limit), offset)
    finally:
        conn.close()


# ── 5. GET /api/politicians/{name}/trades — 特定政治人物交易 ──
@app.get("/api/politicians/{name}/trades", dependencies=[Depends(rate_limit), Depends(verify_api_key)], tags=["Politicians"])
def get_politician_trades(
    name: str = Path(..., description="政治人物姓名"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    conn = get_db()
    try:
        total = conn.execute(
            "SELECT COUNT(*) FROM congress_trades WHERE politician_name = ?", (name,)
        ).fetchone()[0]
        if total == 0:
            raise HTTPException(status_code=404, detail=f"No trades found for politician: {name}")
        rows = conn.execute(
            "SELECT * FROM congress_trades WHERE politician_name = ? ORDER BY transaction_date DESC LIMIT ? OFFSET ?",
            (name, clamp_limit(limit), offset),
        ).fetchall()
        return paginated_response(rows_to_dicts(rows), total, clamp_limit(limit), offset)
    finally:
        conn.close()


# ── 5b. GET /api/politicians/performance — 政治人物實際績效 ──
@app.get("/api/politicians/performance", dependencies=[Depends(rate_limit), Depends(verify_api_key)], tags=["Politicians"])
def politician_performance(
    min_signals: int = Query(5, ge=1, description="最少訊號數"),
    limit: int = Query(20, ge=1, le=50),
):
    """根據 signal_performance 實際表現排名政治人物"""
    conn = get_db()
    try:
        rows = conn.execute("""
            SELECT a.politician_name, a.chamber, COUNT(*) as n_signals,
                   AVG(sp.hit_5d) as hit_rate_5d,
                   AVG(sp.actual_alpha_5d) as avg_alpha_5d,
                   AVG(sp.actual_alpha_20d) as avg_alpha_20d,
                   AVG(sp.max_favorable_excursion) as avg_mfe,
                   AVG(sp.max_adverse_excursion) as avg_mae
            FROM signal_performance sp
            JOIN alpha_signals a ON sp.signal_id = a.id
            WHERE sp.hit_5d IS NOT NULL AND a.politician_name IS NOT NULL
            GROUP BY a.politician_name, a.chamber
            HAVING COUNT(*) >= ?
            ORDER BY AVG(sp.hit_5d) DESC
            LIMIT ?
        """, (min_signals, clamp_limit(limit))).fetchall()
        return {"politicians": rows_to_dicts(rows), "min_signals": min_signals}
    finally:
        conn.close()


# ── 6. GET /api/convergence — 收斂訊號 ──
@app.get("/api/convergence", dependencies=[Depends(rate_limit), Depends(verify_api_key)], tags=["Signals"])
def list_convergence(
    ticker: Optional[str] = Query(None, description="篩選股票代號"),
    min_score: Optional[float] = Query(None, description="最低收斂分數"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    conn = get_db()
    try:
        where, params = [], []
        if ticker:
            where.append("ticker = ?")
            params.append(ticker.upper())
        if min_score is not None:
            where.append("score >= ?")
            params.append(min_score)

        clause = (" WHERE " + " AND ".join(where)) if where else ""

        total = conn.execute(f"SELECT COUNT(*) FROM convergence_signals{clause}", params).fetchone()[0]
        rows = conn.execute(
            f"SELECT * FROM convergence_signals{clause} ORDER BY score DESC LIMIT ? OFFSET ?",
            params + [clamp_limit(limit), offset],
        ).fetchall()
        return paginated_response(rows_to_dicts(rows), total, clamp_limit(limit), offset)
    finally:
        conn.close()


# ── 7. GET /api/trades — 國會交易 ──
@app.get("/api/trades", dependencies=[Depends(rate_limit), Depends(verify_api_key)], tags=["Trades"])
def list_trades(
    date_from: Optional[str] = Query(None, description="起始日期 (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="結束日期 (YYYY-MM-DD)"),
    chamber: Optional[str] = Query(None, description="院別 (Senate/House)"),
    transaction_type: Optional[str] = Query(None, description="交易類型 (Purchase/Sale/...)"),
    ticker: Optional[str] = Query(None, description="篩選股票代號"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    conn = get_db()
    try:
        where, params = [], []
        if date_from:
            where.append("transaction_date >= ?")
            params.append(date_from)
        if date_to:
            where.append("transaction_date <= ?")
            params.append(date_to)
        if chamber:
            where.append("chamber = ?")
            params.append(chamber)
        if transaction_type:
            where.append("transaction_type = ?")
            params.append(transaction_type)
        if ticker:
            where.append("ticker = ?")
            params.append(ticker.upper())

        clause = (" WHERE " + " AND ".join(where)) if where else ""

        total = conn.execute(f"SELECT COUNT(*) FROM congress_trades{clause}", params).fetchone()[0]
        rows = conn.execute(
            f"SELECT * FROM congress_trades{clause} ORDER BY transaction_date DESC LIMIT ? OFFSET ?",
            params + [clamp_limit(limit), offset],
        ).fetchall()
        return paginated_response(rows_to_dicts(rows), total, clamp_limit(limit), offset)
    finally:
        conn.close()


# ── 8. GET /api/insider — SEC Form 4 內部人交易 ──
@app.get("/api/insider", dependencies=[Depends(rate_limit), Depends(verify_api_key)], tags=["Trades"])
def list_insider_trades(
    ticker: Optional[str] = Query(None, description="篩選股票代號"),
    date_from: Optional[str] = Query(None, description="起始日期 (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="結束日期 (YYYY-MM-DD)"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    conn = get_db()
    try:
        where, params = [], []
        if ticker:
            where.append("ticker = ?")
            params.append(ticker.upper())
        if date_from:
            where.append("transaction_date >= ?")
            params.append(date_from)
        if date_to:
            where.append("transaction_date <= ?")
            params.append(date_to)

        clause = (" WHERE " + " AND ".join(where)) if where else ""

        total = conn.execute(f"SELECT COUNT(*) FROM sec_form4_trades{clause}", params).fetchone()[0]
        rows = conn.execute(
            f"SELECT * FROM sec_form4_trades{clause} ORDER BY transaction_date DESC LIMIT ? OFFSET ?",
            params + [clamp_limit(limit), offset],
        ).fetchall()
        return paginated_response(rows_to_dicts(rows), total, clamp_limit(limit), offset)
    finally:
        conn.close()


# ── 9. GET /api/cross-ref — 國會 + 內部人交叉比對 ──
@app.get("/api/cross-ref", dependencies=[Depends(rate_limit), Depends(verify_api_key)], tags=["Trades"])
def cross_reference(
    ticker: Optional[str] = Query(None, description="篩選股票代號"),
    days: int = Query(30, ge=1, le=365, description="交叉比對時間窗口 (天)"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """找出同一股票在指定天數內同時有國會交易與 SEC Form 4 內部人交易的重疊"""
    conn = get_db()
    try:
        base_query = """
            FROM congress_trades c
            JOIN sec_form4_trades s ON c.ticker = s.ticker
            WHERE c.ticker IS NOT NULL
              AND s.ticker IS NOT NULL
              AND ABS(julianday(c.transaction_date) - julianday(s.transaction_date)) <= ?
        """
        params = [days]

        if ticker:
            base_query += " AND c.ticker = ?"
            params.append(ticker.upper())

        count_sql = f"SELECT COUNT(*) {base_query}"
        total = conn.execute(count_sql, params).fetchone()[0]

        select_sql = f"""
            SELECT
                c.ticker,
                c.politician_name,
                c.chamber,
                c.transaction_type AS congress_action,
                c.transaction_date AS congress_date,
                c.amount_range,
                s.filer_name AS insider_name,
                s.filer_title AS insider_title,
                s.transaction_type AS insider_action,
                s.transaction_date AS insider_date,
                s.shares AS insider_shares,
                s.total_value AS insider_value,
                CAST(ABS(julianday(c.transaction_date) - julianday(s.transaction_date)) AS INTEGER) AS date_gap_days
            {base_query}
            ORDER BY c.transaction_date DESC
            LIMIT ? OFFSET ?
        """
        rows = conn.execute(select_sql, params + [clamp_limit(limit), offset]).fetchall()
        return paginated_response(rows_to_dicts(rows), total, clamp_limit(limit), offset)
    finally:
        conn.close()


# ── 10. GET /api/stats — 系統統計 ──
@app.get("/api/stats", dependencies=[Depends(rate_limit), Depends(verify_api_key)], tags=["System"])
def system_stats():
    conn = get_db()
    try:
        tables = [
            "alpha_signals", "portfolio_positions", "politician_rankings",
            "convergence_signals", "congress_trades", "sec_form4_trades",
            "ai_intelligence_signals", "extraction_log", "signal_quality_scores",
            "signal_performance", "fama_french_results", "ml_predictions",
        ]
        counts = {}
        for t in tables:
            try:
                counts[t] = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            except sqlite3.OperationalError:
                counts[t] = None  # 資料表可能不存在

        # 各表最後更新時間
        last_updates = {}
        time_cols = {
            "alpha_signals": "created_at",
            "congress_trades": "created_at",
            "sec_form4_trades": "created_at",
            "politician_rankings": "updated_at",
            "convergence_signals": "detected_at",
            "extraction_log": "created_at",
        }
        for t, col in time_cols.items():
            try:
                row = conn.execute(f"SELECT MAX({col}) FROM {t}").fetchone()
                last_updates[t] = row[0] if row else None
            except sqlite3.OperationalError:
                last_updates[t] = None

        # DB 檔案大小
        db_size_bytes = os.path.getsize(DB_PATH) if os.path.exists(DB_PATH) else 0
        db_size_mb = round(db_size_bytes / (1024 * 1024), 2)

        return {
            "data": {
                "table_counts": counts,
                "last_updates": last_updates,
                "db_size_mb": db_size_mb,
                "db_path": DB_PATH,
            }
        }
    finally:
        conn.close()


# ── 11. GET /api/health — 健康檢查 ──
@app.get("/api/health", tags=["System"])
def health_check():
    db_ok = False
    try:
        conn = get_db()
        conn.execute("SELECT 1")
        conn.close()
        db_ok = True
    except Exception:
        pass

    uptime_s = int(time.time() - _START_TIME)
    return {
        "status": "ok" if db_ok else "degraded",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "database": "connected" if db_ok else "disconnected",
        "version": app.version,
        "uptime_seconds": uptime_s,
    }


# ── 12. GET /api/enhanced-signals — PACS 增強訊號 ──
@app.get("/api/enhanced-signals", dependencies=[Depends(rate_limit), Depends(verify_api_key)], tags=["Signals"])
def list_enhanced_signals(
    ticker: Optional[str] = Query(None, description="篩選股票代號"),
    min_pacs: Optional[float] = Query(None, description="最低 PACS 分數"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """PACS + VIX 增強後的訊號（Signal Enhancer v2 輸出）"""
    conn = get_db()
    try:
        where, params = [], []
        if ticker:
            where.append("ticker = ?")
            params.append(ticker.upper())
        if min_pacs is not None:
            where.append("pacs_score >= ?")
            params.append(min_pacs)

        clause = (" WHERE " + " AND ".join(where)) if where else ""

        total = conn.execute(f"SELECT COUNT(*) FROM enhanced_signals{clause}", params).fetchone()[0]
        rows = conn.execute(
            f"SELECT * FROM enhanced_signals{clause} ORDER BY enhanced_strength DESC LIMIT ? OFFSET ?",
            params + [clamp_limit(limit), offset],
        ).fetchall()
        return paginated_response(rows_to_dicts(rows), total, clamp_limit(limit), offset)
    finally:
        conn.close()


# ── 13. GET /api/sectors — 板塊輪動訊號 ──
@app.get("/api/sectors", dependencies=[Depends(rate_limit), Depends(verify_api_key)], tags=["Portfolio"])
def list_sector_rotation(
    direction: Optional[str] = Query(None, description="方向 (BUY/SELL)"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """國會交易板塊輪動訊號（Sector Rotation Detector 輸出）"""
    conn = get_db()
    try:
        where, params = [], []
        if direction:
            where.append("direction = ?")
            params.append(direction.upper())

        clause = (" WHERE " + " AND ".join(where)) if where else ""

        total = conn.execute(f"SELECT COUNT(*) FROM sector_rotation_signals{clause}", params).fetchone()[0]
        rows = conn.execute(
            f"SELECT * FROM sector_rotation_signals{clause} ORDER BY momentum_score DESC LIMIT ? OFFSET ?",
            params + [clamp_limit(limit), offset],
        ).fetchall()
        return paginated_response(rows_to_dicts(rows), total, clamp_limit(limit), offset)
    finally:
        conn.close()


# ── 14. GET /api/performance — 訊號績效追蹤 ──
@app.get("/api/performance", dependencies=[Depends(rate_limit), Depends(verify_api_key)], tags=["Signals"])
def list_signal_performance(
    ticker: Optional[str] = Query(None, description="篩選股票代號"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """訊號的實際績效追蹤（hit rate、actual alpha、MAE/MFE）"""
    conn = get_db()
    try:
        where, params = [], []
        if ticker:
            where.append("ticker = ?")
            params.append(ticker.upper())

        clause = (" WHERE " + " AND ".join(where)) if where else ""

        total = conn.execute(f"SELECT COUNT(*) FROM signal_performance{clause}", params).fetchone()[0]
        rows = conn.execute(
            f"SELECT * FROM signal_performance{clause} ORDER BY evaluated_at DESC LIMIT ? OFFSET ?",
            params + [clamp_limit(limit), offset],
        ).fetchall()
        return paginated_response(rows_to_dicts(rows), total, clamp_limit(limit), offset)
    finally:
        conn.close()


# ── 15. GET /api/rebalance — 再平衡建議歷史 ──
@app.get("/api/rebalance", dependencies=[Depends(rate_limit), Depends(verify_api_key)], tags=["Portfolio"])
def list_rebalance_history(
    action: Optional[str] = Query(None, description="動作 (BUY/SELL/INCREASE/DECREASE/HOLD)"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """再平衡建議歷史"""
    conn = get_db()
    try:
        where, params = [], []
        if action:
            where.append("action = ?")
            params.append(action.upper())

        clause = (" WHERE " + " AND ".join(where)) if where else ""

        total = conn.execute(f"SELECT COUNT(*) FROM rebalance_history{clause}", params).fetchone()[0]
        rows = conn.execute(
            f"SELECT * FROM rebalance_history{clause} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            params + [clamp_limit(limit), offset],
        ).fetchall()
        return paginated_response(rows_to_dicts(rows), total, clamp_limit(limit), offset)
    finally:
        conn.close()


# ── 16. GET /api/performance/summary — 績效摘要 ──
@app.get("/api/performance/summary", dependencies=[Depends(rate_limit), Depends(verify_api_key)], tags=["Signals"])
def performance_summary():
    """聚合績效摘要：勝率、平均 alpha、最佳/最差表現"""
    conn = get_db()
    try:
        stats_5d = conn.execute("""
            SELECT COUNT(*) as n,
                   AVG(actual_alpha_5d) as avg_alpha,
                   SUM(CASE WHEN hit_5d = 1 THEN 1 ELSE 0 END) as hits,
                   MAX(actual_alpha_5d) as best,
                   MIN(actual_alpha_5d) as worst,
                   AVG(max_favorable_excursion) as avg_mfe,
                   AVG(max_adverse_excursion) as avg_mae
            FROM signal_performance WHERE actual_alpha_5d IS NOT NULL
        """).fetchone()

        stats_20d = conn.execute("""
            SELECT COUNT(*) as n,
                   AVG(actual_alpha_20d) as avg_alpha,
                   SUM(CASE WHEN hit_20d = 1 THEN 1 ELSE 0 END) as hits,
                   MAX(actual_alpha_20d) as best,
                   MIN(actual_alpha_20d) as worst
            FROM signal_performance WHERE actual_alpha_20d IS NOT NULL
        """).fetchone()

        total = conn.execute("SELECT COUNT(*) FROM signal_performance").fetchone()[0]

        def safe(row, idx):
            v = row[idx]
            return round(v, 4) if v is not None else None

        return {
            "data": {
                "total_evaluated": total,
                "five_day": {
                    "n": stats_5d[0],
                    "hit_rate": round(stats_5d[2] / stats_5d[0], 4) if stats_5d[0] else None,
                    "avg_alpha_pct": safe(stats_5d, 1),
                    "best_alpha_pct": safe(stats_5d, 3),
                    "worst_alpha_pct": safe(stats_5d, 4),
                    "avg_mfe_pct": safe(stats_5d, 5),
                    "avg_mae_pct": safe(stats_5d, 6),
                },
                "twenty_day": {
                    "n": stats_20d[0],
                    "hit_rate": round(stats_20d[2] / stats_20d[0], 4) if stats_20d[0] else None,
                    "avg_alpha_pct": safe(stats_20d, 1),
                    "best_alpha_pct": safe(stats_20d, 3),
                    "worst_alpha_pct": safe(stats_20d, 4),
                },
            }
        }
    finally:
        conn.close()


# ── Root health endpoint (for Docker healthcheck at /health) ──
@app.get("/health", tags=["System"])
def health_root():
    """Alias for /api/health — used by Docker healthcheck"""
    return health_check()


# ── 18. GET /api/daily-briefing — 每日晨報 ──
@app.get("/api/daily-briefing", dependencies=[Depends(rate_limit), Depends(verify_api_key)], tags=["System"])
def daily_briefing():
    """每日晨報 — 一個 API 取得所有開盤前決策資訊"""
    conn = get_db()
    try:
        # Top signals (PACS-ranked)
        top_signals = conn.execute("""
            SELECT e.ticker, e.politician_name, e.chamber, e.direction,
                   e.enhanced_strength, e.pacs_score, e.vix_zone, e.insider_confirmed
            FROM enhanced_signals e
            WHERE e.direction = 'LONG'
            ORDER BY e.pacs_score DESC
            LIMIT 5
        """).fetchall()

        # Fresh convergences
        convergences = conn.execute("""
            SELECT ticker, direction, politician_count, score
            FROM convergence_signals
            WHERE detected_at >= date('now', '-7 days')
            ORDER BY score DESC LIMIT 5
        """).fetchall()

        # Signal freshness
        freshness = conn.execute("""
            SELECT
                SUM(CASE WHEN julianday('now') - julianday(ct.filing_date) <= 20 THEN 1 ELSE 0 END) as fresh,
                SUM(CASE WHEN julianday('now') - julianday(ct.filing_date) BETWEEN 20 AND 40 THEN 1 ELSE 0 END) as decaying,
                SUM(CASE WHEN julianday('now') - julianday(ct.filing_date) > 40 THEN 1 ELSE 0 END) as expired
            FROM alpha_signals a
            JOIN congress_trades ct ON a.trade_id = ct.id
            WHERE ct.filing_date IS NOT NULL
        """).fetchone()

        # Performance summary
        perf = conn.execute("""
            SELECT COUNT(*) as n, AVG(hit_5d) as hr5, AVG(actual_alpha_5d) as aa5
            FROM signal_performance WHERE hit_5d IS NOT NULL
        """).fetchone()

        # System stats
        trades = conn.execute("SELECT COUNT(*) FROM congress_trades").fetchone()[0]
        signals = conn.execute("SELECT COUNT(*) FROM alpha_signals").fetchone()[0]

        return {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "top_picks": rows_to_dicts(top_signals),
            "convergences": rows_to_dicts(convergences),
            "freshness": {
                "fresh": freshness[0] or 0,
                "decaying": freshness[1] or 0,
                "expired": freshness[2] or 0,
            },
            "performance": {
                "evaluated": perf[0],
                "hit_rate_5d": round(perf[1] * 100, 1) if perf[1] else None,
                "avg_alpha_5d": round(perf[2], 2) if perf[2] else None,
            },
            "system": {"trades": trades, "signals": signals},
        }
    finally:
        conn.close()


# ── 19. GET /api/factor-correlation — 因子相關性分析 ──
@app.get("/api/factor-correlation", dependencies=[Depends(rate_limit), Depends(verify_api_key)], tags=["Signals"])
def factor_correlation():
    """因子相關性矩陣 — 信號因子 vs 實際 alpha 的 r-value"""
    conn = get_db()
    try:
        rows = conn.execute("""
            SELECT sp.confidence, sp.signal_strength, sp.actual_alpha_5d, sp.actual_alpha_20d,
                   sq.sqs, sq.actionability, sq.timeliness, sq.conviction,
                   sq.information_edge, sq.market_impact
            FROM signal_performance sp
            LEFT JOIN signal_quality_scores sq ON sp.signal_id = sq.trade_id
            WHERE sp.actual_alpha_5d IS NOT NULL
        """).fetchall()

        if len(rows) < 5:
            return {"error": "Insufficient data", "n": len(rows)}

        import numpy as np
        data = np.array([[r[i] if r[i] is not None else 0 for i in range(10)] for r in rows])
        factors = ["confidence", "signal_strength", "actual_alpha_5d", "actual_alpha_20d",
                    "sqs", "actionability", "timeliness", "conviction",
                    "information_edge", "market_impact"]

        correlations = {}
        for target in ["actual_alpha_5d", "actual_alpha_20d"]:
            ti = factors.index(target)
            target_col = data[:, ti]
            corr = {}
            for i, fname in enumerate(factors):
                if fname in ("actual_alpha_5d", "actual_alpha_20d"):
                    continue
                col = data[:, i]
                if np.std(col) > 0 and np.std(target_col) > 0:
                    r = float(np.corrcoef(col, target_col)[0, 1])
                    corr[fname] = round(r, 4)
            correlations[target] = corr

        return {"n": len(rows), "correlations": correlations}
    finally:
        conn.close()


# ── 20. GET /api/social/ticker-mentions — 社群 Ticker 提及頻率 ──
@app.get("/api/social/ticker-mentions", dependencies=[Depends(rate_limit), Depends(verify_api_key)], tags=["Social"])
def social_ticker_mentions(
    limit: int = Query(20, ge=1, le=100, description="回傳筆數"),
):
    """社群 Ticker 提及頻率 — 從 social_signals 解析 tickers_implied"""
    conn = get_db()
    try:
        rows = conn.execute("""
            SELECT tickers_implied, tickers_explicit FROM social_signals
            WHERE tickers_implied IS NOT NULL OR tickers_explicit IS NOT NULL
        """).fetchall()

        import json as _json
        ticker_counts: Dict[str, int] = defaultdict(int)
        for row in rows:
            for col_val in row:
                if not col_val:
                    continue
                try:
                    tickers = _json.loads(col_val) if isinstance(col_val, str) else col_val
                    if isinstance(tickers, list):
                        for t in tickers:
                            if isinstance(t, str) and len(t) <= 6:
                                ticker_counts[t.upper()] += 1
                except (ValueError, TypeError):
                    for t in str(col_val).replace("[", "").replace("]", "").replace("'", "").replace('"', '').split(","):
                        t = t.strip().upper()
                        if t and len(t) <= 6:
                            ticker_counts[t] += 1

        sorted_tickers = sorted(ticker_counts.items(), key=lambda x: -x[1])[:limit]
        return {
            "total_signals": len(rows),
            "unique_tickers": len(ticker_counts),
            "mentions": [{"ticker": t, "count": c} for t, c in sorted_tickers],
        }
    finally:
        conn.close()


# ── 21. GET /api/performance/seasonal — 季節性分析 ──
@app.get("/api/performance/seasonal", dependencies=[Depends(rate_limit), Depends(verify_api_key)], tags=["Signals"])
def seasonal_analysis():
    """季節性分析 — 各月份的平均 alpha 和勝率"""
    conn = get_db()
    try:
        rows = conn.execute("""
            SELECT
                CAST(strftime('%m', signal_date) AS INTEGER) as month,
                COUNT(*) as n,
                AVG(actual_alpha_5d) as avg_alpha_5d,
                AVG(actual_alpha_20d) as avg_alpha_20d,
                AVG(CASE WHEN hit_5d = 1 THEN 1.0 ELSE 0.0 END) as hit_rate_5d,
                AVG(CASE WHEN hit_20d = 1 THEN 1.0 ELSE 0.0 END) as hit_rate_20d
            FROM signal_performance
            WHERE signal_date IS NOT NULL AND actual_alpha_5d IS NOT NULL
            GROUP BY month
            ORDER BY month
        """).fetchall()

        month_names = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
                       "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        result = []
        for row in rows:
            m = row[0]
            result.append({
                "month": m,
                "month_name": month_names[m] if 1 <= m <= 12 else str(m),
                "n": row[1],
                "avg_alpha_5d": round(row[2], 4) if row[2] else None,
                "avg_alpha_20d": round(row[3], 4) if row[3] else None,
                "hit_rate_5d": round(row[4] * 100, 1) if row[4] is not None else None,
                "hit_rate_20d": round(row[5] * 100, 1) if row[5] is not None else None,
            })
        return {"months": result, "total": sum(r["n"] for r in result)}
    finally:
        conn.close()


# ── 22. GET /api/top-performers — 驗證績效排名 ──
@app.get("/api/top-performers", dependencies=[Depends(rate_limit), Depends(verify_api_key)], tags=["Politicians"])
def top_performers(
    min_signals: int = Query(5, ge=2, le=50, description="最低信號數門檻"),
    limit: int = Query(20, ge=1, le=100, description="回傳筆數"),
):
    """已驗證績效排名 — 基於 signal_performance 實際 hit rate"""
    conn = get_db()
    try:
        rows = conn.execute("""
            SELECT a.politician_name, a.chamber,
                   COUNT(*) as total_signals,
                   AVG(CASE WHEN sp.hit_5d = 1 THEN 1.0 ELSE 0.0 END) as hit_rate_5d,
                   AVG(sp.actual_alpha_5d) as avg_alpha_5d,
                   AVG(CASE WHEN sp.hit_20d = 1 THEN 1.0 ELSE 0.0 END) as hit_rate_20d,
                   AVG(sp.actual_alpha_20d) as avg_alpha_20d
            FROM signal_performance sp
            JOIN alpha_signals a ON sp.signal_id = a.id
            WHERE sp.hit_5d IS NOT NULL
            GROUP BY a.politician_name
            HAVING total_signals >= ?
            ORDER BY hit_rate_5d DESC, avg_alpha_5d DESC
            LIMIT ?
        """, (min_signals, limit)).fetchall()

        return {
            "min_signals": min_signals,
            "performers": rows_to_dicts(rows),
        }
    finally:
        conn.close()


# ── 23. GET /api/tickers/concentration — Ticker 集中度分析 ──
@app.get("/api/tickers/concentration", dependencies=[Depends(rate_limit), Depends(verify_api_key)], tags=["Trades"])
def ticker_concentration(
    limit: int = Query(20, ge=5, le=100, description="回傳筆數"),
    days: int = Query(365, ge=30, le=1095, description="回溯天數"),
):
    """Ticker 集中度 — 國會最關注的股票，含 buy/sell 比"""
    conn = get_db()
    try:
        rows = conn.execute("""
            SELECT ticker, COUNT(*) as total,
                   SUM(CASE WHEN transaction_type IN ('Purchase','Buy') THEN 1 ELSE 0 END) as buys,
                   SUM(CASE WHEN transaction_type NOT IN ('Purchase','Buy') THEN 1 ELSE 0 END) as sells,
                   COUNT(DISTINCT politician_name) as politicians,
                   COUNT(DISTINCT chamber) as chambers
            FROM congress_trades
            WHERE ticker IS NOT NULL AND ticker != ''
              AND transaction_date >= date('now', ? || ' days')
            GROUP BY ticker
            HAVING total >= 3
            ORDER BY total DESC
            LIMIT ?
        """, (str(-days), limit)).fetchall()

        return {
            "period_days": days,
            "tickers": rows_to_dicts(rows),
        }
    finally:
        conn.close()


# ── 24. GET /api/chambers/comparison — 院別比較 ──
@app.get("/api/chambers/comparison", dependencies=[Depends(rate_limit), Depends(verify_api_key)], tags=["Trades"])
def chamber_comparison():
    """院別比較 — Senate vs House 一站式統計"""
    conn = get_db()
    try:
        result = {}
        for chamber in ["Senate", "House"]:
            stats = conn.execute("""
                SELECT COUNT(*) as trades,
                       COUNT(DISTINCT politician_name) as politicians,
                       AVG(CASE WHEN filing_date IS NOT NULL AND transaction_date IS NOT NULL
                           THEN julianday(filing_date) - julianday(transaction_date) END) as avg_lag
                FROM congress_trades WHERE chamber = ?
            """, (chamber,)).fetchone()

            alpha = conn.execute("""
                SELECT COUNT(*) as n,
                       AVG(actual_alpha_5d) as avg_alpha,
                       AVG(CASE WHEN hit_5d = 1 THEN 1.0 ELSE 0.0 END) as hit_rate
                FROM signal_performance sp
                JOIN alpha_signals a ON sp.signal_id = a.id
                WHERE a.chamber = ? AND sp.hit_5d IS NOT NULL
            """, (chamber,)).fetchone()

            result[chamber.lower()] = {
                "trades": stats[0],
                "politicians": stats[1],
                "avg_filing_lag_days": round(stats[2], 1) if stats[2] else None,
                "signals_evaluated": alpha[0],
                "avg_alpha_5d": round(alpha[1], 4) if alpha[1] else None,
                "hit_rate_5d": round(alpha[2] * 100, 1) if alpha[2] else None,
            }
        return result
    finally:
        conn.close()


# ── 25. GET /api/flow/weekly — 國會每週淨買賣壓力 ──
@app.get("/api/flow/weekly", dependencies=[Depends(rate_limit), Depends(verify_api_key)], tags=["Trades"])
def weekly_flow(
    weeks: int = Query(26, ge=4, le=104, description="回溯週數"),
):
    """國會每週淨買賣壓力 — 買入筆數減賣出筆數，偵測 regime shift"""
    conn = get_db()
    try:
        rows = conn.execute("""
            SELECT strftime('%Y-W%W', transaction_date) as week,
                   SUM(CASE WHEN transaction_type IN ('Purchase','Buy') THEN 1 ELSE 0 END) as buys,
                   SUM(CASE WHEN transaction_type IN ('Sale','Sale (Full)','Sale (Partial)','Sell') THEN 1 ELSE 0 END) as sells,
                   COUNT(*) as total
            FROM congress_trades
            WHERE transaction_date >= date('now', ? || ' days')
            GROUP BY week
            ORDER BY week
        """, (str(-weeks * 7),)).fetchall()

        result = []
        for row in rows:
            buys, sells = row[1], row[2]
            net = buys - sells
            result.append({
                "week": row[0],
                "buys": buys,
                "sells": sells,
                "total": row[3],
                "net_flow": net,
                "sentiment": "BULLISH" if net > 0 else ("BEARISH" if net < 0 else "NEUTRAL"),
            })
        return {"weeks": result, "total_weeks": len(result)}
    finally:
        conn.close()


# ── 27. GET /api/pipeline/status — Pipeline 狀態總覽 ──
@app.get("/api/pipeline/status", dependencies=[Depends(rate_limit), Depends(verify_api_key)], tags=["System"])
def pipeline_status():
    """Pipeline 狀態 — 各階段數據量、最後執行時間、新鮮度"""
    conn = get_db()
    try:
        stages = {}
        for table in ["congress_trades", "alpha_signals", "enhanced_signals",
                       "signal_performance", "convergence_signals", "social_posts",
                       "social_signals", "fama_french_results", "sec_form4_trades",
                       "portfolio_positions"]:
            try:
                count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                latest = conn.execute(f"SELECT MAX(created_at) FROM {table}").fetchone()[0]
                stages[table] = {"count": count, "latest": latest}
            except Exception:
                stages[table] = {"count": 0, "latest": None}

        # Last ETL run
        last_etl = conn.execute("""
            SELECT source_type, status, created_at
            FROM extraction_log
            ORDER BY created_at DESC LIMIT 1
        """).fetchone()

        return {
            "stages": stages,
            "last_etl": dict(last_etl) if last_etl else None,
            "test_count": 498,
            "api_version": "2.5.0",
        }
    finally:
        conn.close()


# ── 主程式入口 ──
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api_server:app", host="0.0.0.0", port=8000, reload=True)
