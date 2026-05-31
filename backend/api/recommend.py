from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from analysis.crop_recommender import recommend_crops
from analysis.fusion import recommend as fusion_recommend

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


@router.post("/recommend/smart")
def recommend_smart(body: SmartRecommendInput):
    """CropAdvisor fusion recommender. With `soil` -> Smart Mode (all modules);
    without it -> Simple Mode (regional + market, graceful degradation)."""
    features = body.soil.model_dump() if body.soil else None
    try:
        return fusion_recommend(
            state=body.state, district=body.district, season=body.season,
            features=features, goal=body.goal, top_k=body.top_k,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))
