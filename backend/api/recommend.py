from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from analysis.crop_recommender import recommend_crops

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
