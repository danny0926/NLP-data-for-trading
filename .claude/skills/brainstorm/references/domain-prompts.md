# Domain-Specific Brainstorming Prompts

Load this file when the user wants deeper exploration in a specific category.

## New Data Sources

- Committee hearing schedules — do trades spike before hearings?
- Lobbying disclosure data (lobbying filings vs. subsequent trades)
- Campaign contribution data cross-referenced with trading
- SEC enforcement action announcements
- Federal Reserve meeting minutes / dot plot changes
- Government contract awards (USASpending.gov)
- Patent filings by companies that congress members trade
- Options flow data (unusual options activity on congress-traded tickers)
- Dark pool / institutional block trade data
- Congressional staff financial disclosures

## Signal Enhancement

- Ensemble scoring: combine Gemini impact score with FinBERT sentiment
- Historical hit rate per politician (some are better stock pickers)
- Sector momentum overlay — is the sector already trending?
- Insider trading correlation — do corporate insiders agree?
- Unusual volume confirmation on the day of disclosure filing
- Time-decay weighting — how stale is the filing vs. trade date?
- Committee membership relevance scoring (Finance Committee member trading banks = higher signal)

## Timing Optimization

- Optimal holding period analysis per politician tier
- Filing delay analysis — typical gap between trade and disclosure
- Market regime detection (bull/bear) affecting signal quality
- Earnings calendar avoidance — skip signals near earnings dates
- Intraday entry optimization using VWAP or TWAP
- Day-of-week effects in congressional trading alpha

## Multi-Signal Fusion

- Weighted scoring model: congress (40%) + 13F (30%) + social (20%) + news (10%)
- Conviction signals: when 2+ sources agree on same ticker
- Contrarian signals: when congress buys but 13F sells
- Temporal alignment: signals within same 7-day window
- Sector convergence: multiple politicians trading same sector

## Risk Management

- Maximum position size per signal strength
- Portfolio concentration limits by sector
- Correlation-aware sizing (reduce if signals cluster in same sector)
- Drawdown-based throttling (reduce activity after losses)
- Signal decay monitoring — rolling Sharpe ratio of recent signals

## Monitoring & Observability

- Signal quality dashboard (precision/recall of past signals)
- Alpha decay detection (rolling returns vs. benchmark)
- Data pipeline health (scraper success rates, API availability)
- Coverage tracking (which politicians are we missing?)
- Anomaly detection (unusual filing patterns, duplicate trades)
