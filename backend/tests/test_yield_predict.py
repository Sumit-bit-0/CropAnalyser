import pytest
from analysis.yield_predict import predict_yield, UNIT_LABEL
from database import table_exists

pytestmark = pytest.mark.skipif(not table_exists("district_crop_history"),
                                reason="history not loaded")


def test_known_crop_district_returns_yield():
    r = predict_yield("Bihar", "Begusarai", "Kharif", "rice", 2016)
    assert r["level"] in {"district", "state"}
    assert r["predicted_yield"] is not None and r["predicted_yield"] > 0
    assert r["traditional_yield"] is not None
    assert r["trend"] in {"rising", "flat", "falling"}
    assert r["unit"] == UNIT_LABEL.get("rice", "units/ha")


def test_sparse_crop_returns_none():
    # apple is excluded by the min-data filter -> no fabricated number
    r = predict_yield("Bihar", "Begusarai", "Kharif", "apple", 2016)
    assert r["predicted_yield"] is None
    assert r["level"] == "none"
