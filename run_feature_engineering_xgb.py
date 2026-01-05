from src.training_phase.feature_engineering import build_features_dataframe
from pathlib import Path
import pandas as pd

#PROJECT_ROOT = Path(__file__).resolve()#.parents[2]

DATA_FILE = "data/01_raw/generation_2024_raw.csv"

df = pd.read_csv(DATA_FILE)
TARGET_COL = "Wind Onshore" #, "Wind Offshore","Solar"]

X,y,timestamp = build_features_dataframe(df=df, target_col=TARGET_COL)
print(X.head(24))