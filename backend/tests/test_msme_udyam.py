"""Unit tests for the MSME/Udyam adapter's "bigger industry" PIN logic.

These exercise qualify_and_collapse in isolation (no DB, no Excel files): the
size filter (strong-name OR >=MIN_CLUSTER units), PIN collapse, and naming.
"""
import pandas as pd

from tools.ingest.adapters.msme_udyam import qualify_and_collapse, _strong


def _raw(rows):
    return pd.DataFrame(
        rows, columns=["Enterprise Name", "State", "District", "Pin Code"])


def test_strong_name_pin_kept_even_solo():
    """One industrial-named unit qualifies its PIN on its own."""
    out = qualify_and_collapse(
        _raw([["Sharma Roller Flour Mills", "BIHAR", "Patna", "800001"]]),
        "flour_mill", "wheat", min_cluster=5)
    assert len(out) == 1
    assert out.iloc[0]["name"] == "Sharma Roller Flour Mills"
    assert out.iloc[0]["pin"] == "800001"
    assert out.iloc[0]["facility_type"] == "flour_mill"


def test_micro_solo_pin_dropped():
    """A lone non-industrial unit below the cluster size is dropped."""
    out = qualify_and_collapse(
        _raw([["Raju Aata Chakki", "BIHAR", "Patna", "800002"]]),
        "flour_mill", "wheat", min_cluster=5)
    assert len(out) == 0


def test_cluster_pin_kept_without_strong_name():
    """A dense PIN qualifies even when no name is industrial (Andhra case)."""
    rows = [[f"Local Unit {i}", "ANDHRA PRADESH", "Guntur", "522001"]
            for i in range(5)]
    out = qualify_and_collapse(_raw(rows), "rice_mill", "rice", min_cluster=5)
    assert len(out) == 1
    assert "cluster" in out.iloc[0]["name"].lower()
    assert out.iloc[0]["pin"] == "522001"


def test_cluster_below_threshold_dropped():
    rows = [[f"Local Unit {i}", "ANDHRA PRADESH", "Guntur", "522002"]
            for i in range(4)]
    out = qualify_and_collapse(_raw(rows), "rice_mill", "rice", min_cluster=5)
    assert len(out) == 0


def test_one_row_per_pin():
    """Multiple qualifying units in a PIN collapse to a single row."""
    rows = [["A Flour Mill", "BIHAR", "Patna", "800003"],
            ["B Flour Mill", "BIHAR", "Patna", "800003"]]
    out = qualify_and_collapse(_raw(rows), "flour_mill", "wheat")
    assert len(out) == 1
    assert out.iloc[0]["pin"] == "800003"


def test_invalid_pins_dropped():
    out = qualify_and_collapse(
        _raw([["X Flour Mill", "BIHAR", "Patna", "ABC"],
              ["Y Flour Mill", "BIHAR", "Patna", None]]),
        "flour_mill", "wheat")
    assert len(out) == 0


def test_strong_detects_industrial_drops_micro():
    s = _strong(pd.Series(["Sri Rice Mill", "Modern Agro Foods Pvt Ltd",
                           "Raju Aata Chakki", "Aman Kirana Store"]))
    assert list(s) == [True, True, False, False]
