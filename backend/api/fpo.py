from fastapi import APIRouter
from pydantic import BaseModel, Field
from analysis.fpo_bulk import plan_bulk_sale, TransportConfig

router = APIRouter()


class Farmer(BaseModel):
    lat: float
    lon: float
    state: str | None = None
    quantity_q: float = Field(gt=0)


class TransportIn(BaseModel):
    truck_capacity_q: float = Field(100.0, gt=0)
    fixed_hire_per_truck: float = Field(2000.0, ge=0)
    per_km_per_truck: float = Field(30.0, ge=0)
    per_q_local_rate: float = Field(2.0, ge=0)


class BulkPlanRequest(BaseModel):
    crop: str
    farmers: list[Farmer] = Field(min_length=1)
    transport: TransportIn = TransportIn()


@router.post("/fpo/bulk-plan")
def fpo_bulk_plan(req: BulkPlanRequest):
    cfg = TransportConfig(**req.transport.model_dump())
    farmers = [f.model_dump() for f in req.farmers]
    return plan_bulk_sale(req.crop, farmers, cfg)
