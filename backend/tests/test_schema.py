from data.schema import RawPrice, CleanPrice

def test_raw_price_fields():
    r = RawPrice(state="Maharashtra", district="Pune", market="Pune",
                 commodity="Tomato", variety="Local", date="2023-01-01",
                 min_price=500.0, max_price=800.0, modal_price=650.0)
    assert r.state == "Maharashtra"
    assert r.modal_price == 650.0

def test_clean_price_markup():
    c = CleanPrice(state="Maharashtra", commodity="Tomato",
                   year=2023, month=1,
                   farm_gate_price=500.0, modal_price=650.0)
    assert round(c.markup_pct, 2) == 30.0
