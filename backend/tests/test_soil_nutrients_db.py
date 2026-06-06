import pytest

import analysis.soil_nutrients as sn

# ROWS seeded by the `seeded` fixture (defined in conftest.py):
# ("Bihar", "Gopalganj", 270, 22, 210, 7.4)
# ("Bihar", "Patna",     240, 18, 190, 7.6)
# ("Punjab","Ludhiana",  280, 21, 240, 7.8)


def test_district_hit(seeded):
    r = sn.district_soil("Bihar", "Gopalganj")
    assert r["soil_source"] == "district"
    assert r["N"] == 270 and r["ph"] == 7.4


def test_state_fallback(seeded):
    r = sn.district_soil("Bihar", "Nalanda")  # district absent
    assert r["soil_source"] == "state"
    assert r["N"] == 255.0  # mean of 270 + 240


def test_national_fallback(seeded):
    r = sn.district_soil("Kerala", "Wayanad")  # state absent
    assert r["soil_source"] == "national"
    assert set(r) == {"N", "P", "K", "ph", "soil_source"}
