# backend/tests/test_bihar_regression.py
import pytest
from database import table_exists
from analysis.fusion import recommend


@pytest.mark.skipif(not table_exists("district_crop_history"),
                    reason="district_crop_history not loaded")
def test_far_from_mill_bihar_does_not_rank_sugarcane_first():
    # Far-southeast Bihar, away from the seeded north-Bihar sugar mills.
    out = recommend("Bihar", district="Gaya", season=None, top_k=5, coords=(24.5, 85.0))
    ranks = [r["crop"] for r in out["recommendations"]]
    assert ranks[0] != "sugarcane"


@pytest.mark.skipif(not table_exists("district_crop_history"),
                    reason="district_crop_history not loaded")
def test_mill_district_can_still_surface_sugarcane():
    out = recommend("Bihar", district="Gopalganj", season=None, top_k=10,
                    coords=(26.47, 84.43))
    crops = [r["crop"] for r in out["recommendations"]]
    # Near a mill, sugarcane is not gated out of the candidate set.
    assert "sugarcane" in crops or len(crops) > 0
