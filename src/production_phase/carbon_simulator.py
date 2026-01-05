import random
from datetime import datetime

class CarbonSimulator:
    """
    Component responsible for monitoring grid carbon intensity.
    Acts as a 'Virtual Sensor' for the Orchestrator.
    """
    def __init__(self, low_threshold=200, high_threshold=400):
        self.low_range = (50, 180)
        self.high_range = (400, 650)
        self.peak_hours = [(8, 11), (17, 21)]

    def _is_peak_hour(self) -> bool:
        """Internal logic to determine if current time is a peak period."""
        current_hour = datetime.now().hour
        return any(start <= current_hour <= end for start, end in self.peak_hours)

    def get_current_carbon_intensity(self, force_mode=None) -> dict:
        """
        Main interface to fetch current carbon data.
        """
        # 1. Determine Status
        if force_mode and force_mode.upper() in ["HIGH", "LOW"]:
            status = force_mode.upper()
            is_manual = True
        else:
            status = "HIGH" if self._is_peak_hour() else "LOW"
            is_manual = False

        # 2. Generate Simulated Value
        if status == "HIGH":
            carbon_val = random.uniform(*self.high_range)
        else:
            carbon_val = random.uniform(*self.low_range)

        return {
            "timestamp": datetime.now().isoformat(),
            "carbon_intensity": round(carbon_val, 1),
            "status": status,
            "is_manual_override": is_manual,
            "unit": "gCO2/kWh"
        }

# --- Example Usage in Orchestrator ---
# sensor = CarbonSimulator()
# data = sensor.get_current_intensity()