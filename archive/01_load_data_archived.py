import os
import time
import pandas as pd
from entsoe import EntsoePandasClient
from entsoe.exceptions import NoMatchingDataError
from dotenv import load_dotenv
from pathlib import Path

# Source - https://stackoverflow.com/a
# Posted by jrd1, modified by community. See post 'Timeline' for change history
# Retrieved 2025-12-10, License - CC BY-SA 4.0

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# 1. Setup Environment
load_dotenv()  # Load API key from .env file
API_KEY = os.getenv("ENTSOE_API_KEY")
client = EntsoePandasClient(api_key=API_KEY)

if not API_KEY:
    raise ValueError("❌ API Key missing! Please set ENTSOE_API_KEY in your .env file.")

# 2. Configuration
START_DATE = pd.Timestamp("2024-01-01", tz="UTC")
END_DATE = pd.Timestamp("2025-01-01", tz="UTC")
OUTPUT_DIR = PROJECT_ROOT / "data" / "01_raw"
OUTPUT_FILE = OUTPUT_DIR / "generation_2024_raw.csv"

# List of common European country codes (ISO-3166-1 alpha-2 / ENTSOE codes)
# Note: Some small regions are excluded to keep it robust.
# COUNTRIES = [
#     "AT", "BE", "BG", "CH", "CZ", "DE", "DK", "EE", "ES", "FI", 
#     "FR", "GR", "HR", "HU", "IE", "IT", "LT", "LU", "LV", "NL", 
#     "NO", "PL", "PT", "RO", "SE", "SI", "SK", "UK"
# ]
COUNTRIES = ["AT", "IT"]    #short list for testing

# We only want these specific generation types
TARGET_RENEWABLES = [
    'Solar',
    'Wind Onshore',
    'Wind Offshore'
]



def load_data():
    """
    Loops through country codes and loads data from entsoe for each of the listed country,
    concentenates into one single csv, and filter for wind/solar
    """
    print(f"Starting data ingestion from ENSTOE ({START_DATE} to {END_DATE})")
    # Ensure output directory exists

    os.makedirs(OUTPUT_DIR, exist_ok=True) # os.makedirs works with Path objects

    all_data = []
    try:
         for country in COUNTRIES:
            print(f"...fetching data for {country}...")
            df = client.query_generation(country_code=country, start=START_DATE, end=END_DATE, psr_type=None)
            
            if 'Actual Aggregated' in df.columns.get_level_values(1):
                df = df.xs('Actual Aggregated', level=1, axis=1)
            else:
            # Fallback: If the API returns a flat index or different naming
                df.columns = df.columns.droplevel(1)

            # 2. Filter for our target renewables
            # (We use intersection to avoid errors if a country lacks 'Wind Offshore')
            available_cols = [col for col in TARGET_RENEWABLES if col in df.columns]
            
            df_filtered = df[available_cols].copy()
            
            df_filtered = df_filtered.resample("1h").mean()
            df_filtered["Country"] = country
            all_data.append(df_filtered)
            time.sleep(1)
    
    except NoMatchingDataError:
            print(f"⚠️ No data provided by ENTSOE.")
    except Exception as e:
            print(f"❌ Error: {str(e)}")   

    final_df = pd.concat(all_data)

    # 2. Reset Index to turn the Timestamp Index into a Column
    # This moves the index (timestamp) into the dataframe as a regular column
    # final_df = final_df.reset_index()
    #final_df.index = pd.to_datetime(final_df.index, utc=True)
    #final_df = final_df.groupby("Country").resample("1h").mean(numeric_only=True)
    # 3. Rename the first column (which is now the timestamp)
    # The new column is likely named 'index' or 'level_0', we force it to 'datetime_utc'
    #timestamp_idx = df.loc[""]
    #final_df = final_df.rename(columns={final_df.columns[1]: 'datetime_utc'})

    # 4. Reorder Columns explicitly
    # We want: Timestamp -> Country -> [Generation Columns...]
    # Get list of all columns
    #cols = list(final_df.columns)
    
    # Remove 'datetime_utc' and 'country' from the list to handle the rest dynamically
    #cols.remove('datetime_utc')
    #cols.remove('Country')
    
    # Construct the new order
   # new_order = ['datetime_utc', 'Country'] + cols
   # final_df = final_df[new_order]

    final_df.to_csv(OUTPUT_FILE)
    print(final_df.head())
    return

if __name__=="__main__":
    load_data()