# backend/tests/test_demand_gate.py
import analysis.demand_gate as dg

CSV = (
    "facility_type,name,state,district,lat,lon\n"
    "sugar_mill,Gopalganj Mill,Bihar,Gopalganj,26.47,84.43\n"
    "sugar_mill,Kolhapur Mill,Maharashtra,Kolhapur,16.70,74.24\n"
)


def _load_csv(tmp_path, monkeypatch):
    p = tmp_path / "processing_units.csv"
    p.write_text(CSV, encoding="utf-8")
    monkeypatch.setattr(dg, "PROCESSING_CSV", p)
    monkeypatch.setattr(dg, "_UNITS", None)


def test_proximity_factor_bands():
    assert dg.proximity_factor(0) == 1.0
    assert dg.proximity_factor(50) == 1.0
    assert dg.proximity_factor(150) == dg.FLOOR
    assert dg.proximity_factor(300) == dg.FLOOR
    assert dg.proximity_factor(None) == dg.FLOOR
    mid = dg.proximity_factor(100)            # halfway -> halfway to floor
    assert dg.FLOOR < mid < 1.0


def test_nearest_facility_picks_closest(tmp_path, monkeypatch):
    _load_csv(tmp_path, monkeypatch)
    near = dg.nearest_facility("sugar_mill", 26.5, 84.4)   # next to Gopalganj
    assert near["name"] == "Gopalganj Mill"
    assert near["km"] < 20


def test_nearest_facility_none_for_unknown_type(tmp_path, monkeypatch):
    _load_csv(tmp_path, monkeypatch)
    assert dg.nearest_facility("rice_mill", 26.5, 84.4) is None


def test_gated_crops_contains_sugarcane():
    assert dg.GATED_CROPS.get("sugarcane") == "sugar_mill"
