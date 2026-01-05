from fastapi import FastAPI, HTTPException
from src.production_phase.predict_lightweight import HoltWintersForecaster

app = FastAPI(title="Holt Winters Prediction Service")
forecaster = HoltWintersForecaster()

@app.get("/health")
def health_check():
    return {"status": "healthy"}

@app.get("/predict/{country_code}")
def get_prediction(country_code: str):
    # Get the dictionary result
    result = forecaster.predict(country_code.upper())
    # unpack the dictionary
    df_forecast = result["forecast_data"]
    emissions = result["emissions_kg"]


    if df_forecast.empty:
        raise HTTPException(status_code=404, detail="Data not found for this country")
        
# 3. Return both to the API caller
    return {
        "model": "Holt-Winters", # or "XGBoost" for the other file
        "execution_carbon_kg": emissions, # <--- The number you wanted!
        "data": df_forecast.reset_index().to_dict(orient="records")
    }
