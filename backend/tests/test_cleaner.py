import pandas as pd
from data.cleaner import clean_agmarknet

def test_clean_returns_dataframe():
    raw = pd.DataFrame([{
        "State": "Maharashtra", "District": "Pune", "Market": "Pune",
        "Commodity": "Tomato", "Variety": "Local",
        "Arrival_Date": "01/01/2023",
        "Min_Price": "500", "Max_Price": "800", "Modal_Price": "650"
    }])
    result = clean_agmarknet(raw)
    assert "farm_gate_price" in result.columns
    assert "modal_price" in result.columns
    assert "year" in result.columns
    assert "month" in result.columns

def test_clean_converts_prices_to_float():
    raw = pd.DataFrame([{
        "State": "UP", "District": "Agra", "Market": "Agra",
        "Commodity": "Potato", "Variety": "General",
        "Arrival_Date": "15/06/2022",
        "Min_Price": "300", "Max_Price": "500", "Modal_Price": "400"
    }])
    result = clean_agmarknet(raw)
    assert result["farm_gate_price"].dtype == float

def test_clean_drops_nulls():
    raw = pd.DataFrame([
        {"State": None, "District": "X", "Market": "X",
         "Commodity": "Rice", "Variety": "G", "Arrival_Date": "01/01/2023",
         "Min_Price": "200", "Max_Price": "300", "Modal_Price": "250"},
        {"State": "Bihar", "District": "X", "Market": "X",
         "Commodity": "Rice", "Variety": "G", "Arrival_Date": "01/01/2023",
         "Min_Price": "200", "Max_Price": "300", "Modal_Price": "250"}
    ])
    result = clean_agmarknet(raw)
    assert len(result) == 1
