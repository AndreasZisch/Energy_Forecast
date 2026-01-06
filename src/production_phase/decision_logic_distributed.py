import os
import time  # ✅ NEW: For waiting during container startup
import requests
import pandas as pd
import docker  # ✅ NEW: To control the infrastructure
import logging # ✅ NEW: For better status visibility
from src.production_phase.carbon_simulator import CarbonSimulator

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DistributedOrchestrator:
    def __init__(self):
        # 1. Initialize the Virtual Sensor Component
        self.sensor = CarbonSimulator()
        
        # 2. Service Discovery (Docker Network Names)
        self.XGB_URL = os.getenv("XGB_SERVICE_URL", "http://xgb_predict_service:8001/predict/")
        self.HW_URL = os.getenv("HW_SERVICE_URL", "http://hw_predict_service:8002/predict/")

        # 3. ✅ NEW: Infrastructure Control Setup
        # We need the exact container name to kill/revive it
        self.container_name = os.getenv("HEAVY_CONTAINER_NAME", "energy-grid-xgb_service-1")
        self.docker_client = None
        self._connect_to_docker()

    def _connect_to_docker(self):
        """ ✅ NEW: Connect to the local Docker Daemon socket. """
        try:
            self.docker_client = docker.from_env()
            logger.info("✅ Orchestrator connected to Docker Daemon.")
        except Exception as e:
            logger.warning(f"⚠️ Docker connection failed: {e}")
            logger.warning("   (Did you mount /var/run/docker.sock in docker-compose?)")

    def manage_infrastructure(self, carbon_status):
        """
        ✅ NEW: The 'Redeployment' Logic
        - HIGH CARBON -> Stop Container (Save Energy)
        - LOW CARBON -> Start Container (High Performance)
        """
        if not self.docker_client:
            return

        try:
            # Find container by partial name match (more robust than exact match)
            containers = self.docker_client.containers.list(all=True)
            target = next((c for c in containers if self.container_name in c.name), None)

            if not target:
                logger.warning(f"⚠️ Container '{self.container_name}' not found. Cannot scale.")
                return

            # AUTO-SCALING LOGIC
            if carbon_status == "HIGH" and target.status == "running":
                logger.info(f"🛑 GRID DIRTY ({carbon_status}): Stopping Heavy AI to save energy...")
                target.stop()
                
            elif carbon_status == "LOW" and target.status != "running":
                logger.info(f"🟢 GRID CLEAN ({carbon_status}): Starting Heavy AI for performance...")
                target.start()
                logger.info("   ⏳ Waiting 5s for service to initialize...")
                time.sleep(5) 

        except Exception as e:
            logger.error(f"❌ Infrastructure Error: {e}")

    def _call_service(self, base_url, country_code, timeout=10):
        """Internal helper to handle network requests cleanly."""
        try:
            # Ensure URL formatting handles slash correctly
            if not base_url.endswith("/"):
                base_url += "/"
            url = f"{base_url}{country_code}"
            
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()
            
            # 1. Get the raw Dictionary from the API
            payload = response.json()
            
            # 2. Extract Data and Carbon Metric
            # Handle different potential API response structures safely
            if isinstance(payload, dict) and "data" in payload:
                data_rows = payload.get("data", [])
                emissions = payload.get("execution_carbon_kg", 0.0)
            else:
                # Fallback if API returns just a list
                data_rows = payload
                emissions = 0.0
            
            # 3. Create DataFrame
            df = pd.DataFrame(data_rows)
            
            if not df.empty and 'datetime_utc' in df.columns:
                df['datetime_utc'] = pd.to_datetime(df['datetime_utc'])
                df.set_index('datetime_utc', inplace=True)
            
            # 4. Return BOTH Data and Emissions
            return df, emissions
            
        except requests.exceptions.RequestException as e:
            raise ConnectionError(f"Service unreachable at {base_url}: {e}")

    def get_live_grid_status(self, carbon_mode=None):
        """
        Lightweight method to read the Virtual Carbon Sensor.
        ✅ NOW ALSO ENFORCES INFRASTRUCTURE STATE
        """
        # 1. Get Data
        data = self.sensor.get_current_carbon_intensity(force_mode=carbon_mode)
        
        # 2. ✅ TRIGGER THE KILL SWITCH HERE
        # This ensures that every time the GUI polls for status (every 15s),
        # the system checks if it needs to kill/start the container.
        self.manage_infrastructure(data["status"])
        
        return data

    def get_optimized_forecast(self, country_code, carbon_mode=None):
        """
        Main Orchestrator Logic
        """
        # Step 1: Read the Sensor
        carbon_data = self.sensor.get_current_carbon_intensity(force_mode=carbon_mode)
        intensity_status = carbon_data["status"]
        
        logger.info(f"🌍 Carbon Intensity: {carbon_data['carbon_intensity']} g/kWh ({intensity_status})")

        # Step 2: ✅ NEW: Execute Redeployment (Kill/Revive Container)
        # This physically changes the infrastructure before we try to call it
        self.manage_infrastructure(intensity_status)
        
        selected_model = ""
        df = None
        execution_carbon = 0.0

        # Step 3: Route Traffic
        if intensity_status == "LOW":
            logger.info("🌱 Grid Clean. Routing to XGBoost...")
            try:
                # Primary Choice: Heavy Model
                df, execution_carbon = self._call_service(self.XGB_URL, country_code, timeout=15)
                selected_model = "XGBoost (Performance Mode)"
                
            except Exception as e:
                logger.warning(f"⚠️ XGB Service Error: {e}. Falling back to HW...")
                # Fallback Choice
                try:
                    df, execution_carbon = self._call_service(self.HW_URL, country_code)
                    selected_model = "Holt-Winters (Auto-Fallback)"
                except Exception as fallback_err:
                    return None, {"error": f"ALL services failed: {fallback_err}"}

        else:
            logger.info("☁️ Grid High Carbon. Routing to HW (Eco Mode)...")
            # Note: We don't even try XGB here because manage_infrastructure() likely just stopped it.
            try:
                # Primary Choice: Eco Model
                df, execution_carbon = self._call_service(self.HW_URL, country_code)
                selected_model = "Holt-Winters (Eco Mode)"
            except Exception as e:
                return None, {"error": f"Eco-service unavailable: {e}"}

        # Step 4: Return Data + Enhanced Metadata
        return df, {
            "selected_model": selected_model, 
            "carbon_context": carbon_data,
            "execution_carbon_footprint_kg": execution_carbon
        }

if __name__ == "__main__":
    orchestrator = DistributedOrchestrator()
    df, metadata = orchestrator.get_optimized_forecast("DE", carbon_mode="LOW")
    if df is not None:
        print(f"Success! Model used: {metadata['selected_model']}")