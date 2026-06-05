# backend/tests/test_soil_nutrients.py
import analysis.soil_nutrients as sn


def _reload_with_csv(tmp_path, monkeypatch, text):
    csv = tmp_path / "india_district_soil.csv"
    csv.write_text(text, encoding="utf-8")
    monkeypatch.setattr(sn, "SOIL_CSV", csv)
    monkeypatch.setattr(sn, "_ROWS", None)  # reset module cache


CSV = (
    "state,district,N,P,K,ph\n"
    "Bihar,Gopalganj,270,22,210,7.4\n"
    "Bihar,Patna,240,18,190,7.6\n"
    "Punjab,Ludhiana,280,21,240,7.8\n"
)


def test_district_hit(tmp_path, monkeypatch):
    _reload_with_csv(tmp_path, monkeypatch, CSV)
    r = sn.district_soil("Bihar", "Gopalganj")
    assert r["soil_source"] == "district"
    assert r["N"] == 270 and r["ph"] == 7.4


def test_state_fallback(tmp_path, monkeypatch):
    _reload_with_csv(tmp_path, monkeypatch, CSV)
    r = sn.district_soil("Bihar", "Nalanda")  # not in CSV
    assert r["soil_source"] == "state"
    assert r["N"] == 255.0  # mean of Gopalganj(270) + Patna(240)


def test_national_fallback(tmp_path, monkeypatch):
    _reload_with_csv(tmp_path, monkeypatch, CSV)
    r = sn.district_soil("Kerala", "Wayanad")  # state absent
    assert r["soil_source"] == "national"
    assert set(r) == {"N", "P", "K", "ph", "soil_source"}


def test_missing_csv_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(sn, "SOIL_CSV", tmp_path / "absent.csv")
    monkeypatch.setattr(sn, "_ROWS", None)
    assert sn.district_soil("Bihar", "Patna") is None
