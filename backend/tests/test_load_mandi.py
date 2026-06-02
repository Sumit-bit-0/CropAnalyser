import pandas as pd
from data.load_mandi import clean_mandi, AGMARKNET_COLMAP, merge_dedupe


def test_agmarknet_schema_normalizes_to_mandi_columns():
    raw = pd.DataFrame([{
        "Sl no.": 1, "District Name": "Auraiya", "Market Name": "Achalda",
        "Commodity": "Wheat", "Variety": "Dara", "Grade": "FAQ",
        "Min Price (Rs./Quintal)": 2350, "Max Price (Rs./Quintal)": 2550,
        "Modal Price (Rs./Quintal)": 2450, "Price Date": "05 Apr 2025",
        "State": "Uttar Pradesh",
    }])
    out = clean_mandi(raw, AGMARKNET_COLMAP)
    assert list(out.columns) == ["state", "district", "market", "commodity",
                                 "variety", "grade", "min_price", "max_price",
                                 "modal_price", "price_date"]
    row = out.iloc[0]
    assert row["state"] == "Uttar Pradesh" and row["commodity"] == "Wheat"
    assert row["market"] == "Achalda" and row["modal_price"] == 2450
    assert row["price_date"] == "2025-04-05"


def test_merge_dedupe_keeps_latest_price_date():
    cols = ["state", "district", "market", "commodity", "variety", "grade",
            "min_price", "max_price", "modal_price", "price_date"]
    older = pd.DataFrame([["Punjab", "Ludhiana", "Khanna", "Wheat", "Dara", "FAQ",
                           2000, 2100, 2050, "2025-01-01"]], columns=cols)
    newer = pd.DataFrame([["Punjab", "Ludhiana", "Khanna", "Wheat", "Dara", "FAQ",
                           2200, 2300, 2250, "2025-06-01"]], columns=cols)
    out = merge_dedupe([older, newer])
    assert len(out) == 1
    assert out.iloc[0]["modal_price"] == 2250  # latest kept
