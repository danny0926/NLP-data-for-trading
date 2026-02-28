---
name: research-brief
description: >
  生成結構化的量化研究摘要報告。將 DB 中的信號數據、回測結果、統計發現
  整合成決策層可讀的 Research Brief。適用於：定期研究彙報、新發現摘要、
  投資委員會報告、產品決策支持。
  觸發詞: 研究報告, research brief, 研究摘要, 量化報告, alpha report,
  研究進度, research summary, 研究結論, 信號報告, 決策報告, 最新發現,
  what did we find, 研究彙報, 量化摘要, quant report, findings
---

# Research Brief — 量化研究摘要生成器

本 Skill 從 PAM 資料庫中提取最新數據，生成結構化的研究摘要。
目標讀者: CEO/CPO/CDO 層級的決策者，不需要看 SQL 或統計公式。

## 報告結構

### Section 1: Executive Summary (3 bullet points)

用 3 句話回答:
1. 最重要的新發現是什麼？
2. 對交易策略有何影響？
3. 建議的下一步行動？

### Section 2: Signal Overview

```python
python -c "
import sqlite3
conn = sqlite3.connect('file:data/data.db?mode=ro', uri=True)
conn.row_factory = sqlite3.Row
c = conn.cursor()

# 信號總覽
c.execute('SELECT COUNT(*) FROM alpha_signals')
total = c.fetchone()[0]

c.execute('SELECT direction, COUNT(*) as cnt FROM alpha_signals GROUP BY direction')
dirs = {r['direction']: r['cnt'] for r in c.fetchall()}

c.execute('SELECT AVG(expected_alpha_20d) as avg_ea, AVG(confidence) as avg_conf FROM alpha_signals')
avgs = dict(c.fetchone())

c.execute('SELECT COUNT(*) FROM enhanced_signals')
enhanced = c.fetchone()[0]

c.execute('SELECT COUNT(*) FROM convergence_signals')
convergence = c.fetchone()[0]

c.execute('SELECT COUNT(*) FROM portfolio_positions')
positions = c.fetchone()[0]

print(f'Alpha Signals: {total} (LONG={dirs.get(\"LONG\",0)}, SHORT={dirs.get(\"SHORT\",0)})')
print(f'Avg EA20d: {avgs[\"avg_ea\"]:.4f}, Avg Confidence: {avgs[\"avg_conf\"]:.4f}')
print(f'Enhanced Signals: {enhanced}')
print(f'Convergence Events: {convergence}')
print(f'Portfolio Positions: {positions}')
conn.close()
"
```

### Section 3: Top Signals (Actionable)

```python
python -c "
import sqlite3
conn = sqlite3.connect('file:data/data.db?mode=ro', uri=True)
conn.row_factory = sqlite3.Row
c = conn.cursor()

# Top 10 by enhanced_strength (if available) or signal_strength
c.execute('''
    SELECT e.ticker, e.politician_name, e.chamber, e.direction,
           e.enhanced_strength, e.pacs_score, e.confidence_v2, e.vix_zone,
           a.expected_alpha_20d, a.sqs_grade
    FROM enhanced_signals e
    JOIN alpha_signals a ON e.trade_id = a.trade_id
    ORDER BY e.enhanced_strength DESC
    LIMIT 10
''')
for r in c.fetchall():
    print(f'{r[\"ticker\"]:6s} | {r[\"politician_name\"]:20s} | {r[\"chamber\"]:6s} | '
          f'PACS={r[\"pacs_score\"]:.2f} | Str={r[\"enhanced_strength\"]:.3f} | '
          f'EA20d={r[\"expected_alpha_20d\"]:.4f} | VIX={r[\"vix_zone\"]}')
conn.close()
"
```

### Section 4: Convergence Highlights

```python
python -c "
import sqlite3
conn = sqlite3.connect('file:data/data.db?mode=ro', uri=True)
conn.row_factory = sqlite3.Row
c = conn.cursor()
c.execute('''
    SELECT ticker, direction, politician_count, score, politicians
    FROM convergence_signals
    ORDER BY score DESC LIMIT 5
''')
for r in c.fetchall():
    print(f'{r[\"ticker\"]:6s} | {r[\"direction\"]:5s} | {r[\"politician_count\"]} politicians | '
          f'Score={r[\"score\"]:.2f} | {r[\"politicians\"][:60]}')
conn.close()
"
```

### Section 5: Sector Rotation Status

```python
python -c "
import sqlite3
conn = sqlite3.connect('file:data/data.db?mode=ro', uri=True)
conn.row_factory = sqlite3.Row
c = conn.cursor()
c.execute('''
    SELECT sector, etf, direction, signal_strength, momentum_score,
           rotation_type, net_ratio, trades
    FROM sector_rotation_signals
    ORDER BY signal_strength DESC
''')
for r in c.fetchall():
    print(f'{r[\"sector\"]:20s} | {r[\"etf\"]:4s} | {r[\"direction\"]:5s} | '
          f'Str={r[\"signal_strength\"]:.3f} | Mom={r[\"momentum_score\"]:.3f} | '
          f'{r[\"rotation_type\"]} | Ratio={r[\"net_ratio\"]:.1f}% | {r[\"trades\"]} trades')
conn.close()
"
```

### Section 6: Research Progress

列出已完成的研究 (RB-001~007) 和進行中/計畫中的研究 (RB-008+)。

讀取最新研究上下文: Read `.claude/skills/hypothesis-test/references/pam-research-context.md`

### Section 7: Key Risks & Limitations

固定提醒:
- FF3 20d/60d CARs 目前 100% NULL (交易太新，需 2026-03+ 重跑)
- Signal Tracker 尚未首次執行 (signal_performance = 0 rows)
- Social Media API 尚未配置 (social_posts = 0)
- Senate fetcher 依賴 Akamai bypass，可能隨時失效

### Section 8: Recommended Actions

基於以上數據，提出 3-5 個具體的下一步行動建議。
每個建議包含: 行動描述 + 預期影響 + 負責模組。

## 輸出格式

以 Markdown 輸出，標題格式:

```markdown
# PAM Research Brief — YYYY-MM-DD

> 生成時間: [timestamp]
> 資料庫: congress_trades N筆 | alpha_signals N筆 | enhanced N筆

[各 Section 內容]
```

如果使用者要求存檔，存入 `docs/reports/Research_Brief_YYYY-MM-DD.md`。
