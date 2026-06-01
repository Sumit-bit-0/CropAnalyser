from analysis.weather_client import season_months


def test_kharif_months():
    assert season_months("Kharif") == (6, 7, 8, 9, 10)


def test_rabi_months_wrap_year():
    assert season_months("Rabi") == (11, 12, 1, 2, 3)


def test_any_and_blank_default_to_all_twelve():
    assert season_months("Any") == tuple(range(1, 13))
    assert season_months("") == tuple(range(1, 13))
    assert season_months(None) == tuple(range(1, 13))


import pytest
import analysis.weather_client as wc


# Two calendar years of canned daily data: Jan all warm, Jun-Oct (kharif) hot,
# precip 2.0mm per sampled day, 2 samples/month -> 12*2*2.0 = 48mm/year
def _fake_daily():
    times, temp, hum, rain = [], [], [], []
    for year in (2023, 2024):
        for month in range(1, 13):
            for day in (1, 15):
                times.append(f"{year}-{month:02d}-{day:02d}")
                temp.append(30.0 if month in (6, 7, 8, 9, 10) else 18.0)
                hum.append(80.0 if month in (6, 7, 8, 9, 10) else 40.0)
                rain.append(2.0)  # mm per sampled day
    return {"daily": {"time": times, "temperature_2m_mean": temp,
                      "relative_humidity_2m_mean": hum, "precipitation_sum": rain}}


def test_seasonal_climate_aggregates_season_months(monkeypatch):
    wc._seasonal_cached.cache_clear()
    monkeypatch.setattr(wc, "_fetch_archive", lambda *a, **k: _fake_daily())
    out = wc.seasonal_climate(25.7, 85.3, "Kharif")
    assert out["temperature"] == pytest.approx(30.0)      # only kharif months
    assert out["humidity"] == pytest.approx(80.0)
    # rainfall is ANNUAL: 24 sampled days/year * 2mm = 48, averaged over 2 yrs = 48
    assert out["rainfall"] == pytest.approx(48.0)


def test_seasonal_climate_raises_on_empty(monkeypatch):
    wc._seasonal_cached.cache_clear()
    monkeypatch.setattr(wc, "_fetch_archive", lambda *a, **k: {"daily": {"time": []}})
    with pytest.raises(wc.WeatherUnavailable):
        wc.seasonal_climate(25.7, 85.3, "Rabi")
