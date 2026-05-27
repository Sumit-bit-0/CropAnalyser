from fastapi import APIRouter, Query
from analysis.trends import get_price_trend, get_available_filters

router = APIRouter()

@router.get("/trends/filters")
def trends_filters():
    return get_available_filters()

@router.get("/trends")
def price_trend(state: str = Query(...), commodity: str = Query(...)):
    return get_price_trend(state, commodity)
