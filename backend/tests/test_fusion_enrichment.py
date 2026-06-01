import pytest
from analysis.fusion import recommend
from database import table_exists

pytestmark = pytest.mark.skipif(not table_exists("district_crop_history"),
                                reason="history not loaded")


def test_recommendations_carry_tradition_yield_price():
    out = recommend("Bihar", "Begusarai", top_k=5)
    for r in out["recommendations"]:
        assert "traditional" in r and "years_grown" in r["traditional"]
        assert "yield" in r and {"predicted_yield", "traditional_yield", "trend", "unit"} <= set(r["yield"])
        assert "price_outlook" in r and "source" in r["price_outlook"]
    by_crop = {r["crop"]: r for r in out["recommendations"]}
    if "rice" in by_crop:
        assert by_crop["rice"]["traditional"]["years_grown"] > 0


def test_existing_fields_still_present():
    out = recommend("Bihar", "Begusarai", top_k=3)
    for r in out["recommendations"]:
        assert {"crop", "score", "breakdown", "why", "cautions"} <= set(r)
