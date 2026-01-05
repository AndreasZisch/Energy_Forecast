from abc import ABC, abstractmethod
import pandas as pd
from pathlib import Path
from config import DATA_FILE_RAW

class BaseForecaster(ABC):
    """
    Abstract Base Class for all Forecasting models.
    Enforces a consistent interface for the Orchestrator to use.
    """
    def __init__(self):
        self.data_path = DATA_FILE_RAW
        self._raw_data = None

    def _get_data(self) -> pd.DataFrame:
        """Shared internal method to load data safely."""
        if self._raw_data is None:
            if not self.data_path.exists():
                raise FileNotFoundError(f"Data file not found at {self.data_path}")
            self._raw_data = pd.read_csv(self.data_path)
        return self._raw_data

    @abstractmethod
    def predict(self, country_code: str) -> pd.DataFrame:
        """
        Public method that MUST be implemented by every model.
        This is what the API/Orchestrator will call.
        """
        pass