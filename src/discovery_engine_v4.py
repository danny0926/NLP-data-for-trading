import os
import json
import re
import uuid
import sqlite3
import logging
from datetime import datetime
from google import genai
from dotenv import load_dotenv

load_dotenv()

class DiscoveryEngineV4:
    """
    Discovery Engine V4: Integrated AI Agent for Congress, 13F, Social, and News Intel.
    As specified in CONGRESS_AI_SOLUTION.md.
    """
    def __init__(self, db_path="data/data.db", model_name="gemini-2.5-flash"):
        self.api_key = os.getenv("GOOGLE_API_KEY")
        self.client = genai.Client(api_key=self.api_key)
        self.db_path = db_path
        self.model_name = model_name
        self.logger = logging.getLogger(self.__class__.__name__)
        self._init_extended_db()

    def _init_extended_db(self):
        """初始化擴展表，用於儲存 AI 分析結果。"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        # AI 智能分析結果表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS ai_intelligence_signals (
            id TEXT PRIMARY KEY,
            source_type TEXT NOT NULL, -- CONGRESS, 13F, SOCIAL, NEWS
            source_name TEXT NOT NULL, -- 姓名或機構名
            ticker TEXT,
            impact_score INTEGER,
            sentiment TEXT,
            logic_reasoning TEXT,
            raw_content TEXT,
            recommended_execution TEXT, -- OPEN, CLOSE
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        conn.commit()
        conn.close()

    def _get_ai_response(self, prompt, use_search=True):
        config = {"tools": [{"google_search": {}}]} if use_search else {}
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=config
            )
            return response.text
        except Exception as e:
            print(f"[!] API Error: {e}")
            return ""

    def _extract_json(self, text):
        """Enhanced JSON extraction robust to Markdown and formatting issues."""
        if not text: return None
        
        # Remove Markdown code blocks
        text = re.sub(r'```json\s*', '', text)
        text = re.sub(r'```\s*', '', text)
        
        # Search for JSON object or list
        json_match = re.search(r'(\{.*\}|\[.*\])', text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                # Try to clean up common trailing comma issues or similar
                try:
                    cleaned_text = re.sub(r',\s*([\]}])', r'\1', json_match.group(0))
                    return json.loads(cleaned_text)
                except:
                    return None
        return None

    def _save_signal(self, source_type, source_name, signal_data):
        """將分析出的信號存入資料庫。"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 決定建議執行時間 (根據 MD 邏輯：高影響力且為最新消息)
        execution = "CLOSE"
        if isinstance(signal_data.get("score"), (int, float)) and signal_data.get("score") >= 8:
            execution = "OPEN" # 策略 A

        cursor.execute('''
            INSERT INTO ai_intelligence_signals 
            (id, source_type, source_name, ticker, impact_score, sentiment, logic_reasoning, recommended_execution)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            str(uuid.uuid4()),
            source_type,
            source_name,
            signal_data.get("ticker") or signal_data.get("symbol"),
            signal_data.get("score") or signal_data.get("impact_score"),
            signal_data.get("sentiment"),
            signal_data.get("logic") or signal_data.get("reason"),
            execution
        ))
        conn.commit()
        conn.close()

    def _get_local_trades(self, politician_name, days=30):
        """查詢 congress_trades 表中該議員最近的交易，作為 prompt context。

        Args:
            politician_name: 議員姓名（模糊匹配）
            days: 回溯天數（預設 30）

        Returns:
            格式化的交易記錄字串，若無資料則回傳空字串
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.execute(
                """
                SELECT transaction_date, ticker, asset_name, transaction_type,
                       amount_range, extraction_confidence
                FROM congress_trades
                WHERE politician_name LIKE ?
                  AND transaction_date >= date('now', ?)
                ORDER BY transaction_date DESC
                LIMIT 20
                """,
                (f"%{politician_name}%", f"-{days} days"),
            )
            rows = cursor.fetchall()
            conn.close()

            if not rows:
                return ""

            header = "以下是本系統 ETL 已收錄的近期交易記錄（來自官方申報）：\n"
            lines = []
            for row in rows:
                date, ticker, asset, tx_type, amount, conf = row
                ticker_str = ticker if ticker else "N/A"
                lines.append(
                    f"  {date} | {ticker_str} | {asset} | "
                    f"{tx_type} | {amount} | confidence={conf}"
                )
            return header + "\n".join(lines)
        except Exception as e:
            self.logger.warning(f"讀取本地交易失敗: {e}")
            return ""

    def monitor_target(self, target_type, target_name):
        """
        核心監控方法
        target_type: 'CONGRESS', '13F', 'SOCIAL'
        """
        print(f"[*] Discovery Engine 啟動監控 [{target_type}]: {target_name}")

        # 從 ETL 資料庫取得本地交易記錄作為額外 context
        local_context = ""
        if target_type == "CONGRESS":
            local_trades = self._get_local_trades(target_name)
            if local_trades:
                local_context = (
                    f"\n\n{local_trades}\n"
                    "請參考上述已知交易記錄，搜尋是否有更新的交易或相關新聞，"
                    "並結合這些資訊進行分析。\n"
                )
                print(f"  [ETL] 找到本地交易記錄，已附加至 prompt context")

        prompts = {
            "CONGRESS": f"""
                查尋美國國會議員 {target_name} 最近 30 天內的金融活動。
                優先尋找：1. Capitol Trades (股票交易申報)。
                如果沒有交易，請尋找：2. 針對特定上市公司或產業的重大政策發言/新聞 (Policy/News)。
                {local_context}
                請嚴格輸出純 JSON 格式 (不要 Markdown)，結構如下：
                {{
                    "results": [
                        {{
                            "ticker": "股票代碼 (若無明確代碼則留空)",
                            "type": "TRADE" 或 "NEWS",
                            "sentiment": "Positive" 或 "Negative" 或 "Neutral",
                            "score": 1-10 (影響力評分),
                            "logic": "簡短分析原因 (例如：買入 NVDA $50k 或 提出反壟斷法案)"
                        }}
                    ]
                }}
            """,
            "13F": f"""
                查詢 {target_name} 最近一次提交的 13F 報告。
                找出最重要的 3 個持倉變動（新買入、大幅增持或清倉）。
                請嚴格輸出純 JSON 格式 (不要 Markdown)，結構如下：
                {{
                    "results": [
                        {{
                            "ticker": "股票代碼",
                            "type": "13F_BUY" 或 "13F_SELL",
                            "sentiment": "Positive" 或 "Negative",
                            "score": 1-10,
                            "logic": "分析原因 (例如：新買入 5% 倉位)"
                        }}
                    ]
                }}
            """,
            "SOCIAL": f"""
                搜尋 {target_name} 最近 7 天在社群媒體或新聞上的關鍵言論。
                進行零樣本推理 (Zero-shot Reasoning)，判斷其言論對特定上市公司的影響。
                請嚴格輸出純 JSON 格式 (不要 Markdown)，結構如下：
                {{
                    "results": [
                        {{
                            "ticker": "受影響的股票代碼",
                            "type": "SOCIAL_IMPACT",
                            "sentiment": "Positive" 或 "Negative",
                            "score": 1-10,
                            "logic": "推理邏輯 (例如：批評波音安全問題 -> BA Negative)"
                        }}
                    ]
                }}
            """
        }
        
        prompt = prompts.get(target_type)
        if not prompt: return
        
        raw_output = self._get_ai_response(prompt)
        data = self._extract_json(raw_output)
        
        if not data:
            print(f"[!] {target_name}: 無法解析 JSON 或無資料。")
            return

        items = []
        if isinstance(data, dict):
            if "results" in data:
                items = data["results"]
            elif "impact_map" in data: # Backward compatibility
                items = data["impact_map"]
            else:
                # Try to see if the dict itself is a result or contains list
                items = [data]
        elif isinstance(data, list):
            items = data

        valid_items = 0
        for item in items:
            # 簡單過濾無效項目
            if not isinstance(item, dict): continue
            
            # 標準化
            normalized_item = {
                "ticker": item.get("ticker") or item.get("symbol") or item.get("stock_code"),
                "score": item.get("score") or item.get("impact_score") or item.get("magnitude") or 0,
                "sentiment": item.get("sentiment") or "Neutral",
                "logic": item.get("logic") or item.get("reason") or "No logic provided"
            }
            
            # 只有當有 ticker 或邏輯夠強時才存檔
            if normalized_item["ticker"] or normalized_item["score"] > 5:
                self._save_signal(target_type, target_name, normalized_item)
                valid_items += 1

        print(f"[+] {target_name}: 成功儲存 {valid_items} 個有效信號。")

if __name__ == "__main__":
    engine = DiscoveryEngineV4()
    # 測試
    engine.monitor_target("CONGRESS", "Nancy Pelosi")
