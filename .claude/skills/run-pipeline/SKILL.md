---
name: run-pipeline
description: Execute the congressional trading data pipeline. Use when the user wants to fetch latest Senate/House trading data, run the AI discovery engine, or execute the full data collection workflow.
---

# Run Pipeline

Execute the data acquisition and AI analysis pipeline. Activate the virtual environment first.

## Full Pipeline

Run all steps in sequence:

```powershell
.\venv\Scripts\Activate.ps1
```

### Step 1: Initialize database

```bash
python -c "from src.database import init_db; init_db()"
```

### Step 2: Fetch Senate data (last 2 days)

```bash
python -c "from src.senate_fetcher_v1 import SenateFetcherV1; SenateFetcherV1().run(days=2)"
```

### Step 3: Fetch House data

```bash
python -c "from src.house_fetcher_v3_ajax import HouseAjaxFetcher; HouseAjaxFetcher().fetch_latest()"
```

### Step 4: Run AI discovery on monitored targets

```bash
python run_congress_discovery.py
```

## Individual Components

Run specific parts when only partial updates are needed:

- **Senate only**: Step 1 + Step 2
- **House only**: Step 1 + Step 3
- **AI analysis only**: Step 4 (requires existing data in DB)
- **Sector analysis**: `python -c "from src.sector_radar import CongressSectorRadar; r = CongressSectorRadar(); r.fetch_and_process()"`
- **Alpha analysis**: `python -c "from src.congress_alpha_final import CongressAlphaTool; t = CongressAlphaTool(); t.fetch_data(); t.analyze(days=60)"`

## Notes

- Senate fetcher uses `curl_cffi` with Chrome impersonation — requires CSRF token handling
- House fetcher uses DataTable AJAX protocol
- AI discovery requires `GOOGLE_API_KEY` in `.env`
- 5-second delay between AI targets to respect Gemini API rate limits
