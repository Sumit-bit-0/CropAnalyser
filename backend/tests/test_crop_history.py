"""Tests for the district_crop_history loader and table."""
import pandas as pd
import pytest

from data.load_crop_history import clean_history, COLUMNS
from database import query, table_exists


def _raw():
    # mimics "Crop Production data.csv" with the messiness the spike found
    return pd.DataFrame([
        # uppercase state, trailing whitespace, whitelist crop -> pigeonpeas
        ["ANDAMAN AND NICOBAR", "NICOBAR ISLANDS", 2000, "Kharif     ", "Arhar/Tur", 100.0, 250.0],
        # valid crop with no catalog mapping at all -> canonical None
        ["Punjab", "Ludhiana", 2010, "Rabi", "Coriander", 200.0, 600.0],
        ["Bihar", "Patna", 2011, "Kharif", "Maize", 50.0, 150.0],          # -> maize
        ["Goa", "North Goa", 2012, "Whole Year ", "Banana", 10.0, None],    # null production -> dropped
        ["Goa", "South Goa", 2012, "Kharif", "Rice", 0.0, 100.0],          # zero area -> dropped
    ], columns=["State_Name", "District_Name", "Crop_Year", "Season", "Crop", "Area", "Production"])


def test_clean_history_shape_and_columns():
    out = clean_history(_raw())
    assert list(out.columns) == COLUMNS
    assert len(out) == 3  # null-production and zero-area rows dropped


def test_clean_history_normalizes_and_maps():
    out = clean_history(_raw()).reset_index(drop=True)
    arhar = out[out["crop"] == "Arhar/Tur"].iloc[0]
    assert arhar["state"] == "Andaman And Nicobar"   # title-cased
    assert arhar["season"] == "Kharif"               # whitespace stripped
    assert arhar["canonical_crop"] == "pigeonpeas"   # synonym mapped
    assert arhar["crop_yield"] == 2.5                # 250 / 100

    assert out[out["crop"] == "Maize"].iloc[0]["canonical_crop"] == "maize"
    # crop with no catalog mapping -> NULL canonical
    assert out[out["crop"] == "Coriander"].iloc[0]["canonical_crop"] is None


@pytest.mark.skipif(not table_exists("district_crop_history"),
                    reason="district_crop_history not loaded")
def test_table_loaded_and_tagged():
    n = int(query("SELECT COUNT(*) n FROM district_crop_history").iloc[0]["n"])
    assert n > 100_000
    # whitelist crops are tagged and queryable by canonical name
    rice = int(query("SELECT COUNT(*) n FROM district_crop_history "
                     "WHERE canonical_crop = 'rice'").iloc[0]["n"])
    assert rice > 0
    # canonical_crop only ever holds whitelist values or NULL
    from analysis.crop_catalog import WHITELIST
    distinct = query("SELECT DISTINCT canonical_crop FROM district_crop_history "
                     "WHERE canonical_crop IS NOT NULL")["canonical_crop"].tolist()
    assert set(distinct) <= set(WHITELIST)
