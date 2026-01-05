import pandas as pd
import joblib
from pathlib import Path
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from sklearn.metrics import mean_absolute_error
import warnings
from codecarbon import EmissionsTracker


# Suppress warnings
warnings.filterwarnings("ignore")

# --- CONFIGURATION ---
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PROCESSED_DIR = PROJECT_ROOT / "data" / "02_processed" / "lightweight"
MODEL_DIR = PROJECT_ROOT / "models" / "lightweight"
CARBON_DIR = PROJECT_ROOT / "data" / "05_carbon"


# We will save the "Proof" here
METRICS_FILE = MODEL_DIR / "metrics_summary.csv"

MODEL_DIR.mkdir(parents=True, exist_ok=True)
CARBON_DIR.mkdir(parents=True, exist_ok=True)

# Training Cutoff for Validation
# TRAIN_END = "2024-10-31 23:00:00" -> only needed for Model validation (after that, the model is trained with data from the whole year)

def train_lightweight_models():
    print("🚀 STARTING LIGHTWEIGHT TRAINING & VALIDATION")
    
    pipeline_tracker = EmissionsTracker(
        project_name="holtwinters_lightweight_pipeline",
        output_dir=str(CARBON_DIR),
        output_file="hw_pipeline_emissions.csv",
        log_level="error"
    )
    pipeline_tracker.start()
    
    files = list(PROCESSED_DIR.glob("processed_*.csv"))
    if not files:
        raise FileNotFoundError(f"❌ No data in {PROCESSED_DIR}")

    print(f"   Found {len(files)} datasets.")
    
    # List to collect all our proof data
    metrics_log = []

    for file_path in files:
        parts = file_path.stem.split("_")
        country = parts[1]
        target_name = "_".join(parts[2:]) # e.g. "Solar" or "Wind_Onshore"
        
        tracker = EmissionsTracker(
            project_name="holtwinters_lightweight",
            experiment_id=f"{country}_{target_name}",
            output_dir=str(CARBON_DIR),
            output_file="hw_emissions.csv",
            allow_multiple_runs=True,
            log_level="error"
        )

        tracker.start()
        emissions = 0.0
        
        # 1. Load Data
        df = pd.read_csv(file_path, index_col="datetime_utc", parse_dates=True)
        target_col = df.columns[0]
        
        # 2. Split Train/Test
        # train_data = df.loc[:TRAIN_END, target_col]
        # test_data = df.loc[TRAIN_END:, target_col].iloc[1:]
        train_data = df[target_col] # use full data for production phase
        test_data = pd.Series() # Test data empty, not needed in production phase

        if len(train_data) < 48:
            print("      ⚠️ Skipped (not enough data)")
            tracker.stop()
            continue

        print(f"\n⚡ Training: {country} - {target_name}")

        try:
            # --- PARAMETER SELECTION ---
            if "Solar" in target_name:
                trend_mode = "add"
                damped = True
                seasonal_mode = "add"
            else:
                trend_mode = None 
                damped = False
                seasonal_mode = "add"

            model = ExponentialSmoothing(
                train_data, 
                seasonal_periods=24, 
                trend=trend_mode, 
                damped_trend=damped,
                seasonal=seasonal_mode, 
                initialization_method="estimated"
            ).fit()
            
            # 3. Evaluate and Log
            # if not test_data.empty:
            #     forecast = model.forecast(len(test_data))
            #     mae = mean_absolute_error(test_data, forecast)
                
            #     # Calculate Capacity/Peak for context
            #     peak_gen = test_data.max()
            #     error_pct = (mae / peak_gen * 100) if peak_gen > 0 else 0
                
            #     print(f"      ✅ MAE: {mae:.2f} MW  (Approx {error_pct:.1f}%)")
                
            #     # Add to our log list
            #     metrics_log.append({
            #         "Country": country,
            #         "Energy_Type": target_name,
            #         "MAE_MW": round(mae, 2),
            #         "Test_Peak_MW": round(peak_gen, 2),
            #         "Error_Percentage": round(error_pct, 1),
            #         "Status": "Success"
            #     })

            # 4. Save Model
            model_filename = f"hw_{country}_{target_name}.pkl"
            joblib.dump(model, MODEL_DIR / model_filename)
            
            emissions = tracker.stop()
            print(f"      🌱 Carbon emissions: {emissions:.6f} kg CO₂eq")
            
        except Exception as e:
            print(f"      ❌ Failed: {e}")
            metrics_log.append({
                "Country": country,
                "Energy_Type": target_name,
                "MAE_MW": None,
                "Test_Peak_MW": None,
                "Error_Percentage": None,
                "Status": f"Failed: {str(e)}"
            })

    # --- SAVE THE PROOF ---
    if metrics_log:
        metrics_df = pd.DataFrame(metrics_log)
        # Sort by Country for nicer reading
        metrics_df = metrics_df.sort_values(by=["Country", "Energy_Type"])
        
        metrics_df.to_csv(METRICS_FILE, index=False)
        print(f"\n📄 Validation Metrics exported to: {METRICS_FILE}")
        print("   (You can keep this file as proof of model performance.)")
        
    pipeline_emissions = pipeline_tracker.stop()
    print(f"\n🌍 TOTAL Holt-Winters pipeline emissions: {pipeline_emissions:.6f} kg CO₂eq")
    print("🎉 LIGHTWEIGHT MODELS READY")

if __name__ == "__main__":
    train_lightweight_models()