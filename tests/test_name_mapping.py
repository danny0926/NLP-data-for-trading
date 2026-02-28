"""
tests/test_name_mapping.py — 議員姓名標準化單元測試

測試項目：
1. Module import
2. normalize_name()：精確匹配、alias 映射
3. 已知別名映射（如 Dave McCormick → David H McCormick）
4. 不在映射表中的名字應原樣回傳（清理後）
5. Title prefix 移除（Sen. / Rep.）
6. get_aliases() / get_all_canonical_names()
7. 邊界情況：空字串、多餘空白、None-like 輸入
"""

import pytest
from src.name_mapping import (
    normalize_name,
    get_aliases,
    get_all_canonical_names,
    POLITICIAN_ALIASES,
    _ALIAS_TO_CANONICAL,
)


class TestImport:
    def test_module_imports_successfully(self):
        """name_mapping 模組應可正常 import。"""
        from src.name_mapping import normalize_name
        assert normalize_name is not None

    def test_politician_aliases_not_empty(self):
        """POLITICIAN_ALIASES 字典不應為空。"""
        assert len(POLITICIAN_ALIASES) > 0

    def test_alias_to_canonical_index_built(self):
        """_ALIAS_TO_CANONICAL 反向索引應已建立。"""
        assert len(_ALIAS_TO_CANONICAL) > 0


class TestCanonicalNameLookup:
    """測試 canonical name 的精確查找。"""

    @pytest.mark.parametrize("canonical", [
        "David H McCormick",
        "Susan M Collins",
        "Nancy Pelosi",
        "Richard Blumenthal",
    ])
    def test_canonical_name_maps_to_itself(self, canonical):
        """canonical name 本身應映射到自己。"""
        result = normalize_name(canonical)
        assert result == canonical, (
            f"canonical '{canonical}' 應映射到自己，實際='{result}'"
        )


class TestAliasMapping:
    """測試別名 → canonical name 的映射。"""

    @pytest.mark.parametrize("alias,expected_canonical", [
        # Dave McCormick → David H McCormick
        ("Dave McCormick",          "David H McCormick"),
        ("David McCormick",         "David H McCormick"),
        ("David H. McCormick",      "David H McCormick"),
        # Susan Collins 變體
        ("Susan Collins",           "Susan M Collins"),
        ("Susan M. Collins",        "Susan M Collins"),
        # Nancy Pelosi 變體
        ("Nancy P. Pelosi",         "Nancy Pelosi"),
        ("Speaker Pelosi",          "Nancy Pelosi"),
        # Richard Blumenthal
        ("Dick Blumenthal",         "Richard Blumenthal"),
        # Rick Allen
        ("Rick Allen",              "Richard W. Allen"),
        # Don Beyer
        ("Don Beyer",               "Donald Sternoff Jr. Beyer"),
        # Gil Cisneros
        ("Gil Cisneros",            "Gilbert Cisneros"),
        # Bill Hagerty
        ("Bill Hagerty",            "William F Hagerty, IV"),
    ])
    def test_alias_resolves_to_canonical(self, alias, expected_canonical):
        """別名應正確解析為 canonical name。"""
        result = normalize_name(alias)
        assert result == expected_canonical, (
            f"別名 '{alias}' 應映射到 '{expected_canonical}'，實際='{result}'"
        )


class TestTitlePrefixRemoval:
    """測試 Sen. / Rep. 前綴的自動移除。"""

    @pytest.mark.parametrize("name_with_prefix,expected_canonical", [
        ("Sen. Dave McCormick",    "David H McCormick"),
        ("Sen. Susan Collins",     "Susan M Collins"),
        ("Rep. Nancy Pelosi",      "Nancy Pelosi"),
        ("Rep. Rick Allen",        "Richard W. Allen"),
        ("Sen. Bill Hagerty",      "William F Hagerty, IV"),
        ("Rep. Don Beyer",         "Donald Sternoff Jr. Beyer"),
    ])
    def test_title_prefix_stripped(self, name_with_prefix, expected_canonical):
        """帶有 Sen./Rep. 前綴的名字應正確映射到 canonical name。"""
        result = normalize_name(name_with_prefix)
        assert result == expected_canonical, (
            f"'{name_with_prefix}' 應映射到 '{expected_canonical}'，實際='{result}'"
        )


class TestUnknownNames:
    """測試不在映射表中的名字。"""

    def test_unknown_name_returns_cleaned_original(self):
        """不在映射表中的名字應回傳清理後的原名（不是 None 或空字串）。"""
        result = normalize_name("John Doe Unknown Senator")
        assert result == "John Doe Unknown Senator"

    def test_extra_whitespace_cleaned(self):
        """多餘空白應被清理。"""
        result = normalize_name("  Nancy   Pelosi  ")
        assert result == "Nancy Pelosi"

    def test_case_insensitive_match(self):
        """別名查找應不分大小寫。"""
        result = normalize_name("DAVE MCCORMICK")
        # 小寫化後應能找到 Dave McCormick 的映射
        result_lower = normalize_name("dave mccormick")
        # 兩者應得到相同結果
        assert result == result_lower


class TestGetAliases:
    def test_get_aliases_known_name(self):
        """get_aliases() 對已知 canonical name 應回傳非空列表。"""
        aliases = get_aliases("David H McCormick")
        assert isinstance(aliases, list)
        assert len(aliases) > 0
        assert "Dave McCormick" in aliases

    def test_get_aliases_unknown_name(self):
        """get_aliases() 對未知名字應回傳空列表。"""
        aliases = get_aliases("Unknown Person")
        assert aliases == []


class TestGetAllCanonicalNames:
    def test_returns_list(self):
        """get_all_canonical_names() 應回傳列表。"""
        result = get_all_canonical_names()
        assert isinstance(result, list)

    def test_canonical_names_match_aliases_keys(self):
        """get_all_canonical_names() 應回傳所有 POLITICIAN_ALIASES 的 key。"""
        result = get_all_canonical_names()
        expected = list(POLITICIAN_ALIASES.keys())
        assert set(result) == set(expected)

    def test_known_politicians_present(self):
        """關鍵議員應出現在 canonical names 列表中。"""
        all_names = get_all_canonical_names()
        for expected in ["David H McCormick", "Nancy Pelosi", "Susan M Collins"]:
            assert expected in all_names, f"'{expected}' 應在 canonical names 中"


class TestEdgeCases:
    """邊界情況測試。"""

    def test_empty_string_returns_empty(self):
        """空字串應回傳空字串（或清理後的空字串）。"""
        result = normalize_name("")
        assert isinstance(result, str)
        assert result == ""

    def test_single_word_name(self):
        """單詞名字不應觸發例外。"""
        result = normalize_name("Pelosi")
        assert isinstance(result, str)

    def test_name_with_iv_suffix(self):
        """含 IV 後綴的名字（如 Hagerty IV）應正確處理。"""
        result = normalize_name("Bill Hagerty")
        assert result == "William F Hagerty, IV"
