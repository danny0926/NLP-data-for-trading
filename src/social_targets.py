"""社群媒體追蹤清單 — Political Alpha Monitor

追蹤兩類目標：
1. 國會議員 (Politicians) — 社群發言可能暗示政策方向或與交易行為相關
2. 意見領袖 (KOLs) — 市場影響力人物，發言可能影響股價

每個目標包含社群帳號、關注領域、影響力描述等資訊。
"""

from typing import List, Dict, Optional


# ============================================================================
# 國會議員社群追蹤清單
# ============================================================================

POLITICIAN_SOCIAL_TARGETS: List[Dict] = [
    {
        "name": "Nancy Pelosi",
        "twitter": "@SpeakerPelosi",
        "committees": [],
        "sector_focus": ["tech", "finance"],
        "note": "前議長，科技股交易指標人物",
    },
    {
        "name": "Tommy Tuberville",
        "twitter": "@SenTuberville",
        "committees": ["Armed Services", "Agriculture"],
        "sector_focus": ["defense", "agriculture"],
        "note": "軍事委員會成員，國防/農業股集中",
    },
    {
        "name": "Rick Allen",
        "twitter": "@RepRickAllen",
        "committees": ["Education & Labor", "Agriculture"],
        "sector_focus": ["education", "agriculture"],
        "note": "教育與勞動委員會成員",
    },
    {
        "name": "Gilbert Cisneros",
        "twitter": "@RepGilCisneros",
        "committees": ["Armed Services", "Veterans"],
        "sector_focus": ["defense"],
        "note": "軍事委員會成員，國防股關注",
    },
    {
        "name": "John Boozman",
        "twitter": "@JohnBoozman",
        "committees": ["Appropriations", "Agriculture"],
        "sector_focus": ["agriculture", "finance"],
        "note": "撥款委員會成員，農業/金融關注",
    },
    {
        "name": "Dave McCormick",
        "twitter": "@DaveMcCormickPA",
        "committees": ["Banking", "Armed Services"],
        "sector_focus": ["finance", "defense"],
        "note": "前對沖基金 CEO，銀行/軍事委員會",
    },
    {
        "name": "Dan Crenshaw",
        "twitter": "@DanCrenshawTX",
        "committees": ["Energy", "Intelligence"],
        "sector_focus": ["energy", "defense"],
        "note": "能源/情報委員會，高頻交易者",
    },
    {
        "name": "Mark Cohen",
        "twitter": "@CohenMark",
        "committees": [],
        "sector_focus": [],
        "note": "一般追蹤",
    },
]


# ============================================================================
# KOL (意見領袖) 追蹤清單
# ============================================================================

KOL_SOCIAL_TARGETS: List[Dict] = [
    {
        "name": "Donald Trump",
        "platforms": {
            "truth_social": "@realDonaldTrump",
            "twitter": "@realDonaldTrump",
        },
        "influence": "US President, policy impacts energy/defense/tech/crypto",
        "key_tickers": ["DJT"],
        "contrarian": False,
        "note": "總統政策發言直接影響市場，關注能源/國防/科技/加密貨幣",
    },
    {
        "name": "Elon Musk",
        "platforms": {
            "twitter": "@elonmusk",
        },
        "influence": "Tesla/SpaceX/xAI CEO",
        "key_tickers": ["TSLA"],
        "contrarian": False,
        "note": "推文頻繁影響 TSLA 及加密貨幣價格",
    },
    {
        "name": "Cathie Wood",
        "platforms": {
            "twitter": "@CathieDWood",
        },
        "influence": "ARK Invest CEO, growth/innovation focus",
        "key_tickers": ["ARKK"],
        "contrarian": False,
        "note": "ARK 基金操盤手，成長股/創新科技風向標",
    },
    {
        "name": "Jim Cramer",
        "platforms": {
            "twitter": "@jimcramer",
        },
        "influence": "CNBC host, Inverse Cramer effect",
        "key_tickers": [],
        "contrarian": True,
        "note": "CNBC 主持人，Inverse Cramer 效應（反向指標）",
    },
    {
        "name": "Bill Ackman",
        "platforms": {
            "twitter": "@BillAckman",
        },
        "influence": "Pershing Square, activist investor",
        "key_tickers": [],
        "contrarian": False,
        "note": "激進投資人，大型部位公開喊單",
    },
    {
        "name": "Keith Gill",
        "platforms": {
            "twitter": "@TheRoaringKitty",
            "reddit": "u/DeepFuckingValue",
        },
        "influence": "Meme stock catalyst",
        "key_tickers": ["GME"],
        "contrarian": False,
        "note": "迷因股催化劑，GME/AMC 社群領袖",
    },
]


# ============================================================================
# 政策關鍵字 → 相關股票對應表
# ============================================================================

POLITICIAN_SECTOR_MAP: Dict[str, List[str]] = {
    "energy": ["XOM", "CVX", "COP", "SLB", "OXY", "XLE"],
    "defense": ["LMT", "RTX", "NOC", "GD", "BA", "LHX"],
    "big tech": ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA"],
    "healthcare": ["UNH", "JNJ", "PFE", "ABBV", "MRK", "LLY"],
    "finance": ["JPM", "BAC", "GS", "MS", "C", "BLK"],
    "crypto": ["BTC-USD", "ETH-USD", "COIN", "MSTR", "MARA"],
    "tariff": ["CAT", "DE", "X", "NUE", "STLD", "AA"],
    "agriculture": ["ADM", "BG", "CTVA", "MOS", "CF", "DE"],
    "semiconductor": ["NVDA", "AMD", "INTC", "TSM", "AVGO", "QCOM"],
    "ai": ["NVDA", "MSFT", "GOOGL", "META", "PLTR", "AI"],
    "infrastructure": ["VMC", "MLM", "URI", "CAT", "DE", "PWR"],
    "cannabis": ["TLRY", "CGC", "ACB", "SNDL", "MSOS"],
    "ev": ["TSLA", "RIVN", "LCID", "NIO", "LI", "XPEV"],
    "real_estate": ["AMT", "PLD", "SPG", "O", "WELL", "VNQ"],
}


# ============================================================================
# 輔助函式
# ============================================================================

def get_all_twitter_handles() -> List[str]:
    """取得所有 Twitter/X 帳號（議員 + KOL）。"""
    handles = []
    for p in POLITICIAN_SOCIAL_TARGETS:
        if p.get("twitter"):
            handles.append(p["twitter"])
    for k in KOL_SOCIAL_TARGETS:
        twitter = k.get("platforms", {}).get("twitter")
        if twitter:
            handles.append(twitter)
    return handles


def get_all_truth_social_handles() -> List[str]:
    """取得所有 Truth Social 帳號。"""
    handles = []
    for k in KOL_SOCIAL_TARGETS:
        truth = k.get("platforms", {}).get("truth_social")
        if truth:
            handles.append(truth)
    return handles


def get_politician_by_name(name: str) -> Optional[Dict]:
    """依姓名查詢國會議員社群目標（模糊匹配）。

    Args:
        name: 議員姓名（部分匹配即可）

    Returns:
        匹配的目標 dict，或 None
    """
    name_lower = name.lower()
    for p in POLITICIAN_SOCIAL_TARGETS:
        if name_lower in p["name"].lower():
            return p
    return None


def get_kol_by_name(name: str) -> Optional[Dict]:
    """依姓名查詢 KOL 目標（模糊匹配）。

    Args:
        name: KOL 姓名（部分匹配即可）

    Returns:
        匹配的目標 dict，或 None
    """
    name_lower = name.lower()
    for k in KOL_SOCIAL_TARGETS:
        if name_lower in k["name"].lower():
            return k
    return None
