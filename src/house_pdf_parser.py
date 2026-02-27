import pdfplumber
import pandas as pd
import re
import os
import requests
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class HousePDFParser:
    def __init__(self):
        pass

    def download_pdf(self, url, save_path):
        try:
            # Note: House server might block standard requests, use headers
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
            }
            response = requests.get(url, headers=headers, timeout=30)
            if response.status_code == 200:
                with open(save_path, 'wb') as f:
                    f.write(response.content)
                return True
            else:
                logger.error(f"Failed to download PDF: {url}. Status: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"Error downloading PDF {url}: {e}")
            return False

    def parse_pdf(self, pdf_path):
        """
        Extracts transaction tables from a House PTR PDF.
        House PTRs usually have a table with columns: 
        Asset, Owner, Transaction Type, Date, Notification Date, Amount, Cap Gains > $200?
        """
        transactions = []
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    tables = page.extract_tables()
                    for table in tables:
                        # House PTR tables usually have headers like 'Asset', 'Transaction Type', etc.
                        # We look for rows that look like transactions
                        for row in table:
                            # Filter out headers and empty rows
                            if not row or len(row) < 5: continue
                            if 'Asset' in str(row[0]): continue
                            
                            # Basic cleaning
                            asset_desc = str(row[0]).replace('\n', ' ')
                            owner = row[1] if len(row) > 1 else ""
                            trans_type = row[2] if len(row) > 2 else ""
                            trans_date = row[3] if len(row) > 3 else ""
                            amount = row[5] if len(row) > 5 else ""
                            
                            # Filter for actual ticker if present in brackets [TK]
                            ticker_match = re.search(r'\[([A-Z]+)\]', asset_desc)
                            ticker = ticker_match.group(1) if ticker_match else ""
                            
                            if ticker or trans_date:
                                transactions.append({
                                    'asset_description': asset_desc,
                                    'ticker': ticker,
                                    'owner': owner,
                                    'type': trans_type,
                                    'transaction_date': trans_date,
                                    'amount': amount
                                })
            return transactions
        except Exception as e:
            logger.error(f"Error parsing PDF {pdf_path}: {e}")
            return []

if __name__ == "__main__":
    # Test with a known PTR PDF (if we had one locally)
    # Example: Nancy Pelosi's recent NVIDIA trade might be in a PDF
    parser = HousePDFParser()
    test_pdf_url = "https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/2024/20024361.pdf"
    test_path = "data/processed/test_ptr.pdf"
    
    if not os.path.exists("data/processed"):
        os.makedirs("data/processed")
        
    logger.info(f"Testing PDF download and parse for {test_pdf_url}...")
    if parser.download_pdf(test_pdf_url, test_path):
        trades = parser.parse_pdf(test_path)
        logger.info(f"Extracted {len(trades)} trades:")
        for t in trades:
            logger.info(t)
