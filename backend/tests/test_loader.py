import pandas as pd
from data.loader import load_agmarknet

def test_load_returns_dataframe():
    df = load_agmarknet()
    assert isinstance(df, pd.DataFrame)

def test_load_has_required_columns():
    df = load_agmarknet()
    required = {"State", "Commodity", "Arrival_Date", "Min_Price", "Modal_Price"}
    assert required.issubset(set(df.columns))

def test_load_no_empty_states():
    df = load_agmarknet()
    assert df["State"].notna().all()

def test_load_has_rows():
    df = load_agmarknet()
    assert len(df) > 0
