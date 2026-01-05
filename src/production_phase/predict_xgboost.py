import pandas as pd
import joblib
import warnings
import sys
from pathlib import Path
from codecarbon import EmissionsTracker

# Add the project root to the Python path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PROJECT_ROOT))
from src.production_phase.predict_base_class import BaseForecaster
from config import TARGET_COLS, MODEL_DIR_XGB, OUTPUT_DIR

warnings.filterwarnings("ignore")

class XGBoostForecaster(BaseForecaster):
    def __init__(self):
        super().__init__()
        # We don't load the model in __init__ because we have multiple models 
        # (one for Solar, one for Wind, etc.)

    # --- YOUR HELPER FUNCTIONS BECOME INTERNAL METHODS ---
    def _add_time_features(self, df):
        df["hour"] = df.index.hour
        df["dayofweek"] = df.index.dayofweek
        df["month"] = df.index.month
        df["dayofyear"] = df.index.dayofyear
        df["weekofyear"] = df.index.isocalendar().week.astype(int)
        df["is_weekend"] = df["dayofweek"].isin([5, 6]).astype(int)
        return df

    def _get_prediction_row(self, history_df, target_col, real_dt, lookup_dt, country_code, feature_names):
        # Features from REAL DATE (2025)
        row_df = pd.DataFrame(index=[real_dt])
        row_df = self._add_time_features(row_df)
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

    # --- MAIN LOOP BECOMES THE 'predict' METHOD ---
    def predict(self, country_code: str, forecast_date=None) -> dict:
        
                # Start tracking
        tracker = EmissionsTracker(
            project_name="renewable_energy_forecast",
            measure_power_secs=1,
            save_to_file=False,
            logging_logger=None
        )
        tracker.start()
        
# 1. Load Data & STRIP TIMEZONES IMMEDIATELY
        full_df = self._get_data() 
        
        # Convert to datetime (UTC first to handle format)
        full_df["datetime_utc"] = pd.to_datetime(full_df["datetime_utc"], utc=True)
        
        # --- 🔴 NUCLEAR FIX: REMOVE TIMEZONE INFO 🔴 ---
        # This turns "2024-01-03 00:00:00+00:00" into just "2024-01-03 00:00:00"
        full_df["datetime_utc"] = full_df["datetime_utc"].dt.tz_localize(None)
        # -----------------------------------------------

        # Now filter and set index (The index will now be Naive)
        full_df = full_df.drop_duplicates(subset=["datetime_utc", "Country"], keep="last")
        country_history = full_df[full_df["Country"] == country_code].copy()
        
        if country_history.empty:
            return {"forecast_data": pd.DataFrame(), "emissions_kg": 0.0}

        country_history = country_history.set_index("datetime_utc").sort_index()
        
        # 2. Setup Dates (Force Naive Inputs)
        if forecast_date is None:
            # pd.Timestamp.now() is local, normalize() makes it midnight
            real_start = pd.Timestamp.now().normalize() 
        else:
            # Force user input to be naive
            ts = pd.Timestamp(forecast_date)
            if ts.tz is not None:
                ts = ts.tz_localize(None)
            real_start = ts.normalize()

        real_steps = pd.date_range(start=real_start, periods=24, freq="h")

        # --- TIME TRAVEL LOOKUP (Naive vs Naive) ---
        ideal_feature_date = real_start - pd.Timedelta(days=1)
        lookup_start = ideal_feature_date # It is already naive
        
        # Debugging Print (Optional - to confirm fix)
        # print(f"DEBUG: Index TZ: {country_history.index.tz} | Lookup TZ: {lookup_start.tz}")

        max_years_back = 5
        years_back = 0
        
        while lookup_start not in country_history.index and years_back < max_years_back:
            lookup_start -= pd.DateOffset(years=1)
            # No need to normalize or localize, it stays naive
            years_back += 1
            
        if lookup_start not in country_history.index:
            print(f"⚠️ Warning: No historical match found for {ideal_feature_date}. Using last available data.")
            lookup_start = country_history.index.max() # Use max (naive)
            
        print(f"🔮 Prediction Date: {real_start} | 🔙 Using Data From: {lookup_start}")
        
        lookup_steps = pd.date_range(start=lookup_start, periods=24, freq="h")

        forecasts = {}

        for target in TARGET_COLS:
            clean_target = target.replace(' ', '_')

            # --- 🛑 FIX: SKIPPING IMPOSSIBLE TECHNOLOGIES ---
            # If the history for this country is 100% NaN (e.g., Austria Wind Offshore),
            # assume the technology does not exist and return 0.
            if country_history[target].isna().all():
                forecasts[clean_target] = [0.0] * len(real_steps)
                continue
            # ------------------------------------------------

            model_path = MODEL_DIR_XGB / f"xgb_high_cost_{clean_target}.pkl"
            
            if not model_path.exists(): continue
                
            model = joblib.load(model_path)
            feature_names = model.get_booster().feature_names
            
            temp_history = country_history[[target]].copy()
            predictions = []

            for real_dt, lookup_dt in zip(real_steps, lookup_steps):
                X_step = self._get_prediction_row(
                    temp_history, target, real_dt, lookup_dt, country_code, feature_names
                )
                # --- 🔍 DEBUG START: Catch the Ghost ---
                if target == "Solar" and real_dt.hour == 12: # Only check noon (peak solar)
                    print(f"\n🔎 DEBUG NOON CHECK for {real_dt}")
                    print(f"   Lookup Date: {lookup_dt}")
                    # 1. Check what value exists in history for that day
                    try:
                        actual_hist = temp_history.loc[lookup_dt, target]
                        print(f"   📉 Raw Historical Value in DF: {actual_hist}")
                    except:
                        print(f"   ❌ Could not read history for {lookup_dt}")

                    # 2. Check the input features going into the model
                    print(f"   🤖 Model Inputs (First 5 cols): {X_step.iloc[0, :5].to_dict()}")
                    
                    # 3. Check what the model predicts
                    raw_pred = model.predict(X_step)[0]
                    print(f"   🔮 Raw Model Prediction: {raw_pred}")
                # --- 🔍 DEBUG END ---

                pred = model.predict(X_step)[0]
                pred = max(0, float(pred))
                temp_history.loc[lookup_dt, target] = pred
                predictions.append(pred)

            forecasts[clean_target] = predictions

        # Stop tracking
        emissions_kg = tracker.stop()
        
        # 3. Final Assembly
        if forecasts:
            result_df = pd.DataFrame(forecasts, index=real_steps)
            result_df["Total_Generation"] = result_df.sum(axis=1)
            result_df.index.name = "datetime_utc"

            # save as csv for debugging and testing
            # output_file = OUTPUT_DIR / f"xgb_forecast_{country_code}.csv"
            # result_df.to_csv(output_file)
            
            return {
                "forecast_data" : result_df,
                "emissions_kg" : emissions_kg
            }

        else:
            print(f"   ⚠️ No models found for {country_code}")
            tracker.stop()  
            return {
                "forecast_data": pd.DataFrame(),  # Empty DataFrame
                "emissions_kg": 0.0               # Zero emissions
            }
    
if __name__ == "__main__":
    from config import TARGET_COUNTRY   #Target country from config for test purposes
    
    # 1. Initialize the Forecaster object
    # This sets up the paths and internal states
    forecaster = XGBoostForecaster()
    
    print(f"--- Starting Forecast Generation for {TARGET_COUNTRY} ---")
    
    # 2. Call the public 'predict' method
    # Notice we don't need to know about lags or model paths here
    #forecast_results = forecaster.predict(TARGET_COUNTRY)
    
    # 2. Call the standardized predict method
    results = forecaster.predict(TARGET_COUNTRY)

    df_forecast_results = results["forecast_data"]
    emissions = results["emissions_kg"]
    
    if not df_forecast_results.empty:
        print("\n📊 Forecast Summary:")
        print(df_forecast_results.head(24))
        print(f"\n✅ Successfully generated {len(df_forecast_results)} hours of data.")
        print(f"🌱 Execution Carbon Footprint: {emissions:.10f} kg CO2")
    else:
        print("❌ No data generated.")