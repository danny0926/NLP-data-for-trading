"""國會議員追蹤清單 — Political Alpha Monitor

按歷史交易活躍度和影響力分為三個 Tier。
資料來源: Capitol Trades, Quiver Quantitative, Congress Edge,
         Common Cause, Motley Fool, 公開報導 (2024-2026)

Tier 1: 最活躍 / 最具影響力 — 高交易量、高報酬率、或顯著政策影響力
Tier 2: 活躍交易者 — 穩定的交易頻率或顯著報酬表現
Tier 3: 值得關注 — 委員會關鍵成員、特定產業集中、或政策影響力
"""

from typing import List, Dict, Optional


# ============================================================================
# 追蹤目標定義 — Top 30 國會議員
# ============================================================================

CONGRESS_TARGETS: List[Dict] = [

    # ── Tier 1: Top 10 最活躍 / 最具影響力 ──────────────────────────────

    {
        "name": "Nancy Pelosi",
        "chamber": "House",
        "party": "D",
        "state": "CA",
        "tier": 1,
        "note": "前議長，2024 年利潤 $10.6M (+70.9%)，科技股指標",
    },
    {
        "name": "Tommy Tuberville",
        "chamber": "Senate",
        "party": "R",
        "state": "AL",
        "tier": 1,
        "note": "2024 最高報酬 179% (FMCC)，軍事委員會成員，國防股爭議",
    },
    {
        "name": "Josh Gottheimer",
        "chamber": "House",
        "party": "D",
        "state": "NJ",
        "tier": 1,
        "note": "2024 年 526 筆交易 $91M，極高頻交易者",
    },
    {
        "name": "Ro Khanna",
        "chamber": "House",
        "party": "D",
        "state": "CA",
        "tier": 1,
        "note": "累計 4,284 筆交易，國會最高交易次數",
    },
    {
        "name": "Michael McCaul",
        "chamber": "House",
        "party": "R",
        "state": "TX",
        "tier": 1,
        "note": "1,059 筆交易 $79.7M，外交委員會主席",
    },
    {
        "name": "Dan Crenshaw",
        "chamber": "House",
        "party": "R",
        "state": "TX",
        "tier": 1,
        "note": "2024 年 +61.3% 報酬 $1.96M 利潤，高頻交易者",
    },
    {
        "name": "Marjorie Taylor Greene",
        "chamber": "House",
        "party": "R",
        "state": "GA",
        "tier": 1,
        "note": "288 筆交易 $4.85M，高媒體關注度",
    },
    {
        "name": "Richard Blumenthal",
        "chamber": "Senate",
        "party": "D",
        "state": "CT",
        "tier": 1,
        "note": "450 筆交易 $85.7M，參議院最高交易量",
    },
    {
        "name": "Markwayne Mullin",
        "chamber": "Senate",
        "party": "R",
        "state": "OK",
        "tier": 1,
        "note": "NVDA 178% 報酬，2025 初最活躍參議員",
    },
    {
        "name": "Jefferson Shreve",
        "chamber": "House",
        "party": "R",
        "state": "IN",
        "tier": 1,
        "note": "625 筆交易 $150.9M，最高交易金額",
    },

    # ── Tier 2: 11-20 活躍交易者 ────────────────────────────────────

    {
        "name": "David Rouzer",
        "chamber": "House",
        "party": "R",
        "state": "NC",
        "tier": 2,
        "note": "2024 年 +149% 報酬 $3.7M 利潤",
    },
    {
        "name": "Roger Williams",
        "chamber": "House",
        "party": "R",
        "state": "TX",
        "tier": 2,
        "note": "2024 年 +111.2% 報酬 $3.4M 利潤",
    },
    {
        "name": "Pete Sessions",
        "chamber": "House",
        "party": "R",
        "state": "TX",
        "tier": 2,
        "note": "2024 年 +95.2% 報酬 $2.67M 利潤",
    },
    {
        "name": "Julie Johnson",
        "chamber": "House",
        "party": "D",
        "state": "TX",
        "tier": 2,
        "note": "2025 初 123 筆交易，最活躍新人",
    },
    {
        "name": "Ron Wyden",
        "chamber": "Senate",
        "party": "D",
        "state": "OR",
        "tier": 2,
        "note": "2024 年 +123.8% 報酬 $2.72M，財政委員會資深成員",
    },
    {
        "name": "Scott Franklin",
        "chamber": "House",
        "party": "R",
        "state": "FL",
        "tier": 2,
        "note": "69 筆交易 $5.99M，穩定交易者",
    },
    {
        "name": "Dave McCormick",
        "chamber": "Senate",
        "party": "R",
        "state": "PA",
        "tier": 2,
        "note": "202 筆交易 $28.6M，前對沖基金 CEO",
    },
    {
        "name": "Lisa McClain",
        "chamber": "House",
        "party": "R",
        "state": "MI",
        "tier": 2,
        "note": "1,381 筆交易 $12.84M，極高頻",
    },
    {
        "name": "Debbie Wasserman Schultz",
        "chamber": "House",
        "party": "D",
        "state": "FL",
        "tier": 2,
        "note": "2024 年 +142.3% 報酬 $2.56M 利潤",
    },
    {
        "name": "Susan Collins",
        "chamber": "Senate",
        "party": "R",
        "state": "ME",
        "tier": 2,
        "note": "2024 年 +77.5% 報酬 $1.28M，參議院資深成員",
    },

    # ── Tier 3: 21-30 值得關注 ──────────────────────────────────────

    {
        "name": "Josh Hawley",
        "chamber": "Senate",
        "party": "R",
        "state": "MO",
        "tier": 3,
        "note": "2024 年 +55.3% 報酬 $1.47M，科技政策鷹派",
    },
    {
        "name": "David Kustoff",
        "chamber": "House",
        "party": "R",
        "state": "TN",
        "tier": 3,
        "note": "2024 年 +71.5% 報酬 $1.36M",
    },
    {
        "name": "Gil Cisneros",
        "chamber": "House",
        "party": "D",
        "state": "CA",
        "tier": 3,
        "note": "826 筆交易 $22.36M，高頻多元配置",
    },
    {
        "name": "Mark Green",
        "chamber": "House",
        "party": "R",
        "state": "TN",
        "tier": 3,
        "note": "能源股集中，國土安全委員會主席",
    },
    {
        "name": "Ted Cruz",
        "chamber": "Senate",
        "party": "R",
        "state": "TX",
        "tier": 3,
        "note": "+50% 報酬，商務委員會資深成員",
    },
    {
        "name": "Cleo Fields",
        "chamber": "House",
        "party": "D",
        "state": "LA",
        "tier": 3,
        "note": "185 筆交易 $20.48M，新興活躍交易者",
    },
    {
        "name": "Rob Bresnahan",
        "chamber": "House",
        "party": "R",
        "state": "PA",
        "tier": 3,
        "note": "648 筆交易 $8.25M，新任眾議員",
    },
    {
        "name": "Tom Suozzi",
        "chamber": "House",
        "party": "D",
        "state": "NY",
        "tier": 3,
        "note": "+35% 報酬，金融背景",
    },
    {
        "name": "Darrell Issa",
        "chamber": "House",
        "party": "R",
        "state": "CA",
        "tier": 3,
        "note": "單筆 $30M 交易，最富有議員之一",
    },
    {
        "name": "Mitch McConnell",
        "chamber": "Senate",
        "party": "R",
        "state": "KY",
        "tier": 3,
        "note": "前參議院多數黨領袖，政策影響力極大",
    },
]


# ============================================================================
# 輔助函式
# ============================================================================

def get_targets_by_tier(tier: int) -> List[Dict]:
    """取得指定 Tier 的追蹤目標。

    Args:
        tier: 1, 2, 或 3

    Returns:
        該 Tier 的目標清單
    """
    return [t for t in CONGRESS_TARGETS if t["tier"] == tier]


def get_targets_by_chamber(chamber: str) -> List[Dict]:
    """取得指定院別的追蹤目標。

    Args:
        chamber: "House" 或 "Senate"

    Returns:
        該院別的目標清單
    """
    return [t for t in CONGRESS_TARGETS if t["chamber"] == chamber]


def get_all_target_names() -> List[str]:
    """取得所有追蹤議員姓名。"""
    return [t["name"] for t in CONGRESS_TARGETS]


def get_target_by_name(name: str) -> Optional[Dict]:
    """依姓名查詢單一目標（模糊匹配）。

    Args:
        name: 議員姓名（部分匹配即可）

    Returns:
        匹配的目標 dict，或 None
    """
    name_lower = name.lower()
    for t in CONGRESS_TARGETS:
        if name_lower in t["name"].lower():
            return t
    return None


def summary() -> str:
    """回傳追蹤清單摘要字串。"""
    lines = []
    for tier in (1, 2, 3):
        targets = get_targets_by_tier(tier)
        house = [t for t in targets if t["chamber"] == "House"]
        senate = [t for t in targets if t["chamber"] == "Senate"]
        lines.append(
            f"Tier {tier}: {len(targets)} 人 "
            f"(House {len(house)}, Senate {len(senate)})"
        )
    lines.append(f"合計: {len(CONGRESS_TARGETS)} 人")
    return "\n".join(lines)
