"""The canonical crop catalog must stay aligned with the live data sources.
If a dataset changes and an alias disappears, this fails loudly."""
from analysis.crop_catalog import CANONICAL_CROPS, WHITELIST, validate


def test_whitelist_is_canonical_keys_sorted():
    assert WHITELIST == sorted(CANONICAL_CROPS.keys())
    assert len(WHITELIST) == 20


def test_every_alias_exists_in_its_source():
    report = validate()
    assert report["problems"] == [], f"catalog drifted: {report['problems']}"
    assert report["whitelist_size"] == 20


def test_known_mappings_present():
    # spot-check the non-obvious synonym mappings the spike resolved
    assert "Arhar/Tur" in CANONICAL_CROPS["pigeonpeas"]["production"]
    assert "Gram" in CANONICAL_CROPS["chickpea"]["production"]
    assert "Pome Granet" in CANONICAL_CROPS["pomegranate"]["production"]
    assert "kidneybeans" not in WHITELIST  # excluded: no market match
    assert "muskmelon" not in WHITELIST    # excluded: no production history
