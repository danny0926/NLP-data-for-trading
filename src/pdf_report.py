"""
PDF 報告產生器 — Political Alpha Monitor
使用 fpdf2 產生含圖表的專業 PDF 投資報告。

Sections:
  1. 封面 (Cover Page)
  2. 執行摘要 (Executive Summary)
  3. 頂級 Alpha 訊號 (Top Alpha Signals)
  4. 投資組合配置 (Portfolio Allocation)
  5. 議員排名 (Politician Rankings)
  6. Convergence 訊號
  7. 風險評估摘要 (Risk Assessment)
  8. 近期國會交易 (Recent Trades)
  9. SEC Insider 交叉比對
  10. 附錄 (Appendix)

使用方式:
    python -m src.pdf_report                    # 今日報告
    python -m src.pdf_report --date 2026-02-27  # 指定日期
    python -m src.pdf_report --days 7           # 過去 7 天
"""

import argparse
import logging
import os
import sqlite3
import tempfile
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fpdf import FPDF

from src.config import DB_PATH, PROJECT_ROOT

logger = logging.getLogger("PDFReport")

# ============================================================================
# 色彩常數
# ============================================================================

COLOR_PRIMARY = (26, 35, 58)       # 深海軍藍 — 標題
COLOR_SECONDARY = (55, 65, 95)     # 淺海軍藍 — 副標題
COLOR_ACCENT = (0, 123, 167)       # 青藍色 — 強調
COLOR_BUY = (34, 139, 34)          # 綠色 — 買入
COLOR_SELL = (200, 40, 40)         # 紅色 — 賣出
COLOR_GOLD = (218, 165, 32)        # 金色 — Gold 等級
COLOR_PLATINUM = (96, 96, 128)     # 鉑金色 — Platinum 等級
COLOR_HEADER_BG = (230, 235, 245)  # 表頭背景
COLOR_ROW_ALT = (245, 247, 252)    # 交替列背景
COLOR_WHITE = (255, 255, 255)
COLOR_BLACK = (0, 0, 0)
COLOR_GRAY = (120, 120, 120)
COLOR_LIGHT_GRAY = (200, 200, 200)
COLOR_HIGH_RISK = (220, 50, 50)
COLOR_MED_RISK = (230, 160, 40)
COLOR_LOW_RISK = (50, 160, 80)


# ============================================================================
# 資料庫查詢
# ============================================================================

def _safe_query(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> List[dict]:
    """安全查詢，失敗時回傳空列表。"""
    try:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]
    except Exception as e:
        logger.warning(f"查詢失敗: {e}")
        return []


def _safe_scalar(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> Any:
    """安全取得單一值。"""
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        row = cur.fetchone()
        return row[0] if row else None
    except Exception:
        return None


def load_report_data(db_path: str, start_date: str, end_date: str) -> Dict[str, Any]:
    """從資料庫讀取報告所需的所有資料。"""
    conn = sqlite3.connect(db_path)
    data = {}  # type: Dict[str, Any]

    # 1. 基本統計
    data["total_trades"] = _safe_scalar(conn, "SELECT COUNT(*) FROM congress_trades") or 0
    data["unique_politicians"] = _safe_scalar(
        conn, "SELECT COUNT(DISTINCT politician_name) FROM congress_trades") or 0
    data["unique_tickers"] = _safe_scalar(
        conn, "SELECT COUNT(DISTINCT ticker) FROM congress_trades WHERE ticker IS NOT NULL AND ticker != ''") or 0

    # 2. 期間內交易
    data["trades"] = _safe_query(conn, """
        SELECT id, chamber, politician_name, transaction_date, filing_date,
               ticker, asset_name, transaction_type, amount_range, owner,
               extraction_confidence, created_at
        FROM congress_trades
        WHERE transaction_date BETWEEN ? AND ?
        ORDER BY transaction_date DESC, politician_name
    """, (start_date, end_date))

    # 3. Top Alpha 訊號 (按 signal_strength 排序)
    data["top_signals"] = _safe_query(conn, """
        SELECT a.ticker, a.asset_name, a.politician_name, a.chamber,
               a.transaction_type, a.amount_range, a.direction,
               a.signal_strength, a.expected_alpha_5d, a.expected_alpha_20d,
               a.confidence, a.sqs_score, a.sqs_grade, a.has_convergence,
               a.politician_grade, a.filing_lag_days, a.transaction_date
        FROM alpha_signals a
        ORDER BY a.signal_strength DESC
        LIMIT 20
    """)

    # 4. 投資組合配置
    data["portfolio"] = _safe_query(conn, """
        SELECT ticker, sector, weight, conviction_score, expected_alpha,
               volatility_30d, sharpe_estimate
        FROM portfolio_positions
        ORDER BY weight DESC
    """)

    # 5. 議員排名
    data["rankings"] = _safe_query(conn, """
        SELECT politician_name, chamber, total_trades, avg_trade_size,
               trades_per_month, unique_tickers, buy_count, sale_count,
               buy_sale_ratio, avg_filing_lag_days, pis_activity,
               pis_conviction, pis_diversification, pis_timing,
               pis_total, rank
        FROM politician_rankings
        ORDER BY rank ASC
    """)

    # 6. Convergence 訊號
    data["convergence"] = _safe_query(conn, """
        SELECT ticker, direction, politician_count, politicians,
               chambers, window_start, window_end, span_days, score
        FROM convergence_signals
        ORDER BY score DESC
    """)

    # 7. 風險評估
    data["risk"] = _safe_query(conn, """
        SELECT ticker, assessment_date, current_price, entry_price,
               pnl_pct, risk_score, risk_level, violations,
               action_required, sector, weight, beta, volatility_30d,
               sqs_avg, holding_days
        FROM risk_assessments
        ORDER BY risk_score DESC
    """)

    # 8. 近期交易 (最近 7 天)
    data["recent_trades"] = _safe_query(conn, """
        SELECT id, chamber, politician_name, transaction_date, filing_date,
               ticker, asset_name, transaction_type, amount_range,
               extraction_confidence
        FROM congress_trades
        ORDER BY transaction_date DESC
        LIMIT 50
    """)

    # 9. SEC Insider 交叉比對
    data["sec_overlaps"] = _safe_query(conn, """
        SELECT s.ticker, s.filer_name, s.filer_title, s.transaction_type,
               s.transaction_date, s.shares, s.total_value
        FROM sec_form4_trades s
        WHERE s.ticker IN (SELECT DISTINCT ticker FROM congress_trades WHERE ticker IS NOT NULL)
        ORDER BY s.transaction_date DESC
        LIMIT 30
    """)

    # 10. SQS 分布
    data["sqs_dist"] = _safe_query(conn, """
        SELECT grade, COUNT(*) as cnt, AVG(sqs) as avg_sqs
        FROM signal_quality_scores
        GROUP BY grade
        ORDER BY avg_sqs DESC
    """)

    # 11. 交易統計 (買/賣/院別)
    trades = data["trades"]
    data["period_buys"] = sum(1 for t in trades if t.get("transaction_type") == "Buy")
    data["period_sales"] = sum(
        1 for t in trades if t.get("transaction_type") and "Sale" in str(t["transaction_type"]))
    data["period_senate"] = sum(1 for t in trades if t.get("chamber") == "Senate")
    data["period_house"] = sum(1 for t in trades if t.get("chamber") == "House")

    conn.close()
    return data


# ============================================================================
# 圖表生成 (matplotlib → PNG)
# ============================================================================

def _create_sector_pie_chart(portfolio: List[dict], output_path: str) -> bool:
    """產生板塊配置圓餅圖。"""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        if not portfolio:
            return False

        # 依板塊彙總
        sector_weights = {}  # type: Dict[str, float]
        for p in portfolio:
            sector = p.get("sector") or "Unknown"
            sector_weights[sector] = sector_weights.get(sector, 0) + (p.get("weight") or 0)

        if not sector_weights or sum(sector_weights.values()) == 0:
            return False

        labels = list(sector_weights.keys())
        sizes = list(sector_weights.values())

        # 排序
        paired = sorted(zip(sizes, labels), reverse=True)
        sizes = [p[0] for p in paired]
        labels = [p[1] for p in paired]

        # 色彩
        cmap = plt.cm.get_cmap("Set3", len(labels))
        colors = [cmap(i) for i in range(len(labels))]

        fig, ax = plt.subplots(figsize=(6, 4))
        wedges, texts, autotexts = ax.pie(
            sizes, labels=None, autopct="%1.1f%%",
            startangle=90, colors=colors,
            pctdistance=0.85, textprops={"fontsize": 8}
        )
        ax.legend(labels, loc="center left", bbox_to_anchor=(1, 0.5), fontsize=7)
        ax.set_title("Portfolio Sector Allocation", fontsize=10, fontweight="bold")
        fig.tight_layout()
        fig.savefig(output_path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        return True
    except Exception as e:
        logger.warning(f"無法產生板塊圓餅圖: {e}")
        return False


def _create_risk_distribution_chart(risk_data: List[dict], output_path: str) -> bool:
    """產生風險分布橫條圖。"""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        if not risk_data:
            return False

        tickers = [r["ticker"] for r in risk_data[:15]]
        scores = [r.get("risk_score", 0) or 0 for r in risk_data[:15]]
        colors = []
        for s in scores:
            if s >= 60:
                colors.append("#dc3232")
            elif s >= 40:
                colors.append("#e6a028")
            else:
                colors.append("#32a050")

        fig, ax = plt.subplots(figsize=(6, 3.5))
        bars = ax.barh(tickers[::-1], scores[::-1], color=colors[::-1], height=0.6)
        ax.set_xlabel("Risk Score (0-100)", fontsize=8)
        ax.set_title("Position Risk Assessment", fontsize=10, fontweight="bold")
        ax.axvline(x=60, color="red", linestyle="--", alpha=0.5, linewidth=0.8)
        ax.axvline(x=40, color="orange", linestyle="--", alpha=0.5, linewidth=0.8)
        ax.set_xlim(0, 100)
        ax.tick_params(axis="both", labelsize=7)
        fig.tight_layout()
        fig.savefig(output_path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        return True
    except Exception as e:
        logger.warning(f"無法產生風險分布圖: {e}")
        return False


def _create_trade_direction_chart(buys: int, sales: int, others: int, output_path: str) -> bool:
    """產生買賣方向圓餅圖。"""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        values = []
        labels = []
        colors = []
        if buys > 0:
            values.append(buys)
            labels.append(f"Buy ({buys})")
            colors.append("#22a822")
        if sales > 0:
            values.append(sales)
            labels.append(f"Sale ({sales})")
            colors.append("#c82828")
        if others > 0:
            values.append(others)
            labels.append(f"Other ({others})")
            colors.append("#888888")

        if not values:
            return False

        fig, ax = plt.subplots(figsize=(3.5, 3))
        ax.pie(values, labels=labels, autopct="%1.0f%%", colors=colors,
               startangle=90, textprops={"fontsize": 8})
        ax.set_title("Trade Direction", fontsize=10, fontweight="bold")
        fig.tight_layout()
        fig.savefig(output_path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        return True
    except Exception as e:
        logger.warning(f"無法產生買賣方向圖: {e}")
        return False


def _create_sqs_distribution_chart(sqs_dist: List[dict], output_path: str) -> bool:
    """產生 SQS 等級分布長條圖。"""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        if not sqs_dist:
            return False

        grade_order = ["Platinum", "Gold", "Silver", "Bronze", "Discard"]
        grade_colors = {
            "Platinum": "#6060a0",
            "Gold": "#daa520",
            "Silver": "#a0a0a0",
            "Bronze": "#cd7f32",
            "Discard": "#cc4444",
        }

        dist_map = {d["grade"]: d for d in sqs_dist}
        labels = []
        counts = []
        colors = []
        for g in grade_order:
            d = dist_map.get(g)
            if d:
                labels.append(g)
                counts.append(d["cnt"])
                colors.append(grade_colors.get(g, "#888888"))

        if not labels:
            return False

        fig, ax = plt.subplots(figsize=(5, 3))
        ax.bar(labels, counts, color=colors)
        ax.set_ylabel("Count", fontsize=8)
        ax.set_title("Signal Quality Score Distribution", fontsize=10, fontweight="bold")
        ax.tick_params(axis="both", labelsize=8)
        for i, v in enumerate(counts):
            ax.text(i, v + 0.5, str(v), ha="center", fontsize=8)
        fig.tight_layout()
        fig.savefig(output_path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        return True
    except Exception as e:
        logger.warning(f"無法產生 SQS 分布圖: {e}")
        return False


# ============================================================================
# PDF 報告核心類別
# ============================================================================

class PDFReportGenerator(FPDF):
    """Political Alpha Monitor PDF 報告產生器。"""

    def __init__(self, report_date: str, start_date: str, end_date: str):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.report_date = report_date
        self.start_date = start_date
        self.end_date = end_date
        self._temp_dir = tempfile.mkdtemp(prefix="pam_report_")
        self.set_auto_page_break(auto=True, margin=20)

    # ── Header / Footer ──

    def header(self):
        """每頁頂部 — 跳過第一頁（封面）。"""
        if self.page_no() == 1:
            return
        self.set_font("Helvetica", "I", 7)
        self.set_text_color(*COLOR_GRAY)
        self.cell(0, 5, f"Political Alpha Monitor  |  {self.report_date}", align="L")
        self.cell(0, 5, "CONFIDENTIAL", align="R", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(*COLOR_LIGHT_GRAY)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(3)

    def footer(self):
        """每頁底部。"""
        self.set_y(-15)
        self.set_font("Helvetica", "I", 7)
        self.set_text_color(*COLOR_GRAY)
        if self.page_no() == 1:
            return
        self.cell(0, 5, f"Page {self.page_no() - 1}", align="C")

    # ── 工具方法 ──

    def _section_title(self, title: str):
        """區段標題。"""
        self.set_font("Helvetica", "B", 14)
        self.set_text_color(*COLOR_PRIMARY)
        self.cell(0, 10, title, new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(*COLOR_ACCENT)
        self.set_line_width(0.5)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(4)

    def _sub_title(self, title: str):
        """子標題。"""
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(*COLOR_SECONDARY)
        self.cell(0, 7, title, new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def _body_text(self, text: str):
        """內文文字。"""
        self.set_font("Helvetica", "", 9)
        self.set_text_color(*COLOR_BLACK)
        self.multi_cell(0, 5, text)
        self.ln(2)

    def _kpi_box(self, label: str, value: str, x: float, y: float, w: float = 42, h: float = 18):
        """KPI 指標方塊。"""
        self.set_fill_color(*COLOR_HEADER_BG)
        self.rect(x, y, w, h, "F")
        self.set_xy(x, y + 2)
        self.set_font("Helvetica", "", 7)
        self.set_text_color(*COLOR_GRAY)
        self.cell(w, 4, label, align="C")
        self.set_xy(x, y + 7)
        self.set_font("Helvetica", "B", 12)
        self.set_text_color(*COLOR_PRIMARY)
        self.cell(w, 8, value, align="C")

    def _table_header(self, col_widths: List[float], headers: List[str]):
        """繪製表格標題列。"""
        self.set_fill_color(*COLOR_PRIMARY)
        self.set_text_color(*COLOR_WHITE)
        self.set_font("Helvetica", "B", 7)
        for i, (w, h) in enumerate(zip(col_widths, headers)):
            self.cell(w, 6, h, border=0, fill=True, align="C")
        self.ln()

    def _table_row(self, col_widths: List[float], values: List[str],
                   aligns: Optional[List[str]] = None, row_idx: int = 0,
                   highlight_col: Optional[int] = None, highlight_color: Optional[tuple] = None):
        """繪製表格內容列。"""
        if row_idx % 2 == 1:
            self.set_fill_color(*COLOR_ROW_ALT)
        else:
            self.set_fill_color(*COLOR_WHITE)

        self.set_font("Helvetica", "", 7)
        fill = True

        for i, (w, v) in enumerate(zip(col_widths, values)):
            align = "C"
            if aligns and i < len(aligns):
                align = aligns[i]

            if highlight_col is not None and i == highlight_col and highlight_color:
                self.set_text_color(*highlight_color)
            else:
                self.set_text_color(*COLOR_BLACK)

            self.cell(w, 5, v[:25] if len(v) > 25 else v, border=0, fill=fill, align=align)

        self.ln()

    def _ensure_space(self, needed_mm: float):
        """確保頁面有足夠空間，否則換頁。"""
        if self.get_y() + needed_mm > 280:
            self.add_page()

    # ── 封面 ──

    def add_cover_page(self, data: Dict[str, Any]):
        """封面頁。"""
        self.add_page()

        # 大標題區域
        self.ln(40)
        self.set_font("Helvetica", "B", 28)
        self.set_text_color(*COLOR_PRIMARY)
        self.cell(0, 15, "Political Alpha Monitor", align="C", new_x="LMARGIN", new_y="NEXT")

        self.set_draw_color(*COLOR_ACCENT)
        self.set_line_width(0.8)
        self.line(50, self.get_y() + 2, 160, self.get_y() + 2)
        self.ln(8)

        self.set_font("Helvetica", "", 14)
        self.set_text_color(*COLOR_SECONDARY)
        self.cell(0, 10, "Daily Intelligence Report", align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(5)

        # 日期
        self.set_font("Helvetica", "B", 16)
        self.set_text_color(*COLOR_ACCENT)
        if self.start_date == self.end_date:
            date_str = self.end_date
        else:
            date_str = f"{self.start_date}  ~  {self.end_date}"
        self.cell(0, 10, date_str, align="C", new_x="LMARGIN", new_y="NEXT")

        # 封面中段統計
        self.ln(25)
        y = self.get_y()
        x_start = 20
        gap = 44

        self._kpi_box("Total Trades", str(data.get("total_trades", 0)),
                       x_start, y, 40, 20)
        self._kpi_box("Politicians", str(data.get("unique_politicians", 0)),
                       x_start + gap, y, 40, 20)
        self._kpi_box("Tickers", str(data.get("unique_tickers", 0)),
                       x_start + gap * 2, y, 40, 20)
        self._kpi_box("Signals", str(len(data.get("top_signals", []))),
                       x_start + gap * 3, y, 40, 20)

        self.set_y(y + 30)

        # 底部資訊
        self.ln(30)
        self.set_font("Helvetica", "", 9)
        self.set_text_color(*COLOR_GRAY)
        self.cell(0, 5, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                  align="C", new_x="LMARGIN", new_y="NEXT")
        self.cell(0, 5, "Sources: congress_trades, alpha_signals, portfolio_positions, risk_assessments",
                  align="C", new_x="LMARGIN", new_y="NEXT")
        self.cell(0, 5, "CONFIDENTIAL  |  v3.0", align="C", new_x="LMARGIN", new_y="NEXT")

    # ── Section 2: Executive Summary ──

    def add_executive_summary(self, data: Dict[str, Any]):
        """執行摘要。"""
        self.add_page()
        self._section_title("1. Executive Summary")

        trades = data.get("trades", [])
        total = len(trades)
        buys = data.get("period_buys", 0)
        sales = data.get("period_sales", 0)
        others = total - buys - sales

        # KPI 方塊
        y = self.get_y()
        self._kpi_box("Period Trades", str(total), 10, y, 37, 18)
        self._kpi_box("Buys", str(buys), 50, y, 37, 18)
        self._kpi_box("Sales", str(sales), 90, y, 37, 18)
        self._kpi_box("Senate", str(data.get("period_senate", 0)), 130, y, 37, 18)
        self._kpi_box("House", str(data.get("period_house", 0)), 170, y, 37, 18)
        self.set_y(y + 22)

        # 買賣比
        if sales > 0:
            ratio = buys / sales
            if ratio > 1.5:
                sentiment = "Bullish (Buy-dominated)"
            elif ratio < 0.67:
                sentiment = "Bearish (Sale-dominated)"
            else:
                sentiment = "Neutral"
            self._body_text(f"Buy/Sale Ratio: {ratio:.2f} -- {sentiment}")
        elif buys > 0:
            self._body_text("Buy/Sale Ratio: N/A (no sales)")

        # 圖表: 買賣方向
        chart_path = os.path.join(self._temp_dir, "trade_direction.png")
        if _create_trade_direction_chart(buys, sales, others, chart_path):
            self.image(chart_path, x=10, w=55)
            self.ln(5)

        # 活躍議員
        if trades:
            pol_counts = Counter(t["politician_name"] for t in trades)
            top3 = pol_counts.most_common(3)
            if top3:
                self._sub_title("Most Active Politicians")
                for name, cnt in top3:
                    self.set_font("Helvetica", "", 9)
                    self.set_text_color(*COLOR_BLACK)
                    self.cell(0, 5, f"  {name} ({cnt} trades)", new_x="LMARGIN", new_y="NEXT")
                self.ln(3)

        # 熱門 Ticker
        if trades:
            ticker_counts = Counter(t["ticker"] for t in trades if t.get("ticker"))
            top5 = ticker_counts.most_common(5)
            if top5:
                self._sub_title("Top Tickers")
                for tk, cnt in top5:
                    self.set_font("Helvetica", "", 9)
                    self.set_text_color(*COLOR_BLACK)
                    self.cell(0, 5, f"  {tk} ({cnt} trades)", new_x="LMARGIN", new_y="NEXT")
                self.ln(3)

    # ── Section 3: Top Alpha Signals ──

    def add_top_signals(self, data: Dict[str, Any]):
        """頂級 Alpha 訊號表格。"""
        self.add_page()
        self._section_title("2. Top Alpha Signals")

        signals = data.get("top_signals", [])
        if not signals:
            self._body_text("No alpha signals available.")
            return

        # SQS 分布圖
        sqs_chart_path = os.path.join(self._temp_dir, "sqs_dist.png")
        if _create_sqs_distribution_chart(data.get("sqs_dist", []), sqs_chart_path):
            self.image(sqs_chart_path, x=10, w=90)
            self.ln(5)

        self._sub_title(f"Top {len(signals)} Signals by Signal Strength")

        col_widths = [6, 25, 12, 30, 10, 18, 14, 16, 16, 14, 14, 14]
        headers = ["#", "Politician", "Ticker", "Asset", "Dir", "Amount",
                    "Strength", "Alpha 5d", "Alpha 20d", "SQS", "Grade", "Conv"]
        self._table_header(col_widths, headers)

        aligns = ["C", "L", "C", "L", "C", "C", "C", "C", "C", "C", "C", "C"]

        for i, s in enumerate(signals):
            direction = s.get("direction", "")
            txn_color = COLOR_BUY if direction == "Buy" else COLOR_SELL if direction == "Sale" else None

            vals = [
                str(i + 1),
                (s.get("politician_name") or "")[:23],
                s.get("ticker") or "N/A",
                (s.get("asset_name") or "")[:28],
                direction,
                (s.get("amount_range") or "")[:16],
                f"{s.get('signal_strength', 0):.2f}",
                f"{s.get('expected_alpha_5d', 0):.2%}" if s.get("expected_alpha_5d") else "N/A",
                f"{s.get('expected_alpha_20d', 0):.2%}" if s.get("expected_alpha_20d") else "N/A",
                f"{s.get('sqs_score', 0):.0f}" if s.get("sqs_score") else "-",
                s.get("sqs_grade") or "-",
                "Y" if s.get("has_convergence") else "",
            ]

            self._ensure_space(6)
            self._table_row(col_widths, vals, aligns, i, highlight_col=4, highlight_color=txn_color)

    # ── Section 4: Portfolio Allocation ──

    def add_portfolio(self, data: Dict[str, Any]):
        """投資組合配置。"""
        self.add_page()
        self._section_title("3. Portfolio Allocation")

        portfolio = data.get("portfolio", [])
        if not portfolio:
            self._body_text("No portfolio positions available.")
            return

        # 板塊圓餅圖
        pie_path = os.path.join(self._temp_dir, "sector_pie.png")
        if _create_sector_pie_chart(portfolio, pie_path):
            self.image(pie_path, x=10, w=110)
            self.ln(5)

        self._sub_title("Position Details")

        col_widths = [8, 14, 32, 18, 22, 22, 22, 22]
        headers = ["#", "Ticker", "Sector", "Weight", "Conviction",
                    "Alpha Est.", "Vol 30d", "Sharpe"]
        self._table_header(col_widths, headers)

        total_weight = 0.0
        aligns = ["C", "C", "L", "C", "C", "C", "C", "C"]

        for i, p in enumerate(portfolio):
            w = p.get("weight") or 0
            total_weight += w
            vals = [
                str(i + 1),
                p.get("ticker") or "N/A",
                (p.get("sector") or "")[:28],
                f"{w:.1%}",
                f"{p.get('conviction_score', 0):.1f}",
                f"{p.get('expected_alpha', 0):.2%}" if p.get("expected_alpha") else "-",
                f"{p.get('volatility_30d', 0):.1%}" if p.get("volatility_30d") else "-",
                f"{p.get('sharpe_estimate', 0):.2f}" if p.get("sharpe_estimate") else "-",
            ]
            self._ensure_space(6)
            self._table_row(col_widths, vals, aligns, i)

        # 小計
        self.ln(2)
        self.set_font("Helvetica", "B", 8)
        self.set_text_color(*COLOR_PRIMARY)
        self.cell(0, 5, f"Total Weight: {total_weight:.1%}  |  Positions: {len(portfolio)}",
                  new_x="LMARGIN", new_y="NEXT")

    # ── Section 5: Politician Rankings ──

    def add_politician_rankings(self, data: Dict[str, Any]):
        """議員排名。"""
        self.add_page()
        self._section_title("4. Politician Influence Score (PIS)")

        rankings = data.get("rankings", [])
        if not rankings:
            self._body_text("No politician ranking data available.")
            return

        self._body_text(
            "PIS is a composite score based on activity frequency, conviction level, "
            "portfolio diversification, and filing timeliness."
        )

        col_widths = [8, 30, 14, 14, 18, 16, 16, 16, 16, 16]
        headers = ["Rank", "Politician", "Chamber", "Trades", "PIS Total",
                    "Activity", "Convict.", "Divers.", "Timing", "Lag (d)"]
        self._table_header(col_widths, headers)

        aligns = ["C", "L", "C", "C", "C", "C", "C", "C", "C", "C"]

        for i, r in enumerate(rankings):
            pis = r.get("pis_total") or 0
            vals = [
                str(r.get("rank", i + 1)),
                (r.get("politician_name") or "")[:28],
                r.get("chamber") or "",
                str(r.get("total_trades") or 0),
                f"{pis:.1f}",
                f"{r.get('pis_activity', 0):.1f}",
                f"{r.get('pis_conviction', 0):.1f}",
                f"{r.get('pis_diversification', 0):.1f}",
                f"{r.get('pis_timing', 0):.1f}",
                f"{r.get('avg_filing_lag_days', 0):.0f}",
            ]
            self._ensure_space(6)
            self._table_row(col_widths, vals, aligns, i)

    # ── Section 6: Convergence Signals ──

    def add_convergence(self, data: Dict[str, Any]):
        """Convergence 訊號。"""
        self._ensure_space(40)
        self.ln(5)
        self._section_title("5. Convergence Signals")

        convergence = data.get("convergence", [])
        if not convergence:
            self._body_text("No convergence signals detected.")
            return

        self._body_text(
            "Convergence signals fire when multiple politicians trade the same ticker "
            "in the same direction within a short time window. Cross-chamber signals "
            "carry higher significance."
        )

        col_widths = [14, 14, 22, 50, 22, 28, 18]
        headers = ["Ticker", "Dir", "Count", "Politicians", "Chambers", "Window", "Score"]
        self._table_header(col_widths, headers)

        aligns = ["C", "C", "C", "L", "C", "C", "C"]

        for i, c in enumerate(convergence):
            direction = c.get("direction") or ""
            txn_color = COLOR_BUY if direction == "Buy" else COLOR_SELL
            window = f"{(c.get('window_start') or '')[:10]}~{(c.get('window_end') or '')[:10]}"
            vals = [
                c.get("ticker") or "N/A",
                direction,
                str(c.get("politician_count") or 0),
                (c.get("politicians") or "")[:48],
                c.get("chambers") or "",
                window,
                f"{c.get('score', 0):.3f}",
            ]
            self._ensure_space(6)
            self._table_row(col_widths, vals, aligns, i, highlight_col=1, highlight_color=txn_color)

    # ── Section 7: Risk Assessment ──

    def add_risk_assessment(self, data: Dict[str, Any]):
        """風險評估。"""
        self.add_page()
        self._section_title("6. Risk Assessment")

        risk_data = data.get("risk", [])
        if not risk_data:
            self._body_text("No risk assessment data available.")
            return

        # 風險分布圖
        risk_chart_path = os.path.join(self._temp_dir, "risk_dist.png")
        if _create_risk_distribution_chart(risk_data, risk_chart_path):
            self.image(risk_chart_path, x=10, w=110)
            self.ln(5)

        # 風險統計
        high = sum(1 for r in risk_data if r.get("risk_level") == "HIGH")
        med = sum(1 for r in risk_data if r.get("risk_level") == "MEDIUM")
        low = sum(1 for r in risk_data if r.get("risk_level") == "LOW")

        y = self.get_y()
        self._kpi_box("HIGH Risk", str(high), 10, y, 35, 18)
        self._kpi_box("MEDIUM Risk", str(med), 50, y, 35, 18)
        self._kpi_box("LOW Risk", str(low), 90, y, 35, 18)
        avg_score = sum(r.get("risk_score", 0) or 0 for r in risk_data) / max(len(risk_data), 1)
        self._kpi_box("Avg Score", f"{avg_score:.1f}", 130, y, 35, 18)
        self.set_y(y + 24)

        self._sub_title("Position Risk Details")

        col_widths = [12, 22, 16, 16, 16, 16, 14, 14, 14, 16]
        headers = ["Ticker", "Sector", "Price", "P&L %", "Risk", "Level",
                    "Beta", "Vol 30d", "Days", "Weight"]
        self._table_header(col_widths, headers)

        aligns = ["C", "L", "C", "C", "C", "C", "C", "C", "C", "C"]

        for i, r in enumerate(risk_data):
            risk_level = r.get("risk_level") or ""
            if risk_level == "HIGH":
                hl_color = COLOR_HIGH_RISK
            elif risk_level == "MEDIUM":
                hl_color = COLOR_MED_RISK
            else:
                hl_color = COLOR_LOW_RISK

            pnl = r.get("pnl_pct")
            pnl_str = f"{pnl:.1%}" if pnl is not None else "-"

            vals = [
                r.get("ticker") or "N/A",
                (r.get("sector") or "")[:20],
                f"${r.get('current_price', 0):.2f}" if r.get("current_price") else "-",
                pnl_str,
                f"{r.get('risk_score', 0):.0f}",
                risk_level,
                f"{r.get('beta', 0):.2f}" if r.get("beta") else "-",
                f"{r.get('volatility_30d', 0):.1%}" if r.get("volatility_30d") else "-",
                str(r.get("holding_days") or 0),
                f"{r.get('weight', 0):.1%}" if r.get("weight") else "-",
            ]
            self._ensure_space(6)
            self._table_row(col_widths, vals, aligns, i, highlight_col=5, highlight_color=hl_color)

    # ── Section 8: Recent Trades ──

    def add_recent_trades(self, data: Dict[str, Any]):
        """近期國會交易。"""
        self.add_page()
        self._section_title("7. Recent Congressional Trades")

        trades = data.get("recent_trades", [])
        if not trades:
            self._body_text("No recent trades available.")
            return

        self._body_text(f"Showing up to 50 most recent trades.")

        col_widths = [6, 28, 12, 12, 10, 18, 40, 18, 16]
        headers = ["#", "Politician", "Ticker", "Chamber", "Type", "Amount",
                    "Asset", "Tx Date", "Conf"]
        self._table_header(col_widths, headers)

        aligns = ["C", "L", "C", "C", "C", "C", "L", "C", "C"]

        for i, t in enumerate(trades[:50]):
            txn = t.get("transaction_type") or ""
            txn_color = COLOR_BUY if txn == "Buy" else COLOR_SELL if "Sale" in txn else None
            conf = t.get("extraction_confidence")
            conf_str = f"{conf:.0%}" if conf is not None else "-"

            vals = [
                str(i + 1),
                (t.get("politician_name") or "")[:26],
                t.get("ticker") or "N/A",
                t.get("chamber") or "",
                txn[:8] if txn else "",
                (t.get("amount_range") or "")[:16],
                (t.get("asset_name") or "")[:38],
                (t.get("transaction_date") or "")[:10],
                conf_str,
            ]
            self._ensure_space(6)
            self._table_row(col_widths, vals, aligns, i, highlight_col=4, highlight_color=txn_color)

    # ── Section 9: SEC Insider Overlaps ──

    def add_sec_overlaps(self, data: Dict[str, Any]):
        """SEC Insider 交叉比對。"""
        self._ensure_space(40)
        self.ln(5)
        self._section_title("8. SEC Form 4 Insider Overlaps")

        overlaps = data.get("sec_overlaps", [])
        if not overlaps:
            self._body_text("No SEC insider trading overlaps found with congressional trades.")
            return

        self._body_text(
            "SEC Form 4 insider trades that overlap with congressional trading tickers. "
            "Convergence between insider and congressional activity may signal stronger conviction."
        )

        col_widths = [14, 35, 24, 14, 20, 20, 28]
        headers = ["Ticker", "Insider", "Title", "Type", "Date", "Shares", "Value"]
        self._table_header(col_widths, headers)

        aligns = ["C", "L", "L", "C", "C", "C", "C"]

        for i, s in enumerate(overlaps[:30]):
            txn = s.get("transaction_type") or ""
            total_val = s.get("total_value")
            val_str = f"${total_val:,.0f}" if total_val else "-"

            vals = [
                s.get("ticker") or "N/A",
                (s.get("filer_name") or "")[:33],
                (s.get("filer_title") or "")[:22],
                txn[:12],
                (s.get("transaction_date") or "")[:10],
                f"{s.get('shares', 0):,.0f}" if s.get("shares") else "-",
                val_str[:26],
            ]
            self._ensure_space(6)
            self._table_row(col_widths, vals, aligns, i)

    # ── Section 10: Appendix ──

    def add_appendix(self):
        """附錄：方法論和資料來源。"""
        self.add_page()
        self._section_title("9. Appendix: Methodology & Data Sources")

        self._sub_title("Signal Quality Score (SQS)")
        self._body_text(
            "Each congressional trade is scored 0-100 based on five dimensions: "
            "Actionability (30%), Timeliness (20%), Conviction (25%), "
            "Information Edge (15%), Market Impact (10%). "
            "Grades: Platinum (80+), Gold (60-79), Silver (40-59), "
            "Bronze (20-39), Discard (<20)."
        )

        self._sub_title("Politician Influence Score (PIS)")
        self._body_text(
            "Composite ranking of congressional traders based on: "
            "Activity frequency, conviction (buy/sale consistency), "
            "portfolio diversification (unique tickers/sectors), "
            "and timing (average filing lag vs. STOCK Act deadlines)."
        )

        self._sub_title("Convergence Detection")
        self._body_text(
            "Identifies when 2+ politicians trade the same ticker in the same direction "
            "within a sliding window. Cross-chamber convergence (Senate + House) receives "
            "higher weighting. Score components: base, cross_chamber bonus, time_density, "
            "amount_weight."
        )

        self._sub_title("Alpha Signal Generation")
        self._body_text(
            "Expected alpha calculated using historical backtest results: "
            "Buy CAR(5d) = +0.77%, Sale contrarian CAR(5d) = +0.50%. "
            "Multipliers applied for: amount range, chamber (House > Senate), "
            "politician PIS grade, SQS score, convergence bonus, SEC insider overlap."
        )

        self._sub_title("Risk Management")
        self._body_text(
            "Position-level rules: stop-loss (-5%), take-profit (+15%), "
            "max holding 60 trading days, trailing stop (-3% from peak after +5%). "
            "Portfolio-level: max sector 30%, max single position 10%, "
            "max beta 1.3, drawdown limit -10%."
        )

        self._sub_title("Data Sources")
        self._body_text(
            "1. Senate EFD (efdsearch.senate.gov) -- Playwright + Akamai bypass\n"
            "2. House Clerk (disclosures-clerk.house.gov) -- PDF + Gemini Vision\n"
            "3. Capitol Trades (capitoltrades.com) -- Fallback for Senate\n"
            "4. SEC EDGAR Form 4 (efts.sec.gov) -- Insider trading\n"
            "5. yfinance -- Market prices, volatility, beta\n"
            "6. Google Gemini 2.5 Flash -- LLM extraction and analysis"
        )

        self._sub_title("Disclaimer")
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(*COLOR_GRAY)
        self.multi_cell(0, 4,
            "This report is for informational and educational purposes only. "
            "It does not constitute investment advice, and no trading decisions "
            "should be made solely based on this report. Congressional trading "
            "data is subject to filing delays and may not reflect current "
            "positions. Past performance does not guarantee future results."
        )

    # ── 主要生成方法 ──

    def generate(self, db_path: str) -> str:
        """生成完整 PDF 報告，回傳輸出路徑。"""
        logger.info(f"開始生成 PDF 報告: {self.start_date} ~ {self.end_date}")

        # 載入資料
        data = load_report_data(db_path, self.start_date, self.end_date)
        logger.info(f"  資料載入完成: {len(data.get('trades', []))} trades, "
                     f"{len(data.get('top_signals', []))} signals")

        # 組裝 PDF
        self.add_cover_page(data)
        self.add_executive_summary(data)
        self.add_top_signals(data)
        self.add_portfolio(data)
        self.add_politician_rankings(data)
        self.add_convergence(data)
        self.add_risk_assessment(data)
        self.add_recent_trades(data)
        self.add_sec_overlaps(data)
        self.add_appendix()

        # 輸出
        output_dir = PROJECT_ROOT / "docs" / "reports"
        output_dir.mkdir(parents=True, exist_ok=True)

        if self.start_date == self.end_date:
            filename = f"PAM_Report_{self.end_date}.pdf"
        else:
            filename = f"PAM_Report_{self.start_date}_{self.end_date}.pdf"

        output_path = str(output_dir / filename)
        self.output(output_path)
        logger.info(f"  PDF 報告已儲存: {output_path}")

        # 清理臨時檔案
        import shutil
        try:
            shutil.rmtree(self._temp_dir, ignore_errors=True)
        except Exception:
            pass

        return output_path


# ============================================================================
# CLI 入口
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Political Alpha Monitor -- PDF 報告產生器"
    )
    parser.add_argument(
        "--date", type=str, default=None,
        help="報告日期 (YYYY-MM-DD)，預設今日",
    )
    parser.add_argument(
        "--days", type=int, default=1,
        help="回溯天數 (預設 1)",
    )
    parser.add_argument(
        "--db", type=str, default=DB_PATH,
        help=f"資料庫路徑 (預設: {DB_PATH})",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(name)s | %(message)s")

    if args.date:
        try:
            end_dt = datetime.strptime(args.date, "%Y-%m-%d")
        except ValueError:
            print(f"[!] 日期格式錯誤: {args.date}")
            return
    else:
        end_dt = datetime.now()

    end_date = end_dt.strftime("%Y-%m-%d")
    start_dt = end_dt - timedelta(days=args.days - 1)
    start_date = start_dt.strftime("%Y-%m-%d")

    if not os.path.exists(args.db):
        print(f"[!] 資料庫不存在: {args.db}")
        return

    print(f"[PDFReport] 生成 PDF 報告: {start_date} ~ {end_date}")

    gen = PDFReportGenerator(
        report_date=end_date,
        start_date=start_date,
        end_date=end_date,
    )
    output_path = gen.generate(args.db)

    print(f"[PDFReport] 報告已儲存: {output_path}")
    file_size = os.path.getsize(output_path) / 1024
    print(f"[PDFReport] 檔案大小: {file_size:.1f} KB")


if __name__ == "__main__":
    main()
