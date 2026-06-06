# backend/tests/test_demand_gate.py
"""Unit tests for analysis/demand_gate.py.

CSV-based helpers (PROCESSING_CSV / _UNITS / GATED_CROPS module attrs) were
removed when the gate was migrated to Postgres (Task 11).  The proximity-factor
arithmetic and the public function signatures are unchanged; behaviour tests that
needed the old CSV path are superseded by tests/test_demand_gate_db.py.
"""
import analysis.demand_gate as dg


def test_proximity_factor_bands():
    assert dg.proximity_factor(0) == 1.0
    assert dg.proximity_factor(50) == 1.0
    assert dg.proximity_factor(150) == dg.FLOOR
    assert dg.proximity_factor(300) == dg.FLOOR
    assert dg.proximity_factor(None) == dg.FLOOR
    mid = dg.proximity_factor(100)            # halfway -> halfway to floor
    assert dg.FLOOR < mid < 1.0


def test_nearest_facility_returns_dict_or_none():
    """nearest_facility returns a {name, km} dict or None — never raises."""
    result = dg.nearest_facility("sugar_mill", 26.5, 84.4)
    # DB may or may not have records; just validate the contract.
    assert result is None or (isinstance(result, dict)
                               and "name" in result and "km" in result)


def test_nearest_facility_none_for_unknown_type():
    """An unknown facility_type not in the DB must return None."""
    assert dg.nearest_facility("__no_such_mill__", 26.5, 84.4) is None


def test_gated_crops_returns_dict():
    """gated_crops() returns a dict (may be empty if facility_crop_map absent)."""
    result = dg.gated_crops()
    assert isinstance(result, dict)


def test_gated_crops_only_includes_types_with_facilities():
    """Guard invariant: a crop is gated only if its facility_type has >=1
    facility loaded. A taxonomy entry whose facility_type has no facilities is a
    data gap and must be excluded (otherwise the crop is penalised everywhere)."""
    from database import query
    gated = dg.gated_crops()
    if gated:
        types = set(query(
            "SELECT DISTINCT facility_type FROM processing_units")["facility_type"])
        assert all(ft in types for ft in gated.values())
