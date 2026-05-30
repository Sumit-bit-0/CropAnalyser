"""Tests for the trained-model catalog used to filter the Forecast page dropdowns."""
from pathlib import Path
from models.predictor import available_forecasts
from config import MODELS_DIR


def _safe(state: str, commodity: str) -> str:
    return f"{state}_{commodity}".replace(" ", "_").replace("/", "-")


def test_returns_dict_of_state_to_commodities():
    avail = available_forecasts()
    assert isinstance(avail, dict)
    assert avail, "expected at least one trained state"
    for state, commodities in avail.items():
        assert isinstance(state, str)
        assert isinstance(commodities, list) and commodities


def test_every_listed_pair_has_a_model_file():
    """Catalog must never advertise a combo without a real .pt on disk."""
    avail = available_forecasts()
    for state, commodities in avail.items():
        for commodity in commodities:
            assert (MODELS_DIR / f"{_safe(state, commodity)}.pt").exists(), \
                f"catalog lists {state}/{commodity} but no model file exists"


def test_known_trained_pair_present():
    avail = available_forecasts()
    assert "Punjab" in avail
    assert "Wheat" in avail["Punjab"]


def test_untrained_combo_absent():
    """Pondicherry has only a Sesamum model — Wheat must not be offered."""
    avail = available_forecasts()
    if "Pondicherry" in avail:
        assert "Wheat" not in avail["Pondicherry"]


def test_commodities_sorted():
    avail = available_forecasts()
    for commodities in avail.values():
        assert commodities == sorted(commodities)
