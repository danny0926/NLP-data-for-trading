import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger("ETL.USASpendingFetcher")

USA_SPENDING_AWARDS_URL = "https://api.usaspending.gov/api/v2/search/spending_by_award/"
USA_SPENDING_NAICS_URL = "https://api.usaspending.gov/api/v2/search/spending_by_category/naics/"
CONTRACT_AWARD_CODES = ["A", "B", "C", "D"]
MIN_CONTRACT_AMOUNT = 100_000
CROSS_REF_WINDOW_DAYS = 90
PROJECT_ROOT = Path(__file__).parent.parent.parent
CONTRACTOR_MAP_PATH = PROJECT_ROOT / "data" / "contractor_tickers.json"
REQUEST_DELAY = 0.5
