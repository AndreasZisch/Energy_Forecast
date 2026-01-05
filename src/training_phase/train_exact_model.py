import pandas as pd
from pathlib import Path
from xgboost import XGBRegressor
import joblib
from sklearn.metrics import mean_absolute_error
from feature_engineering import build_features_dataframe
from codecarbon import EmissionsTracker


# ============================================================
# CONFIG
# ============================================================
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_FILE = PROJECT_ROOT / "data" / "01_raw" / "generation_2024_raw.csv"
MODEL_DIR = PROJECT_ROOT / "models"
METRICS_DIR = PROJECT_ROOT / "data" / "04_metrics"
CARBON_DIR = PROJECT_ROOT / "data" / "05_carbon"
MODEL_DIR.mkdir(parents=True, exist_ok=True)
METRICS_DIR.mkdir(parents=True, exist_ok=True)
CARBON_DIR.mkdir(parents=True, exist_ok=True)


TARGET_COL = ["Solar", "Wind Onshore", "Wind Offshore"]

# Step 1 Dates: Validation for metrics
TRAIN_END = "2024-10-31"
VAL_END = "2024-11-30"

XGB_PARAMS = dict(
    n_estimators=1500,
    max_depth=10,
    learning_rate=0.03,
    subsample=0.8,
    colsample_bytree=0.8,
    objective="reg:squarederror",
    tree_method="hist",
    n_jobs=-1,
    random_state=42,
)

def main():
    print("\n🚀 STARTING XGBOOST TRAINING PIPELINE")
    pipeline_tracker = EmissionsTracker(
        project_name="xgb_generation_pipeline",
        output_dir=str(CARBON_DIR),
        output_file="pipeline_emissions.csv",
        log_level="error"
    )
    pipeline_tracker.start()
    df_raw = pd.read_csv(DATA_FILE)
    all_metrics = []

    for target in TARGET_COL:
        if target not in df_raw.columns:
            continue

        print(f"\n➡️ Target: {target}")
        target_tracker = EmissionsTracker(
            project_name=f"xgb_{target.replace(' ', '_')}",
            output_dir=str(CARBON_DIR),
            output_file="emissions.csv",             
            allow_multiple_runs=True,
            log_level="error"
        )
        target_tracker.start()
        emissions = 0.0
            
        X, y, timestamps = build_features_dataframe(df_raw, target_col=target)

            # --- STEP 1: VALIDATION FOR METRICS ---
        train_mask = timestamps <= TRAIN_END
        val_mask = (timestamps > TRAIN_END) & (timestamps <= VAL_END)
            
        X_train_val, y_train_val = X.loc[train_mask], y.loc[train_mask]
        X_val, y_val = X.loc[val_mask], y.loc[val_mask]

        if not X_val.empty:
                model_val = XGBRegressor(**XGB_PARAMS)
                model_val.fit(X_train_val, y_train_val, eval_set=[(X_val, y_val)], verbose=False)
                
                # Calculate Metrics (Global average for this target)
                preds = model_val.predict(X_val)
                mae = mean_absolute_error(y_val, preds)
                peak = y_val.max()
                error_pct = (mae / peak * 100) if peak != 0 else 0
                
                all_metrics.append({
                    "Country": "GLOBAL", # XGBoost is trained across countries
                    "Energy_Type": target.replace(" ", "_"),
                    "MAE_MW": round(mae, 2),
                    "Test_Peak_MW": round(peak, 2),
                    "Error_Percentage": round(error_pct, 1),
                    "Carbon_kg_CO2": round(emissions, 4),
                    "Status": "Success"
                })

            # --- STEP 2: FULL RETRAIN ON 100% DATA ---
            # No masks = use all data points from 01.01 to 12.31
        print(f"🔄 Retraining final model on 100% of data (Samples: {len(X)})...")
        final_model = XGBRegressor(**XGB_PARAMS)
        final_model.fit(X, y, verbose=False)

        # Save Final Model
        model_path = MODEL_DIR / f"xgb_high_cost_{target.replace(' ', '_')}.pkl"
        joblib.dump(final_model, model_path)
        print(f"✅ Saved Final Model: {model_path.name}")
        
        # ✅ ALWAYS stop tracker here
        emissions = target_tracker.stop()
        print(f"🌱 Carbon emissions for {target}: {emissions:.4f} kg CO₂eq")

    # Save Metrics to CSV
    metrics_df = pd.DataFrame(all_metrics)
    metrics_path = METRICS_DIR / "xgb_metrics.csv"
    metrics_df.to_csv(metrics_path, index=False)
    print(f"\n📊 Metrics saved to: {metrics_path}")
    print("🎉 ALL MODELS TRAINED AND READY FOR DEPLOYMENT")
    pipeline_emissions = pipeline_tracker.stop()
    print(f"\n🌍 TOTAL pipeline emissions: {pipeline_emissions:.4f} kg CO₂eq")


if __name__ == "__main__":
    main()