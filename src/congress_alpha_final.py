import pandas as pd
import requests
import logging
from datetime import datetime, timedelta
import io

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("CongressAlpha")

class CongressAlphaTool:
    HOUSE_URL = "https://raw.githubusercontent.com/sw-yx/house-stock-watcher-data/master/data/all_transactions.json"
    SENATE_URL = "https://raw.githubusercontent.com/timothycarambat/senate-stock-watcher-data/master/data/all_transactions.csv"

    def __init__(self):
        self.data = pd.DataFrame()

    def fetch_data(self):
        logger.info("Fetching House & Senate data from stable sources...")
        try:
            # Fetch House (JSON)
            h_resp = requests.get(self.HOUSE_URL, timeout=30)
            if h_resp.status_code == 200:
                h_df = pd.DataFrame(h_resp.json())
                h_df['chamber'] = 'House'
                # Standardize columns
                if 'representative' in h_df.columns:
                    h_df = h_df.rename(columns={'representative': 'name'})
            else:
                logger.error(f"House data 404: {self.HOUSE_URL}")
                h_df = pd.DataFrame()

            # Fetch Senate (CSV)
            s_resp = requests.get(self.SENATE_URL, timeout=30)
            if s_resp.status_code == 200:
                s_df = pd.read_csv(io.StringIO(s_resp.text))
                s_df['chamber'] = 'Senate'
                if 'representative' in s_df.columns:
                    s_df = s_df.rename(columns={'representative': 'name'})
                elif 'senator' in s_df.columns:
                    s_df = s_df.rename(columns={'senator': 'name'})
            else:
                logger.error(f"Senate data 404: {self.SENATE_URL}")
                s_df = pd.DataFrame()

            self.data = pd.concat([h_df, s_df], ignore_index=True)
            logger.info(f"Successfully loaded {len(self.data)} historical records.")
            return not self.data.empty
        except Exception as e:
            logger.error(f"Failed to fetch data: {e}")
            return False

    def analyze(self, days=30):
        if self.data.empty: return
        
        df = self.data.copy()
        df['transaction_date'] = pd.to_datetime(df['transaction_date'], errors='coerce')
        df['disclosure_date'] = pd.to_datetime(df.get('disclosure_date', df['transaction_date']), errors='coerce')
        df = df.dropna(subset=['transaction_date', 'ticker'])
        
        # Filter for 2025-2026 data
        recent_df = df[df['disclosure_date'] >= (datetime.now() - timedelta(days=days))]
        
        print("\n" + "🔥"*20)
        print(f" LATEST CONGRESSIONAL TRADES (Last {days} Days)")
        print("🔥"*20)
        if not recent_df.empty:
            # Sort by most recent disclosure
            latest = recent_df.sort_values(by='disclosure_date', ascending=False)
            print(latest[['disclosure_date', 'name', 'ticker', 'type', 'amount', 'chamber']].head(20))
        else:
            print(f"No records found in the last {days} days.")

        # Simple Ticker Accumulation
        print("\n" + "💎"*20)
        print(" TOP TICKERS BY DISCLOSURE COUNT")
        print("💎"*20)
        print(recent_df['ticker'].value_counts().head(10))

if __name__ == "__main__":
    tool = CongressAlphaTool()
    if tool.fetch_data():
        tool.analyze(days=60) # Look back 60 days to see the turn of the year