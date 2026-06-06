import pandas as pd
from tools.ingest import validators as v


def test_in_india_bbox():
    assert v.in_india_bbox(26.47, 84.43) is True   # Gopalganj, Bihar
    assert v.in_india_bbox(0.0, 0.0) is False
    assert v.in_india_bbox(51.5, -0.1) is False     # London


def test_validate_facilities_drops_bad_rows():
    df = pd.DataFrame([
        {"facility_type": "sugar_mill", "name": "A", "state": "Bihar",
         "district": "Gopalganj", "lat": 26.47, "lon": 84.43,
         "crop": "sugarcane", "source": "isma_sugar", "source_id": "1"},
        {"facility_type": "sugar_mill", "name": "B", "state": "Bihar",
         "district": "Patna", "lat": None, "lon": 85.1,
         "crop": "sugarcane", "source": "isma_sugar", "source_id": "2"},
        {"facility_type": "sugar_mill", "name": "C", "state": "Bihar",
         "district": "X", "lat": 0.0, "lon": 0.0,
         "crop": "sugarcane", "source": "isma_sugar", "source_id": "3"},
        {"facility_type": "tea_factory", "name": "D", "state": "Assam",
         "district": "Jorhat", "lat": 26.75, "lon": 94.2,
         "crop": "tea", "source": "x", "source_id": "4"},
    ])
    out = v.validate_facilities(df)
    assert list(out["name"]) == ["A"]
    assert out.iloc[0]["state"] == "bihar"  # normalized to lowercase


def test_validate_facilities_dedupes():
    df = pd.DataFrame([
        {"facility_type": "sugar_mill", "name": "A", "state": "Bihar",
         "district": "Gopalganj", "lat": 26.47, "lon": 84.43,
         "crop": "sugarcane", "source": "isma_sugar", "source_id": "1"},
        {"facility_type": "sugar_mill", "name": "A-dup", "state": "Bihar",
         "district": "Gopalganj", "lat": 26.47, "lon": 84.43,
         "crop": "sugarcane", "source": "isma_sugar", "source_id": "1"},
    ])
    out = v.validate_facilities(df)
    assert len(out) == 1


def test_validate_soil_drops_all_npk_missing():
    df = pd.DataFrame([
        {"state": "Bihar", "district": "Gopalganj", "N": 270, "P": 22,
         "K": 210, "ph": 7.4, "source": "shc_soil"},
        {"state": "Bihar", "district": "Empty", "N": None, "P": None,
         "K": None, "ph": None, "source": "shc_soil"},
    ])
    out = v.validate_soil(df)
    assert list(out["district"]) == ["Gopalganj"]


def test_validate_crop_map_rejects_non_whitelist():
    df = pd.DataFrame([
        {"crop": "sugarcane", "facility_type": "sugar_mill"},
        {"crop": "tea", "facility_type": "tea_factory"},
    ])
    out = v.validate_crop_map(df)
    assert list(out["crop"]) == ["sugarcane"]
