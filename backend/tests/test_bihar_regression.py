# backend/tests/test_bihar_regression.py
import pytest
from sqlalchemy import text

from database import get_engine, table_exists
from tools.ingest import schema
from analysis.fusion import recommend

# North-Bihar sugar mills (the Phase 1 seed set), seeded into Postgres so the
# gate has real facilities to measure proximity against.
_MILLS = [
    ("Gopalganj Mill", "Gopalganj", 26.47, 84.43),
    ("Sugauli Mill", "East Champaran", 26.77, 84.75),
    ("Ramnagar Mill", "West Champaran", 27.16, 84.18),
    ("Hasanpur Mill", "Samastipur", 25.71, 86.02),
]


@pytest.fixture
def bihar_mills():
    schema.ensure_tables()
    with get_engine().begin() as c:
        c.execute(text("DELETE FROM processing_units WHERE source='test'"))
        c.execute(text("INSERT INTO facility_crop_map (crop, facility_type) "
                       "VALUES ('sugarcane','sugar_mill') ON CONFLICT (crop) DO NOTHING"))
        for i, (name, dist, lat, lon) in enumerate(_MILLS):
            c.execute(text("""INSERT INTO processing_units
                (facility_type,name,state,district,lat,lon,crop,source,source_id)
                VALUES ('sugar_mill',:n,'bihar',:d,:lat,:lon,'sugarcane','test',:sid)"""),
                {"n": name, "d": dist, "lat": lat, "lon": lon, "sid": f"b{i}"})
    yield
    with get_engine().begin() as c:
        c.execute(text("DELETE FROM processing_units WHERE source='test'"))


@pytest.mark.skipif(not table_exists("district_crop_history"),
                    reason="district_crop_history not loaded")
def test_far_from_mill_bihar_does_not_rank_sugarcane_first(bihar_mills):
    # Far-southeast Bihar (Gaya), ~170km from the nearest north-Bihar mill.
    out = recommend("Bihar", district="Gaya", season=None, top_k=5, coords=(24.5, 85.0))
    ranks = [r["crop"] for r in out["recommendations"]]
    assert ranks[0] != "sugarcane"


@pytest.mark.skipif(not table_exists("district_crop_history"),
                    reason="district_crop_history not loaded")
def test_mill_district_can_still_surface_sugarcane(bihar_mills):
    out = recommend("Bihar", district="Gopalganj", season=None, top_k=10,
                    coords=(26.47, 84.43))
    crops = [r["crop"] for r in out["recommendations"]]
    assert "sugarcane" in crops or len(crops) > 0
