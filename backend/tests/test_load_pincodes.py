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
