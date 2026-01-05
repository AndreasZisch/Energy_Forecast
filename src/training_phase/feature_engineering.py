import pandas as pd
from pathlib import Path

# ==========================================
# CONFIGURATION
# ==========================================
PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DATA_PATH = PROJECT_ROOT / "data" / "01_raw" / "generation_2024_raw.csv"
PROCESSED_DIR = PROJECT_ROOT / "data" / "02_processed"
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

def add_time_features(df: pd.DataFrame) -> pd.DataFrame:
    df["hour"] = df["datetime_utc"].dt.hour
    df["dayofweek"] = df["datetime_utc"].dt.dayofweek
    df["month"] = df["datetime_utc"].dt.month
    df["dayofyear"] = df["datetime_utc"].dt.dayofyear
    df["weekofyear"] = df["datetime_utc"].dt.isocalendar().week.astype(int)
    df["is_weekend"] = df["dayofweek"].isin([5, 6]).astype(int)
    return df

def build_features_dataframe(df: pd.DataFrame, target_col: str, save_csv: bool = True):
    target_col = target_col.strip()
    
    # 1. PREP: Filter columns IMMEDIATELY to prevent interference from other targets
    # This ensures NaNs in 'Wind Offshore' don't kill 'Solar' rows for Austria
    relevant_cols = ["datetime_utc", "Country", target_col]
    df = df[relevant_cols].copy()
    
    # 2. Fill NaNs for the TARGET only (e.g. fill Solar NaNs with 0)
    # This saves landlocked countries if the target itself has gaps
    df[target_col] = df[target_col].fillna(0)
    
    df["datetime_utc"] = pd.to_datetime(df["datetime_utc"], utc=True)
    df = df.sort_values(["Country", "datetime_utc"])

    # 3. Feature Engineering
    df = add_time_features(df)

    # Lags
    lags = [1, 3, 6, 12, 24, 48, 168]
    for lag in lags:
        df[f"{target_col}_lag_{lag}"] = df.groupby("Country")[target_col].shift(lag)

    # Rolling Stats
    for window in [24, 168]:
        df[f"{target_col}_roll_mean_{window}"] = (
            df.groupby("Country")[target_col].rolling(window).mean().reset_index(level=0, drop=True)
        )
        df[f"{target_col}_roll_std_{window}"] = (
            df.groupby("Country")[target_col].rolling(window).std().reset_index(level=0, drop=True)
        )

    # 4. Country Encoding
    country_dummies = pd.get_dummies(df["Country"], prefix="country")
    df = pd.concat([df, country_dummies], axis=1)

    # 5. Drop rows with insufficient history (the first 168 hours)
    df = df.dropna()

    if save_csv:
        safe_target = target_col.replace(" ", "_")
        output_path = PROCESSED_DIR / f"features_{safe_target}.csv"
        df.to_csv(output_path, index=False)
        print(f"   💾 Features saved to: {output_path.name}")

    X = df.drop(columns=["datetime_utc", "Country", target_col])
    y = df[target_col]
    timestamps = df["datetime_utc"]

    return X.astype(float), y.astype(float), timestamps

# Example usage for testing
if __name__ == "__main__":
    print(f"Loading raw data from {RAW_DATA_PATH}...")
    if RAW_DATA_PATH.exists():
        raw_df = pd.read_csv(RAW_DATA_PATH)
        
        # Process and save for each target
        for target in ["Solar", "Wind Onshore", "Wind Offshore"]:
            if target in raw_df.columns:
                print(f"\nProcessing {target}...")
                build_features_dataframe(raw_df, target_col=target, save_csv=True)
    else:
        print("❌ Raw data file not found.")