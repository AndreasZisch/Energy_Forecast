import sys
from pathlib import Path

# Get the root directory (3 levels up)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
# Add it to Python's search list
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

import warnings
import pandas as pd
import joblib

# Now this will work because Python knows where to look
from config import TARGET_COUNTRY, TARGET_COLS, MODEL_DIR, OUTPUT_DIR


# Suppress warnings
warnings.filterwarnings("ignore")

def load_model(country, target):
    # 1. FIX: Convert "Wind Onshore" -> "Wind_Onshore" for filename lookup
    clean_target = target.replace(' ', '_')
    
    filename = f"hw_{country}_{clean_target}.pkl"
    model_path = MODEL_DIR / filename
    
    if not model_path.exists():
        return None
    try:
        return joblib.load(model_path)
    except Exception as e:
        print(f"Error loading {filename}: {e}")
        return None

def generate_forecast(country_code="DE"):
    """
    Generates a standard 24h profile (Midnight to Midnight) for the current date.
    Returns the DataFrame for the API to use.
    """
    print(f"\n🔮 Generating Daily Forecast for {country_code} (Lightweight)...")
    
    # Define "Today" from 00:00 to 23:00 UTC
    today_midnight = pd.Timestamp.now(tz="UTC").normalize()
    future_index = pd.date_range(start=today_midnight, periods=24, freq="h")
    
    forecasts = {}
    
    for target in TARGET_COLS:
        # Load model using the helper
        model = load_model(country_code, target)
        
        if model is None:
            continue
            
        # Create clean name for Output CSV/JSON (e.g., "Wind_Onshore")
        clean_target = target.replace(' ', '_')
            
        try:
            # Get the model's raw 24-hour pattern
            raw_values = model.forecast(24).values
            
            # Physics Check (No negative energy)
            raw_values[raw_values < 0] = 0
            
            # Map directly to 00:00 - 23:00
            forecast_series = pd.Series(data=raw_values, index=future_index)
            
            # Store using the clean name
            forecasts[clean_target] = forecast_series
            
            print(f"   ✅ {clean_target:<15} | Peak: {forecast_series.max():,.0f} MW")
            
        except Exception as e:
            print(f"   ❌ Failed to predict {target}: {e}")

    # Process Results
    if forecasts:
        result_df = pd.DataFrame(forecasts)
        
        # Add Total Generation
        result_df["Total_Generation"] = result_df.sum(axis=1)
        result_df.index.name = "datetime_utc"
        
        # Save to CSV (Optional, but good for debugging)
        output_file = OUTPUT_DIR / f"forecast_{country_code}.csv"
        result_df.to_csv(output_file)
        print(f"   📄 Saved to: {output_file.name}")
        
        # CRITICAL: Return the dataframe so the API can send it to React
        return result_df
    else:
        print(f"   ⚠️ No models found for {country_code}. Check 'models/lightweight' folder.")
        return None

if __name__ == "__main__":
    # Test run using config default
    generate_forecast(TARGET_COUNTRY)