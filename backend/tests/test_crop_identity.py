import pytest
import analysis.crop_catalog as cc


@pytest.fixture(autouse=True)
def _fake_commodities(monkeypatch):
    # normalized -> actual, injected so tests never hit the DB
    monkeypatch.setattr(cc, "_MANDI_MAP", {
        "maize": "Maize", "onion": "Onion",
        "arharturredgramwhole": "Arhar (Tur/Red Gram)(Whole)",
    })
    monkeypatch.setattr(cc, "_PRICES_MAP", {
        "maize": "Maize", "onion": "Onion", "redgram": "Red Gram",
        "bottlegourd": "Bottle Gourd",   # prices-only, no mandi
    })


def test_resolve_canonical_with_both_vocabularies():
    ident = cc.resolve_crop("maize")
    assert ident.canonical == "maize"
    assert ident.mandi_name == "Maize" and ident.prices_name == "Maize"
    assert ident.has_mandi and ident.has_forecast


def test_resolve_canonical_with_alias_mismatch():
    # pigeonpeas: mandi names it "Arhar (Tur/Red Gram)(Whole)" while prices uses
    # the shorter "Red Gram" — both are real aliases the resolver must bridge.
    ident = cc.resolve_crop("pigeonpeas")
    assert ident.mandi_name == "Arhar (Tur/Red Gram)(Whole)"
    assert ident.prices_name == "Red Gram"
    assert ident.has_mandi


def test_resolve_prices_only_commodity():
    ident = cc.resolve_crop("Bottle Gourd")
    assert ident.prices_name == "Bottle Gourd"
    assert ident.mandi_name is None and ident.has_mandi is False
    assert ident.has_forecast is True


def test_resolve_unknown_returns_self_identity():
    ident = cc.resolve_crop("Dragonfruit")
    assert ident.mandi_name is None and ident.prices_name is None
    assert ident.has_mandi is False and ident.has_forecast is False


def test_list_all_crops_unions_and_dedupes():
    crops = cc.list_all_crops()
    names = [c.display_name for c in crops]
    assert "Bottle Gourd" in names            # prices-only included
    assert any(c.has_mandi for c in crops)     # mandi crops flagged
    assert len(names) == len(set(names))       # deduped
