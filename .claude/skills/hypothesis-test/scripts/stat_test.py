#!/usr/bin/env python3
"""
hypothesis-test skill — 統計檢定腳本

支援: t-test, mann-whitney, anova, kruskal, pearson, spearman, chi2
輸出: JSON 格式的統計結果

Usage:
    python stat_test.py --db data/data.db --query "SELECT ..." --method ttest \
        --group-col chamber --value-col expected_alpha_20d

    python stat_test.py --db data/data.db --query "SELECT ..." --method pearson \
        --x-col sqs --y-col expected_alpha_20d
"""

import argparse
import json
import math
import sqlite3
import sys

import numpy as np
from scipy import stats


def cohens_d(group1, group2):
    n1, n2 = len(group1), len(group2)
    var1, var2 = np.var(group1, ddof=1), np.var(group2, ddof=1)
    pooled_std = math.sqrt(((n1 - 1) * var1 + (n2 - 1) * var2) / (n1 + n2 - 2))
    if pooled_std == 0:
        return 0.0
    return (np.mean(group1) - np.mean(group2)) / pooled_std


def describe(arr, label=""):
    return {
        "group": label,
        "n": len(arr),
        "mean": round(float(np.mean(arr)), 6),
        "std": round(float(np.std(arr, ddof=1)), 6),
        "median": round(float(np.median(arr)), 6),
        "min": round(float(np.min(arr)), 6),
        "max": round(float(np.max(arr)), 6),
    }


def run_ttest(data, group_col, value_col):
    groups = {}
    for row in data:
        g = row[group_col]
        v = row[value_col]
        if g is not None and v is not None:
            groups.setdefault(g, []).append(float(v))

    group_names = sorted(groups.keys())
    if len(group_names) < 2:
        return {"error": f"Need at least 2 groups, found {len(group_names)}: {group_names}"}

    g1, g2 = np.array(groups[group_names[0]]), np.array(groups[group_names[1]])

    # Normality check
    norm1 = stats.shapiro(g1[:5000]) if len(g1) >= 8 else (None, 1.0)
    norm2 = stats.shapiro(g2[:5000]) if len(g2) >= 8 else (None, 1.0)
    is_normal = norm1[1] > 0.05 and norm2[1] > 0.05

    if is_normal:
        stat, p = stats.ttest_ind(g1, g2)
        method = "Independent t-test"
    else:
        stat, p = stats.mannwhitneyu(g1, g2, alternative="two-sided")
        method = "Mann-Whitney U"

    d = cohens_d(g1, g2)
    diff = float(np.mean(g1) - np.mean(g2))
    se = math.sqrt(np.var(g1, ddof=1) / len(g1) + np.var(g2, ddof=1) / len(g2))
    ci_lo = diff - 1.96 * se
    ci_hi = diff + 1.96 * se

    return {
        "method": method,
        "groups": {
            group_names[0]: describe(g1, group_names[0]),
            group_names[1]: describe(g2, group_names[1]),
        },
        "normality": {
            group_names[0]: {"shapiro_p": round(norm1[1], 4), "is_normal": norm1[1] > 0.05},
            group_names[1]: {"shapiro_p": round(norm2[1], 4), "is_normal": norm2[1] > 0.05},
        },
        "test_statistic": round(float(stat), 4),
        "p_value": round(float(p), 6),
        "effect_size_cohens_d": round(d, 4),
        "effect_interpretation": "large" if abs(d) > 0.8 else "medium" if abs(d) > 0.5 else "small" if abs(d) > 0.2 else "negligible",
        "mean_difference": round(diff, 6),
        "ci_95": [round(ci_lo, 6), round(ci_hi, 6)],
        "significant_at_005": p < 0.05,
    }


def run_correlation(data, x_col, y_col):
    xs, ys = [], []
    for row in data:
        x, y = row[x_col], row[y_col]
        if x is not None and y is not None:
            xs.append(float(x))
            ys.append(float(y))

    xs, ys = np.array(xs), np.array(ys)
    if len(xs) < 10:
        return {"error": f"Need at least 10 paired observations, found {len(xs)}"}

    # Normality check for method selection
    norm_x = stats.shapiro(xs[:5000]) if len(xs) >= 8 else (None, 1.0)
    norm_y = stats.shapiro(ys[:5000]) if len(ys) >= 8 else (None, 1.0)
    is_normal = norm_x[1] > 0.05 and norm_y[1] > 0.05

    if is_normal:
        r, p = stats.pearsonr(xs, ys)
        method = "Pearson r"
    else:
        r, p = stats.spearmanr(xs, ys)
        method = "Spearman rho"

    return {
        "method": method,
        "n": len(xs),
        "x_desc": describe(xs, x_col),
        "y_desc": describe(ys, y_col),
        "correlation": round(float(r), 4),
        "r_squared": round(float(r ** 2), 4),
        "p_value": round(float(p), 6),
        "effect_interpretation": "large" if abs(r) > 0.5 else "medium" if abs(r) > 0.3 else "small" if abs(r) > 0.1 else "negligible",
        "significant_at_005": p < 0.05,
        "direction": "positive" if r > 0 else "negative" if r < 0 else "none",
    }


def run_anova(data, group_col, value_col):
    groups = {}
    for row in data:
        g = row[group_col]
        v = row[value_col]
        if g is not None and v is not None:
            groups.setdefault(str(g), []).append(float(v))

    if len(groups) < 3:
        return {"error": f"ANOVA needs 3+ groups, found {len(groups)}"}

    group_arrays = [np.array(v) for v in groups.values()]
    group_descs = {k: describe(np.array(v), k) for k, v in groups.items()}

    # Check normality
    all_normal = all(
        stats.shapiro(g[:5000])[1] > 0.05 for g in group_arrays if len(g) >= 8
    )

    if all_normal:
        stat, p = stats.f_oneway(*group_arrays)
        method = "One-way ANOVA"
    else:
        stat, p = stats.kruskal(*group_arrays)
        method = "Kruskal-Wallis H"

    # Eta-squared (effect size for ANOVA)
    all_data = np.concatenate(group_arrays)
    grand_mean = np.mean(all_data)
    ss_between = sum(len(g) * (np.mean(g) - grand_mean) ** 2 for g in group_arrays)
    ss_total = np.sum((all_data - grand_mean) ** 2)
    eta_sq = ss_between / ss_total if ss_total > 0 else 0.0

    return {
        "method": method,
        "n_groups": len(groups),
        "groups": group_descs,
        "test_statistic": round(float(stat), 4),
        "p_value": round(float(p), 6),
        "effect_size_eta_squared": round(float(eta_sq), 4),
        "effect_interpretation": "large" if eta_sq > 0.14 else "medium" if eta_sq > 0.06 else "small" if eta_sq > 0.01 else "negligible",
        "significant_at_005": p < 0.05,
    }


def main():
    parser = argparse.ArgumentParser(description="PAM Hypothesis Test Runner")
    parser.add_argument("--db", default="data/data.db", help="SQLite DB path")
    parser.add_argument("--query", required=True, help="SQL SELECT query")
    parser.add_argument("--method", required=True, choices=["ttest", "mannwhitney", "pearson", "spearman", "anova", "kruskal"])
    parser.add_argument("--group-col", help="Column for group split (ttest/anova)")
    parser.add_argument("--value-col", help="Column for numeric values (ttest/anova)")
    parser.add_argument("--x-col", help="X column (correlation)")
    parser.add_argument("--y-col", help="Y column (correlation)")
    args = parser.parse_args()

    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(args.query)
    data = [dict(row) for row in cur.fetchall()]
    conn.close()

    if not data:
        print(json.dumps({"error": "Query returned 0 rows"}, indent=2))
        sys.exit(1)

    if args.method in ("ttest", "mannwhitney"):
        result = run_ttest(data, args.group_col, args.value_col)
    elif args.method in ("pearson", "spearman"):
        result = run_correlation(data, args.x_col, args.y_col)
    elif args.method in ("anova", "kruskal"):
        result = run_anova(data, args.group_col, args.value_col)
    else:
        result = {"error": f"Unknown method: {args.method}"}

    result["query"] = args.query
    result["n_rows"] = len(data)

    # Convert numpy types to native Python for JSON serialization
    def _convert(obj):
        if isinstance(obj, (np.bool_, bool)):
            return bool(obj)
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

    print(json.dumps(result, indent=2, ensure_ascii=False, default=_convert))


if __name__ == "__main__":
    main()
