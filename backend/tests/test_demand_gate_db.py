import pytest
from sqlalchemy import text

from database import get_engine
from tools.ingest import schema
import analysis.demand_gate as dg


@pytest.fixture
def gate_seeded():
    schema.ensure_tables()
    with get_engine().begin() as c:
        c.execute(text("DELETE FROM processing_units WHERE source='test'"))
        c.execute(text("INSERT INTO facility_crop_map (crop, facility_type) "
                       "VALUES ('sugarcane','sugar_mill') ON CONFLICT (crop) DO NOTHING"))
        # wheat -> flour_mill mapping exists in the taxonomy, but we seed NO flour
        # mill facility, so wheat must NOT be gated (data gap, not a demand signal).
        c.execute(text("INSERT INTO facility_crop_map (crop, facility_type) "
                       "VALUES ('wheat','flour_mill') ON CONFLICT (crop) DO NOTHING"))
        c.execute(text("DELETE FROM processing_units WHERE facility_type='flour_mill'"))
        c.execute(text("""INSERT INTO processing_units
            (facility_type,name,state,district,lat,lon,crop,source,source_id)
            VALUES ('sugar_mill','Gopalganj Mill','bihar','Gopalganj',
                    26.47,84.43,'sugarcane','test','1')"""))
    yield
    with get_engine().begin() as c:
        c.execute(text("DELETE FROM processing_units WHERE source='test'"))


def test_gated_crops_from_db(gate_seeded):
    assert dg.gated_crops().get("sugarcane") == "sugar_mill"


def test_crop_not_gated_when_no_facility_of_type(gate_seeded):
    # flour_mill has no facilities loaded -> wheat is a data gap, not gated.
    gated = dg.gated_crops()
    assert "wheat" not in gated
    assert "sugarcane" in gated  # sugar_mill facility IS present


def test_nearest_facility_from_db(gate_seeded):
    near = dg.nearest_facility("sugar_mill", 26.47, 84.43)
    assert near["name"] == "Gopalganj Mill"
    assert near["km"] < 5.0


def test_proximity_factor_unchanged():
    assert dg.proximity_factor(10) == 1.0
    assert dg.proximity_factor(None) == dg.FLOOR
    assert dg.proximity_factor(200) == dg.FLOOR
