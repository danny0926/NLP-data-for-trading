---
name: validate-data
description: Validate congressional trading data integrity in SQLite database. Use when checking data quality, verifying pipeline output, or debugging data issues in senate_trades, house_trades, or ai_intelligence_signals tables.
---

# Validate Data

Validate the `data/data.db` SQLite database by running these checks:

## Checks

1. **Table existence** — Verify senate_trades, house_trades, institutional_holdings, ocr_queue, ai_intelligence_signals tables exist
2. **Record counts** — Report row count per table
3. **Recency** — Show the most recent `filing_date` or `timestamp` per table to confirm freshness
4. **Required fields** — Check for NULL values in NOT NULL columns (politician_name, filing_date, ptr_link, data_hash)
5. **Ticker format** — Flag any ticker values that don't match `^[A-Z]{1,5}$`
6. **Duplicate hashes** — Check for duplicate `data_hash` values in senate_trades and house_trades
7. **Date sanity** — Flag any transaction_date in the future or before 2020
8. **AI signals** — Check ai_intelligence_signals for NULL impact_score or missing source_name

## Execution

Run validation using Python with sqlite3:

```bash
python -c "
import sqlite3, os
conn = sqlite3.connect('data/data.db')
c = conn.cursor()

tables = ['senate_trades','house_trades','institutional_holdings','ocr_queue','ai_intelligence_signals']
for t in tables:
    try:
        c.execute(f'SELECT COUNT(*) FROM {t}')
        print(f'{t}: {c.fetchone()[0]} rows')
    except:
        print(f'{t}: TABLE MISSING')

# Latest dates
for t in [('senate_trades','filing_date'),('house_trades','filing_date'),('ai_intelligence_signals','timestamp')]:
    try:
        c.execute(f'SELECT MAX({t[1]}) FROM {t[0]}')
        print(f'{t[0]} latest: {c.fetchone()[0]}')
    except: pass

# Duplicate hashes
for t in ['senate_trades','house_trades']:
    try:
        c.execute(f'SELECT data_hash, COUNT(*) FROM {t} GROUP BY data_hash HAVING COUNT(*)>1')
        dupes = c.fetchall()
        print(f'{t} duplicate hashes: {len(dupes)}')
    except: pass

conn.close()
"
```

Report findings in a summary table format.
