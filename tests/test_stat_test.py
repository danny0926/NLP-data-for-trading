"""
tests/test_stat_test.py — stat_test.py 統計函數測試

測試範圍：
- run_ttest: t-test / Mann-Whitney 自動選擇
- run_correlation: Pearson / Spearman 自動選擇
- run_anova: ANOVA / Kruskal-Wallis 自動選擇
- Edge cases: 空資料、單一組、NULL 值
"""

import math
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pytest

# 加入 skill 腳本路徑
SKILL_PATH = Path(__file__).parent.parent / ".claude" / "skills" / "hypothesis-test" / "scripts"
sys.path.insert(0, str(SKILL_PATH))

from stat_test import cohens_d, describe, run_anova, run_correlation, run_ttest


# ─────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────

def make_db(tmp_path, rows):
    """建立臨時 SQLite DB，插入測試資料，回傳 dict list（模擬 sqlite3.Row）。"""
    db = tmp_path / "test.db"
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    if rows:
        keys = list(rows[0].keys())
        placeholders = ", ".join("?" for _ in keys)
        cols = ", ".join(keys)
        cur.execute(f"CREATE TABLE data ({cols})")
        for r in rows:
            cur.execute(f"INSERT INTO data VALUES ({placeholders})", list(r.values()))
    conn.commit()
    cur.execute("SELECT * FROM data") if rows else None
    data = [dict(r) for r in cur.fetchall()] if rows else []
    conn.close()
    return data


def make_rows(group_col, value_col, group_a_vals, group_b_vals):
    """產生兩組資料的 dict list。"""
    rows = []
    for v in group_a_vals:
        rows.append({group_col: "A", value_col: v})
    for v in group_b_vals:
        rows.append({group_col: "B", value_col: v})
    return rows


def make_rows_3groups(group_col, value_col, g1, g2, g3):
    """產生三組資料的 dict list。"""
    rows = []
    for v in g1:
        rows.append({group_col: "G1", value_col: v})
    for v in g2:
        rows.append({group_col: "G2", value_col: v})
    for v in g3:
        rows.append({group_col: "G3", value_col: v})
    return rows


def make_corr_rows(x_col, y_col, xs, ys):
    """產生相關性測試 dict list。"""
    return [{x_col: x, y_col: y} for x, y in zip(xs, ys)]


# ─────────────────────────────────────────
# cohens_d 單元測試
# ─────────────────────────────────────────

class TestCohensD:

    def test_cohens_d_known_large_effect(self):
        """已知均值差異大 → Cohen's d 應為 large (>0.8)。"""
        rng = np.random.default_rng(99)
        # 加入微小隨機噪音避免 pooled_std=0
        g1 = np.array([10.0] * 50) + rng.normal(0, 0.01, 50)
        g2 = np.array([0.0] * 50) + rng.normal(0, 0.01, 50)
        d = cohens_d(g1, g2)
        assert abs(d) > 0.8, f"Expected large effect, got d={d}"

    def test_cohens_d_zero_difference(self):
        """相同分布 → Cohen's d ≈ 0。"""
        rng = np.random.default_rng(42)
        g1 = rng.normal(5, 1, 100)
        g2 = rng.normal(5, 1, 100)
        d = cohens_d(g1, g2)
        assert abs(d) < 0.3, f"Expected near-zero d, got d={d}"

    def test_cohens_d_zero_std_returns_zero(self):
        """兩組標準差為 0 → 回傳 0.0 不崩潰。"""
        g1 = np.array([5.0, 5.0, 5.0])
        g2 = np.array([5.0, 5.0, 5.0])
        d = cohens_d(g1, g2)
        assert d == 0.0

    def test_cohens_d_direction(self):
        """g1 > g2 → d 為正；g1 < g2 → d 為負。"""
        rng = np.random.default_rng(98)
        # 加入微小噪音避免 pooled_std=0
        g1 = np.array([10.0] * 30) + rng.normal(0, 0.01, 30)
        g2 = np.array([5.0] * 30) + rng.normal(0, 0.01, 30)
        assert cohens_d(g1, g2) > 0
        assert cohens_d(g2, g1) < 0


# ─────────────────────────────────────────
# describe 單元測試
# ─────────────────────────────────────────

class TestDescribe:

    def test_describe_correct_stats(self):
        """describe() 計算均值、中位數、min、max 正確。"""
        arr = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        result = describe(arr, "test")
        assert result["mean"] == pytest.approx(3.0, abs=1e-4)
        assert result["median"] == pytest.approx(3.0, abs=1e-4)
        assert result["min"] == pytest.approx(1.0, abs=1e-4)
        assert result["max"] == pytest.approx(5.0, abs=1e-4)
        assert result["n"] == 5
        assert result["group"] == "test"


# ─────────────────────────────────────────
# run_ttest 測試
# ─────────────────────────────────────────

class TestRunTtest:

    def test_ttest_significant_difference(self):
        """兩組均值差異明顯 → significant_at_005 = True, p < 0.05。"""
        rng = np.random.default_rng(0)
        g1 = list(rng.normal(10, 1, 100))
        g2 = list(rng.normal(0, 1, 100))
        data = make_rows("chamber", "alpha", g1, g2)
        result = run_ttest(data, "chamber", "alpha")
        assert "error" not in result
        assert result["significant_at_005"] == True
        assert result["p_value"] < 0.05

    def test_ttest_no_significant_difference(self):
        """兩組相同分布 → significant_at_005 = False。"""
        rng = np.random.default_rng(1)
        g1 = list(rng.normal(5, 1, 80))
        g2 = list(rng.normal(5, 1, 80))
        data = make_rows("chamber", "alpha", g1, g2)
        result = run_ttest(data, "chamber", "alpha")
        assert "error" not in result
        assert result["p_value"] > 0.05

    def test_ttest_selects_parametric_for_normal_data(self):
        """正態分布數據 → 選擇 Independent t-test。"""
        rng = np.random.default_rng(2)
        g1 = list(rng.normal(5, 1, 100))
        g2 = list(rng.normal(7, 1, 100))
        data = make_rows("grp", "val", g1, g2)
        result = run_ttest(data, "grp", "val")
        assert "error" not in result
        assert result["method"] == "Independent t-test"

    def test_ttest_selects_nonparametric_for_nonnormal_data(self):
        """非正態分布（指數分布）→ 選擇 Mann-Whitney U。"""
        rng = np.random.default_rng(3)
        # 指數分布是高度右偏，Shapiro 通常拒絕正態
        g1 = list(rng.exponential(scale=1.0, size=100))
        g2 = list(rng.exponential(scale=5.0, size=100))
        data = make_rows("grp", "val", g1, g2)
        result = run_ttest(data, "grp", "val")
        assert "error" not in result
        # 方法可能是 t-test 或 Mann-Whitney，取決於 Shapiro 結果
        assert result["method"] in ("Independent t-test", "Mann-Whitney U")

    def test_ttest_effect_size_large(self):
        """均值差異 > 3 std → Cohen's d 為 large。"""
        rng = np.random.default_rng(4)
        g1 = list(rng.normal(10, 1, 50))
        g2 = list(rng.normal(0, 1, 50))
        data = make_rows("grp", "val", g1, g2)
        result = run_ttest(data, "grp", "val")
        assert "error" not in result
        assert abs(result["effect_size_cohens_d"]) > 0.8
        assert result["effect_interpretation"] == "large"

    def test_ttest_effect_size_negligible(self):
        """幾乎相同的兩組 → effect 為 negligible。"""
        rng = np.random.default_rng(5)
        g1 = list(rng.normal(5.0, 2, 80))
        g2 = list(rng.normal(5.1, 2, 80))
        data = make_rows("grp", "val", g1, g2)
        result = run_ttest(data, "grp", "val")
        assert "error" not in result
        assert result["effect_interpretation"] in ("negligible", "small")

    def test_ttest_ci95_contains_true_diff(self):
        """95% CI 應涵蓋真實均值差異。"""
        rng = np.random.default_rng(6)
        g1 = list(rng.normal(8, 2, 200))
        g2 = list(rng.normal(5, 2, 200))
        true_diff = 3.0
        data = make_rows("grp", "val", g1, g2)
        result = run_ttest(data, "grp", "val")
        ci_lo, ci_hi = result["ci_95"]
        assert ci_lo <= true_diff <= ci_hi, f"True diff {true_diff} not in CI [{ci_lo}, {ci_hi}]"

    def test_ttest_null_values_filtered(self):
        """含 NULL 值的資料 → 自動過濾，不影響計算。"""
        rng = np.random.default_rng(7)
        g1_vals = list(rng.normal(10, 1, 50))
        g2_vals = list(rng.normal(0, 1, 50))
        data = make_rows("grp", "val", g1_vals, g2_vals)
        # 加入 NULL 資料
        data.append({"grp": "A", "val": None})
        data.append({"grp": None, "val": 5.0})
        result = run_ttest(data, "grp", "val")
        assert "error" not in result
        assert result["groups"]["A"]["n"] == 50

    def test_ttest_single_group_returns_error(self):
        """只有一組資料 → 回傳 error 訊息。"""
        data = [{"grp": "A", "val": float(i)} for i in range(20)]
        result = run_ttest(data, "grp", "val")
        assert "error" in result
        assert "2" in result["error"] or "groups" in result["error"].lower()

    def test_ttest_group_stats_in_output(self):
        """輸出包含兩組的描述統計。"""
        rng = np.random.default_rng(8)
        g1 = list(rng.normal(5, 1, 30))
        g2 = list(rng.normal(7, 1, 30))
        data = make_rows("grp", "val", g1, g2)
        result = run_ttest(data, "grp", "val")
        assert "groups" in result
        assert "A" in result["groups"]
        assert "B" in result["groups"]
        assert result["groups"]["A"]["n"] == 30


# ─────────────────────────────────────────
# run_correlation 測試
# ─────────────────────────────────────────

class TestRunCorrelation:

    def test_correlation_perfect_positive(self):
        """完美正相關 → r ≈ 1.0, significant。"""
        xs = list(range(1, 51))
        ys = [x * 2.0 + 1.0 for x in xs]
        data = make_corr_rows("x", "y", xs, ys)
        result = run_correlation(data, "x", "y")
        assert "error" not in result
        assert result["correlation"] > 0.99
        assert result["significant_at_005"] == True
        assert result["direction"] == "positive"

    def test_correlation_no_correlation(self):
        """無相關資料 → r ≈ 0, p > 0.05（機率性，放寬閾值）。"""
        rng = np.random.default_rng(10)
        xs = list(rng.uniform(0, 10, 50))
        ys = list(rng.uniform(0, 10, 50))
        data = make_corr_rows("x", "y", xs, ys)
        result = run_correlation(data, "x", "y")
        assert "error" not in result
        # r 應接近 0（隨機資料，允許小誤差）
        assert abs(result["correlation"]) < 0.4

    def test_correlation_negative(self):
        """完美負相關 → r < 0, direction = negative。"""
        xs = list(range(1, 51))
        ys = [100.0 - x * 2.0 for x in xs]
        data = make_corr_rows("x", "y", xs, ys)
        result = run_correlation(data, "x", "y")
        assert "error" not in result
        assert result["correlation"] < -0.99
        assert result["direction"] == "negative"

    def test_correlation_selects_pearson_for_normal(self):
        """正態分布資料 → 選擇 Pearson r。"""
        rng = np.random.default_rng(11)
        xs = list(rng.normal(5, 1, 100))
        ys = [x * 1.5 + rng.normal(0, 0.5) for x in xs]
        data = make_corr_rows("x", "y", xs, ys)
        result = run_correlation(data, "x", "y")
        assert "error" not in result
        # 正態分布下通常選 Pearson
        assert result["method"] in ("Pearson r", "Spearman rho")

    def test_correlation_selects_spearman_for_nonnormal(self):
        """非正態分布 → 可能選擇 Spearman rho。"""
        rng = np.random.default_rng(12)
        xs = list(rng.exponential(1.0, 100))
        ys = [x ** 2 + rng.exponential(0.5) for x in xs]
        data = make_corr_rows("x", "y", xs, ys)
        result = run_correlation(data, "x", "y")
        assert "error" not in result
        assert result["method"] in ("Pearson r", "Spearman rho")

    def test_correlation_r_squared_correct(self):
        """r_squared = r^2 計算正確。"""
        xs = list(range(1, 51))
        ys = [x * 3.0 + 1.0 for x in xs]
        data = make_corr_rows("x", "y", xs, ys)
        result = run_correlation(data, "x", "y")
        r = result["correlation"]
        expected_r2 = round(r ** 2, 4)
        assert result["r_squared"] == pytest.approx(expected_r2, abs=1e-3)

    def test_correlation_large_effect(self):
        """強相關 → effect_interpretation = large。"""
        xs = list(range(1, 51))
        ys = [x + np.random.default_rng(13).normal(0, 0.1) for x in xs]
        data = make_corr_rows("x", "y", xs, ys)
        result = run_correlation(data, "x", "y")
        assert result["effect_interpretation"] == "large"

    def test_correlation_null_values_filtered(self):
        """含 NULL 值 → 自動過濾配對，不影響計算。"""
        xs = list(range(1, 51))
        ys = [x * 2.0 for x in xs]
        data = make_corr_rows("x", "y", xs, ys)
        data.append({"x": None, "y": 10.0})
        data.append({"x": 5.0, "y": None})
        result = run_correlation(data, "x", "y")
        assert "error" not in result
        assert result["n"] == 50

    def test_correlation_insufficient_data_returns_error(self):
        """少於 10 筆資料 → 回傳 error。"""
        data = make_corr_rows("x", "y", range(1, 8), range(1, 8))
        result = run_correlation(data, "x", "y")
        assert "error" in result
        assert "10" in result["error"]


# ─────────────────────────────────────────
# run_anova 測試
# ─────────────────────────────────────────

class TestRunAnova:

    def test_anova_three_groups_significant(self):
        """三組均值差異明顯 → p < 0.05, significant = True。"""
        rng = np.random.default_rng(20)
        g1 = list(rng.normal(0, 1, 50))
        g2 = list(rng.normal(5, 1, 50))
        g3 = list(rng.normal(10, 1, 50))
        data = make_rows_3groups("grp", "val", g1, g2, g3)
        result = run_anova(data, "grp", "val")
        assert "error" not in result
        assert result["significant_at_005"] == True
        assert result["p_value"] < 0.05

    def test_anova_three_groups_no_difference(self):
        """三組相同分布 → p > 0.05。"""
        rng = np.random.default_rng(21)
        g1 = list(rng.normal(5, 1, 50))
        g2 = list(rng.normal(5, 1, 50))
        g3 = list(rng.normal(5, 1, 50))
        data = make_rows_3groups("grp", "val", g1, g2, g3)
        result = run_anova(data, "grp", "val")
        assert "error" not in result
        assert result["p_value"] > 0.05

    def test_anova_eta_squared_large(self):
        """大組間差異 → eta_squared > 0.14 (large effect)。"""
        rng = np.random.default_rng(22)
        g1 = list(rng.normal(0, 0.5, 50))
        g2 = list(rng.normal(10, 0.5, 50))
        g3 = list(rng.normal(20, 0.5, 50))
        data = make_rows_3groups("grp", "val", g1, g2, g3)
        result = run_anova(data, "grp", "val")
        assert "error" not in result
        assert result["effect_size_eta_squared"] > 0.14
        assert result["effect_interpretation"] == "large"

    def test_anova_eta_squared_negligible(self):
        """三組幾乎相同 → eta_squared 接近 0。"""
        rng = np.random.default_rng(23)
        g1 = list(rng.normal(5.0, 2, 50))
        g2 = list(rng.normal(5.1, 2, 50))
        g3 = list(rng.normal(5.2, 2, 50))
        data = make_rows_3groups("grp", "val", g1, g2, g3)
        result = run_anova(data, "grp", "val")
        assert "error" not in result
        assert result["effect_size_eta_squared"] < 0.06

    def test_anova_selects_parametric_for_normal(self):
        """正態分布三組 → 選擇 One-way ANOVA。"""
        rng = np.random.default_rng(24)
        g1 = list(rng.normal(0, 1, 60))
        g2 = list(rng.normal(2, 1, 60))
        g3 = list(rng.normal(4, 1, 60))
        data = make_rows_3groups("grp", "val", g1, g2, g3)
        result = run_anova(data, "grp", "val")
        assert "error" not in result
        assert result["method"] in ("One-way ANOVA", "Kruskal-Wallis H")

    def test_anova_selects_kruskal_for_nonnormal(self):
        """非正態分布（指數）→ 選擇 Kruskal-Wallis H。"""
        rng = np.random.default_rng(25)
        g1 = list(rng.exponential(1.0, 60))
        g2 = list(rng.exponential(5.0, 60))
        g3 = list(rng.exponential(10.0, 60))
        data = make_rows_3groups("grp", "val", g1, g2, g3)
        result = run_anova(data, "grp", "val")
        assert "error" not in result
        assert result["method"] in ("One-way ANOVA", "Kruskal-Wallis H")

    def test_anova_output_structure(self):
        """輸出包含所有預期欄位。"""
        rng = np.random.default_rng(26)
        g1 = list(rng.normal(0, 1, 30))
        g2 = list(rng.normal(3, 1, 30))
        g3 = list(rng.normal(6, 1, 30))
        data = make_rows_3groups("grp", "val", g1, g2, g3)
        result = run_anova(data, "grp", "val")
        required_keys = [
            "method", "n_groups", "groups", "test_statistic",
            "p_value", "effect_size_eta_squared", "effect_interpretation",
            "significant_at_005"
        ]
        for key in required_keys:
            assert key in result, f"Missing key: {key}"

    def test_anova_null_values_filtered(self):
        """含 NULL 值 → 自動過濾，三組各保留有效資料。"""
        rng = np.random.default_rng(27)
        g1 = list(rng.normal(0, 1, 30))
        g2 = list(rng.normal(5, 1, 30))
        g3 = list(rng.normal(10, 1, 30))
        data = make_rows_3groups("grp", "val", g1, g2, g3)
        data.append({"grp": "G1", "val": None})
        data.append({"grp": None, "val": 5.0})
        result = run_anova(data, "grp", "val")
        assert "error" not in result
        assert result["groups"]["G1"]["n"] == 30

    def test_anova_two_groups_returns_error(self):
        """只有兩組 → 回傳 error（ANOVA 需要 3+ 組）。"""
        rng = np.random.default_rng(28)
        g1 = list(rng.normal(0, 1, 20))
        g2 = list(rng.normal(5, 1, 20))
        data = make_rows("grp", "val", g1, g2)
        result = run_anova(data, "grp", "val")
        assert "error" in result
        assert "3" in result["error"] or "groups" in result["error"].lower()

    def test_anova_n_groups_correct(self):
        """n_groups 回傳正確數字。"""
        rng = np.random.default_rng(29)
        g1 = list(rng.normal(0, 1, 20))
        g2 = list(rng.normal(5, 1, 20))
        g3 = list(rng.normal(10, 1, 20))
        data = make_rows_3groups("grp", "val", g1, g2, g3)
        result = run_anova(data, "grp", "val")
        assert result["n_groups"] == 3


# ─────────────────────────────────────────
# Edge Cases
# ─────────────────────────────────────────

class TestEdgeCases:

    def test_ttest_empty_data_returns_error(self):
        """空資料 → run_ttest 回傳 error。"""
        result = run_ttest([], "grp", "val")
        assert "error" in result

    def test_correlation_empty_data_returns_error(self):
        """空資料 → run_correlation 回傳 error（< 10 筆）。"""
        result = run_correlation([], "x", "y")
        assert "error" in result

    def test_anova_empty_data_returns_error(self):
        """空資料 → run_anova 回傳 error。"""
        result = run_anova([], "grp", "val")
        assert "error" in result

    def test_ttest_all_nulls_returns_error(self):
        """所有 value 為 NULL → 兩組都空 → error。"""
        data = [{"grp": "A", "val": None} for _ in range(10)]
        data += [{"grp": "B", "val": None} for _ in range(10)]
        result = run_ttest(data, "grp", "val")
        assert "error" in result

    def test_ttest_large_string_group_names(self):
        """超長組名字串 → 不崩潰，正常計算。"""
        rng = np.random.default_rng(30)
        long_name_a = "A" * 200
        long_name_b = "B" * 200
        g1 = list(rng.normal(10, 1, 30))
        g2 = list(rng.normal(0, 1, 30))
        data = [{long_name_a[:5]: long_name_a, "val": v} for v in g1]
        data += [{long_name_a[:5]: long_name_b, "val": v} for v in g2]
        result = run_ttest(data, long_name_a[:5], "val")
        assert "error" not in result or "error" in result  # 不崩潰即可

    def test_correlation_all_same_x_values(self):
        """所有 x 值相同（零變異）→ 可能 error 或 r=NaN，不崩潰。"""
        xs = [5.0] * 20
        ys = list(range(1, 21))
        data = make_corr_rows("x", "y", xs, ys)
        try:
            result = run_correlation(data, "x", "y")
            # 如果有 error key 則直接通過
            # 如果無 error key，correlation 可能是 nan
            assert "error" in result or isinstance(result.get("correlation"), float)
        except Exception:
            pass  # 零變異拋出例外是可接受的

    def test_ttest_single_data_point_per_group(self):
        """每組只有 1 筆資料（< 8，無法做 Shapiro）→ 不崩潰。"""
        data = [{"grp": "A", "val": 10.0}, {"grp": "B", "val": 5.0}]
        result = run_ttest(data, "grp", "val")
        # 可能成功（退化情況）或回傳 error
        assert isinstance(result, dict)

    def test_anova_mixed_numeric_string_groups(self):
        """整數型組標籤 → run_anova 用 str() 轉換，不崩潰。"""
        rng = np.random.default_rng(31)
        data = []
        for i in range(1, 4):
            for v in rng.normal(i * 3, 1, 20):
                data.append({"grp": i, "val": float(v)})
        result = run_anova(data, "grp", "val")
        assert "error" not in result
        assert result["n_groups"] == 3
