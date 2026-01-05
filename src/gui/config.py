from pathlib import Path

# Base paths
BASE_DIR = Path(__file__).parent.parent.parent
DATA_DIR = BASE_DIR / "data"
MODELS_DIR = BASE_DIR / "models"

# Data subdirectories
RAW_DATA_DIR = DATA_DIR / "01_raw"
PROCESSED_DATA_DIR = DATA_DIR / "02_processed"
FORECASTS_DIR = DATA_DIR / "03_forecasts"
METRICS_DIR = DATA_DIR / "04_metrics"
CARBON_DIR = DATA_DIR / "05_carbon"

# Model configurations
AVAILABLE_MODELS = {
    "lightweight": {
        "path": MODELS_DIR / "lightweight",
        "name": "Lightweight Model",
        "description": "Fast inference, minimal emissions",
        "co2_per_request": 0.02
    },
    "performance": {
        "path": MODELS_DIR / "performance",
        "name": "Performance Model", 
        "description": "Maximum accuracy, higher emissions",
        "co2_per_request": 0.15
    }
}

# Default settings
DEFAULT_COUNTRY = "Germany"
DEFAULT_ENERGY_TYPE = "Wind Onshore"
DEFAULT_FORECAST_HOURS = 24