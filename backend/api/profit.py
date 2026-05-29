from fastapi import APIRouter, Query
from pydantic import BaseModel, Field
from analysis.profit_planner import plan_profit, get_price_reference

router = APIRouter()


class ProfitInput(BaseModel):
    area_acres: float = Field(gt=0)
    yield_q_per_acre: float = Field(ge=0)
    input_cost: float = Field(ge=0)
    labour_cost: float = Field(ge=0)
    transport_cost: float = Field(ge=0)
    market_price: float = Field(ge=0)
    desired_margin_pct: float = Field(default=20.0, ge=0)


@router.post("/profit/plan")
def profit_plan(body: ProfitInput):
    return plan_profit(**body.model_dump())


@router.get("/profit/price-reference")
def price_reference(state: str = Query(...), commodity: str = Query(...)):
    return get_price_reference(state, commodity)
