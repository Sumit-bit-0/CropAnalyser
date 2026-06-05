from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from analysis.crop_recommender import recommend_crops
from analysis.fusion import recommend as fusion_recommend
from analysis.soil_profile import soil_profile

router = APIRouter()


class CropInput(BaseModel):
    N: float = Field(ge=0)
    P: float = Field(ge=0)
    K: float = Field(ge=0)
    temperature: float
    humidity: float = Field(ge=0, le=100)
    ph: float = Field(ge=0, le=14)
    rainfall: float = Field(ge=0)


@router.post("/recommend/crop")
def recommend(body: CropInput):
    try:
        recs = recommend_crops(body.model_dump(), top_k=3)
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))
    return {"top": recs[0], "recommendations": recs, "model_trained": True}


class SmartRecommendInput(BaseModel):
    state: str
    district: Optional[str] = None
    season: Optional[str] = None
    goal: Optional[str] = None  # max_profit | low_risk | sustainable | water_efficient
    top_k: int = Field(default=3, ge=1, le=20)
    # optional soil/climate block -> Smart Mode (adds the suitability module).
    # Omit it for Simple Mode (location/season/goal only -> regional + market).
    soil: Optional[CropInput] = None
    lat: Optional[float] = None
    lon: Optional[float] = None


@router.post("/recommend/smart")
def recommend_smart(body: SmartRecommendInput):
    """CropAdvisor fusion recommender. Soil/climate is auto-derived from the
    location; a posted `soil` block overrides it (the optional manual panel)."""
    coords = (body.lat, body.lon) if body.lat is not None and body.lon is not None else None
    soil_source = climate_source = None
    if body.soil is not None:
        features = body.soil.model_dump()
        soil_source = "manual"
    else:
        prof = soil_profile(body.state, body.district, coords=coords, season=body.season)
        if prof:
            features = prof["features"]
            soil_source, climate_source = prof["soil_source"], prof["climate_source"]
        else:
            features = None  # no soil data anywhere -> degrade to regional+market
    try:
        result = fusion_recommend(
            state=body.state, district=body.district, season=body.season,
            features=features, goal=body.goal, top_k=body.top_k, coords=coords,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))
    result["soil_source"] = soil_source
    result["climate_source"] = climate_source
    return result
