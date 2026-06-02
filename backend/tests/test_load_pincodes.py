from data.load_pincodes import aggregate_pincodes


def test_aggregates_to_one_row_per_pincode_with_centroid():
    rows = [
        {"officename": "Begusarai H.O", "officetype": "HO", "pincode": "851101",
         "district": "BEGUSARAI", "statename": "BIHAR", "latitude": "25.40", "longitude": "86.10"},
        {"officename": "Begusarai Bazar B.O", "officetype": "BO", "pincode": "851101",
         "district": "BEGUSARAI", "statename": "BIHAR", "latitude": "25.44", "longitude": "86.16"},
        {"officename": "No Coords B.O", "officetype": "BO", "pincode": "851101",
         "district": "BEGUSARAI", "statename": "BIHAR", "latitude": "NA", "longitude": "NA"},
    ]
    out = aggregate_pincodes(rows)
    assert len(out) == 1
    rec = out[0]
    assert rec["pincode"] == "851101"
    assert rec["area"] == "Begusarai H.O"      # head office preferred
    assert rec["district"] == "Begusarai"      # title-cased
    assert rec["state"] == "Bihar"
    assert rec["lat"] == round((25.40 + 25.44) / 2, 5)   # NA office excluded
    assert rec["lon"] == round((86.10 + 86.16) / 2, 5)


def test_pincode_with_no_valid_coords_is_skipped():
    rows = [{"officename": "X B.O", "officetype": "BO", "pincode": "999999",
             "district": "Z", "statename": "Y", "latitude": "NA", "longitude": "NA"}]
    assert aggregate_pincodes(rows) == []


def test_swapped_coords_are_recovered():
    # Many India Post rows store latitude/longitude transposed: Kasimpalli
    # (Telangana, ~17N 79E) appears as latitude=79 longitude=17. The lat (6-38)
    # and lon (67-98) ranges don't overlap, so the swap is unambiguous.
    rows = [
        {"officename": "Kasimpalli B.O", "officetype": "BO", "pincode": "506169",
         "district": "WARANGAL", "statename": "TELANGANA", "latitude": "79.0", "longitude": "17.0"},
    ]
    out = aggregate_pincodes(rows)
    assert len(out) == 1
    assert out[0]["lat"] == 17.0 and out[0]["lon"] == 79.0


def test_garbage_coords_excluded_from_average():
    # A malformed office row (column misalignment) yields absurd coordinates.
    # It must not poison the pincode centroid.
    rows = [
        {"officename": "Hyderabad GPO", "officetype": "HO", "pincode": "500001",
         "district": "HYDERABAD", "statename": "TELANGANA", "latitude": "17.38", "longitude": "78.47"},
        {"officename": "Garbage B.O", "officetype": "BO", "pincode": "500001",
         "district": "HYDERABAD", "statename": "TELANGANA",
         "latitude": "33377611.54", "longitude": "469168467.49"},
    ]
    out = aggregate_pincodes(rows)
    assert len(out) == 1
    assert out[0]["lat"] == 17.38 and out[0]["lon"] == 78.47


def test_pincode_with_only_garbage_coords_is_skipped():
    rows = [{"officename": "X B.O", "officetype": "BO", "pincode": "999999",
             "district": "Z", "statename": "Y", "latitude": "99999.0", "longitude": "0.0"}]
    assert aggregate_pincodes(rows) == []
