# Research Brief: Frontier Scan -- Congressional Trading Alpha Research (2025-2026)

> Date: 2026-03-07 | Researcher: Research Lead | Status: Reviewed

## Problem Definition

PAM system core value is providing text-based intelligence advantage beyond price/volume. To ensure our methodology, data sources, and analysis techniques stay at the frontier, we need periodic scanning of academia, open-source community, competitive landscape, and regulatory environment. This scan focuses on major developments in 2025-2026, evaluating impact on PAM North Star Metric (Actionable Text Signals / Week).

## Research Method

- WebSearch across 5 directions: academic papers, ML/NLP techniques, open-source tools/competitors, regulatory changes, alternative data combinations
- Sources covered: SSRN, arXiv, CRA Literature Watch, Congress.gov, GitHub, Unusual Whales, Quiver Quantitative
- Cross-validated findings across multiple independent sources

---

## 1. Academic Paper Discoveries

### 1.1 Alpha Dissipation Theory -- Filing Lag is Key

**The Death of Insider Trading Alpha: Most Returns Occur Before Public Disclosure**
- Authors: Omer Ozlen, Ozkan Batumoglu (2025.12)
- Core finding: **70-80% of insider trading alpha dissipates between trade date and next trading day**, well before any public disclosure
- Source: [SSRN #5966834](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5966834)
- **PAM Impact**: Highly relevant. Our PACS formula assigns 25% weight to filing_lag_inverse (RB-006), this paper provides academic validation. **Signals with filing lag < 3 days should receive greater weighting**, while lag > 30 days has near-zero alpha. Our Smart Alert already includes abnormally fast filing detection -- direction is correct.

### 1.2 Post-STOCK Act Alpha -- Evidence is Mixed

**Do senators and house members beat the stock market? Evidence from the STOCK Act**
- Source: [ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S0047272722000044)
- Core finding: 2012-2020 data shows House buy trades underperform by 26 bps over 6 months on average
- **However** Unusual Whales 2025 report shows leadership still massively outperforms, gap of 40-50 percentage points
- **PAM Impact**: Alpha is not evenly distributed. Our PIS politician ranking (RB-005) and Senate > House preference (RB-004) already reflect this divergence. **Recommend strengthening politician tier logic**, further distinguishing Leadership vs Rank-and-file.

### 1.3 Shadow Trading -- Cross-Company Information Exploitation

**Shadow Trading Detection: A Graph-Based Surveillance Approach**
- Authors: Li, Stenfors, Dilshani, Guo, Mere, Chen
- Source: [ScienceDirect](https://www.sciencedirect.com/science/article/pii/S1544612325017787) / [SSRN #5290642](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5290642)
- Core finding: Uses Adaptive Market Graph Intelligence Network (AMGIN) to detect cross-company insider trading, based on SEC v. Panuwat case
- **PAM Impact**: Moderately relevant. Congress members may not trade the regulated company itself but its suppliers or competitors. Our convergence_detector could extend to industry graph convergence -- multiple politicians buying tickers in the same supply chain. **Needs further feasibility verification**.

### 1.4 Insider Buy/Sell Asymmetric Correction

**Does Insider Trading Correct Mispricing?**
- Authors: Faralli, Ma, Yun, Jiang George
- Core finding: Insider **sales** immediately correct overvaluation, but **purchases** take longer to correct undervaluation
- **PAM Impact**: Consistent with our RB-004 findings (Sale is contrarian indicator). Supports Buy-Only strategy, while suggesting Sale signals may have short-term (5d) reverse alpha that fades quickly.

### 1.5 Predictive Value of Insider Sales

**Insider Trading Against the Corporation**
- Authors: Sureyya Burcu Avci, H. Nejat Seyhun, Andrew Verstein
- Core finding: Insider sales tend to precede large drops in company value
- **PAM Impact**: Supports our direction of tracking SEC Form 4 insider_confirmed signals. **Recommend strengthening Sale signal cross-reference** (politician sells + company insider sells = strong negative signal).
---

## 2. Technical Method Innovation

### 2.1 ML for Insider Trading Prediction

**A Comparative Study of ML Algorithms for Stock Price Prediction Using Insider Trading Data**
- Authors: Amitabh Chakravorty, Nelly Elsayed (arXiv:2502.08728, 2025.02)
- Source: [arXiv](https://arxiv.org/abs/2502.08728)
- Methods: Decision Tree, Random Forest, SVM (RBF), K-Means
- Best model: SVM-RBF (88% accuracy), Random Forest second
- Feature engineering: Recursive Feature Elimination (RFE) for feature set optimization
- **PAM Impact**: We currently use rule-based scoring (SQS, PACS), no ML models for prediction. **Could train RF/SVM alpha prediction model** using filing_lag, amount, chamber, politician_grade, convergence as features, actual_return as label. Prerequisite: need more signal_performance data (currently only 93 records).

### 2.2 Graph Neural Networks (GNN) for Anomalous Trading Detection

**Graph Reinforcement Learning for Insider Trading Detection**
- Source: [SSRN #5559840](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5559840)
- Method: Models financial market as spatiotemporal graph, GNN propagates cross-entity information
- **PAM Impact**: Conceptual inspiration. We could model Politician-Ticker-Committee-Industry as knowledge graph, using graph structure to enhance convergence detection. **Current scale does not need GNN**, but graph-structured thinking can inform manual rules.

### 2.3 LLM for Political Statement Market Impact Prediction

**Exploring the Use of High-Impact Political and Economic Statements in LLM for Judging Financial Market Trend**
- Source: [MDPI](https://www.mdpi.com/2227-7390/14/5/869)
- Method: Uses LLM to analyze high-impact political/economic statements (HIPES), combined with technical indicators for market trend prediction
- **PAM Impact**: Highly relevant to our Social Media Intelligence (Pillar B). We already use Gemini Flash for KOL tweet analysis. **Could integrate technical indicators (RSI, MACD) as LLM prompt context** to improve signal quality.

### 2.4 Social Media Bot Manipulation Detection

**Bot-Induced Social Media Manipulation and Stock Market Distortion**
- Authors: Daniel Bradley, Jan Hanousek Jr., Dominik Svoboda
- Core finding: Bots generate sharp positive returns followed by partial reversals with retail order imbalances
- **PAM Impact**: Our social_nlp.py has sarcasm detection (4 patterns) but no bot detection. **Recommend adding bot detection logic** (account age, posting frequency, interaction patterns).

---

## 3. Open-Source Tools / Competitive Landscape

### 3.1 Commercial Competitor Comparison

| Product | Price | Core Features | PAM Differentiation |
|---------|-------|---------------|---------------------|
| [Unusual Whales](https://unusualwhales.com/congress-trading-report-2025) | $10/mo | Real-time options flow + congress trading + dark pool | No NLP/LLM analysis, no multi-signal fusion |
| [Quiver Quantitative](https://www.quiverquant.com/) | $25/mo (Premium), API $10-75/mo | Congress Backtester + Social Sentiment Backtester + Smart Score + API | No AI Discovery, no PACS scoring |
| [InsiderFinance](https://www.insiderfinance.io/) | $49-99/mo | Options flow + dark pool + insider + congress | Options-focused, no text analysis |
| Capitol Trades | Free | Basic congress trading tracking | No analysis features |

**PAM Differentiation Advantages**:
1. LLM-driven zero-shot signal generation (Gemini Flash) -- no competitor has this
2. PACS multi-signal fusion (SQS + VIX + Options + Convergence) -- competitors are single-dimension
3. Politician speech-trade cross-reference (social posts vs actual trades) -- not seen in competitors
4. Fama-French three-factor adjusted backtesting -- Quiver only offers raw return comparison

**PAM Weaknesses**:
1. No real-time options flow data (Unusual Whales core strength)
2. No dark pool data
3. No public API for external integration (we have FastAPI but not yet public)
4. Data update frequency slower than commercial products (45-day disclosure delay cannot be accelerated)

### 3.2 Quiver API + QuantConnect Integration

- Quiver Python API (quiverquant) provides structured congressional trading data
- Source: [GitHub - Quiver API](https://github.com/Quiver-Quantitative/python-api)
- QuantConnect has integrated Quiver data for backtesting
- Source: [QuantConnect - Congress Trading](https://www.quantconnect.com/data/quiver-quantitative-congress-trading)
- **PAM Impact**: Could use Quiver API as **third data source** (supplementing Senate EFD + Capitol Trades), but need to evaluate cost vs reliability of our own scrapers.

### 3.3 Open-Source Community Projects

Mainly academic or no longer maintained:
- [congress_trades_dashboard](https://github.com/adrianmross/congress_trades_dashboard) -- Lehigh U final project, Streamlit + S&P 500 comparison
- [congress-stock-trades](https://github.com/semerriam/congress-stock-trades) -- Committee vs trade correlation analysis
- [Apify Congressional Trading Scraper](https://github.com/johnisanerd/Apify-Congressional-Trading-Data-Scraper) -- Apify-based scraper, updated 2025.11

**Conclusion**: Open-source community has no system comparable to PAM in functionality. Most are single-function (scraper or visualization), no LLM analysis, no signal scoring, no portfolio optimization.

### 3.4 n8n Automation Workflow

- [n8n Congress Trades Workflow](https://n8n.io/workflows/4509-daily-us-congress-members-stock-trades-report-via-firecrawl-openai-gmail/) -- Uses Firecrawl + OpenAI + Gmail for daily congress trade reports
- **PAM Impact**: Similar concept to our run_daily.py but using no-code tools. Could reference its UX design.

---

## 4. Regulatory Environment Changes

### 4.1 Congressional Trading Ban Bills -- Closest to Passing in History

**119th Congress (2025-2026) has at least 25 bills proposed**, two have advanced beyond committee:

| Bill | Name | Content | Progress |
|------|------|---------|----------|
| [S. 1498](https://www.congress.gov/bill/119th-congress/senate-bill/1498/text/rs?format=txt) | HONEST Act | **Complete ban** on members and spouses/dependents holding/purchasing/trading covered assets | 2025.12.10 Senate committee passed |
| [H.R. 7008](https://www.congress.gov/bill/119th-congress/house-bill/7008/all-actions) | Stop Insider Trading Act | Ban purchases; sales require **7-14 day advance public notice** | 2026.01.14 House committee passed |
| [H.R. 1908](https://www.congress.gov/bill/119th-congress/house-bill/1908) | End Congressional Stock Trading Act | Ban trading and require blind trust | Pending vote |

**Key Analysis**:
- Source: [CRS Report R48641](https://www.congress.gov/crs-product/R48641)
- STOCK Act penalty is only $200, widely considered ineffective ([Harvard JOL](https://journals.law.harvard.edu/jol/2025/11/03/congressional-stock-trading-ban-challenges/))
- Bipartisan support in both chambers, **probability of passage is highest ever**
- Even if passed, implementation may have **6-18 month transition period**

**PAM Impact -- SEVERE**:
- **Short-term (6-12 months)**: During bill discussion, politician trading may become more cautious or more frequent (rushing before ban), signals may show abnormal volatility
- **Mid-term (12-24 months)**: If passed, Pillar A (congressional trading intelligence) will gradually lose data source
- **Mitigation Strategies**:
  1. Accelerate Pillar B (social/KOL intelligence) development priority
  2. Expand to other informed traders (13F institutions, SEC Form 4 insiders)
  3. H.R. 7008 advance 7-day notice actually **creates a new signal source** (pre-announcement -> market reaction)
  4. Even if ban passes, existing historical data remains usable for backtesting and model training

### 4.2 Unusual Whales 2025 Annual Report Key Data

- Source: [Unusual Whales Congress Trading Report 2025](https://unusualwhales.com/congress-trading-report-2025)
- Only **32.2%** of members beat the market (S&P 500 +16.6%)
- Democrats averaged +14.4%, Republicans +17.3%
- Full year 14,451 trades, $720M total
- Members net sold $45M ($170M sold vs $125M bought), rotating into fixed income
- **PAM Impact**: Overall underperformance does not mean signals are invalid. Our PIS-ranked Top 5 politicians may still outperform -- needs verification. The $170M to $125M net selling trend is worth tracking in sector_rotation module.

---

## 5. Alternative Data Combinations

### 5.1 Triple Sentiment Signal Framework

- Source: [Medium - Three Hidden Sentiment Signals](https://medium.com/@trading.dude/the-three-hidden-sentiment-signals-most-traders-ignore-congress-institutions-and-insiders-b78ff8deab50)
- Framework: Congressional trades + Institutional holdings + Corporate insider trades -> each scored 0-3 -> total 0-9
- Score 9 = triple confirmation, strong buy; 0-2 = lack of support
- **PAM Impact**: We already have congressional trades + SEC Form 4 cross-reference (insider_confirmed). **Missing piece is real-time 13F institutional holdings integration**. Could incorporate institutional_holdings table data into PACS scoring.

### 5.2 Social Sentiment + Congressional Trades

- We already integrated this in RB-009 (social_alignment: CONSISTENT +0.05, CONTRADICTORY -0.03)
- Academic paper support: LLM analysis of political statements can predict market trends (MDPI study)
- **Enhancement direction**: Add StockTwits retail sentiment as contrarian indicator -- when retail is bullish but politicians are selling, signal is stronger

### 5.3 Options Flow + Congressional Trades

- Unusual Whales core selling point is options flow + congressional trades
- Our signal_enhancer already includes options_sentiment component (PACS 15% weight), but data source is limited
- **Recommendation**: Evaluate CBOE DataShop or OptionStrat API cost to get unusual options activity data. If a politician buys a ticker while unusual bullish options flow appears, signal confidence should increase significantly.

---

## Solution Comparison

| Improvement Direction | Expected Impact | Implementation Cost | Risk | Priority |
|----------------------|----------------|--------------------|----- |----------|
| Strengthen filing lag weighting | High: academic evidence supports | S (parameter tuning) | Low | P0 |
| Politician tier refinement (Leadership vs Rank-and-file) | High: capture alpha concentration | M (needs data labeling) | Low | P1 |
| Strengthen Sale cross-reference (politician+insider same-direction sell) | Med-High: new signal type | M | Med | P1 |
| ML model (RF/SVM) to replace rule-based scoring | High: but needs data | L (needs 500+ signal_performance) | High: overfitting | P2 |
| 13F institutional holdings integration into PACS | Med: triple confirmation framework | M | Med | P2 |
| Options flow data source | High: competitor core feature | L (API cost $50-200/mo) | Med: cost | P2 |
| Bot detection (social signal quality) | Med: reduce noise | S | Low | P3 |
| H.R. 7008 advance notice signal parsing | High: new signal source (if bill passes) | M | High: bill may not pass | P3 (monitoring) |
| Do nothing -- maintain status quo | Low | Zero | High: competitors catch up | -- |

---

## Recommended Actions

### Immediate (P0, This Week)

1. **Adjust PACS filing_lag_inverse weight**: Increase from 25% to 30%, add nonlinear decay (lag > 30d weight approaches 0). Academic paper (Ozlen and Batumoglu 2025) provides strong support.

### Short-term (P1, This Month)

2. **Politician Leadership tag**: Add is_leadership field to politician_rankings, marking Speaker, Majority/Minority Leader, Committee Chair. Give Leadership politicians additional PIS bonus.
3. **Sale Cross-Reference Enhancement**: When congress_trades shows Sale + sec_form4_trades shows insider Sale on same ticker, generate double sell alert signal.

### Mid-term (P2, Q2 2026)

4. **Accumulate signal_performance data**: Target 500+ records to prepare for ML model training.
5. **Evaluate Quiver API**: $10/mo Hobbyist tier provides structured data as third data source validation.
6. **Options flow data source POC**: Evaluate CBOE DataShop vs OptionStrat vs Unusual Whales API cost and coverage.

### Ongoing Monitoring

7. **Congressional trading ban bills**: Track S. 1498 and H.R. 7008 progress. If floor vote approaches, immediately launch Pillar B acceleration plan.

---

## Risks and Mitigation

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| Congressional trading ban passes | Med (40-60%) | Critical: Pillar A data source disappears | Accelerate Pillar B + 13F/Form 4 alternatives; H.R. 7008 advance notice creates new data source |
| ML model overfitting | High | Med: false signals | Strict out-of-sample validation, walk-forward testing |
| Competitors catch up on NLP analysis | Med | Med: differentiation shrinks | Continue iterating PACS + multi-signal fusion, maintain 6-12 month tech lead |
| Options flow API cost too high | Low | Low: feature gap | Start with free yfinance options chain, upgrade when quality justifies |
| Filing lag over-weighting | Low | Low: some signals ignored | A/B test old vs new weights, validate with signal_performance |

---

## References

### Academic Papers
- [Ozlen and Batumoglu (2025) - The Death of Insider Trading Alpha](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5966834)
- [Do Senators and House Members Beat the Stock Market?](https://www.sciencedirect.com/science/article/abs/pii/S0047272722000044)
- [Shadow Trading Detection: A Graph-Based Surveillance Approach](https://www.sciencedirect.com/science/article/pii/S1544612325017787)
- [ML Algorithms for Stock Prediction Using Insider Trading Data (arXiv:2502.08728)](https://arxiv.org/abs/2502.08728)
- [HIPES + LLM for Financial Market Trend](https://www.mdpi.com/2227-7390/14/5/869)
- [Graph RL for Insider Trading Detection (SSRN #5559840)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5559840)
- [CRA Q4 2025 Literature Watch](https://www.crai.com/insights-events/publications/insider-trading-market-manipulation-literature-watch-q4-2025/)

### Regulatory and Policy
- [CRS Report R48641 - 119th Congress Financial Activity Proposals](https://www.congress.gov/crs-product/R48641)
- [S. 1498 HONEST Act Full Text](https://www.congress.gov/bill/119th-congress/senate-bill/1498/text/rs?format=txt)
- [H.R. 7008 Stop Insider Trading Act](https://www.congress.gov/bill/119th-congress/house-bill/7008/all-actions)
- [Harvard JOL - Congressional Stock Trading Ban Challenges](https://journals.law.harvard.edu/jol/2025/11/03/congressional-stock-trading-ban-challenges/)

### Competitors and Tools
- [Unusual Whales Congress Trading Report 2025](https://unusualwhales.com/congress-trading-report-2025)
- [Quiver Quantitative](https://www.quiverquant.com/)
- [Quiver Python API (GitHub)](https://github.com/Quiver-Quantitative/python-api)
- [QuantConnect - Quiver Congress Trading Data](https://www.quantconnect.com/data/quiver-quantitative-congress-trading)
- [InsiderFinance](https://www.insiderfinance.io/)

### Alternative Data
- [Three Hidden Sentiment Signals (Medium)](https://medium.com/@trading.dude/the-three-hidden-sentiment-signals-most-traders-ignore-congress-institutions-and-insiders-b78ff8deab50)
- [Alpha Architect - Congress is Insider Trading](https://alphaarchitect.com/congress-is-insider-trading/)
- [The Political Alpha (AInvest)](https://www.ainvest.com/news/political-alpha-congressional-leaders-exploit-insider-access-outperform-500-47-2601/)
