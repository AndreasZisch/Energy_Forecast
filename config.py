# config.py

import os
from pathlib import Path

# --- PATHS ---
PROJECT_ROOT = Path(__file__).resolve().parent

# --- SETTINGS FOR RAW DATA INGESTION ---
# The specific file where raw data lives
DATA_FILE_RAW = PROJECT_ROOT / "data" / "01_raw" / "generation_2024_raw.csv"
DATA_FILE = DATA_FILE_RAW

# Target countries for raw data ingestion from ENTSOE platform
TARGET_COUNTRIES = [
    "AT", "BE", "BG", "CH", "CZ", "DE", "DK", "EE", "ES", "FI", 
    "FR", "GR", "HR", "HU", "IE", "IT", "LT", "LU", "LV", "NL", 
    "NO", "PL", "PT", "RO", "SE", "SI", "SK", "UK"
]
TARGET_COLS = ["Solar", "Wind Onshore", "Wind Offshore"]
START_DATE = "2024-01-01"
END_DATE = "2025-01-01"

# --- GLOBAL SETTINGS ---
TARGET_COUNTRY = "DE"


# --- 🔴 FIX IS HERE 🔴 ---
# Point to the specific subfolder where the .pkl files are.
# If your folder is named "holt_winters", change "lightweight" to "holt_winters".
MODEL_DIR = PROJECT_ROOT / "models" / "lightweight" 
MODEL_DIR_XGB = PROJECT_ROOT / "models"
CARBON_DIR = PROJECT_ROOT / "data" / "05_carbon"
OUTPUT_DIR = PROJECT_ROOT / "data" / "03_forecasts"

# Ensure directories exist
MODEL_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
CARBON_DIR.mkdir(parents=True, exist_ok=True)