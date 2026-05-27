from fastapi import APIRouter, Query, HTTPException
from models.predictor import predict

router = APIRouter()

@router.get("/forecast")
def forecast(state: str = Query(...), commodity: str = Query(...)):
    try:
        return predict(state, commodity)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
