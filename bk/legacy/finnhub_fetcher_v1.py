import requests
import pandas as pd
import logging
import time
from datetime import datetime, timedelta
from config_v1 import ConfigV1

logger = logging.getLogger(__name__)

class FinnhubCongressV1:
    """
    Fetcher for US Congress Trades using Finnhub API.
    Docs: https://finnhub.io/docs/api/congressional-trading
    """
    BASE_URL = "https://finnhub.io/api/v1"

    def __init__(self):
        self.api_key = ConfigV1.FINNHUB_KEY
        if not self.api_key:
            # Try to get from .env directly if ConfigV1 failed
            from dotenv import load_dotenv
            import os
            load_dotenv()
            self.api_key = os.getenv("FINNHUB_API_KEY")

    def fetch_all_trades(self, days=30):
        """
        Finnhub's congress endpoint typically requires a symbol or returns latest.
        We will fetch the latest global trades.
        """
        url = f"{self.BASE_URL}/stock/congressional-trading"
        params = {"token": self.api_key}
        
        logger.info("Fetching latest Congress trades from Finnhub...")
        try:
            response = requests.get(url, params=params, timeout=20)
            response.raise_for_status()
            data = response.json()
            
            if 'data' in data:
                df = pd.DataFrame(data['data'])
                logger.info(f"Fetched {len(df)} recent trades from Finnhub.")
                return df
            return pd.DataFrame()
        except Exception as e:
            logger.error(f"Finnhub Fetch Error: {e}")
            return pd.DataFrame()

    def get_sector_info(self, symbol):
        """
        Fetches sector info using Finnhub's profile2 endpoint.
        This avoids the Yahoo Finance rate limit.
        """
        url = f"{self.BASE_URL}/stock/profile2"
        params = {"symbol": symbol, "token": self.api_key}
        try:
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                res_data = response.json()
                return {
                    'sector': res_data.get('finnhubIndustry', 'Unknown'),
                    'name': res_data.get('name', 'Unknown')
                }
        except:
            pass
        return {'sector': 'Unknown', 'name': 'Unknown'}
