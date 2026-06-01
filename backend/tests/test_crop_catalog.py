"""The canonical crop catalog must stay aligned with the live data sources.
If a dataset changes and an alias disappears, this fails loudly."""
from analysis.crop_catalog import CANONICAL_CROPS, WHITELIST, validate


def test_whitelist_is_canonical_keys_sorted():
    assert WHITELIST == sorted(CANONICAL_CROPS.keys())
    assert len(WHITELIST) >= 30  # expanded well beyond the original 20


def test_every_alias_exists_in_its_source():
    report = validate()
    assert report["problems"] == [], f"catalog drifted: {report['problems']}"
    assert report["whitelist_size"] == len(WHITELIST)


def test_known_mappings_present():
    # spot-check the non-obvious synonym mappings the spike resolved
    assert "Arhar/Tur" in CANONICAL_CROPS["pigeonpeas"]["production"]
    assert "Gram" in CANONICAL_CROPS["chickpea"]["production"]
    assert "Pome Granet" in CANONICAL_CROPS["pomegranate"]["production"]
    assert "kidneybeans" not in WHITELIST  # excluded: no market match
    assert "muskmelon" not in WHITELIST    # excluded: no production history


def test_expanded_staples_present():
    # the whole point of the expansion: staples the soil model never saw
    for c in ["wheat", "sugarcane", "potato", "mustard", "bajra", "jowar"]:
        assert c in WHITELIST


def test_staples_have_no_soil_label_but_cereals_do():
    # crops outside the 22-crop soil model carry suitability=None
    assert CANONICAL_CROPS["wheat"]["suitability"] is None
    assert CANONICAL_CROPS["sugarcane"]["suitability"] is None
    # crops inside it keep their label
    assert CANONICAL_CROPS["rice"]["suitability"] == "rice"
    assert CANONICAL_CROPS["maize"]["suitability"] == "maize"
