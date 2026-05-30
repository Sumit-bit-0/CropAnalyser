from fastapi import APIRouter, Query, HTTPException
from models.predictor import predict, available_forecasts

router = APIRouter()

@router.get("/forecast/available")
def forecast_available():
    """{state: [commodities]} for which a trained model exists — drives the UI dropdowns."""
    return available_forecasts()

@router.get("/forecast")
def forecast(state: str = Query(...), commodity: str = Query(...)):
    try:
        return predict(state, commodity)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
