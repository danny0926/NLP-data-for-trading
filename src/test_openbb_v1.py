from openbb import obb
import pandas as pd

def test_congress_data():
    print("Fetching Congress Trades for AAPL via OpenBB...")
    try:
        # Fetching data
        res = obb.equity.gov.congress_trades(symbol="AAPL")
        
        # Convert to DataFrame
        df = res.to_df()
        
        if df.empty:
            print("No trades found for AAPL or data source unavailable.")
        else:
            print("\n=== AAPL CONGRESS TRADES ===")
            print(df.head(10))
            
    except Exception as e:
        print(f"Error during OpenBB execution: {e}")

if __name__ == "__main__":
    test_congress_data()

