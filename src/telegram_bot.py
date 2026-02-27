"""
Telegram Bot — Political Alpha Monitor
互動式 Telegram 機器人：查詢交易信號、投資組合、議員排名等系統資料

Commands:
    /start       — 歡迎訊息 + 指令說明
    /signals     — Top 5 Alpha 信號 (by signal_strength)
    /portfolio   — 投資組合摘要
    /politicians — Top 5 議員排名 (PIS)
    /convergence — 活躍收斂信號
    /stats       — 系統狀態
    /subscribe   — 訂閱自動告警
    /unsubscribe — 取消訂閱

使用方式:
    python run_telegram_bot.py
"""

import logging
import os
import sqlite3
import sys
from datetime import datetime
from typing import List, Dict, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.config import DB_PATH, TELEGRAM_BOT_TOKEN

logger = logging.getLogger(__name__)


# ── MarkdownV2 跳脫工具 ──

_MD2_SPECIAL = r'_*[]()~`>#+-=|{}.!'

def _escape_md2(text: str) -> str:
    """跳脫 Telegram MarkdownV2 特殊字元。"""
    result = []
    for ch in str(text):
        if ch in _MD2_SPECIAL:
            result.append('\\')
        result.append(ch)
    return ''.join(result)


# ── 告警類型常數 ──

ALERT_TYPE_HIGH_ALPHA = 'HIGH_ALPHA'
ALERT_TYPE_CONVERGENCE = 'CONVERGENCE'
ALERT_TYPE_LARGE_TRADE = 'LARGE_TRADE'
ALERT_TYPE_INSIDER_OVERLAP = 'INSIDER_OVERLAP'


class TelegramAlertBot:
    """Telegram 互動機器人 + 自動告警推送。"""

    def __init__(self, token: str = '', db_path: str = DB_PATH):
        self.token = token or TELEGRAM_BOT_TOKEN
        self.db_path = db_path
        self.application = None  # type: Optional[object]

    # ── DB 工具 ──

    def _query(self, sql: str, params: tuple = ()) -> List[Dict]:
        """安全查詢資料庫。"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            rows = conn.execute(sql, params).fetchall()
            conn.close()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.warning(f"DB query failed: {e}")
            return []

    def _execute(self, sql: str, params: tuple = ()) -> bool:
        """執行寫入操作。"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute(sql, params)
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.warning(f"DB execute failed: {e}")
            return False

    def _ensure_subscriber_table(self) -> None:
        """確保 telegram_subscribers 表存在。"""
        self._execute("""
            CREATE TABLE IF NOT EXISTS telegram_subscribers (
                chat_id INTEGER UNIQUE,
                subscribed_at TEXT,
                active INTEGER DEFAULT 1
            )
        """)

    # ── 指令處理 ──

    async def cmd_start(self, update, context) -> None:
        """/start — 歡迎訊息 + 指令清單。"""
        text = (
            "*Political Alpha Monitor*\n\n"
            "Available commands:\n"
            "/signals \\- Top 5 Alpha signals\n"
            "/portfolio \\- Portfolio summary\n"
            "/politicians \\- Top 5 PIS rankings\n"
            "/convergence \\- Active convergence signals\n"
            "/stats \\- System status\n"
            "/subscribe \\- Subscribe to auto\\-alerts\n"
            "/unsubscribe \\- Unsubscribe"
        )
        await update.message.reply_text(text, parse_mode='MarkdownV2')

    async def cmd_signals(self, update, context) -> None:
        """/signals — Top 5 Alpha 信號。"""
        rows = self._query("""
            SELECT a.ticker, a.direction, a.expected_alpha_5d, a.expected_alpha_20d,
                   a.confidence, a.signal_strength, a.politician_name, a.chamber
            FROM alpha_signals a
            ORDER BY a.signal_strength DESC
            LIMIT 5
        """)

        if not rows:
            await update.message.reply_text("No alpha signals found\\.", parse_mode='MarkdownV2')
            return

        lines = ["*Top 5 Alpha Signals*\n"]
        for i, r in enumerate(rows, 1):
            ticker = _escape_md2(r['ticker'] or 'N/A')
            direction = _escape_md2(r['direction'] or '?')
            strength = r['signal_strength'] or 0
            conf = r['confidence'] or 0
            alpha5 = r['expected_alpha_5d'] or 0
            alpha20 = r['expected_alpha_20d'] or 0
            politician = _escape_md2(r['politician_name'] or 'Unknown')
            chamber = _escape_md2(r['chamber'] or '?')

            # 信號強度指示器
            if strength > 0.8:
                indicator = "🔴"
            elif strength > 0.6:
                indicator = "🟡"
            else:
                indicator = "🟢"

            lines.append(
                f"{indicator} *{i}\\. {ticker}* {direction}\n"
                f"   Strength: {_escape_md2(f'{strength:.2f}')} "
                f"Conf: {_escape_md2(f'{conf:.0%}')}\n"
                f"   Alpha 5d: {_escape_md2(f'{alpha5:+.2f}%')} "
                f"20d: {_escape_md2(f'{alpha20:+.2f}%')}\n"
                f"   {politician} \\({chamber}\\)\n"
            )

        await update.message.reply_text('\n'.join(lines), parse_mode='MarkdownV2')

    async def cmd_portfolio(self, update, context) -> None:
        """/portfolio — 投資組合摘要。"""
        rows = self._query("""
            SELECT ticker, sector, weight, conviction_score, expected_alpha
            FROM portfolio_positions
            ORDER BY weight DESC
        """)

        if not rows:
            await update.message.reply_text("No portfolio positions found\\.", parse_mode='MarkdownV2')
            return

        total_weight = sum(r['weight'] or 0 for r in rows)
        # 統計 sector
        sectors = {}  # type: Dict[str, float]
        for r in rows:
            s = r['sector'] or 'Unknown'
            sectors[s] = sectors.get(s, 0) + (r['weight'] or 0)

        top_sectors = sorted(sectors.items(), key=lambda x: x[1], reverse=True)[:3]

        lines = [
            "*Portfolio Summary*\n",
            f"Positions: {_escape_md2(str(len(rows)))}",
            f"Total weight: {_escape_md2(f'{total_weight:.1f}%')}",
            f"\n*Top Sectors:*",
        ]
        for s_name, s_weight in top_sectors:
            lines.append(f"  {_escape_md2(s_name)}: {_escape_md2(f'{s_weight:.1f}%')}")

        lines.append(f"\n*Top Holdings:*")
        for r in rows[:5]:
            ticker = _escape_md2(r['ticker'] or 'N/A')
            weight = r['weight'] or 0
            conv = r['conviction_score'] or 0
            lines.append(
                f"  *{ticker}* {_escape_md2(f'{weight:.1f}%')} "
                f"\\(conviction: {_escape_md2(f'{conv:.2f}')}\\)"
            )

        await update.message.reply_text('\n'.join(lines), parse_mode='MarkdownV2')

    async def cmd_politicians(self, update, context) -> None:
        """/politicians — Top 5 議員 PIS 排名。"""
        rows = self._query("""
            SELECT politician_name, chamber, pis_total, rank,
                   total_trades, avg_filing_lag_days
            FROM politician_rankings
            ORDER BY pis_total DESC
            LIMIT 5
        """)

        if not rows:
            await update.message.reply_text("No politician rankings found\\.", parse_mode='MarkdownV2')
            return

        lines = ["*Top 5 Politicians \\(PIS Score\\)*\n"]
        for i, r in enumerate(rows, 1):
            name = _escape_md2(r['politician_name'] or 'Unknown')
            chamber = _escape_md2(r['chamber'] or '?')
            pis = r['pis_total'] or 0
            trades = r['total_trades'] or 0
            lag = r['avg_filing_lag_days'] or 0

            if pis >= 50:
                grade = 'A'
            elif pis >= 45:
                grade = 'B'
            elif pis >= 35:
                grade = 'C'
            else:
                grade = 'D'

            lines.append(
                f"*{i}\\. {name}* \\({chamber}\\)\n"
                f"   PIS: {_escape_md2(f'{pis:.1f}')} \\(Grade {grade}\\)\n"
                f"   Trades: {_escape_md2(str(trades))} "
                f"Avg lag: {_escape_md2(f'{lag:.0f}')}d\n"
            )

        await update.message.reply_text('\n'.join(lines), parse_mode='MarkdownV2')

    async def cmd_convergence(self, update, context) -> None:
        """/convergence — 活躍收斂信號。"""
        rows = self._query("""
            SELECT ticker, direction, politician_count, politicians, score
            FROM convergence_signals
            ORDER BY score DESC
            LIMIT 5
        """)

        if not rows:
            await update.message.reply_text("No convergence signals found\\.", parse_mode='MarkdownV2')
            return

        lines = ["*Active Convergence Signals*\n"]
        for r in rows:
            ticker = _escape_md2(r['ticker'] or 'N/A')
            direction = _escape_md2(r['direction'] or '?')
            count = r['politician_count'] or 0
            score = r['score'] or 0
            politicians = _escape_md2(r['politicians'] or '')

            if count >= 3:
                indicator = "🔴"
            else:
                indicator = "🟡"

            lines.append(
                f"{indicator} *{ticker}* {direction}\n"
                f"   {_escape_md2(str(count))} politicians \\| "
                f"Score: {_escape_md2(f'{score:.2f}')}\n"
                f"   {politicians}\n"
            )

        await update.message.reply_text('\n'.join(lines), parse_mode='MarkdownV2')

    async def cmd_stats(self, update, context) -> None:
        """/stats — 系統狀態。"""
        tables = [
            ('congress_trades', 'Congress Trades'),
            ('alpha_signals', 'Alpha Signals'),
            ('convergence_signals', 'Convergence Signals'),
            ('portfolio_positions', 'Portfolio Positions'),
            ('politician_rankings', 'Politician Rankings'),
            ('sec_form4_trades', 'SEC Form 4'),
        ]

        lines = ["*System Status*\n"]

        for table_name, label in tables:
            rows = self._query(f"SELECT COUNT(*) as cnt FROM {table_name}")
            cnt = rows[0]['cnt'] if rows else 0
            lines.append(f"{_escape_md2(label)}: {_escape_md2(str(cnt))}")

        # 最新 ETL 時間
        etl_rows = self._query("""
            SELECT created_at FROM extraction_log
            ORDER BY created_at DESC LIMIT 1
        """)
        if etl_rows:
            last_etl = _escape_md2(etl_rows[0]['created_at'] or 'N/A')
            lines.append(f"\nLast ETL: {last_etl}")

        # 訂閱者數量
        self._ensure_subscriber_table()
        sub_rows = self._query(
            "SELECT COUNT(*) as cnt FROM telegram_subscribers WHERE active = 1"
        )
        sub_cnt = sub_rows[0]['cnt'] if sub_rows else 0
        lines.append(f"Active subscribers: {_escape_md2(str(sub_cnt))}")

        await update.message.reply_text('\n'.join(lines), parse_mode='MarkdownV2')

    async def cmd_subscribe(self, update, context) -> None:
        """/subscribe — 訂閱自動告警。"""
        chat_id = update.effective_chat.id
        self._ensure_subscriber_table()
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        ok = self._execute(
            "INSERT OR REPLACE INTO telegram_subscribers (chat_id, subscribed_at, active) "
            "VALUES (?, ?, 1)",
            (chat_id, now)
        )
        if ok:
            await update.message.reply_text(
                "Subscribed to auto\\-alerts\\. You will receive notifications for:\n"
                "\\- High Alpha signals \\(strength \\> 0\\.8\\)\n"
                "\\- Convergence events \\(3\\+ politicians\\)\n"
                "\\- Large trades \\(\\> $250K\\)\n"
                "\\- Insider overlap signals",
                parse_mode='MarkdownV2'
            )
        else:
            await update.message.reply_text("Failed to subscribe\\. Please try again\\.", parse_mode='MarkdownV2')

    async def cmd_unsubscribe(self, update, context) -> None:
        """/unsubscribe — 取消訂閱。"""
        chat_id = update.effective_chat.id
        self._ensure_subscriber_table()
        ok = self._execute(
            "UPDATE telegram_subscribers SET active = 0 WHERE chat_id = ?",
            (chat_id,)
        )
        if ok:
            await update.message.reply_text(
                "Unsubscribed from auto\\-alerts\\.",
                parse_mode='MarkdownV2'
            )
        else:
            await update.message.reply_text("Failed to unsubscribe\\.", parse_mode='MarkdownV2')

    # ── 自動告警推送 ──

    def get_active_subscribers(self) -> List[int]:
        """取得所有活躍訂閱者的 chat_id。"""
        self._ensure_subscriber_table()
        rows = self._query(
            "SELECT chat_id FROM telegram_subscribers WHERE active = 1"
        )
        return [r['chat_id'] for r in rows]

    def _format_alert_md2(self, alert_type: str, data: Dict) -> str:
        """格式化告警訊息為 MarkdownV2。"""
        now = _escape_md2(datetime.now().strftime('%Y-%m-%d %H:%M'))

        if alert_type == ALERT_TYPE_HIGH_ALPHA:
            ticker = _escape_md2(data.get('ticker', 'N/A'))
            direction = _escape_md2(data.get('direction', '?'))
            strength = data.get('signal_strength', 0)
            politician = _escape_md2(data.get('politician_name', 'Unknown'))
            return (
                f"🔴 *HIGH ALPHA SIGNAL*\n\n"
                f"*{ticker}* {direction}\n"
                f"Signal strength: {_escape_md2(f'{strength:.2f}')}\n"
                f"Politician: {politician}\n"
                f"Time: {now}"
            )

        elif alert_type == ALERT_TYPE_CONVERGENCE:
            ticker = _escape_md2(data.get('ticker', 'N/A'))
            direction = _escape_md2(data.get('direction', '?'))
            count = data.get('politician_count', 0)
            politicians = _escape_md2(data.get('politicians', ''))
            return (
                f"🟠 *CONVERGENCE SIGNAL*\n\n"
                f"*{ticker}* {direction}\n"
                f"{_escape_md2(str(count))} politicians converging\n"
                f"{politicians}\n"
                f"Time: {now}"
            )

        elif alert_type == ALERT_TYPE_LARGE_TRADE:
            ticker = _escape_md2(data.get('ticker', 'N/A'))
            politician = _escape_md2(data.get('politician_name', 'Unknown'))
            amount = _escape_md2(data.get('amount_range', '?'))
            tx_type = _escape_md2(data.get('transaction_type', '?'))
            return (
                f"💰 *LARGE TRADE*\n\n"
                f"*{ticker}* {tx_type}\n"
                f"Amount: {amount}\n"
                f"Politician: {politician}\n"
                f"Time: {now}"
            )

        elif alert_type == ALERT_TYPE_INSIDER_OVERLAP:
            ticker = _escape_md2(data.get('ticker', 'N/A'))
            politician = _escape_md2(data.get('politician_name', 'Unknown'))
            filer = _escape_md2(data.get('filer_name', 'Unknown'))
            return (
                f"⚡ *INSIDER OVERLAP*\n\n"
                f"*{ticker}*\n"
                f"Congress: {politician}\n"
                f"SEC Form 4: {filer}\n"
                f"Time: {now}"
            )

        else:
            return f"*Alert*\n\n{_escape_md2(str(data))}\nTime: {now}"

    def send_alert_sync(self, alert_type: str, data: Dict) -> int:
        """同步發送告警到所有訂閱者（供外部模組呼叫）。回傳成功發送數。"""
        import requests as req

        if not self.token:
            logger.warning("TELEGRAM_BOT_TOKEN not set, skipping alert")
            return 0

        subscribers = self.get_active_subscribers()
        if not subscribers:
            logger.info("No active subscribers")
            return 0

        message = self._format_alert_md2(alert_type, data)
        sent = 0

        for chat_id in subscribers:
            try:
                url = f"https://api.telegram.org/bot{self.token}/sendMessage"
                resp = req.post(url, json={
                    'chat_id': chat_id,
                    'text': message,
                    'parse_mode': 'MarkdownV2'
                }, timeout=10)
                resp.raise_for_status()
                sent += 1
            except Exception as e:
                logger.warning(f"Failed to send alert to {chat_id}: {e}")

        logger.info(f"Alert sent to {sent}/{len(subscribers)} subscribers")
        return sent

    # ── Bot 啟動 ──

    def build_application(self):
        """建立 telegram.ext.Application 實例。"""
        from telegram.ext import Application, CommandHandler

        app = Application.builder().token(self.token).build()

        app.add_handler(CommandHandler('start', self.cmd_start))
        app.add_handler(CommandHandler('signals', self.cmd_signals))
        app.add_handler(CommandHandler('portfolio', self.cmd_portfolio))
        app.add_handler(CommandHandler('politicians', self.cmd_politicians))
        app.add_handler(CommandHandler('convergence', self.cmd_convergence))
        app.add_handler(CommandHandler('stats', self.cmd_stats))
        app.add_handler(CommandHandler('subscribe', self.cmd_subscribe))
        app.add_handler(CommandHandler('unsubscribe', self.cmd_unsubscribe))

        self.application = app
        return app

    def run(self) -> None:
        """啟動 polling loop。"""
        if not self.token:
            logger.error("TELEGRAM_BOT_TOKEN not set. Cannot start bot.")
            return

        logger.info("Starting Telegram bot polling...")
        app = self.build_application()
        app.run_polling(drop_pending_updates=True)


# ── 外部呼叫介面 ──

def send_telegram_alert(alert_type: str, data: Dict, token: str = '', db_path: str = DB_PATH) -> int:
    """
    從外部模組（如 smart_alerts.py、run_daily.py）呼叫的統一介面。

    Args:
        alert_type: ALERT_TYPE_HIGH_ALPHA / CONVERGENCE / LARGE_TRADE / INSIDER_OVERLAP
        data: 告警資料 dict
        token: Bot token（預設從 .env 讀取）
        db_path: 資料庫路徑

    Returns:
        成功發送的訂閱者數量
    """
    try:
        bot = TelegramAlertBot(token=token, db_path=db_path)
        return bot.send_alert_sync(alert_type, data)
    except Exception as e:
        logger.warning(f"send_telegram_alert failed: {e}")
        return 0
