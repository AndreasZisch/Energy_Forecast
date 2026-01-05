import os
import requests
import pandas as pd
from src.production_phase.carbon_simulator import CarbonSimulator

class DistributedOrchestrator:
    def __init__(self):
        # 1. Initialize the Virtual Sensor Component
        self.sensor = CarbonSimulator()
        
        # 2. Service Discovery (Docker Network Names)
        # USE ENVIRONMENT VARIABLES (Best Practice)
        self.XGB_URL = os.getenv("XGB_SERVICE_URL", "http://xgb_predict_service:8001/predict/")
        self.HW_URL = os.getenv("HW_SERVICE_URL", "http://hw_predict_service:8002/predict/")

    def _call_service(self, base_url, country_code, timeout=10):
        """Internal helper to handle network requests cleanly."""
        try:
            url = f"{base_url}{country_code}"
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()
            
            # --- UPDATED PARSING LOGIC ---
            # 1. Get the raw Dictionary from the API
            payload = response.json()
            
            # 2. Extract the Data and the Carbon Metric separately
            data_rows = payload.get("data", [])
            emissions = payload.get("execution_carbon_kg", 0.0) # <--- CAPTURE THIS
            
            # 3. Create DataFrame from just the 'data' list
            df = pd.DataFrame(data_rows)
            
            if not df.empty:
                df['datetime_utc'] = pd.to_datetime(df['datetime_utc'])
                df.set_index('datetime_utc', inplace=True)
            
            # 4. Return BOTH the Data and the Emissions
            return df, emissions
            
        except requests.exceptions.RequestException as e:
            # Re-raise to let the main logic decide on fallback
            raise ConnectionError(f"Service unreachable at {base_url}: {e}")



    def get_live_grid_status(self, carbon_mode=None):
        """
        Lightweight method to just read the Virtual Carbon Sensor.
        Does NOT trigger any forecast models.
        """
        return self.sensor.get_current_carbon_intensity(force_mode=carbon_mode)

    def get_optimized_forecast(self, country_code, carbon_mode=None):
        """
        Main Orchestrator Logic:
        1. Check Carbon Sensor.
        2. Route traffic to the correct Microservice.
        """
        # Step 1: Read the Sensor
        carbon_data = self.sensor.get_current_carbon_intensity(force_mode=carbon_mode)
        intensity_status = carbon_data["status"]
        
        selected_model = ""
        df = None
        execution_carbon = 0.0 # Placeholder for the metric

        # Step 2: Route Traffic
        if intensity_status == "LOW":
            print(f"🌱 Grid Clean ({carbon_data['carbon_intensity']}g). Routing to XGBoost Container...")
            try:
                # Primary Choice: Heavy Model
                # --- UPDATE: UNPACK TUPLE ---
                df, execution_carbon = self._call_service(self.XGB_URL, country_code, timeout=15)
                selected_model = "XGBoost (Performance Mode)"
                
            except Exception as e:
                print(f"⚠️ XGB Service Error: {e}. Falling back to HW...")
                # Fallback Choice
                try:
                    # --- UPDATE: UNPACK TUPLE ---
                    df, execution_carbon = self._call_service(self.HW_URL, country_code)
                    selected_model = "Holt-Winters (Auto-Fallback)"
                except Exception as fallback_err:
                    return None, {"error": f"ALL services failed: {fallback_err}"}

        else:
            print(f"☁️ Grid High Carbon ({carbon_data['carbon_intensity']}g). Routing to HW Container...")
            try:
                # Primary Choice: Eco Model
                # --- UPDATE: UNPACK TUPLE ---
                df, execution_carbon = self._call_service(self.HW_URL, country_code)
                selected_model = "Holt-Winters (Eco Mode)"
            except Exception as e:
                return None, {"error": f"Eco-service unavailable: {e}"}

        # Step 3: Return Data + Enhanced Metadata
        return df, {
            "selected_model": selected_model, 
            "carbon_context": carbon_data,
            "execution_carbon_footprint_kg": execution_carbon # <--- PASS TO API/USER
        }

# --- Example Usage (If running locally for test) ---
if __name__ == "__main__":
    orchestrator = DistributedOrchestrator()
    df, metadata = orchestrator.get_optimized_forecast("DE", carbon_mode="LOW")
    if df is not None:
        print(f"Success! Model used: {metadata['selected_model']}")
        print(f"Carbon Footprint: {metadata['execution_carbon_footprint_kg']} kg")