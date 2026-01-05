import os
import sys
import time
import pandas as pd
from entsoe.entsoe import EntsoePandasClient
from entsoe.exceptions import NoMatchingDataError
from dotenv import load_dotenv
from pathlib import Path

# Add the project root to the Python path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PROJECT_ROOT))

from config import PROJECT_ROOT, DATA_FILE_RAW, TARGET_COUNTRIES, TARGET_COLS, START_DATE, END_DATE

class EnergyDataLoader:
    """
    Component responsible for extracting energy generation data from Entsoe,
    transforming it into a standardized format, and save it as csv.
    """
    
    # Constant mapping for API codes
    PSR_MAP = {
        'Solar': 'B16',
        'Wind Onshore': 'B19',
        'Wind Offshore': 'B18'
    }

    def __init__(self, config_path: Path):
            self.project_root = config_path
            self.api_key = self._get_api_key()
            self.client = EntsoePandasClient(api_key=self.api_key)
            self.data_buffer = []

    def _get_api_key(self) -> str:  # Added return type hint
        """Load and return API key from environment variables."""
        load_dotenv(self.project_root / ".env")
        key = os.getenv("ENTSOE_API_KEY")
        
        if not key:
            raise ValueError("❌ API Key missing! Check .env file.")
            
        return key

    def _clean_dataframe(self, df: pd.DataFrame, country_code: str) -> pd.DataFrame:
            """Helper to standardize any dataframe chunk (1h resampling, formatting)."""
            # 1. Handle MultiIndex columns
            if isinstance(df.columns, pd.MultiIndex):
                if 'Actual Aggregated' in df.columns.get_level_values(1):
                    df = df.xs('Actual Aggregated', level=1, axis=1) # type: ignore
                else:
                    df.columns = df.columns.droplevel(1)

            # 2. Resample numeric data to 1h Mean
            df = df.resample('1h').mean()
            
            # 3. Add Metadata
            df["Country"] = country_code
            return df

# ----------------------------------------------------------------------------------------------------------
# Because data for each country are slightly different in format and frequency, two approaches are needed
# bulk: download everything, extract needed columns afterwards
# targeted: only fetch the needed columns. Generally cleaner, but doesn't work for every country
#-----------------------------------------------------------------------------------------------------------
    def _fetch_strategy_bulk(self, country: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame | None:
            """Strategy A: Attempt to download all generation types at once."""
            print("  Attempting bulk download...", end=" ")
            df = self.client.query_generation(country, start=start, end=end, psr_type=None)
            df = self._clean_dataframe(df, country)
            
            # Filter for only the columns we care about
            cols_to_keep = [c for c in TARGET_COLS if c in df.columns]  #TARGET_COLS defined in config
            
            if not cols_to_keep:
                print("⚠️ (No Solar/Wind found) ", end="")
                return None
                
            print("✅ Success (Bulk)")
            return df[cols_to_keep + ['Country']]

    def _fetch_strategy_targeted(self, country: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame | None:
            """Strategy B: Fallback - Fetch Solar/Wind separately and merge."""
            country_parts = []
            
            for friendly_name, psr_code in self.PSR_MAP.items():
                try:
                    part_df = self.client.query_generation(country, start=start, end=end, psr_type=psr_code)
                    part_df = self._clean_dataframe(part_df, country)
                    
                    # Rename the single data column to friendly name
                    data_col = [c for c in part_df.columns if c != "Country"][0]
                    part_df = part_df.rename(columns={data_col: friendly_name})
                    
                    country_parts.append(part_df[[friendly_name]])
                except (NoMatchingDataError, Exception):
                    pass # Specific type not found for this country

            if country_parts:
                # Merge all individual parts on Timestamp index
                full_df = pd.concat(country_parts, axis=1)
                full_df["Country"] = country
                print(f"  ✅ Success (Merged {len(country_parts)} types)")
                return full_df
            
            print("  ❌ Failed completely.")
            return None

    def fetch_country_data(self, country: str, start: pd.Timestamp, end: pd.Timestamp):
            """Orchestrates the fetching logic for a single country."""
            print(f"\n🌍 Processing {country}...", end=" ")
            
            try:
                # Try Strategy A
                df = self._fetch_strategy_bulk(country, start, end)
                if df is not None:
                    self.data_buffer.append(df)
                    return
            except Exception as e:
                print(f"⚠️ Bulk failed ({str(e)}). Switching to specific queries...")

            # Fallback to Strategy B
            df = self._fetch_strategy_targeted(country, start, end)
            if df is not None:
                self.data_buffer.append(df)
            
            time.sleep(1) # Respect API limits

    def save_data(self, output_file: Path):
            """Finalizes the dataset and saves to CSV."""
            if not self.data_buffer:
                print("❌ No data collected.")
                return

            print("\n📦 Combining and Saving...")
            final_df = pd.concat(self.data_buffer)

            # Standardization
            final_df.index = pd.to_datetime(final_df.index, utc=True)
            final_df = final_df.reset_index()
            final_df = final_df.rename(columns={final_df.columns[0]: 'datetime_utc'})

            # Reorder columns safely
            desired_cols = ['datetime_utc', 'Country', 'Solar', 'Wind Onshore', 'Wind Offshore']
            existing_cols = [c for c in desired_cols if c in final_df.columns]
            final_df = final_df[existing_cols]

            # Ensure directory exists
            output_file.parent.mkdir(parents=True, exist_ok=True)
            final_df.to_csv(output_file, index=False)
            print(f"✅ DONE! Saved to: {output_file}")

    def run_pipeline(self, countries: list, start_date: str, end_date: str, output_path: Path):
            """Public entry point to run the full ingestion process."""
            start = pd.Timestamp(start_date, tz="UTC")
            end = pd.Timestamp(end_date, tz="UTC")
            out_file = self.project_root / output_path

            print(f"🚀 Starting Hybrid Ingestion ({start.date()} to {end.date()})")

            for country in countries:
                self.fetch_country_data(country, start, end)
                
            self.save_data(out_file)

# --- Usage Example---
if __name__ == "__main__":
    
    # Instantiate and Run
    loader = EnergyDataLoader(config_path=PROJECT_ROOT)
    loader.run_pipeline(
        countries=TARGET_COUNTRIES,     #all imported from config
        start_date=START_DATE, 
        end_date=END_DATE, 
        output_path=DATA_FILE_RAW
    )