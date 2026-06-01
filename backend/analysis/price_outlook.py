"""Near-term price outlook per crop for the advisor.

Prefers the trained LSTM forecast (models.predictor.predict) for the state + the
crop's primary market commodity; falls back to the recent historical modal-price
slope when no model covers that state x commodity. `source` labels which path ran
so the UI never over-claims a forecast.
"""
from config import LSTM_FORECAST_LEN
from database import query
from models.predictor import predict
from analysis.crop_catalog import CANONICAL_CROPS

DEADBAND = 0.02


def _commodity(crop: str) -> str | None:
    aliases = CANONICAL_CROPS.get(crop, {}).get("market", [])
    return aliases[0] if aliases else None


def _trend(first: float, last: float) -> str:
    if last > first * (1 + DEADBAND): return "rising"
    if last < first * (1 - DEADBAND): return "falling"
    return "flat"


def _forecast(state: str, commodity: str):
    """(near-term price, trend) from the LSTM; raises if no model."""
    fc = predict(state, commodity)  # list of {period, modal_price, ...}; raises FileNotFoundError
    prices = [f["modal_price"] for f in fc]
    return float(prices[0]), _trend(prices[0], prices[-1])


def _historical(state: str, commodity: str):
    """(recent modal price, trend) from the last few years; None if no data."""
    df = query("""SELECT year, AVG(modal_price) p FROM prices
                  WHERE commodity = ? AND LOWER(state)=LOWER(?)
                  GROUP BY year ORDER BY year""", (commodity, state))
    if df.empty:
        df = query("""SELECT year, AVG(modal_price) p FROM prices
                      WHERE commodity = ? GROUP BY year ORDER BY year""", (commodity,))
    if df.empty:
        return None, None
    ps = df["p"].tolist()
    recent = float(ps[-1])
    base = float(ps[-3]) if len(ps) >= 3 else float(ps[0])
    return recent, _trend(base, recent)


def price_outlook(state: str, crop: str) -> dict:
    commodity = _commodity(crop)
    if not commodity:
        return {"price": None, "trend": None, "horizon_months": 0, "source": "none"}
    try:
        price, trend = _forecast(state, commodity)
        return {"price": round(price, 2), "trend": trend,
                "horizon_months": LSTM_FORECAST_LEN, "source": "forecast"}
    except (FileNotFoundError, ValueError):
        price, trend = _historical(state, commodity)
        if price is None:
            return {"price": None, "trend": None, "horizon_months": 0, "source": "none"}
        return {"price": round(price, 2), "trend": trend, "horizon_months": 0, "source": "historical"}
