import os
import time
import pandas as pd
from entsoe.entsoe import EntsoePandasClient
from entsoe.exceptions import NoMatchingDataError
from dotenv import load_dotenv
from pathlib import Path

# --- Path Setup ---
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env")
API_KEY = os.getenv("ENTSOE_API_KEY")

if not API_KEY:
    raise ValueError("❌ API Key missing! Check .env file.")

# --- Configuration ---
START_DATE = pd.Timestamp("2024-01-01", tz="UTC")
END_DATE = pd.Timestamp("2025-01-01", tz="UTC")
OUTPUT_FILE = PROJECT_ROOT / "data" / "01_raw" / "generation_2024_raw.csv"

# COUNTRIES = ["AT", "BE", "DE", "FR", "NL", "IT"]
#              #"DE", "FR", "NL", "IT", "ES", "PL", "DK", "SE", "NO"]
COUNTRIES = [
    "AT", "BE", "BG", "CH", "CZ", "DE", "DK", "EE", "ES", "FI", 
    "FR", "GR", "HR", "HU", "IE", "IT", "LT", "LU", "LV", "NL", 
    "NO", "PL", "PT", "RO", "SE", "SI", "SK", "UK"
]

# Mapping for the Fallback Mechanism
PSR_MAP = {
    'Solar': 'B16',
    'Wind Onshore': 'B19',
    'Wind Offshore': 'B18'
}

def clean_and_format(df, country_code):
    """Helper to standardize any dataframe chunk"""
    # 1. Handle MultiIndex (Drop 'Actual Consumption' or 'Aggregated' levels)
    if isinstance(df.columns, pd.MultiIndex):
        # If 'Actual Aggregated' is explicitly there, take it
        if 'Actual Aggregated' in df.columns.get_level_values(1):
            df = df.xs('Actual Aggregated', level=1, axis=1)
        else:
            # Fallback: Just drop the second level
            df.columns = df.columns.droplevel(1)

    # 2. Resample numeric data to 1h Mean
    df = df.resample('1h').mean()
    
    # 3. Add Country Code
    df["Country"] = country_code
    return df

def load_data():
    print(f"🚀 Starting Hybrid Ingestion ({START_DATE.date()} to {END_DATE.date()})")
    
    client = EntsoePandasClient(api_key=API_KEY)
    all_data = []

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    for country in COUNTRIES:
        print(f"\n🌍 Processing {country}...", end=" ")
        
        try:
            # --- STRATEGY A: The "Wholesale" Query ---
            # Best for Austria (AT), France (FR), etc.
            # We try to get ALL generation types at once.
            print("Attempting bulk download...", end=" ")
            
            df = client.query_generation(country, start=START_DATE, end=END_DATE, psr_type=None)
            
            # If successful, filter for what we need
            df = clean_and_format(df, country)
            
            # Select only target columns (ignore Biomass, Hydro, etc.)
            cols_to_keep = [c for c in ['Solar', 'Wind Onshore', 'Wind Offshore'] if c in df.columns]
            
            if not cols_to_keep:
                print("⚠️ (No Solar/Wind found) ", end="")
            else:
                df = df[cols_to_keep + ['Country']] # Keep Country column!
                all_data.append(df)
                print("✅ Success (Bulk)")
            
            time.sleep(1)
            continue # Move to next country

        except Exception as e:
            # If Strategy A fails (e.g. Belgium 400 Error), we catch it here
            print(f"⚠️ Bulk failed ({str(e)}). Switching to specific queries...")

        # --- STRATEGY B: The "Targeted" Query (Fallback) ---
        # Essential for Belgium (BE), Germany (DE)
        # We fetch Solar, Wind On, Wind Off separately and merge them.
        
        country_parts = []
        for friendly_name, psr_code in PSR_MAP.items():
            try:
                part_df = client.query_generation(country, start=START_DATE, end=END_DATE, psr_type=psr_code)
                
                # Clean this specific part
                part_df = clean_and_format(part_df, country)
                
                # Rename the single data column to 'Solar', 'Wind Onshore', etc.
                # (The clean_and_format leaves it with original name or integer, so we rename)
                data_col = [c for c in part_df.columns if c != "Country"][0]
                part_df = part_df.rename(columns={data_col: friendly_name})
                
                # We only need the data column for merging (we'll add Country later)
                country_parts.append(part_df[[friendly_name]])

            except NoMatchingDataError:
                pass # Normal (e.g. No Offshore for AT)
            except Exception:
                pass

        if country_parts:
            # Merge parts on Timestamp
            full_country_df = pd.concat(country_parts, axis=1)
            full_country_df["Country"] = country # Add label back
            all_data.append(full_country_df)
            print(f"   ✅ Success (Merged {len(country_parts)} types)")
        else:
            print(f"   ❌ Failed completely.")

    # --- Final Assembly ---
    if not all_data:
        print("❌ No data collected.")
        return

    print("\n📦 Combining and Saving...")
    final_df = pd.concat(all_data)

    # 1. Reset Index -> 'datetime_utc'
    final_df.index = pd.to_datetime(final_df.index, utc=True)
    final_df = final_df.reset_index()
    final_df = final_df.rename(columns={final_df.columns[0]: 'datetime_utc'})

    # 2. Reorder columns
    cols = ['datetime_utc', 'Country', 'Solar', 'Wind Onshore', 'Wind Offshore']
    # Filter for cols that actually exist (in case no country had Offshore)
    existing_cols = [c for c in cols if c in final_df.columns]
    final_df = final_df[existing_cols]

    final_df.to_csv(OUTPUT_FILE, index=False)
    print(f"✅ DONE! Saved to: {OUTPUT_FILE}")

if __name__ == "__main__":
    load_data()