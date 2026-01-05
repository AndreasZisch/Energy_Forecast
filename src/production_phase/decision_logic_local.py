from src.production_phase.carbon_simulator import CarbonSimulator
from src.production_phase.predict_xgboost import XGBoostForecaster
from src.production_phase.predict_lightweight import HoltWintersForecaster

class LocalOrchestrator:
    def __init__(self):
        # CarbonSimulator as Virtual Sensor
        self.sensor = CarbonSimulator()     
        # Instantiate both strategies locally
        self.performance_model = XGBoostForecaster()
        self.eco_model = HoltWintersForecaster()

    def get_optimized_forecast(self, country_code, carbon_mode=None):
        carbon_data = self.sensor.get_current_carbon_intensity(force_mode=carbon_mode)
        intensity_status = carbon_data['status']
        
        metadata = {"carbon_context": carbon_data, "selected_model": "", "reasoning": ""}

        # Strategy Selection Logic
        if intensity_status == "HIGH":
            print(f"⚠️ HIGH Carbon: Using ECO Model.")
            forecast_df = self.eco_model.predict(country_code)
            metadata["selected_model"] = "Eco Model (Holt-Winters)"
        else:
            print(f"✅ LOW Carbon: Using PERFORMANCE Model.")
            try:
                forecast_df = self.performance_model.predict(country_code)
                metadata["selected_model"] = "Performance Model (XGBoost)"
            except Exception as e:
                print(f"Fallback to Eco: {e}")
                forecast_df = self.eco_model.predict(country_code)
                metadata["selected_model"] = "Eco Model (Fallback)"

        return forecast_df, metadata