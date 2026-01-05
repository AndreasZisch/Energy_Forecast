import joblib
import warnings
import pandas as pd
import sys
from pathlib import Path
from codecarbon import EmissionsTracker


# Add the project root to the Python path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PROJECT_ROOT))
from src.production_phase.predict_base_class import BaseForecaster
from config import TARGET_COLS, MODEL_DIR, OUTPUT_DIR

# Suppress warnings
warnings.filterwarnings("ignore")

class HoltWintersForecaster(BaseForecaster):
    """
    Holt-Winters implementation that loads pre-trained pkl models.
    Refactored to follow the Class-based Architectural Design.
    """
    def __init__(self):
        super().__init__()
        # Note: We use MODEL_DIR from config for the .pkl files

    def _load_model(self, country: str, target: str):
        """Internal helper to load specific country/target pkl files."""
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

    def predict(self, country_code: str, forecast_date = None) -> dict:
        """
        Generates a standard 24h profile (Midnight to Midnight) for the current date.
        Returns the DataFrame for the API/Orchestrator to use.
        """
        print(f"\n🔮 Generating Daily Forecast for {country_code} (Lightweight)...")
        
        # Define "Today" from 00:00 to 23:00 UTC
        # Unified date logic (same as XGBoost + your function)
                # Start tracking emissions
        tracker = EmissionsTracker(
            project_name="renewable_energy_forecast",
            measure_power_secs=1,
            save_to_file=False,
            logging_logger=None  # Suppress logs
        )
        tracker.start()

        if forecast_date is None:
            real_start = pd.Timestamp.now(tz="UTC").normalize()
        else:
            real_start = pd.Timestamp(forecast_date, tz="UTC").normalize()
        future_index = pd.date_range(start=real_start, periods=24, freq="h")
        
        forecasts = {}
        
        for target in TARGET_COLS:
            model = self._load_model(country_code, target)
            
            if model is None:
                continue
                
            clean_target = target.replace(' ', '_')
                
            try:
                # Get the model's raw 24-hour pattern
                raw_values = model.forecast(24).values
                
                # Physics Check (No negative energy)
                raw_values[raw_values < 0] = 0
                
                # Map directly to 00:00 - 23:00
                forecast_series = pd.Series(data=raw_values, index=future_index)
                forecasts[clean_target] = forecast_series
                
                print(f"   ✅ {clean_target:<15} | Peak: {forecast_series.max():,.0f} MW")
                
            except Exception as e:
                print(f"   ❌ Failed to predict {target}: {e}")

        
        emissions_kg = tracker.stop()
        # Final Assembly
        if forecasts:
            result_df = pd.DataFrame(forecasts)
            result_df["Total_Generation"] = result_df.sum(axis=1)
            result_df.index.name = "datetime_utc"
            
            # Store emissions as attribute (for GUI to access)
            # result_df.attrs['carbon_emissions_kg'] = emissions_kg
            
            # Save to CSV for debugging (Traceability)
            output_file = OUTPUT_DIR / f"forecast_{country_code}.csv"
            result_df.to_csv(output_file)
            
            return {
                "forecast_data" : result_df,
                "emissions_kg" : emissions_kg
            }
        else:
            print(f"   ⚠️ No models found for {country_code}. Check 'models/lightweight' folder.")
            
            # Return an empty structure that matches the "success" case
            return {
                "forecast_data": pd.DataFrame(),  # Empty DataFrame
                "emissions_kg": 0.0               # Zero emissions
            }

# ==========================================
# EXAMPLE USAGE
# ==========================================
if __name__ == "__main__":
    from config import TARGET_COUNTRY
    
    # 1. Instantiate the class
    forecaster = HoltWintersForecaster()
    
    print(f"--- Starting Forecast Generation for {TARGET_COUNTRY} ---")

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