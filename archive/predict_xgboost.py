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
from config import TARGET_COUNTRY, TARGET_COLS, MODEL_DIR_XGB, OUTPUT_DIR, DATA_FILE_RAW

warnings.filterwarnings("ignore")

# ... rest of the file

# ==========================================
# HELPER FUNCTIONS
# ==========================================

def add_time_features(df):
    df["hour"] = df.index.hour
    df["dayofweek"] = df.index.dayofweek
    df["month"] = df.index.month
    df["dayofyear"] = df.index.dayofyear
    df["weekofyear"] = df.index.isocalendar().week.astype(int)
    df["is_weekend"] = df["dayofweek"].isin([5, 6]).astype(int)
    return df

def get_prediction_row_mapped(history_df, target_col, real_dt, lookup_dt, country_code, feature_names):
    # 1. Features from REAL DATE (2025)
    row_df = pd.DataFrame(index=[real_dt])
    row_df = add_time_features(row_df)
    
    # 2. Lags from LOOKUP DATE (2024)
    lags = [1, 3, 6, 12, 24, 48, 168]
    for lag in lags:
        lag_lookup_time = lookup_dt - pd.Timedelta(hours=lag)
        
        # Robust Lookup
        if lag_lookup_time in history_df.index:
            val = history_df.loc[lag_lookup_time, target_col]
            if isinstance(val, pd.Series): val = val.iloc[0] # Handle duplicates
        else:
            val = 0
            
        row_df[f"{target_col}_lag_{lag}"] = val

    # 3. Rolling Stats
    for window in [24, 168]:
        window_data = history_df[target_col].loc[:lookup_dt].tail(window)
        
        if len(window_data) > 0:
            row_df[f"{target_col}_roll_mean_{window}"] = window_data.mean()
            row_df[f"{target_col}_roll_std_{window}"] = window_data.std()
        else:
            row_df[f"{target_col}_roll_mean_{window}"] = 0
            row_df[f"{target_col}_roll_std_{window}"] = 0

    # 4. Country One-Hot
    for col in feature_names:
        if col.startswith("country_"):
            country_suffix = col.replace("country_", "")
            row_df[col] = 1.0 if country_suffix == country_code else 0.0

    # 5. Final Alignment
    for col in feature_names:
        if col not in row_df.columns:
            row_df[col] = 0.0

    return row_df[feature_names]

# ==========================================
# MAIN LOOP
# ==========================================

def generate_forecast(country_code="DE"):
    """
    Generates XGBoost forecast.
    Accepts country_code argument to work with Decision Logic.
    """
    
    # 1. Load Data
    full_df = pd.read_csv(DATA_FILE_RAW)
    full_df["datetime_utc"] = pd.to_datetime(full_df["datetime_utc"], utc=True)
    full_df = full_df.drop_duplicates(subset=["datetime_utc", "Country"], keep="last")
    
    # Filter by the REQUESTED country_code, not the config constant
    country_history = full_df[full_df["Country"] == country_code].copy()
    
    if country_history.empty:
        print(f"❌ No historical data found for {country_code}")
        return None

    country_history = country_history.set_index("datetime_utc").sort_index()
    
    # 2. Setup Dates
    # Real = Today (2025)
    real_start = pd.Timestamp.now(tz="UTC").normalize()
    real_steps = pd.date_range(start=real_start, periods=24, freq="h")
    
    # Lookup = Same day in 2024 (Data Source)
    lookup_start = real_start - pd.DateOffset(years=1)
    lookup_steps = pd.date_range(start=lookup_start, periods=24, freq="h")

    print(f"\n🔮 Generating Forecast for {country_code} (XGBoost)")
    print(f"   📅 Display Date: {real_start.date()}")
    print(f"   🔎 Source Data : {lookup_start.date()} (Using history from CSV)\n")
    
    all_forecasts = {}

    for target in TARGET_COLS:
        # File names use underscores
        clean_target = target.replace(' ', '_')
        model_name = f"xgb_high_cost_{clean_target}.pkl"
        model_path = MODEL_DIR_XGB / model_name
        
        if not model_path.exists():
            print(f"   ⚠️ Model missing: {model_name}")
            continue
            
        model = joblib.load(model_path)
        feature_names = model.get_booster().feature_names
        
        temp_history = country_history[[target]].copy()
        predictions = []

        for real_dt, lookup_dt in zip(real_steps, lookup_steps):
            
            X_step = get_prediction_row_mapped(
                temp_history, target, real_dt, lookup_dt, country_code, feature_names
            )
            
            pred = model.predict(X_step)[0]
            pred = max(0, float(pred))
            
            # Update history for recursive lags
            temp_history.loc[lookup_dt, target] = pred
            predictions.append(pred)

        all_forecasts[clean_target] = predictions
        print(f"   ✅ {clean_target:<15} | Peak: {max(predictions):,.0f} MW")

    if all_forecasts:
        res_df = pd.DataFrame(all_forecasts, index=real_steps)
        res_df["Total_Generation"] = res_df.sum(axis=1)
        res_df.index.name = "datetime_utc"
        
        output_file = OUTPUT_DIR / f"xgb_forecast_{country_code}.csv"
        res_df.to_csv(output_file)
        print(f"\n   📄 Saved to: {output_file.name}")
        
        # CRITICAL: Return the dataframe
        return res_df
    
    return None

if __name__ == "__main__":
    generate_forecast(TARGET_COUNTRY)