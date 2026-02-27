"""
Congress Trading Fetcher - 整合版本
結合 burd5/congress_stock_trading 專案的架構與你現有的資料抓取功能
"""

import pandas as pd
import requests
import logging
import sqlite3
import json
from datetime import datetime, timedelta
from curl_cffi import requests as cf_requests
from bs4 import BeautifulSoup
import os
import sys

# Ensure src is in path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from database import DB_PATH, generate_hash

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("CongressTradingFetcher")


class CongressTradingFetcher:
    """
    整合國會議員股票交易資料的統一介面
    參考 burd5/congress_stock_trading 專案架構
    
    資料來源：
    1. 參議院官方網站 (efdsearch.senate.gov) - 使用 AJAX API 抓取表格資料
    2. 眾議院官方網站 (disclosures-clerk.house.gov) - 需解析 PDF 文件
    """
    
    # 官方網站
    SENATE_BASE_URL = "https://efdsearch.senate.gov"
    HOUSE_BASE_URL = "https://disclosures-clerk.house.gov"
    
    def __init__(self, db_path=None):
        """
        初始化 Congress Trading Fetcher
        
        Args:
            db_path: SQLite 資料庫路徑，預設使用 database.py 中的 DB_PATH
        """
        self.db_path = db_path or DB_PATH
        self.data = pd.DataFrame()
        self.init_db()
        
    def init_db(self):
        """初始化資料庫表格"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 建立國會交易主表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS congress_trades (
                record_id TEXT PRIMARY KEY,
                chamber TEXT NOT NULL,
                name TEXT NOT NULL,
                ticker TEXT,
                transaction_date TEXT,
                disclosure_date TEXT,
                transaction_type TEXT,
                amount TEXT,
                asset_description TEXT,
                owner TEXT,
                report_url TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                data_source TEXT
            )
        ''')
        
        # 建立參議院報告表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS senate_reports (
                report_id TEXT PRIMARY KEY,
                senator_name TEXT,
                report_type TEXT,
                filing_date TEXT,
                report_url TEXT,
                is_processed INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 建立眾議院報告表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS house_reports (
                doc_id TEXT PRIMARY KEY,
                representative_name TEXT,
                filing_type TEXT,
                filing_date TEXT,
                year INTEGER,
                pdf_url TEXT,
                is_processed INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info(f"Database initialized at {self.db_path}")
    
    def fetch_senate_transactions(self, start_date=None, end_date=None, days_back=30):
        """
        從參議院官方網站抓取交易資料（使用 AJAX API）
        參考 burd5/congress_stock_trading 的 Senate scraper
        
        Args:
            start_date: 開始日期 (MM/DD/YYYY)
            end_date: 結束日期 (MM/DD/YYYY)
            days_back: 如果未指定日期，往前抓取的天數
        
        Returns:
            bool: 是否成功
        """
        logger.info("Fetching Senate transactions from official website...")
        
        # 如果未指定日期，使用 days_back
        if not start_date or not end_date:
            end_dt = datetime.now()
            start_dt = end_dt - timedelta(days=days_back)
            start_date = start_dt.strftime("%m/%d/%Y")
            end_date = end_dt.strftime("%m/%d/%Y")
        
        try:
            from senate_fetcher_v1 import SenateFetcherV1
            
            fetcher = SenateFetcherV1()
            reports = fetcher.fetch_report_list(start_date, end_date)
            
            if reports:
                logger.info(f"✓ Found {len(reports)} Senate reports")
                
                # 轉換為 DataFrame
                senate_df = pd.DataFrame(reports)
                senate_df['chamber'] = 'Senate'
                senate_df['data_source'] = 'senate_official'
                
                self.data = senate_df
                return True
            else:
                logger.warning("No Senate reports found")
                return False
                
        except Exception as e:
            logger.error(f"Failed to fetch Senate data: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def fetch_senate_official(self, start_date=None, end_date=None, days_back=30):
        """
        從參議院官方網站獲取最新資料
        
        Args:
            start_date: 開始日期 (MM/DD/YYYY 格式)
            end_date: 結束日期 (MM/DD/YYYY 格式)
            days_back: 如果未指定日期，往前抓取的天數
        
        Returns:
            pd.DataFrame: 參議院交易資料
        """
        logger.info("Fetching latest data from Senate official website...")
        
        # 如果未指定日期，使用 days_back
        if not start_date or not end_date:
            end_dt = datetime.now()
            start_dt = end_dt - timedelta(days=days_back)
            start_date = start_dt.strftime("%m/%d/%Y")
            end_date = end_dt.strftime("%m/%d/%Y")
        
        try:
            from senate_fetcher_v1 import SenateFetcherV1
            house_transactions(self, year=None):
        """
        從眾議院官方網站抓取交易資料（需解析 PDF）
        參考 burd5/congress_stock_trading 的 House scraper
        
        Args:
            year: 年份，預設為當前年份
        
        Returns:
            bool: 是否成功
        """
        if not year:
            year = datetime.now().year
        
        logger.info(f"Fetching House transactions for {year} from official website...")
        logger.info("Note: House data requires PDF parsing, this may take a while...")
        
        try:
            from house_fetcher_v3_ajax import HouseAjaxFetcher
            
            fetcher = HouseAjaxFetcher(self.db_path)
            fetcher.fetch_latest()
            
            # 從資料庫讀取資料
            conn = sqlite3.connect(self.db_path)
            house_df = pd.read_sql_query(
                "SELECT * FROM house_reports WHERE year = ? ORDER BY filing_date DESC",
                conn,
                params=(year,)
            )
            conn.close()
            
            if not house_df.empty:
                house_df['chamber'] = 'House'
                house_df['data_source'] = 'house_official'
                logger.info(f"✓ Found {len(house_df)} House reports")
                
                if self.data.empty:
                    self.data = house_df
                else:
                    self.data = pd.concat([self.data, house_df], ignore_index=True)
                return True
            else:
                logger.warning(f"No House reports found for {year}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to fetch House data: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def fetch_all(self, days_back=30, include_house=True):
        """
        從官方網站抓取所有資料
        
        Args:
            days_back: 參議院資料回溯天數
            include_house: 是否包含眾議院（會比較慢，因為需要處理 PDF）
        
        Returns:
            bool: 是否成功
        """
        logger.info("=" * 60)
        logger.info("🔥 Congress Trading Fetcher - Scraping Official Sources")
        logger.info("=" * 60)
        
        success = False
        
        # 抓取參議院資料
        logger.info("\n[1/2] Fetching Senate data...")
        if self.fetch_senate_transactions(days_back=days_back):
            success = True
        
        # 抓取眾議院資料
        if include_house:
            logger.info("\n[2/2] Fetching House data...")
            if self.fetch_house_transactions():
                success = True
        
        if success and not self.data.empty:
            # 去重
            if 'record_id' in self.data.columns:
                original_count = len(self.data)
                self.data = self.data.drop_duplicates(subset=['record_id'])
                removed = original_count - len(self.data)
                if removed > 0:
                    logger.info(f"Removed {removed} duplicate records"
        if 'record_id' not in df.columns:
            df['record_id'] = df.apply(
                lambda row: generate_hash(f"{row.get('name', '')}_{row.get('ticker', '')}_{row.get('transaction_date', '')}"),
                axis=1
            )
        
        # 選擇需要的欄位
        columns = ['record_id', 'chamber', 'name', 'ticker', 'transaction_date', 
                   'disclosure_date', 'transaction_type', 'amount', 'asset_description',
                   'owner', 'report_url', 'data_source']
        
        # 只保留存在的欄位
        available_columns = [col for col in columns if col in df.columns]
        df_to_save = df[available_columns]
        
        # 儲存到資料庫 (使用 replace 避免重複)
        df_to_save.to_sql('congress_trades', conn, if_exists='append', index=False)
        
        conn.commit()
        conn.close()
        
        logger.info(f"✓ {len(df_to_save)} records saved to database")
        return len(df_to_save)
    
    def analyze(self, days=30, top_n=20):
        """
        分析交易資料
        
        Args:
            days: 分析最近幾天的資料
            top_n: 顯示前 N 名
        """
        if self.data.empty:
            logger.warning("No data to analyze")
            return
        
        df = self.data.copy()
        
        # 轉換日期欄位
        date_col = 'disclosure_date' if 'disclosure_date' in df.columns else 'transaction_date'
        if date_col in df.columns:
            df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
            df = df.dropna(subset=[date_col])
            
            # 過濾最近的資料
            recent_df = df[df[date_col] >= (datetime.now() - timedelta(days=days))]
        else:
            recent_df = df
        
        print("\n" + "🔥" * 30)
        print(f" LATEST CONGRESSIONAL TRADES (Last {days} Days)")
        print("🔥" * 30)
        
        if not recent_df.empty:
            # 顯示欄位（根據可用欄位調整）
            display_cols = []
            for col in [date_col, 'name', 'ticker', 'transaction_type', 'amount', 'chamber', 'data_source']:
                if col in recent_df.columns:
                    display_cols.append(col)
            
            latest = recent_df.sort_values(by=date_col, ascending=False)
            print(latest[display_cols].head(top_n).to_string(index=False))
        else:
            print(f"No records found in the last {days} days.")
        
        # 熱門股票統計
        if 'ticker' in recent_df.columns:
            print("\n" + "💎" * 30)
            print(" TOP TICKERS BY DISCLOSURE COUNT")
            print("💎" * 30)
            ticker_counts = recent_df['ticker'].value_counts().head(10)
            print(ticker_counts.to_string())
        
        # 按議員統計
        if 'name' in recent_df.columns:
            print("\n" + "👥" * 30)
            print(" TOP TRADERS BY TRANSACTION COUNT")
            print("👥" * 30)
            trader_counts = recent_df['name'].value_counts().head(10)
            print(trader_counts.to_string())
        
        # 交易類型統計
        if 'transaction_type' in recent_df.columns:
            print("\n" + "📊" * 30)
            print(" TRANSACTION TYPES BREAKDOWN")
            print("📊" * 30)
            type_counts = recent_df['transaction_type'].value_counts()
            print(type_counts.to_string())
    
    def get_trades_by_ticker(self, ticker, days=90):
        """
        獲取特定股票的所有交易紀錄
        
        Args:
            ticker: 股票代碼
            days: 回溯天數
        
        Returns:
            pd.DataFrame: 交易紀錄
        """
        if self.data.empty:
            return pd.DataFrame()
        
        df = self.data.copy()
        
        # 過濾股票代碼
        if 'ticker' in df.columns:
            ticker_df = df[df['ticker'].str.upper() == ticker.upper()]
            
            # 過濾日期
            date_col = 'disclosure_date' if 'disclosure_date' in ticker_df.columns else 'transaction_date'
            if date_col in ticker_df.columns:
                ticker_df[date_col] = pd.to_datetime(ticker_df[date_col], errors='coerce')
                ticker_df = ticker_df[ticker_df[date_col] >= (datetime.now() - timedelta(days=days))]
                ticker_df = ticker_df.sort_values(by=date_col, ascending=False)
            
            return ticker_df
        
        return pd.DataFrame()
    
    def get_trades_by_politician(self, name, days=180):
        """
        獲取特定議員的所有交易紀錄
        
        Args:
            name: 議員姓名（部分匹配）
            days: 回溯天數
        
        Returns:
            pd.DataFrame: 交易紀錄
        """
        if self.data.empty:
            return pd.DataFrame()
        
        df = self.data.copy()
        
        # 過濾議員姓名
        if 'name' in df.columns:
            politician_df = df[df['name'].str.contains(name, case=False, na=False)]
            
            # 過濾日期
            date_col = 'disclosure_date' if 'disclosure_date' in politician_df.columns else 'transaction_date'
            if date_col in politician_df.columns:
                politician_df[date_col] = pd.to_datetime(politician_df[date_col], errors='coerce')
                politician_df = politician_df[politician_df[date_col] >= (datetime.now() - timedelta(days=days))]
                politician_df = politician_df.sort_values(by=date_col, ascending=False)
            
            return politician_df
        
        return pd.DataFrame()


def main():
    """主程式：示範如何使用"""
    print("\n" + "=" * 60)
    print("Congress Trading Fetcher - Demo")
    print("=" * 60 + "\n")
    
    # 初始化
    fetcher = CongressTradingFetcher()
    
    # 方案 1：只獲取 GitHub 歷史資料（最快）
    print("\n[Option 1] Fetching from GitHub (Fast)...")
    if fetcher.fetch_from_github('both'):
        fetcher.analyze(days=60, top_n=15)
    
    # 方案 2：獲取所有資料源（包含官方最新資料）
    # 注意：這會比較慢，因為要抓取官方網站
    # print("\n[Option 2] Fetching from all sources (Slow but complete)...")
    # if fetcher.fetch_all_sources(include_official=True, days_back=30):
    #     fetcher.save_to_database()
    #     fetcher.analyze(days=30, top_n=15)
    
    # 方案 3：查詢特定股票
    print("\n[Option 3] Search by ticker (NVDA)...")
    nvda_trades = fetcher.get_trades_by_ticker('NVDA', days=90)
    if not nvda_trades.empty:
        print(f"\nFound {len(nvda_trades)} NVDA trades:")
        display_cols = [col for col in ['transaction_date', 'name', 'transaction_type', 'amount', 'chamber'] 
                       if col in nvda_trades.columns]
        print(nvda_trades[display_cols].head(10).to_string(index=False))
    
    # 方案 4：查詢特定議員
    print("\n[Option 4] Search by politician (Pelosi)...")
    pelosi_trades = fetcher.get_trades_by_politician('Pelosi', days=180)
    if not pelosi_trades.empty:
        print(f"\nFound {len(pelosi_trades)} trades by Pelosi:")
        display_cols = [col for col in ['transaction_date', 'ticker', 'transaction_type', 'amount'] 
                       if col in pelosi_trades.columns]
        print(pelosi_trades[display_cols].head(10).to_string(index=False))


if __name__ == "__main__":
    main()
抓取參議院最近 30 天資料（推薦，較快）
    print("\n[Option 1] Scraping Senate data (30 days)...")
    if fetcher.fetch_senate_transactions(days_back=30):
        fetcher.save_to_database()
        fetcher.analyze(days=30, top_n=15)
    
    # 方案 2：抓取所有資料（參議院 + 眾議院）
    # 注意：眾議院需要處理 PDF，會比較慢
    # print("\n[Option 2] Scraping all sources...")
    # if fetcher.fetch_all(days_back=30, include_house=True):
    #     fetcher.save_to_database()
    #     fetcher.analyze(days=30, top_n=15