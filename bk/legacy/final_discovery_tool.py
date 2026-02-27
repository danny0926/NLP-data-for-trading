import os
import json
import re
import time
from google import genai
from dotenv import load_dotenv

load_dotenv()

class DiscoveryAgent:
    def __init__(self):
        self.api_key = os.getenv("GOOGLE_API_KEY")
        self.client = genai.Client(api_key=self.api_key)

    def _get_ai_response(self, prompt, use_search=True):
        config = {}
        if use_search:
            config["tools"] = [{"google_search": {}}]
        
        response = self.client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=config
        )
        return response.text

    def _extract_json(self, text):
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except:
                return {"error": "JSON parse failed", "raw": text}
        return {"error": "No JSON found", "raw": text}

    def analyze_congress(self, name):
        print(f"[*] 正在分析議員交易: {name}...")
        prompt = f"查詢美國國會議員 {name} 最近 30 天內的 Capitol Trades 持股變動。請提供詳細交易列表並以 JSON 格式輸出，包含股票代碼、日期、類型、金額。"
        raw = self._get_ai_response(prompt)
        return self._extract_json(raw)

    def analyze_13f(self, fund_name):
        print(f"[*] 正在分析避險基金 13F: {fund_name}...")
        prompt = f"查詢 {fund_name} 最近一次的 13F 報告變動。請識別新買入、增持與清倉標的，並以 JSON 格式輸出。"
        raw = self._get_ai_response(prompt)
        return self._extract_json(raw)

    def analyze_social_impact(self, person, post_content):
        print(f"[*] 正在進行社群影響力動態推理: {person}...")
        prompt = f"""
        你是一位動態研究員。請分析來自 {person} 的言論："{post_content}"
        任務：
        1. 識別核心實體與技術。
        2. 推理與全球上市企業的商業關聯（禁止使用預設表，需現場推理）。
        3. 評估影響力與情緒。
        僅輸出 JSON 格式：
        {{
          "impact_map": [
            {{"ticker": "TICKER", "company": "NAME", "logic": "REASONING", "sentiment": "Pos/Neg", "score": 1-10}}
          ]
        }}
        """
        raw = self._get_ai_response(prompt)
        return self._extract_json(raw)

if __name__ == "__main__":
    agent = DiscoveryAgent()
    
    # 範例執行流程
    print("=== 全方位政商情報監控啟動 ===\n")
    
    # 1. 國會測試
    # congress_data = agent.analyze_congress("Tim Moore")
    # print(json.dumps(congress_data, indent=2, ensure_ascii=False))
    
    # 2. 13F 測試
    # fund_data = agent.analyze_13f("Scion Asset Management")
    # print(json.dumps(fund_data, indent=2, ensure_ascii=False))
    
    # 3. 社群動態推理測試
    social_data = agent.analyze_social_impact(
        "Elon Musk", 
        "The regulatory burden on the space industry is slowing down Mars exploration. We need a more streamlined FAA."
    )
    print("\n[社群影響報告]")
    print(json.dumps(social_data, indent=2, ensure_ascii=False))