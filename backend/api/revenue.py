from fastapi import APIRouter
from analysis.revenue_loss import get_revenue_loss

router = APIRouter()

@router.get("/revenue-loss")
def revenue_loss():
    return get_revenue_loss()
