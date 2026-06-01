from analysis.weather_client import season_months


def test_kharif_months():
    assert season_months("Kharif") == (6, 7, 8, 9, 10)


def test_rabi_months_wrap_year():
    assert season_months("Rabi") == (11, 12, 1, 2, 3)


def test_any_and_blank_default_to_all_twelve():
    assert season_months("Any") == tuple(range(1, 13))
    assert season_months("") == tuple(range(1, 13))
    assert season_months(None) == tuple(range(1, 13))
