import logging
import os
from datetime import datetime
from senate_fetcher_v1 import SenateFetcherV1
from database import init_db

# Setup logging
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, "main.log")),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("Main")

def run_pipeline():
    logger.info("Starting Political Alpha Monitor Pipeline...")
    
    # 1. Initialize Database
    init_db()
    
    # 2. Senate Scraper
    logger.info("Phase 2: Running Senate Scraper...")
    senate_fetcher = SenateFetcherV1()
    try:
        new_senate, updated_senate = senate_fetcher.run(days=2) # Run for last 2 days for daily monitor
        logger.info(f"Senate Scraper finished: {new_senate} new, {updated_senate} updated.")
    except Exception as e:
        logger.error(f"Senate Scraper failed: {e}")

    # 3. House Scraper (Placeholder for Phase 3)
    logger.info("Phase 3: House Scraper - Pending implementation.")
    
    # 4. Institutional Fetcher (Placeholder for Phase 3)
    logger.info("Phase 3: Institutional Fetcher - Pending implementation.")
    
    # 5. Notifier (Placeholder for Phase 4)
    logger.info("Phase 4: Notifier - Pending implementation.")
    
    logger.info("Pipeline execution finished.")

if __name__ == "__main__":
    run_pipeline()
