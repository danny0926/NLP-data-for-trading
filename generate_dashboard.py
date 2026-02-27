"""
Political Alpha Monitor — Interactive Dashboard Generator
生成獨立 HTML 儀表板，無需伺服器即可在瀏覽器中查看

使用方式:
    python generate_dashboard.py              # 生成 dashboard
    python generate_dashboard.py --output dashboard.html
"""

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime
from typing import List, Dict, Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.config import DB_PATH


def query_db(sql: str, params: tuple = ()) -> List[Dict]:
    """查詢資料庫。"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_dashboard_data() -> Dict[str, Any]:
    """收集所有 dashboard 需要的資料。"""
    data = {}

    # 1. Portfolio positions
    data['positions'] = query_db(
        'SELECT * FROM portfolio_positions ORDER BY weight DESC'
    )

    # 2. Alpha signals (deduplicated, top 20)
    data['signals'] = query_db('''
        SELECT ticker, direction,
               MAX(signal_strength) as signal_strength,
               MAX(expected_alpha_5d) as alpha_5d,
               MAX(expected_alpha_20d) as alpha_20d,
               AVG(confidence) as confidence
        FROM alpha_signals
        GROUP BY ticker, direction
        ORDER BY signal_strength DESC
        LIMIT 20
    ''')

    # 3. Politician rankings
    data['rankings'] = query_db(
        'SELECT * FROM politician_rankings ORDER BY pis_total DESC'
    )

    # 4. Convergence signals
    data['convergence'] = query_db(
        'SELECT * FROM convergence_signals ORDER BY score DESC'
    )

    # 5. Recent trades (last 20)
    data['recent_trades'] = query_db('''
        SELECT politician_name, ticker, transaction_type, amount_range,
               transaction_date, filing_date, chamber
        FROM congress_trades
        WHERE ticker IS NOT NULL AND ticker != ''
        ORDER BY filing_date DESC
        LIMIT 20
    ''')

    # 6. Sector distribution
    sectors = {}
    for p in data['positions']:
        s = p.get('sector', 'Unknown') or 'Unknown'
        sectors[s] = sectors.get(s, 0) + (p.get('weight', 0) or 0)
    data['sectors'] = sectors

    # 7. Stats
    stats = {}
    for table in ['congress_trades', 'ai_intelligence_signals', 'alpha_signals',
                   'signal_quality_scores', 'convergence_signals',
                   'politician_rankings', 'portfolio_positions']:
        try:
            row = query_db(f'SELECT COUNT(*) as cnt FROM {table}')
            stats[table] = row[0]['cnt'] if row else 0
        except Exception:
            stats[table] = 0
    data['stats'] = stats

    # 8. Trade type distribution
    data['trade_types'] = query_db('''
        SELECT transaction_type, COUNT(*) as cnt
        FROM congress_trades
        GROUP BY transaction_type
        ORDER BY cnt DESC
    ''')

    # 9. Chamber distribution
    data['chambers'] = query_db('''
        SELECT chamber, COUNT(*) as cnt
        FROM congress_trades
        GROUP BY chamber
        ORDER BY cnt DESC
    ''')

    # 10. Top traded tickers
    data['top_tickers'] = query_db('''
        SELECT ticker, COUNT(*) as trade_count,
               COUNT(DISTINCT politician_name) as politician_count
        FROM congress_trades
        WHERE ticker IS NOT NULL AND ticker != ''
        GROUP BY ticker
        ORDER BY trade_count DESC
        LIMIT 15
    ''')

    return data


def generate_html(data: Dict[str, Any]) -> str:
    """生成完整 HTML dashboard。"""
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # Prepare JSON data for JavaScript
    positions_json = json.dumps(data['positions'], default=str)
    signals_json = json.dumps(data['signals'], default=str)
    rankings_json = json.dumps(data['rankings'], default=str)
    convergence_json = json.dumps(data['convergence'], default=str)
    recent_trades_json = json.dumps(data['recent_trades'], default=str)
    sectors_json = json.dumps(data['sectors'], default=str)
    stats_json = json.dumps(data['stats'], default=str)
    trade_types_json = json.dumps(data['trade_types'], default=str)
    chambers_json = json.dumps(data['chambers'], default=str)
    top_tickers_json = json.dumps(data['top_tickers'], default=str)

    # Compute summary stats
    total_trades = data['stats'].get('congress_trades', 0)
    total_signals = data['stats'].get('alpha_signals', 0)
    total_positions = data['stats'].get('portfolio_positions', 0)
    convergence_count = data['stats'].get('convergence_signals', 0)
    avg_alpha = 0
    if data['signals']:
        avg_alpha = sum(s.get('alpha_5d', 0) or 0 for s in data['signals']) / len(data['signals'])

    html = f'''<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Political Alpha Monitor Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
  :root {{
    --bg: #0f172a;
    --card: #1e293b;
    --border: #334155;
    --text: #e2e8f0;
    --text-dim: #94a3b8;
    --accent: #38bdf8;
    --green: #4ade80;
    --red: #f87171;
    --yellow: #fbbf24;
    --purple: #a78bfa;
  }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.6;
  }}
  .header {{
    background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
    border-bottom: 1px solid var(--border);
    padding: 1.5rem 2rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }}
  .header h1 {{ font-size: 1.5rem; color: var(--accent); }}
  .header .meta {{ color: var(--text-dim); font-size: 0.85rem; }}
  .container {{ max-width: 1400px; margin: 0 auto; padding: 1.5rem; }}

  /* KPI Cards */
  .kpi-row {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 1rem;
    margin-bottom: 1.5rem;
  }}
  .kpi {{
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 1.2rem;
    text-align: center;
  }}
  .kpi .value {{
    font-size: 2rem;
    font-weight: 700;
    color: var(--accent);
  }}
  .kpi .label {{
    font-size: 0.85rem;
    color: var(--text-dim);
    margin-top: 0.3rem;
  }}
  .kpi.green .value {{ color: var(--green); }}
  .kpi.yellow .value {{ color: var(--yellow); }}
  .kpi.purple .value {{ color: var(--purple); }}

  /* Grid Layout */
  .grid-2 {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1.5rem;
    margin-bottom: 1.5rem;
  }}
  .grid-3 {{
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: 1.5rem;
    margin-bottom: 1.5rem;
  }}
  @media (max-width: 900px) {{
    .grid-2, .grid-3 {{ grid-template-columns: 1fr; }}
  }}

  /* Cards */
  .card {{
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 1.2rem;
  }}
  .card h2 {{
    font-size: 1.1rem;
    margin-bottom: 1rem;
    color: var(--text);
    border-bottom: 1px solid var(--border);
    padding-bottom: 0.5rem;
  }}

  /* Tables */
  table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 0.85rem;
  }}
  th, td {{
    padding: 0.5rem 0.6rem;
    text-align: left;
    border-bottom: 1px solid var(--border);
  }}
  th {{
    color: var(--text-dim);
    font-weight: 600;
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }}
  tr:hover {{ background: rgba(56, 189, 248, 0.05); }}

  /* Tags */
  .tag {{
    display: inline-block;
    padding: 0.15rem 0.5rem;
    border-radius: 4px;
    font-size: 0.75rem;
    font-weight: 600;
  }}
  .tag-long {{ background: rgba(74, 222, 128, 0.15); color: var(--green); }}
  .tag-short {{ background: rgba(248, 113, 113, 0.15); color: var(--red); }}
  .tag-buy {{ background: rgba(74, 222, 128, 0.15); color: var(--green); }}
  .tag-sale {{ background: rgba(248, 113, 113, 0.15); color: var(--red); }}
  .tag-high {{ background: rgba(248, 113, 113, 0.15); color: var(--red); }}
  .tag-medium {{ background: rgba(251, 191, 36, 0.15); color: var(--yellow); }}
  .tag-house {{ background: rgba(56, 189, 248, 0.15); color: var(--accent); }}
  .tag-senate {{ background: rgba(167, 139, 250, 0.15); color: var(--purple); }}

  /* Progress bar */
  .progress-bar {{
    height: 8px;
    background: var(--border);
    border-radius: 4px;
    overflow: hidden;
    margin-top: 0.3rem;
  }}
  .progress-fill {{
    height: 100%;
    border-radius: 4px;
    background: linear-gradient(90deg, var(--accent), var(--green));
  }}

  /* Chart containers */
  .chart-container {{
    position: relative;
    height: 280px;
  }}

  /* Footer */
  .footer {{
    text-align: center;
    padding: 2rem;
    color: var(--text-dim);
    font-size: 0.8rem;
    border-top: 1px solid var(--border);
    margin-top: 2rem;
  }}

  /* Signal strength bar */
  .strength-bar {{
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }}
  .strength-bar .bar {{
    flex: 1;
    height: 6px;
    background: var(--border);
    border-radius: 3px;
    overflow: hidden;
  }}
  .strength-bar .fill {{
    height: 100%;
    border-radius: 3px;
  }}
</style>
</head>
<body>

<div class="header">
  <div>
    <h1>Political Alpha Monitor</h1>
    <div class="meta">Congressional Trading Intelligence Dashboard</div>
  </div>
  <div class="meta" style="text-align:right">
    <div>Generated: {now}</div>
    <div>Data source: data/data.db</div>
  </div>
</div>

<div class="container">

  <!-- KPI Row -->
  <div class="kpi-row">
    <div class="kpi">
      <div class="value">{total_trades}</div>
      <div class="label">Congress Trades</div>
    </div>
    <div class="kpi green">
      <div class="value">{total_signals}</div>
      <div class="label">Alpha Signals</div>
    </div>
    <div class="kpi yellow">
      <div class="value">{total_positions}</div>
      <div class="label">Portfolio Positions</div>
    </div>
    <div class="kpi purple">
      <div class="value">{convergence_count}</div>
      <div class="label">Convergence Events</div>
    </div>
    <div class="kpi green">
      <div class="value">+{avg_alpha:.2f}%</div>
      <div class="label">Avg Alpha (5d)</div>
    </div>
  </div>

  <!-- Charts Row -->
  <div class="grid-2">
    <div class="card">
      <h2>Portfolio Sector Allocation</h2>
      <div class="chart-container">
        <canvas id="sectorChart"></canvas>
      </div>
    </div>
    <div class="card">
      <h2>Top Traded Tickers</h2>
      <div class="chart-container">
        <canvas id="tickerChart"></canvas>
      </div>
    </div>
  </div>

  <!-- Signal Strength + Convergence -->
  <div class="grid-2">
    <div class="card">
      <h2>Top Alpha Signals</h2>
      <table>
        <thead>
          <tr>
            <th>Ticker</th>
            <th>Direction</th>
            <th>Alpha 5d</th>
            <th>Alpha 20d</th>
            <th>Strength</th>
          </tr>
        </thead>
        <tbody id="signalsTable"></tbody>
      </table>
    </div>
    <div class="card">
      <h2>Convergence Signals</h2>
      <table>
        <thead>
          <tr>
            <th>Ticker</th>
            <th>Direction</th>
            <th>Politicians</th>
            <th>Score</th>
          </tr>
        </thead>
        <tbody id="convergenceTable"></tbody>
      </table>
      <div style="margin-top:1rem">
        <h2>Trade Type Distribution</h2>
        <div class="chart-container" style="height:200px">
          <canvas id="tradeTypeChart"></canvas>
        </div>
      </div>
    </div>
  </div>

  <!-- Portfolio Positions -->
  <div class="card" style="margin-bottom:1.5rem">
    <h2>Portfolio Positions (Top 20)</h2>
    <table>
      <thead>
        <tr>
          <th>#</th>
          <th>Ticker</th>
          <th>Sector</th>
          <th>Weight</th>
          <th>Conviction</th>
          <th>Alpha 5d</th>
          <th>Volatility</th>
          <th>Sharpe</th>
        </tr>
      </thead>
      <tbody id="positionsTable"></tbody>
    </table>
  </div>

  <!-- Rankings + Recent Trades -->
  <div class="grid-2">
    <div class="card">
      <h2>Politician Intelligence Score (PIS)</h2>
      <table>
        <thead>
          <tr>
            <th>Rank</th>
            <th>Politician</th>
            <th>Chamber</th>
            <th>Trades</th>
            <th>PIS</th>
          </tr>
        </thead>
        <tbody id="rankingsTable"></tbody>
      </table>
    </div>
    <div class="card">
      <h2>Recent Filings</h2>
      <table>
        <thead>
          <tr>
            <th>Politician</th>
            <th>Ticker</th>
            <th>Type</th>
            <th>Amount</th>
            <th>Filed</th>
          </tr>
        </thead>
        <tbody id="recentTable"></tbody>
      </table>
    </div>
  </div>

</div>

<div class="footer">
  Political Alpha Monitor v2.0 | Congressional Trading Intelligence System<br>
  Research use only. Not investment advice. Past performance does not guarantee future results.
</div>

<script>
// ── Data ──
const positions = {positions_json};
const signals = {signals_json};
const rankings = {rankings_json};
const convergence = {convergence_json};
const recentTrades = {recent_trades_json};
const sectors = {sectors_json};
const tradeTypes = {trade_types_json};
const topTickers = {top_tickers_json};

// ── Color palette ──
const colors = [
  '#38bdf8', '#4ade80', '#fbbf24', '#a78bfa', '#f87171',
  '#fb923c', '#2dd4bf', '#e879f9', '#818cf8', '#34d399'
];

// ── Sector Pie Chart ──
const sectorLabels = Object.keys(sectors);
const sectorValues = Object.values(sectors).map(v => (v * 100).toFixed(1));
new Chart(document.getElementById('sectorChart'), {{
  type: 'doughnut',
  data: {{
    labels: sectorLabels,
    datasets: [{{ data: sectorValues, backgroundColor: colors }}]
  }},
  options: {{
    responsive: true,
    maintainAspectRatio: false,
    plugins: {{
      legend: {{
        position: 'right',
        labels: {{ color: '#94a3b8', font: {{ size: 11 }} }}
      }},
      tooltip: {{
        callbacks: {{
          label: ctx => `${{ctx.label}}: ${{ctx.raw}}%`
        }}
      }}
    }}
  }}
}});

// ── Top Tickers Bar Chart ──
new Chart(document.getElementById('tickerChart'), {{
  type: 'bar',
  data: {{
    labels: topTickers.map(t => t.ticker),
    datasets: [
      {{
        label: 'Trades',
        data: topTickers.map(t => t.trade_count),
        backgroundColor: '#38bdf8',
        borderRadius: 4
      }},
      {{
        label: 'Politicians',
        data: topTickers.map(t => t.politician_count),
        backgroundColor: '#a78bfa',
        borderRadius: 4
      }}
    ]
  }},
  options: {{
    responsive: true,
    maintainAspectRatio: false,
    scales: {{
      x: {{ ticks: {{ color: '#94a3b8' }}, grid: {{ display: false }} }},
      y: {{ ticks: {{ color: '#94a3b8' }}, grid: {{ color: '#334155' }} }}
    }},
    plugins: {{
      legend: {{ labels: {{ color: '#94a3b8' }} }}
    }}
  }}
}});

// ── Trade Type Chart ──
new Chart(document.getElementById('tradeTypeChart'), {{
  type: 'pie',
  data: {{
    labels: tradeTypes.map(t => t.transaction_type),
    datasets: [{{
      data: tradeTypes.map(t => t.cnt),
      backgroundColor: ['#4ade80', '#f87171', '#fbbf24', '#a78bfa', '#38bdf8']
    }}]
  }},
  options: {{
    responsive: true,
    maintainAspectRatio: false,
    plugins: {{
      legend: {{
        position: 'bottom',
        labels: {{ color: '#94a3b8', font: {{ size: 11 }} }}
      }}
    }}
  }}
}});

// ── Signals Table ──
const signalsBody = document.getElementById('signalsTable');
signals.forEach(s => {{
  const dirClass = s.direction === 'LONG' ? 'tag-long' : 'tag-short';
  const alpha5d = s.alpha_5d ? s.alpha_5d.toFixed(3) : '-';
  const alpha20d = s.alpha_20d ? s.alpha_20d.toFixed(3) : '-';
  const strength = s.signal_strength ? s.signal_strength : 0;
  const strengthPct = (strength * 100).toFixed(0);
  const barColor = strength > 0.8 ? '#4ade80' : strength > 0.5 ? '#fbbf24' : '#f87171';
  signalsBody.innerHTML += `<tr>
    <td><strong>${{s.ticker}}</strong></td>
    <td><span class="tag ${{dirClass}}">${{s.direction}}</span></td>
    <td>+${{alpha5d}}%</td>
    <td>+${{alpha20d}}%</td>
    <td>
      <div class="strength-bar">
        <div class="bar"><div class="fill" style="width:${{strengthPct}}%;background:${{barColor}}"></div></div>
        <span style="font-size:0.75rem;color:#94a3b8">${{strengthPct}}%</span>
      </div>
    </td>
  </tr>`;
}});

// ── Convergence Table ──
const convBody = document.getElementById('convergenceTable');
convergence.forEach(c => {{
  const dirClass = (c.direction || '').toLowerCase().includes('buy') ? 'tag-buy' : 'tag-sale';
  convBody.innerHTML += `<tr>
    <td><strong>${{c.ticker}}</strong></td>
    <td><span class="tag ${{dirClass}}">${{c.direction}}</span></td>
    <td>${{c.politician_count || c.politicians || '-'}}</td>
    <td>${{c.score ? c.score.toFixed(2) : '-'}}</td>
  </tr>`;
}});

// ── Positions Table ──
const posBody = document.getElementById('positionsTable');
positions.slice(0, 20).forEach((p, i) => {{
  const weight = p.weight ? (p.weight * 100).toFixed(2) : '-';
  const conviction = p.conviction_score ? p.conviction_score.toFixed(1) : '-';
  const alpha = p.expected_alpha_5d ? p.expected_alpha_5d.toFixed(3) : '-';
  const vol = p.volatility_30d ? (p.volatility_30d * 100).toFixed(1) : '-';
  const sharpe = p.sharpe_estimate ? p.sharpe_estimate.toFixed(2) : '-';
  posBody.innerHTML += `<tr>
    <td>${{i + 1}}</td>
    <td><strong>${{p.ticker}}</strong></td>
    <td style="color:#94a3b8">${{p.sector || '-'}}</td>
    <td>
      <div class="progress-bar" style="width:100px">
        <div class="progress-fill" style="width:${{Math.min(weight, 100)}}%"></div>
      </div>
      <span style="font-size:0.75rem">${{weight}}%</span>
    </td>
    <td>${{conviction}}</td>
    <td style="color:#4ade80">+${{alpha}}%</td>
    <td>${{vol}}%</td>
    <td>${{sharpe}}</td>
  </tr>`;
}});

// ── Rankings Table ──
const rankBody = document.getElementById('rankingsTable');
rankings.forEach(r => {{
  const chamberClass = r.chamber === 'House' ? 'tag-house' : 'tag-senate';
  const pis = r.pis_total ? r.pis_total.toFixed(1) : '-';
  const grade = r.pis_total >= 50 ? 'A' : r.pis_total >= 45 ? 'B' : r.pis_total >= 35 ? 'C' : 'D';
  const gradeColor = grade === 'A' ? '#4ade80' : grade === 'B' ? '#38bdf8' : '#fbbf24';
  rankBody.innerHTML += `<tr>
    <td>#${{r.rank}}</td>
    <td>${{r.politician_name}}</td>
    <td><span class="tag ${{chamberClass}}">${{r.chamber}}</span></td>
    <td>${{r.total_trades}}</td>
    <td><span style="color:${{gradeColor}};font-weight:700">${{pis}} (${{grade}})</span></td>
  </tr>`;
}});

// ── Recent Trades Table ──
const recentBody = document.getElementById('recentTable');
recentTrades.forEach(t => {{
  const typeClass = (t.transaction_type || '').toLowerCase().includes('buy') ? 'tag-buy' : 'tag-sale';
  const amount = t.amount_range || '-';
  const shortAmount = amount.replace('$', '').replace(/,/g, '').split(' - ')[0];
  recentBody.innerHTML += `<tr>
    <td>${{t.politician_name}}</td>
    <td><strong>${{t.ticker || '-'}}</strong></td>
    <td><span class="tag ${{typeClass}}">${{t.transaction_type}}</span></td>
    <td style="font-size:0.75rem">${{amount}}</td>
    <td style="color:#94a3b8;font-size:0.8rem">${{t.filing_date || '-'}}</td>
  </tr>`;
}});
</script>

</body>
</html>'''

    return html


def main():
    parser = argparse.ArgumentParser(
        description='Political Alpha Monitor — Dashboard Generator'
    )
    parser.add_argument('--output', '-o', type=str,
                        default='docs/reports/dashboard.html',
                        help='Output HTML file path')
    parser.add_argument('--db', type=str, default=DB_PATH,
                        help='Database path')
    args = parser.parse_args()

    print(f"  Collecting data from {args.db}...")
    data = get_dashboard_data()

    print(f"  Generating dashboard...")
    html = generate_html(data)

    # Ensure output directory exists
    os.makedirs(os.path.dirname(args.output) or '.', exist_ok=True)

    with open(args.output, 'w', encoding='utf-8') as f:
        f.write(html)

    size_kb = os.path.getsize(args.output) / 1024
    print(f"  [OK] Dashboard generated: {args.output} ({size_kb:.1f} KB)")
    print(f"  Open in browser to view.")


if __name__ == '__main__':
    main()
