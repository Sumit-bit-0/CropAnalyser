from fastapi import APIRouter
from analysis.markup import get_state_markup

router = APIRouter()

@router.get("/states/markup")
def states_markup():
    return get_state_markup()
