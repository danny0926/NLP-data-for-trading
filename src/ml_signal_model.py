"""
ML Signal Prediction Model — 國會交易訊號特徵重要性分析

探索性機器學習分析：利用 SQS 維度、政治人物排名、申報延遲、
交易金額、Fama-French 因子等特徵，預測訊號強度與品質等級。

重點產出：特徵重要性排名（哪些因子最影響訊號品質？）
"""

import sqlite3
import warnings
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.ensemble import (
    GradientBoostingClassifier,
    RandomForestClassifier,
    RandomForestRegressor,
)
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    mean_absolute_error,
    r2_score,
)
from sklearn.model_selection import KFold, cross_val_score
from sklearn.preprocessing import LabelEncoder

warnings.filterwarnings("ignore", category=FutureWarning)

# ── 專案路徑 ──
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "data" / "data.db"
REPORT_DIR = PROJECT_ROOT / "docs" / "reports"
PLOT_DIR = PROJECT_ROOT / "docs" / "plots"


# ═══════════════════════════════════════════════════════════════
# 1. 特徵工程
# ═══════════════════════════════════════════════════════════════

AMOUNT_ENCODING = {
    "$1,001 - $15,000": 1,
    "$15,001 - $50,000": 2,
    "$50,001 - $100,000": 3,
    "$100,001 - $250,000": 4,
    "$250,001 - $500,000": 5,
    "$500,001 - $1,000,000": 6,
    "$1,000,001 - $5,000,000": 7,
    "$5,000,001 - $25,000,000": 8,
    "$25,000,001 - $50,000,000": 9,
}


def load_feature_matrix(db_path: Optional[str] = None) -> pd.DataFrame:
    """從 SQLite 建立特徵矩陣，跨表 JOIN 整合所有可用特徵。

    以 signal_quality_scores + congress_trades 為基底（404 筆），
    LEFT JOIN alpha_signals 取 signal_strength，確保 Bronze/Discard 也包含在內。
    """
    conn = sqlite3.connect(str(db_path or DB_PATH))

    query = """
    SELECT
        -- 識別欄位
        s.trade_id,
        c.ticker,
        c.politician_name,

        -- 目標變數
        s.sqs            AS sqs_score,
        s.grade          AS sqs_grade,
        a.signal_strength,
        a.confidence,

        -- SQS 維度特徵
        s.actionability,
        s.timeliness,
        s.conviction     AS sqs_conviction,
        s.information_edge,
        s.market_impact,

        -- 交易基本特徵
        c.transaction_type,
        c.chamber,
        c.amount_range,
        c.asset_type,
        c.transaction_date,
        c.filing_date,

        -- alpha_signals 額外特徵
        a.direction,
        a.filing_lag_days,
        a.has_convergence,
        a.convergence_bonus,

        -- 政治人物排名特徵
        p.pis_total,
        p.pis_activity     AS pis_activity,
        p.pis_conviction   AS pis_conviction,
        p.pis_diversification,
        p.pis_timing,
        p.total_trades     AS politician_total_trades,
        p.avg_filing_lag_days AS politician_avg_lag,

        -- Fama-French 因子特徵
        f.beta_mkt,
        f.beta_smb,
        f.beta_hml,
        f.r_squared        AS ff_r_squared,
        f.ff3_car_5d,
        f.ff3_car_20d,
        f.mkt_car_5d,
        f.mkt_car_20d,
        f.alpha_est        AS ff_alpha

    FROM signal_quality_scores s
    JOIN congress_trades c       ON s.trade_id = c.id
    LEFT JOIN alpha_signals a    ON s.trade_id = a.trade_id
    LEFT JOIN politician_rankings p ON c.politician_name = p.politician_name
    LEFT JOIN fama_french_results f ON c.ticker = f.ticker
                                    AND c.politician_name = f.politician_name
                                    AND c.transaction_date = f.transaction_date
    """

    df = pd.read_sql_query(query, conn)
    conn.close()

    # ── 計算 filing_lag（若 alpha_signals 缺失則自己算）──
    if "filing_lag_days" in df.columns:
        mask = df["filing_lag_days"].isna()
        if mask.any():
            td = pd.to_datetime(df.loc[mask, "transaction_date"], errors="coerce")
            fd = pd.to_datetime(df.loc[mask, "filing_date"], errors="coerce")
            df.loc[mask, "filing_lag_days"] = (fd - td).dt.days

    # ── 編碼分類特徵 ──
    df["amount_encoded"] = df["amount_range"].map(AMOUNT_ENCODING).fillna(0).astype(int)
    df["chamber_encoded"] = (df["chamber"] == "Senate").astype(int)
    df["is_buy"] = df["transaction_type"].isin(["Buy", "Purchase"]).astype(int)
    df["direction_encoded"] = df["direction"].fillna("LONG").apply(
        lambda x: 1 if x == "LONG" else 0
    )

    # ── 編碼 grade 為二元分類（Gold/Silver = 1, Bronze/Discard = 0）──
    df["grade_binary"] = df["sqs_grade"].isin(["Gold", "Silver"]).astype(int)

    # ── 填補 PIS 缺失值（無排名的政治人物用中位數）──
    pis_cols = ["pis_total", "pis_activity", "pis_conviction",
                "pis_diversification", "pis_timing",
                "politician_total_trades", "politician_avg_lag"]
    for col in pis_cols:
        df[col] = df[col].fillna(df[col].median())

    # ── 填補 FF 缺失值 ──
    ff_cols = ["beta_mkt", "beta_smb", "beta_hml", "ff_r_squared",
               "ff3_car_5d", "ff3_car_20d", "mkt_car_5d", "mkt_car_20d", "ff_alpha"]
    for col in ff_cols:
        df[col] = df[col].fillna(0.0)

    # ── 填補其他數值缺失 ──
    df["filing_lag_days"] = df["filing_lag_days"].fillna(df["filing_lag_days"].median())
    df["has_convergence"] = df["has_convergence"].fillna(0).astype(int)
    df["convergence_bonus"] = df["convergence_bonus"].fillna(0.0)

    return df


def get_feature_columns(include_sqs_dims: bool = True) -> list:
    """回傳用於建模的特徵欄位名稱。

    Args:
        include_sqs_dims: 是否包含 SQS 子維度。
            回歸預測 SQS 分數時設為 False（避免 target leakage），
            分類預測 Grade 時設為 True。
    """
    features = []

    if include_sqs_dims:
        # SQS 維度（與 SQS score 有直接組成關係，僅用於分類）
        features += [
            "actionability", "timeliness", "sqs_conviction",
            "information_edge", "market_impact",
        ]

    features += [
        # 交易特徵
        "amount_encoded", "chamber_encoded", "is_buy",
        "direction_encoded", "filing_lag_days",
        # 政治人物特徵
        "pis_total", "pis_activity", "pis_conviction",
        "pis_diversification", "pis_timing",
        "politician_total_trades", "politician_avg_lag",
        # 收斂訊號
        "has_convergence", "convergence_bonus",
        # Fama-French 因子
        "beta_mkt", "beta_smb", "beta_hml",
        "ff_r_squared", "ff_alpha",
    ]
    return features


# ═══════════════════════════════════════════════════════════════
# 2. 模型訓練
# ═══════════════════════════════════════════════════════════════

def train_regression_model(
    df: pd.DataFrame,
    target: str = "sqs_score",
    n_folds: int = 5,
) -> Tuple[RandomForestRegressor, dict]:
    """RandomForest 回歸模型預測 SQS 分數（所有 404 筆皆有）。

    排除 SQS 子維度以避免 target leakage（SQS = f(子維度)）。
    """
    features = get_feature_columns(include_sqs_dims=False)
    X = df[features].values
    y = df[target].values

    model = RandomForestRegressor(
        n_estimators=200,
        max_depth=8,
        min_samples_leaf=10,
        random_state=42,
        n_jobs=-1,
    )

    # 5-fold CV
    kf = KFold(n_splits=n_folds, shuffle=True, random_state=42)
    r2_scores = cross_val_score(model, X, y, cv=kf, scoring="r2")
    mae_scores = -cross_val_score(model, X, y, cv=kf, scoring="neg_mean_absolute_error")

    # 全量訓練（用於特徵重要性）
    model.fit(X, y)
    y_pred = model.predict(X)

    results = {
        "cv_r2_mean": float(np.mean(r2_scores)),
        "cv_r2_std": float(np.std(r2_scores)),
        "cv_r2_scores": r2_scores.tolist(),
        "cv_mae_mean": float(np.mean(mae_scores)),
        "cv_mae_std": float(np.std(mae_scores)),
        "train_r2": float(r2_score(y, y_pred)),
        "train_mae": float(mean_absolute_error(y, y_pred)),
        "feature_importance": dict(zip(features, model.feature_importances_.tolist())),
    }

    return model, results


def train_classification_model(
    df: pd.DataFrame,
    n_folds: int = 5,
) -> Tuple[GradientBoostingClassifier, dict]:
    """GradientBoosting 分類模型預測品質等級（Gold/Silver vs Bronze/Discard）。"""
    features = get_feature_columns(include_sqs_dims=True)
    X = df[features].values
    y = df["grade_binary"].values

    model = GradientBoostingClassifier(
        n_estimators=150,
        max_depth=4,
        min_samples_leaf=10,
        learning_rate=0.1,
        random_state=42,
    )

    kf = KFold(n_splits=n_folds, shuffle=True, random_state=42)
    acc_scores = cross_val_score(model, X, y, cv=kf, scoring="accuracy")
    f1_scores = cross_val_score(model, X, y, cv=kf, scoring="f1")

    # 全量訓練
    model.fit(X, y)
    y_pred = model.predict(X)

    results = {
        "cv_accuracy_mean": float(np.mean(acc_scores)),
        "cv_accuracy_std": float(np.std(acc_scores)),
        "cv_accuracy_scores": acc_scores.tolist(),
        "cv_f1_mean": float(np.mean(f1_scores)),
        "cv_f1_std": float(np.std(f1_scores)),
        "train_accuracy": float(accuracy_score(y, y_pred)),
        "classification_report": classification_report(
            y, y_pred, target_names=["Bronze/Discard", "Gold/Silver"], output_dict=True
        ),
        "feature_importance": dict(zip(features, model.feature_importances_.tolist())),
        "class_distribution": {
            "Gold/Silver": int(np.sum(y == 1)),
            "Bronze/Discard": int(np.sum(y == 0)),
        },
    }

    return model, results


# ═══════════════════════════════════════════════════════════════
# 3. 特徵重要性分析
# ═══════════════════════════════════════════════════════════════

def analyze_feature_importance(
    reg_results: dict,
    clf_results: dict,
) -> pd.DataFrame:
    """合併回歸與分類模型的特徵重要性，計算綜合排名。

    注意：回歸模型排除了 SQS 子維度（避免 target leakage），
    因此兩個模型的特徵集不完全相同。合併時用 outer join。
    """
    reg_imp = pd.Series(reg_results["feature_importance"], name="regression")
    clf_imp = pd.Series(clf_results["feature_importance"], name="classification")

    fi = pd.DataFrame({"regression": reg_imp, "classification": clf_imp})

    # 填補 NaN（回歸沒有 SQS 維度的 importance）
    fi["regression"] = fi["regression"].fillna(0.0)
    fi["classification"] = fi["classification"].fillna(0.0)

    # 正規化到 0-1
    reg_max = fi["regression"].max()
    clf_max = fi["classification"].max()
    fi["reg_norm"] = fi["regression"] / reg_max if reg_max > 0 else 0.0
    fi["clf_norm"] = fi["classification"] / clf_max if clf_max > 0 else 0.0

    # 綜合分數：有兩個模型分數的取平均，只有一個的取該值
    has_reg = fi["regression"] > 0
    has_clf = fi["classification"] > 0
    fi["combined_score"] = 0.0
    both = has_reg & has_clf
    fi.loc[both, "combined_score"] = (fi.loc[both, "reg_norm"] + fi.loc[both, "clf_norm"]) / 2
    fi.loc[~has_reg & has_clf, "combined_score"] = fi.loc[~has_reg & has_clf, "clf_norm"]
    fi.loc[has_reg & ~has_clf, "combined_score"] = fi.loc[has_reg & ~has_clf, "reg_norm"]

    fi = fi.sort_values("combined_score", ascending=False)
    fi["rank"] = range(1, len(fi) + 1)

    return fi


# ═══════════════════════════════════════════════════════════════
# 4. 視覺化
# ═══════════════════════════════════════════════════════════════

def plot_feature_importance(fi_df: pd.DataFrame, save_path: Optional[str] = None):
    """繪製特徵重要性雙柱狀圖。"""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(16, 8))

    # 回歸模型
    sorted_reg = fi_df.sort_values("regression", ascending=True)
    axes[0].barh(sorted_reg.index, sorted_reg["regression"], color="#2196F3", alpha=0.8)
    axes[0].set_title("RandomForest Regression\n(Target: SQS Score)", fontsize=12)
    axes[0].set_xlabel("Feature Importance")

    # 分類模型
    sorted_clf = fi_df.sort_values("classification", ascending=True)
    axes[1].barh(sorted_clf.index, sorted_clf["classification"], color="#FF5722", alpha=0.8)
    axes[1].set_title("GradientBoosting Classification\n(Target: Gold/Silver vs Bronze/Discard)", fontsize=12)
    axes[1].set_xlabel("Feature Importance")

    plt.suptitle("Congressional Trading Signal — Feature Importance Analysis",
                 fontsize=14, fontweight="bold", y=1.02)
    plt.tight_layout()

    path = save_path or str(PLOT_DIR / "ml_feature_importance.png")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    return path


def plot_combined_importance(fi_df: pd.DataFrame, save_path: Optional[str] = None):
    """繪製綜合特徵重要性排名圖。"""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    sorted_df = fi_df.sort_values("combined_score", ascending=True)

    fig, ax = plt.subplots(figsize=(12, 8))

    bars = ax.barh(sorted_df.index, sorted_df["combined_score"],
                   color=["#4CAF50" if v > 0.5 else "#FFC107" if v > 0.25 else "#9E9E9E"
                          for v in sorted_df["combined_score"]],
                   alpha=0.85)

    ax.set_xlabel("Combined Importance Score (normalized)", fontsize=11)
    ax.set_title("Combined Feature Importance Ranking\n(Regression + Classification Average)",
                 fontsize=13, fontweight="bold")

    for bar, val in zip(bars, sorted_df["combined_score"]):
        ax.text(bar.get_width() + 0.01, bar.get_y() + bar.get_height() / 2,
                f"{val:.3f}", va="center", fontsize=9)

    plt.tight_layout()

    path = save_path or str(PLOT_DIR / "ml_combined_importance.png")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    return path


# ═══════════════════════════════════════════════════════════════
# 5. 預測儲存
# ═══════════════════════════════════════════════════════════════

def save_predictions_to_db(
    df: pd.DataFrame,
    reg_model: RandomForestRegressor,
    clf_model: GradientBoostingClassifier,
    db_path: Optional[str] = None,
):
    """將模型預測結果存入 ml_predictions 表。"""
    conn = sqlite3.connect(str(db_path or DB_PATH))
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ml_predictions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        trade_id TEXT,
        ticker TEXT,
        politician_name TEXT,
        actual_sqs_score REAL,
        predicted_sqs_score REAL,
        actual_grade_binary INTEGER,
        predicted_grade_binary INTEGER,
        predicted_grade_proba REAL,
        model_version TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    reg_features = get_feature_columns(include_sqs_dims=False)
    clf_features = get_feature_columns(include_sqs_dims=True)

    pred_sqs = reg_model.predict(df[reg_features].values)
    pred_grade = clf_model.predict(df[clf_features].values)
    pred_proba = clf_model.predict_proba(df[clf_features].values)[:, 1]

    version = datetime.now().strftime("v%Y%m%d")

    rows = []
    for idx_pos, (i, row) in enumerate(df.iterrows()):
        rows.append((
            row["trade_id"],
            row["ticker"],
            row["politician_name"],
            float(row["sqs_score"]),
            float(pred_sqs[idx_pos]),
            int(row["grade_binary"]),
            int(pred_grade[idx_pos]),
            float(pred_proba[idx_pos]),
            version,
        ))

    cursor.executemany("""
    INSERT INTO ml_predictions
        (trade_id, ticker, politician_name, actual_sqs_score,
         predicted_sqs_score, actual_grade_binary, predicted_grade_binary,
         predicted_grade_proba, model_version)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, rows)

    conn.commit()
    print(f"  已儲存 {len(rows)} 筆預測到 ml_predictions 表 (版本: {version})")
    conn.close()
    return len(rows)


# ═══════════════════════════════════════════════════════════════
# 6. 報告生成
# ═══════════════════════════════════════════════════════════════

def generate_report(
    df: pd.DataFrame,
    fi_df: pd.DataFrame,
    reg_results: dict,
    clf_results: dict,
    plot_paths: dict,
) -> str:
    """生成 Markdown 研究報告。"""
    today = datetime.now().strftime("%Y-%m-%d")
    n_samples = len(df)

    # Top features
    top_features = fi_df.head(10)

    report = f"""# ML Feature Importance Analysis Report
# 國會交易訊號 — 機器學習特徵重要性分析

**Generated**: {today}
**Samples**: {n_samples}
**Models**: RandomForestRegressor, GradientBoostingClassifier

---

## Executive Summary

本報告使用機器學習模型分析國會交易訊號中各特徵的重要性。
透過 {n_samples} 筆交易資料，我們識別出影響訊號品質分數（SQS Score）
與品質等級（SQS Grade）的關鍵因子。

**核心發現**：
"""

    # Top 3 findings
    top3 = fi_df.head(3)
    for rank, (feat, row) in enumerate(top3.iterrows(), 1):
        report += f"- **#{rank} {feat}** — 綜合重要性分數 {row['combined_score']:.3f}\n"

    report += f"""
---

## 1. Feature Importance Ranking (Top 10)

| Rank | Feature | Regression | Classification | Combined |
|------|---------|-----------|---------------|----------|
"""
    for _, row in top_features.iterrows():
        report += (
            f"| {int(row['rank'])} | {row.name} | "
            f"{row['regression']:.4f} | {row['classification']:.4f} | "
            f"{row['combined_score']:.3f} |\n"
        )

    report += f"""
### Feature Categories Summary

| Category | Features | Avg Combined Score |
|----------|----------|-------------------|
"""
    # 分類統計
    categories = {
        "SQS Dimensions": ["actionability", "timeliness", "sqs_conviction",
                           "information_edge", "market_impact"],
        "Trade Attributes": ["amount_encoded", "chamber_encoded", "is_buy",
                             "direction_encoded", "filing_lag_days"],
        "Politician Profile": ["pis_total", "pis_activity", "pis_conviction",
                               "pis_diversification", "pis_timing",
                               "politician_total_trades", "politician_avg_lag"],
        "Convergence": ["has_convergence", "convergence_bonus"],
        "Fama-French": ["beta_mkt", "beta_smb", "beta_hml",
                        "ff_r_squared", "ff_alpha"],
    }
    for cat, feats in categories.items():
        avgs = fi_df.loc[fi_df.index.isin(feats), "combined_score"].mean()
        n = len([f for f in feats if f in fi_df.index])
        report += f"| {cat} | {n} features | {avgs:.3f} |\n"

    report += f"""
---

## 2. Regression Model (Signal Strength Prediction)

| Metric | Value |
|--------|-------|
| CV R2 (mean ± std) | {reg_results['cv_r2_mean']:.4f} ± {reg_results['cv_r2_std']:.4f} |
| CV MAE (mean ± std) | {reg_results['cv_mae_mean']:.4f} ± {reg_results['cv_mae_std']:.4f} |
| Training R2 | {reg_results['train_r2']:.4f} |
| Training MAE | {reg_results['train_mae']:.4f} |

**Per-fold R2 scores**: {', '.join(f'{s:.3f}' for s in reg_results['cv_r2_scores'])}

### Interpretation

"""
    if reg_results['cv_r2_mean'] > 0.5:
        report += "模型對 SQS Score 有中等以上的預測能力。特徵組合能解釋目標變數的大部分變異。\n"
    elif reg_results['cv_r2_mean'] > 0.2:
        report += "模型對 SQS Score 有一定預測能力，但仍有大量未被捕捉的變異，可能需要更多外部特徵。\n"
    else:
        report += "模型的預測能力有限，SQS Score 可能受到資料中未包含的因子影響較大。特徵重要性排名仍具參考價值。\n"

    # Classification results
    cls_report = clf_results["classification_report"]
    report += f"""
---

## 3. Classification Model (Grade Prediction)

| Metric | Value |
|--------|-------|
| CV Accuracy (mean ± std) | {clf_results['cv_accuracy_mean']:.4f} ± {clf_results['cv_accuracy_std']:.4f} |
| CV F1 (mean ± std) | {clf_results['cv_f1_mean']:.4f} ± {clf_results['cv_f1_std']:.4f} |
| Training Accuracy | {clf_results['train_accuracy']:.4f} |

**Class Distribution**:
- Gold/Silver: {clf_results['class_distribution']['Gold/Silver']} ({clf_results['class_distribution']['Gold/Silver']/n_samples*100:.1f}%)
- Bronze/Discard: {clf_results['class_distribution']['Bronze/Discard']} ({clf_results['class_distribution']['Bronze/Discard']/n_samples*100:.1f}%)

**Per-class Metrics**:

| Class | Precision | Recall | F1-Score | Support |
|-------|-----------|--------|----------|---------|
| Bronze/Discard | {cls_report['Bronze/Discard']['precision']:.3f} | {cls_report['Bronze/Discard']['recall']:.3f} | {cls_report['Bronze/Discard']['f1-score']:.3f} | {cls_report['Bronze/Discard']['support']} |
| Gold/Silver | {cls_report['Gold/Silver']['precision']:.3f} | {cls_report['Gold/Silver']['recall']:.3f} | {cls_report['Gold/Silver']['f1-score']:.3f} | {cls_report['Gold/Silver']['support']} |

### Interpretation

"""
    imbalance_ratio = clf_results['class_distribution']['Gold/Silver'] / max(1, clf_results['class_distribution']['Bronze/Discard'])
    if imbalance_ratio > 5:
        report += (
            f"資料高度不平衡（Gold/Silver : Bronze/Discard = {imbalance_ratio:.1f}:1），"
            "分類器可能偏向多數類別。特徵重要性仍可作為參考，但需謹慎解讀準確率。\n"
        )
    else:
        report += "資料分布相對均衡，分類結果較可靠。\n"

    report += f"""
---

## 4. Key Insights & Recommendations

### 最重要的特徵類別

"""
    cat_scores = {}
    for cat, feats in categories.items():
        avgs = fi_df.loc[fi_df.index.isin(feats), "combined_score"].mean()
        cat_scores[cat] = avgs
    for cat, score in sorted(cat_scores.items(), key=lambda x: -x[1]):
        report += f"1. **{cat}** (avg score: {score:.3f})\n"

    report += """
### Actionable Takeaways

"""
    # 根據 top features 生成建議
    top_feat_names = fi_df.head(5).index.tolist()
    if "filing_lag_days" in top_feat_names:
        report += "- **申報延遲 (filing_lag_days)** 是重要特徵 — 延遲天數顯著影響訊號品質，較短的申報延遲通常產生更強的訊號。\n"
    if any(f.startswith("pis_") or f == "pis_total" for f in top_feat_names):
        report += "- **政治人物信用評分 (PIS)** 很重要 — 建議優先關注高 PIS 評分政治人物的交易。\n"
    if "amount_encoded" in top_feat_names:
        report += "- **交易金額** 影響顯著 — 較大金額交易傾向產生更強訊號（更高的 conviction）。\n"
    if any(f in top_feat_names for f in ["actionability", "timeliness", "sqs_conviction", "information_edge", "market_impact"]):
        report += "- **SQS 維度** 是核心驅動因子 — 這些經 LLM 評估的品質維度與最終訊號強度高度相關。\n"
    if any(f.startswith("beta_") or f.startswith("ff_") for f in top_feat_names):
        report += "- **Fama-French 因子** 有影響力 — 市場系統性風險因子也影響訊號品質，建議納入風險調整。\n"

    report += f"""
### Limitations

- **樣本量限制**: 僅 {n_samples} 筆樣本，模型泛化能力有限
- **目標變數可能有洩漏**: signal_strength 部分由 SQS 維度計算而來，兩者可能存在循環依賴
- **時間序列未考慮**: 使用隨機 K-Fold，未考慮時間順序（未來可改用 TimeSeriesSplit）
- **類別不平衡**: Grade 分類嚴重不平衡，Bronze/Discard 樣本太少

---

## 5. Plots

- Feature Importance (Dual): `{plot_paths.get('dual', 'N/A')}`
- Combined Ranking: `{plot_paths.get('combined', 'N/A')}`

---

## 6. Technical Details

**Regression Model**: RandomForestRegressor(n_estimators=200, max_depth=8, min_samples_leaf=10)
**Classification Model**: GradientBoostingClassifier(n_estimators=150, max_depth=4, lr=0.1)
**Cross-Validation**: 5-fold KFold (shuffle=True, random_state=42)
**Feature Count**: Regression={len(get_feature_columns(False))}, Classification={len(get_feature_columns(True))}

---

*Generated by ML Signal Model — Congressional Trading Intelligence System*
"""
    return report


# ═══════════════════════════════════════════════════════════════
# 7. 主流程
# ═══════════════════════════════════════════════════════════════

def run_full_analysis(db_path: Optional[str] = None) -> dict:
    """執行完整 ML 分析流程。"""
    print("=" * 60)
    print("  ML Feature Importance Analysis")
    print("  國會交易訊號特徵重要性分析")
    print("=" * 60)

    # Step 1: 載入特徵矩陣
    print("\n[1/6] 載入特徵矩陣...")
    df = load_feature_matrix(db_path)
    print(f"  Feature matrix: {df.shape[0]} rows x {df.shape[1]} cols")
    print(f"  Regression features: {len(get_feature_columns(False))} (excl. SQS dims)")
    print(f"  Classification features: {len(get_feature_columns(True))} (incl. SQS dims)")
    print(f"  Grade 分布: Gold/Silver={df['grade_binary'].sum()}, "
          f"Bronze/Discard={len(df) - df['grade_binary'].sum()}")

    # Step 2: 回歸模型
    print("\n[2/6] 訓練回歸模型 (RandomForest → signal_strength)...")
    reg_model, reg_results = train_regression_model(df)
    print(f"  CV R2 = {reg_results['cv_r2_mean']:.4f} +/- {reg_results['cv_r2_std']:.4f}")
    print(f"  CV MAE = {reg_results['cv_mae_mean']:.4f} +/- {reg_results['cv_mae_std']:.4f}")

    # Step 3: 分類模型
    print("\n[3/6] 訓練分類模型 (GradientBoosting → Grade)...")
    clf_model, clf_results = train_classification_model(df)
    print(f"  CV Accuracy = {clf_results['cv_accuracy_mean']:.4f} +/- {clf_results['cv_accuracy_std']:.4f}")
    print(f"  CV F1 = {clf_results['cv_f1_mean']:.4f} +/- {clf_results['cv_f1_std']:.4f}")

    # Step 4: 特徵重要性分析
    print("\n[4/6] 分析特徵重要性...")
    fi_df = analyze_feature_importance(reg_results, clf_results)
    print("\n  Top 10 特徵重要性排名:")
    print("  " + "-" * 55)
    for _, row in fi_df.head(10).iterrows():
        print(f"  #{int(row['rank']):2d} {row.name:<28s} combined={row['combined_score']:.3f}")

    # Step 5: 視覺化
    print("\n[5/6] 生成圖表...")
    PLOT_DIR.mkdir(parents=True, exist_ok=True)
    plot_paths = {
        "dual": plot_feature_importance(fi_df),
        "combined": plot_combined_importance(fi_df),
    }
    for name, path in plot_paths.items():
        print(f"  {name}: {path}")

    # Step 6: 儲存預測
    print("\n[6/6] 儲存預測結果到資料庫...")
    n_saved = save_predictions_to_db(df, reg_model, clf_model, db_path)

    # 生成報告
    print("\n生成研究報告...")
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_text = generate_report(df, fi_df, reg_results, clf_results, plot_paths)
    today = datetime.now().strftime("%Y-%m-%d")
    report_path = REPORT_DIR / f"ML_Feature_Importance_{today}.md"
    report_path.write_text(report_text, encoding="utf-8")
    print(f"  報告已儲存: {report_path}")

    print("\n" + "=" * 60)
    print("  分析完成！")
    print("=" * 60)

    return {
        "df": df,
        "fi_df": fi_df,
        "reg_results": reg_results,
        "clf_results": clf_results,
        "reg_model": reg_model,
        "clf_model": clf_model,
        "plot_paths": plot_paths,
        "report_path": str(report_path),
        "n_predictions_saved": n_saved,
    }
