import pandas as pd
import requests
import logging
import yfinance as yf
import sys
import os

# Ensure src is in path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime, timedelta
from .config_v1 import ConfigV1
from io import StringIO

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class CongressSectorRadar:
    """
    V3.1: Aggregates Congress data AND enriches it with Sector info to find hidden trends.
    """
    
    # Using GitHub Raw for stability (House Data)
    HOUSE_URL = "https://raw.githubusercontent.com/sw-yx/house-stock-watcher-data/master/data/all_transactions.json"
    
    def __init__(self):
        self.merged_df = pd.DataFrame()

    def fetch_and_process(self):
        logger.info("Fetching House data...")
        try:
            response = requests.get(self.HOUSE_URL, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            df = pd.DataFrame(data)
            
            # 1. Basic Cleaning
            df['transaction_date'] = pd.to_datetime(df['transaction_date'], errors='coerce')
            df['disclosure_date'] = pd.to_datetime(df['disclosure_date'], errors='coerce')
            df = df.dropna(subset=['transaction_date', 'ticker'])
            
            # Filter: Last 90 Days only (Focus on recent trends)
            cutoff_date = datetime.now() - timedelta(days=90)
            df = df[df['transaction_date'] >= cutoff_date]
            
            # 2. Amount Parsing
            df[['min_amount', 'max_amount']] = df['amount'].apply(self._parse_amount).tolist()
            df['est_amount'] = (df['min_amount'] + df['max_amount']) / 2
            
            self.merged_df = df
            logger.info(f"Filtered to {len(df)} records from the last 90 days.")
            return df
            
        except Exception as e:
            logger.error(f"Error fetching data: {e}")
            return pd.DataFrame()

    def _parse_amount(self, amount_str):
        if not isinstance(amount_str, str): return 0, 0
        clean = amount_str.replace('$', '').replace(',', '').strip()
        try:
            if ' - ' in clean:
                parts = clean.split(' - ')
                return float(parts[0]), float(parts[1])
            elif '+' in clean:
                val = float(clean.replace('+', '').strip())
                return val, val * 1.5
            else:
                return 0, 0
        except: return 0, 0

    def enrich_sectors(self):
        """
        Uses yfinance to get Sector and Industry for unique tickers.
        Optimization: Batch fetching is hard with yf, so we loop unique tickers.
        """
        if self.merged_df.empty: return

        unique_tickers = self.merged_df['ticker'].unique()
        logger.info(f"Enriching sector data for {len(unique_tickers)} tickers. This may take a moment...")
        
        ticker_info = {}
        
        # Limit to top 50 most active tickers to save time for this demo
        # In production, you'd run this asynchronously or cache it.
        top_tickers = self.merged_df['ticker'].value_counts().head(30).index.tolist()
        
        for ticker in top_tickers:
            try:
                # Use Ticker object (faster than download for info)
                t = yf.Ticker(ticker)
                info = t.info
                ticker_info[ticker] = {
                    'sector': info.get('sector', 'Unknown'),
                    'industry': info.get('industry', 'Unknown')
                }
            except: ticker_info[ticker] = {'sector': 'Unknown', 'industry': 'Unknown'}
        
        # Map back to DataFrame
        self.merged_df['sector'] = self.merged_df['ticker'].map(lambda x: ticker_info.get(x, {}).get('sector', 'Unknown'))
        self.merged_df['industry'] = self.merged_df['ticker'].map(lambda x: ticker_info.get(x, {}).get('industry', 'Unknown'))
        
        # Filter out Unknowns for the report
        self.enriched_df = self.merged_df[self.merged_df['sector'] != 'Unknown']
        return self.enriched_df

    def analyze_flows(self):
        """
        Calculates Net Flow by Sector.
        """
        if getattr(self, 'enriched_df', None) is None or self.enriched_df.empty:
            logger.warning("No enriched data to analyze.")
            return

        df = self.enriched_df.copy()
        
        # Direction
        df['flow'] = df.apply(lambda x: x['est_amount'] if 'purchase' in x['type'].lower() else -x['est_amount'], axis=1)
        
        # Group by Sector
        sector_stats = df.groupby('sector')['flow'].agg(['sum', 'count', 'nunique'])
        sector_stats.columns = ['Net_Flow', 'Trade_Count', 'Unique_Tickers']
        sector_stats = sector_stats.sort_values(by='Net_Flow', ascending=False)
        
        return sector_stats

    def get_top_picks_in_sector(self, sector):
        """Returns top bought stocks in a specific sector."""
        df = self.enriched_df[self.enriched_df['sector'] == sector]
        stock_flow = df.groupby('ticker')['flow'].sum().sort_values(ascending=False)
        return stock_flow.head(3)

if __name__ == "__main__":
    radar = CongressSectorRadar()
    radar.fetch_and_process()
    radar.enrich_sectors()
    
    stats = radar.analyze_flows()
    if stats is not None:
        print("\n=== CONGRESS SECTOR FLOW (Last 90 Days) ===")
        print(stats)
        
        top_sector = stats.index[0]
        print(f"\nTop Picks in {top_sector}:")
        print(radar.get_top_picks_in_sector(top_sector))
