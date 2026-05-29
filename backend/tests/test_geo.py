from analysis.geo import haversine, get_centroid


def test_haversine_known_distance():
    # Delhi (28.65, 77.19) to Mumbai (19.07, 72.88) ~ 1150 km
    d = haversine(28.65, 77.19, 19.07, 72.88)
    assert 1100 < d < 1200


def test_haversine_zero():
    assert haversine(20.0, 75.0, 20.0, 75.0) == 0.0


def test_get_centroid_state_fallback():
    # A state always resolves even if the district is unknown
    c = get_centroid("Maharashtra", "NoSuchDistrict12345")
    assert c is not None
    assert 8 < c[0] < 37 and 68 < c[1] < 98  # within India bounds


def test_get_centroid_unknown_state_is_none():
    assert get_centroid("Atlantis", "Nowhere") is None
