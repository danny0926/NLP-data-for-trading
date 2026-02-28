# Spike Report: RB-008 Congress.gov 委員會歸屬資料評估

**日期**: 2026-02-28
**評估人**: CDO (Research Team)
**評估結果**: **CONDITIONAL GO** (6.6/10 — Phase 1 可行，歷史資料缺口需緩解)

---

## 評估摘要

| 維度 | 權重 | 評分 | 加權 |
|------|------|------|------|
| 資料品質 | 30% | 6/10 | 1.8 |
| 技術整合 | 25% | 6/10 | 1.5 |
| Alpha 潛力 | 25% | 8/10 | 2.0 |
| 成本 | 10% | 10/10 | 1.0 |
| 合規 | 10% | 9/10 | 0.9 |
| **加權總分** | | | **7.2/10** |

**建議**: CONDITIONAL GO — Alpha 潛力高 (學術研究強力支持委員會主席 +40-47%/年)，但資料來源是 GitHub YAML (非 API)，且歷史委員會成員名單缺失。分兩階段實施。

---

## 1. 資料來源 (非 Congress.gov API)

**重要發現**: Congress.gov API v3 的 `/committee` 端點**不直接回傳委員成員名單**。實際最佳資料來源是:

### unitedstates/congress-legislators (GitHub, 推薦)

| 項目 | 詳情 |
|------|------|
| 來源 | `github.com/unitedstates/congress-legislators` |
| 認證 | 不需要 (公開 YAML/JSON/CSV) |
| 成本 | 完全免費 |
| 關鍵檔案 | `committee-membership-current.yaml` (現任成員) |
| 歷史深度 | **僅現任** (119 屆)。歷史成員名單不存在 |
| 更新頻率 | 新屆次後數週，自動爬取官方網站 |
| 識別碼 | bioguide ID (跨系統橋接關鍵) |

### 資料結構範例

```yaml
SSAS:        # Senate Armed Services Committee
- name: Roger Wicker
  party: majority
  rank: 1
  title: Chairman
  bioguide: W000437
- name: Jack Reed
  party: minority
  rank: 1
  title: Ranking Member
  bioguide: R000122
```

### Congress.gov API (補充用)

| 項目 | 詳情 |
|------|------|
| URL | `api.congress.gov/v3/committee/{chamber}/{committeeCode}` |
| 認證 | 免費 API Key (data.gov 申請) |
| 速率限制 | 5,000 req/hour |
| 用途 | 委員會 metadata、相關法案、會議記錄 |
| 限制 | 不含成員名單；2025/08 曾中斷 |

---

## 2. 學術研究：委員會 Alpha 量化證據

| 研究 | 核心發現 | Alpha 估計 |
|------|---------|-----------|
| Kempf et al. (2022) | 黨派領袖成為主席後 alpha | **+40-47%/年** |
| WVU Dissertation | 委員會匹配 Purchase → 1 月正向 CAR | 顯著正向 |
| WVU Dissertation | 委員會匹配 Sale → 1 年負向 CAR | **-5.7%** |
| Brennan Center 2024 | 18% 議員在委員會相關產業交易 | Armed Services 最多 |
| NBER w26975 | EPU 高時 × 委員會 alpha 有交乘效果 | 正向 |
| Ziobrowski (pre-STOCK Act) | Senate 年超額報酬 | +10%/年 |

### 關鍵委員會 Alpha 排名

| 委員會 | 代碼 | 相關板塊 | 證據強度 |
|--------|------|---------|---------|
| Senate Finance | SSFI | 金融/稅務 | 強 |
| Senate Appropriations | SSAP | 國防/聯邦承包 | 強 |
| Senate Armed Services | SSAS | 航天國防 | 強 |
| House Ways & Means | HSWM | 稅務/金融 | 強 |
| House Appropriations | HSAP | 國防/基建 | 強 |
| Senate HELP | SSHR | 醫療/生技 | 中 |
| Senate Commerce | SSCM | 科技/電信 | 中 |
| Senate Energy | SSEG | 能源 | **低** (RB-007: 國會能源擇時差) |

---

## 3. 整合架構

### 委員會 → 板塊映射 (概念驗證)

```python
COMMITTEE_SECTOR_MAP = {
    "SSAS": ["Aerospace & Defense"],       # Armed Services
    "SSFI": ["Financial Services"],         # Finance
    "SSHR": ["Healthcare", "Biotech"],      # HELP
    "SSEG": ["Energy"],                     # Energy (注意: alpha 低)
    "SSCM": ["Technology", "Telecom"],      # Commerce
    "SSBK": ["Banking", "Real Estate"],     # Banking
    "HSAS": ["Aerospace & Defense"],        # House Armed Services
    "HSBA": ["Financial Services"],         # House Financial Services
    "HSIF": ["Energy", "Tech", "Health"],   # House Energy & Commerce
    "HSWM": ["Financial Services"],         # House Ways & Means
}

RANK_MULTIPLIERS = {
    "Chair": 1.5,           # 委員會主席
    "Ranking Member": 1.3,  # 少數黨首席
    None: 1.0,              # 一般成員
}
```

### PACS v2 公式 (加入委員會因子)

```
PACS v2 = 45% signal_strength + 22% filing_lag_inv + 13% options_sentiment
         + 8% convergence + 12% committee_match
```

### 新增 DB Schema

```sql
CREATE TABLE committee_memberships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    committee_id TEXT NOT NULL,
    committee_name TEXT,
    chamber TEXT,
    politician_name TEXT NOT NULL,
    bioguide TEXT,
    rank INTEGER,
    title TEXT,
    congress_number INTEGER,
    related_sectors TEXT,  -- JSON array
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(committee_id, politician_name, congress_number)
);
```

---

## 4. 主要風險

| 風險 | 嚴重度 | 緩解方式 |
|------|--------|---------|
| 歷史成員名單缺失 | 高 | Phase 1 僅對 119 屆 (2025+) 生效；Phase 2 爬取 LegiScan |
| bioguide ↔ politician_name 映射 | 中 | 擴充 name_mapping.py (約 30-40 位議員) |
| Post-STOCK Act alpha 衰減 | 中 | 聚焦主席/領袖 (Kempf: alpha 仍在) |
| Energy 委員會反向 | 低 | SSEG 成員能源股不加乘 (配合 RB-007) |
| Congress.gov API 不穩定 | 低 | 主要用 GitHub YAML，API 僅補充 |

---

## 5. 建議實作路徑

### Phase 1: 現任委員會 (3-4 天)
- 下載 `committee-membership-current.yaml` + `committees-current.yaml`
- 建立 `committee_memberships` 表
- 實作 `CommitteeMatcher` class
- 在 `signal_enhancer.py` 注入 committee_match 因子
- 對近期交易 (2025+) 立即生效

### Phase 2: 歷史補齊 + 回測 (4-5 天)
- 爬取 LegiScan 或 Civic Eagle 歷史委員會成員
- 回填 118 屆 (2023-2024)
- 執行 RB-008 回測: committee_match vs no_match CAR 比較

**總工時**: 7-9 天

---

## 參考資料

- [unitedstates/congress-legislators (GitHub)](https://github.com/unitedstates/congress-legislators)
- [LibraryOfCongress/api.congress.gov](https://github.com/LibraryOfCongress/api.congress.gov)
- [Kempf et al. (2022) — Political Power and Profitable Trades](https://cepr.org/voxeu/columns/political-power-and-profitable-trades-us-congress)
- [WVU Dissertation — Three Essays on Trading by Members of Congress](https://researchrepository.wvu.edu/cgi/viewcontent.cgi?article=1424&context=etd)
- [Brennan Center — Congressional Stock Trading Explained](https://www.brennancenter.org/our-work/research-reports/congressional-stock-trading-explained)
- [NBER Working Paper w26975](https://www.nber.org/system/files/working_papers/w26975/w26975.pdf)
