import pandas as pd
from pathlib import Path

# --- CONFIGURATION ---
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
RAW_DATA_FILE = PROJECT_ROOT / "data" / "01_raw" / "generation_2024_raw.csv"
PROCESSED_DIR = PROJECT_ROOT / "data" / "02_processed" / "lightweight"

# Ensure the output directory exists
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

TARGETS = ["Solar", "Wind Onshore", "Wind Offshore"]

def preprocess_lightweight_data():
    print("🚀 STARTING PREPROCESSING FOR LIGHTWEIGHT MODELS")
    
    if not RAW_DATA_FILE.exists():
        raise FileNotFoundError(f"❌ Raw data not found at {RAW_DATA_FILE}")

    print(f"   Loading raw data from: {RAW_DATA_FILE.name}...")
    df = pd.read_csv(RAW_DATA_FILE)
    
    # 1. Standardize Time
    df["datetime_utc"] = pd.to_datetime(df["datetime_utc"], utc=True)
    
    # 2. Get Unique Countries
    countries = df["Country"].unique()
    print(f"   Found countries: {', '.join(countries)}")

    processed_count = 0

    for country in countries:
        print(f"\n🌍 Processing Country: {country}")
        
        for target in TARGETS:
            # 3. Filter Data for specific Country & Target
            mask = (df["Country"] == country)
            
            # Select only time and the specific target column
            series_df = df.loc[mask, ["datetime_utc", target]].set_index("datetime_utc")
            
            # 4. Check for Empty Data (e.g., Austria has no Offshore Wind)
            if target not in series_df.columns or series_df[target].isna().all() or series_df.empty:
                print(f"      ⚠️ Skipping {target} (No valid data found)")
                continue
            
            # 5. Force Hourly Frequency & Handle Missing Values
            # Holt-Winters CRASHES if there are missing hours. We must fill them.
            series_df = series_df.resample("h").mean()
            
            # Interpolate small gaps (linear) and fill remaining NaNs with 0
            series_df[target] = series_df[target].interpolate(method="linear").fillna(0.0)
            
            # 6. Save Individual Series
            # We save as a simple CSV: index=datetime, column=value
            filename = f"processed_{country}_{target.replace(' ', '_')}.csv"
            save_path = PROCESSED_DIR / filename
            
            series_df.to_csv(save_path)
            processed_count += 1
            print(f"      ✅ Saved: {filename}")

    print(f"\n✨ Preprocessing Complete. {processed_count} files saved to {PROCESSED_DIR}")

if __name__ == "__main__":
    preprocess_lightweight_data()