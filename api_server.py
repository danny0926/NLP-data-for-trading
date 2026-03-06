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
    version="2.1.0",
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


# ── 主程式入口 ──
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api_server:app", host="0.0.0.0", port=8000, reload=True)
