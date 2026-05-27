from fastapi import APIRouter
from analysis.markup import get_crop_markup

router = APIRouter()

@router.get("/crops/{commodity}/markup")
def crop_markup(commodity: str):
    return get_crop_markup(commodity)
