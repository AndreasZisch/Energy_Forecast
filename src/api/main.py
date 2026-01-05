from fastapi import FastAPI, HTTPException, Query
import os
import requests
from fastapi.middleware.cors import CORSMiddleware
import sys
from pathlib import Path
from typing import Optional
import pandas as pd
from datetime import datetime, timedelta

# 1. Setup Path to import your scripts from the project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PROJECT_ROOT))

# 2. Import the decision logic
from src.production_phase.decision_logic_distributed import DistributedOrchestrator

app = FastAPI(title="Renewable Energy Forecast API")

# initialize for live carbon logic
decision_logic = DistributedOrchestrator()

# 3. Allow React Frontend (localhost:3000) to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allows all connections (simplest for dev)
    allow_methods=["*"],
    allow_headers=["*"],
)

# 4. Instantiate the Orchestrator once
orchestrator = DistributedOrchestrator()

@app.get("/")
def home():
    return {"status": "API is running. Use /forecast/optimized/{country_code}"}


@app.get("/health")
def system_health():
    status = {"orchestrator": "🟢 Online", "xgb_service": "🔴 Offline", "hw_service": "🔴 Offline"}
    
    # 1. Get URLs and strip trailing slashes to be safe
    xgb_base = os.getenv("XGB_SERVICE_URL", "http://xgb_predict_service:8001/predict")
    hw_base = os.getenv("HW_SERVICE_URL", "http://hw_predict_service:8002/predict")

    # 2. Build health URLs by removing '/predict' and adding '/health'
    # This works regardless of slashes
    xgb_health = xgb_base.rstrip("/").replace("/predict", "") + "/health"
    hw_health = hw_base.rstrip("/").replace("/predict", "") + "/health"

    # Check XGB
    try:
        # Diagnostic print - check your docker logs to see what URL is being called
        print(f"DEBUG: Pinging XGB health at: {xgb_health}")
        if requests.get(xgb_health, timeout=1).status_code == 200:
            status["xgb_service"] = "🟢 Online"
    except Exception as e:
        print(f"DEBUG: XGB Health failed: {e}")

    # Check HW
    try:
        if requests.get(hw_health, timeout=1).status_code == 200:
            status["hw_service"] = "🟢 Online"
    except: pass
    
    return status

@app.get("/carbon-live")
def carbon_live_readout(
    # Add this parameter so the GUI can force the mode
    carbon_mode: Optional[str] = Query(None, description="Force HIGH or LOW")
):
    """
    Returns the real-time grid status from the Carbon Simulator.
    """
    return decision_logic.get_live_grid_status(carbon_mode=carbon_mode)

@app.get("/forecast/optimized/{country_code}")
def get_smart_forecast(
    country_code: str, 
    # This captures the optional ?carbon_mode=HIGH/LOW parameter
    carbon_mode: Optional[str] = Query(None, description="Force HIGH or LOW carbon simulation")
):
    """
    Smart Endpoint: Checks Carbon -> Picks Model -> Returns Forecast
    Includes DOUBLE FALLBACK:
    1. Primary (XGBoost) -> Handled by Orchestrator
    2. Secondary (Holt-Winters) -> Handled by Orchestrator
    3. Emergency (Static Data) -> Handled here in main.py
    """
    print(f"📡 Request: {country_code} (Carbon Override: {carbon_mode})")

    try:
        # --- LEVEL 1 & 2: Try to get data from Orchestrator (XGBoost or Holt-Winters) ---
        df, metadata = orchestrator.get_optimized_forecast(country_code, carbon_mode=carbon_mode)
        
        if df is None or df.empty:
            raise ValueError("Received empty forecast from Orchestrator")

        # --- SUCCESS PATH ---
        # Format Data for React (Convert DataFrame to JSON-friendly list)
        df_clean = df.reset_index()
        # Ensure datetime is formatted as string
        if 'datetime_utc' in df_clean.columns:
            df_clean["datetime_utc"] = df_clean["datetime_utc"].dt.strftime("%Y-%m-%d %H:%M:%S")
        
        forecast_list = df_clean.to_dict(orient="records")
        
        return {
            "metadata": metadata, 
            "forecast": forecast_list
        }

    except Exception as e:
        # --- LEVEL 3: EMERGENCY STATIC FALLBACK ---
        # If both models failed (Orchestrator raised an error), we catch it here.
        print(f"🔥 CRITICAL SYSTEM FAILURE: {e}")
        print("🛡️ ACTIVATING EMERGENCY STATIC FALLBACK")

        # Generate 24 hours of safe "dummy" data so the frontend doesn't crash
        base_time = datetime.now()
        static_forecast = []
        for i in range(24):
            time_point = base_time + timedelta(hours=i)
            static_forecast.append({
                "datetime_utc": time_point.strftime("%Y-%m-%d %H:%M:%S"),
                "predicted_generation_mw": 0.0,  # Return 0 or a safe average
                "lower_bound": 0.0,
                "upper_bound": 0.0
            })

        return {
            "metadata": {
                "selected_model": "Emergency Mode (Static Fallback)",
                "carbon_intensity": "UNKNOWN",
                "reason": f"System Failure: {str(e)}",
                "status": "Critical - All Services Down"
            },
            "forecast": static_forecast
        }

# To run: uvicorn src.api.main:app --host 0.0.0.0 --port 8000