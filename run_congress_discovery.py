import time
from src.discovery_engine_v4 import DiscoveryEngineV4

def run_congress_monitoring():
    # 使用新 Key 並切換回 Flash 模型以加快速度
    engine = DiscoveryEngineV4(model_name="gemini-2.5-flash")
    
    targets = [
        {"name": "Tim Moore", "tier": 1, "note": "+52% Return"},
        {"name": "Ted Cruz", "tier": 1, "note": "+50% Return"},
        {"name": "Tom Suozzi", "tier": 1, "note": "+35% Return"},
        {"name": "Lisa McClain", "tier": 1, "note": "+37% Return"},
        {"name": "Pete Sessions", "tier": 1, "note": "+37% Return"},
        {"name": "Marjorie Taylor Greene", "tier": 2, "note": "Diversified"},
        {"name": "Mitch McConnell", "tier": 2, "note": "Leadership Influence"}
    ]
    
    print(f"=== 啟動國會議員情報監控任務 (新 API Key + Flash) ===")
    
    for target in targets:
        print(f"\n[Tier {target['tier']}] 正在處理: {target['name']} ({target['note']})")
        try:
            engine.monitor_target("CONGRESS", target['name'])
        except Exception as e:
            print(f"[!] 處理 {target['name']} 時發生錯誤: {e}")
        
        # Flash 模型 RPM 較高，等待 5 秒即可
        time.sleep(5)

    print("\n[✔] 所有監控任務執行完畢。")

if __name__ == "__main__":
    run_congress_monitoring()
