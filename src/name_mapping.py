"""議員姓名標準化與映射模組。

解決 ETL (congress_trades) 與 AI Discovery (ai_intelligence_signals)
之間的議員名字不匹配問題。

ETL 來源使用官方揭露格式（如 "David H McCormick"），
AI Discovery 使用常見稱呼（如 "Dave McCormick"）。
此模組將所有變體統一為 canonical 格式。
"""
import re
import sqlite3
from typing import Optional, Dict, List, Set

from src.config import DB_PATH


# ── 標準名字 → 所有已知別名的映射 ──
# canonical_name 採用 ETL (congress_trades) 中的格式作為主鍵，
# 同時涵蓋 AI Discovery 及其他常見稱呼。
POLITICIAN_ALIASES: Dict[str, List[str]] = {
    # --- 兩表皆有的議員（需映射） ---
    "David H McCormick": [
        "Dave McCormick", "David McCormick", "David H. McCormick",
        "Sen. Dave McCormick", "Sen. David McCormick",
    ],
    "Susan M Collins": [
        "Susan Collins", "Susan M. Collins",
        "Sen. Susan Collins", "Sen. Susan M. Collins",
    ],
    "Nancy Pelosi": [
        "Rep. Nancy Pelosi", "Speaker Pelosi", "Speaker Nancy Pelosi",
        "Nancy P. Pelosi",
    ],
    "Richard Blumenthal": [
        "Richard J. Blumenthal", "Sen. Richard Blumenthal",
        "Dick Blumenthal",
    ],

    # --- 僅在 congress_trades 中的議員 ---
    "April McClain Delaney": [
        "April Delaney", "April M. Delaney", "April McClain-Delaney",
    ],
    "Debbie Dingell": [
        "Deborah Dingell", "Rep. Debbie Dingell",
    ],
    "Donald Sternoff Jr. Beyer": [
        "Don Beyer", "Donald Beyer", "Donald S. Beyer Jr.",
        "Donald S. Beyer", "Donald Sternoff Beyer",
        "Rep. Don Beyer", "Rep. Donald Beyer",
    ],
    "Gilbert Cisneros": [
        "Gil Cisneros", "Gilbert R. Cisneros", "Gilbert Ray Cisneros Jr.",
        "Rep. Gil Cisneros",
    ],
    "Jake Auchincloss": [
        "Jacob Auchincloss", "Rep. Jake Auchincloss",
    ],
    "John Boozman": [
        "John N. Boozman", "Sen. John Boozman",
    ],
    "Michael A. Jr. Collins": [
        "Mike Collins", "Michael Collins", "Michael A. Collins Jr.",
        "Michael A. Collins", "Rep. Mike Collins",
    ],
    "Richard W. Allen": [
        "Rick Allen", "Rick W. Allen", "Richard Allen",
        "Rep. Rick Allen", "Rep. Richard Allen",
    ],
    "Rob Bresnahan": [
        "Robert Bresnahan", "Rep. Rob Bresnahan",
    ],
    "Sheri Biggs": [
        "Rep. Sheri Biggs",
    ],
    "Steve Cohen": [
        "Stephen Cohen", "Stephen I. Cohen", "Rep. Steve Cohen",
    ],
    "Suzan K. DelBene": [
        "Suzan DelBene", "Suzan K DelBene", "Rep. Suzan DelBene",
    ],
    "William F Hagerty, IV": [
        "Bill Hagerty", "William Hagerty", "William F. Hagerty",
        "William Francis Hagerty IV", "Sen. Bill Hagerty",
    ],

    # --- 僅在 ai_intelligence_signals 中的議員 ---
    "Dan Crenshaw": [
        "Daniel Crenshaw", "Daniel Reed Crenshaw", "Rep. Dan Crenshaw",
    ],
    "David Rouzer": [
        "David C. Rouzer", "Rep. David Rouzer",
    ],
    "Debbie Wasserman Schultz": [
        "Deborah Wasserman Schultz", "Rep. Debbie Wasserman Schultz",
    ],
    "Jefferson Shreve": [
        "Jeff Shreve", "Rep. Jefferson Shreve",
    ],
    "Josh Gottheimer": [
        "Joshua Gottheimer", "Joshua S. Gottheimer", "Rep. Josh Gottheimer",
    ],
    "Julie Johnson": [
        "Rep. Julie Johnson",
    ],
    "Lisa McClain": [
        "Lisa C. McClain", "Rep. Lisa McClain",
    ],
    "Marjorie Taylor Greene": [
        "MTG", "Rep. Marjorie Taylor Greene",
    ],
    "Markwayne Mullin": [
        "Sen. Markwayne Mullin", "Mark Wayne Mullin",
    ],
    "Michael McCaul": [
        "Michael T. McCaul", "Mike McCaul", "Rep. Michael McCaul",
    ],
    "Mitch McConnell": [
        "Addison Mitchell McConnell", "Sen. Mitch McConnell",
    ],
    "Pete Sessions": [
        "Peter Sessions", "Rep. Pete Sessions",
    ],
    "Ro Khanna": [
        "Rohit Khanna", "Rep. Ro Khanna",
    ],
    "Roger Williams": [
        "John Roger Williams", "Rep. Roger Williams",
    ],
    "Ron Wyden": [
        "Ronald Wyden", "Ronald L. Wyden", "Sen. Ron Wyden",
    ],
    "Scott Franklin": [
        "Scott J. Franklin", "Rep. Scott Franklin",
    ],
    "Ted Cruz": [
        "Rafael Edward Cruz", "Sen. Ted Cruz", "Rafael Cruz",
    ],
    "Tim Moore": [
        "Timothy Moore", "Rep. Tim Moore",
    ],
    "Tom Suozzi": [
        "Thomas Suozzi", "Thomas R. Suozzi", "Rep. Tom Suozzi",
    ],
}

# ── 反向索引：alias → canonical_name（啟動時自動建立） ──
_ALIAS_TO_CANONICAL: Dict[str, str] = {}


def _build_reverse_index() -> None:
    """建立反向索引，將所有別名對應回 canonical name。"""
    _ALIAS_TO_CANONICAL.clear()
    for canonical, aliases in POLITICIAN_ALIASES.items():
        # canonical 本身也加入索引
        key = canonical.strip().lower()
        _ALIAS_TO_CANONICAL[key] = canonical
        for alias in aliases:
            key = alias.strip().lower()
            _ALIAS_TO_CANONICAL[key] = canonical

_build_reverse_index()


def _clean_name(name: str) -> str:
    """移除多餘空白、標點，統一格式。"""
    # 移除前後空白
    name = name.strip()
    # 合併多餘空白
    name = re.sub(r'\s+', ' ', name)
    return name


def normalize_name(name: str) -> str:
    """將任何格式的議員名字標準化為 canonical 格式。

    查找順序：
    1. 精確匹配（不分大小寫）
    2. 移除 title prefix 後再匹配
    3. 若都找不到，回傳清理後的原名

    Args:
        name: 任意格式的議員名字

    Returns:
        canonical 格式的名字，或清理後的原名（若無匹配）
    """
    cleaned = _clean_name(name)
    key = cleaned.lower()

    # 1. 精確匹配
    if key in _ALIAS_TO_CANONICAL:
        return _ALIAS_TO_CANONICAL[key]

    # 2. 移除常見 title prefix
    for prefix in ("sen.", "rep.", "speaker", "hon.", "honorable"):
        stripped = re.sub(r'^' + re.escape(prefix) + r'\s+', '', key, flags=re.IGNORECASE)
        if stripped != key and stripped in _ALIAS_TO_CANONICAL:
            return _ALIAS_TO_CANONICAL[stripped]

    # 3. 嘗試只比對姓氏（最後一個 token）— 僅在姓氏唯一時回傳
    tokens = key.split()
    if tokens:
        last_name = tokens[-1]
        matches = [
            canonical for canon_key, canonical in _ALIAS_TO_CANONICAL.items()
            if canon_key.split()[-1] == last_name
        ]
        # 去重
        unique_matches = list(dict.fromkeys(matches))
        if len(unique_matches) == 1:
            return unique_matches[0]

    # 找不到就回傳清理後的原名
    return cleaned


def find_politician_in_trades(
    source_name: str,
    db_path: str = None,
) -> Optional[str]:
    """在 congress_trades 中查找與 source_name 匹配的議員。

    Args:
        source_name: AI Discovery 中的來源名字
        db_path: SQLite 資料庫路徑

    Returns:
        匹配到的 congress_trades.politician_name，或 None
    """
    db_path = db_path or DB_PATH
    canonical = normalize_name(source_name)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # 先嘗試精確匹配 canonical name
    cur.execute(
        "SELECT DISTINCT politician_name FROM congress_trades WHERE politician_name = ?",
        (canonical,),
    )
    row = cur.fetchone()
    if row:
        conn.close()
        return row[0]

    # 嘗試不分大小寫的 LIKE 匹配
    cur.execute(
        "SELECT DISTINCT politician_name FROM congress_trades WHERE LOWER(politician_name) = LOWER(?)",
        (canonical,),
    )
    row = cur.fetchone()
    if row:
        conn.close()
        return row[0]

    # 嘗試用所有 canonical name 的別名去比對 DB 中的名字
    cur.execute("SELECT DISTINCT politician_name FROM congress_trades")
    db_names = [r[0] for r in cur.fetchall()]
    conn.close()

    # 對 DB 中每個名字做 normalize，看是否與 source_name 的 canonical 相同
    for db_name in db_names:
        if normalize_name(db_name) == canonical:
            return db_name

    return None


def get_all_canonical_names() -> List[str]:
    """取得所有已知的 canonical 議員名字。"""
    return list(POLITICIAN_ALIASES.keys())


def get_aliases(canonical_name: str) -> List[str]:
    """取得指定 canonical name 的所有別名。"""
    return POLITICIAN_ALIASES.get(canonical_name, [])


def find_cross_table_matches(db_path: str = None) -> Dict[str, Optional[str]]:
    """找出 ai_intelligence_signals 中所有 source_name 與 congress_trades 的對應關係。

    Returns:
        Dict[ai_source_name, matched_etl_name_or_None]
    """
    db_path = db_path or DB_PATH
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("SELECT DISTINCT source_name FROM ai_intelligence_signals ORDER BY source_name")
    ai_names = [r[0] for r in cur.fetchall()]
    conn.close()

    result = {}
    for name in ai_names:
        result[name] = find_politician_in_trades(name, db_path)

    return result
