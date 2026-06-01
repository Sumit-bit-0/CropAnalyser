import os
import sys

# Add backend/ to path so `data`, `analysis`, `models`, `api` are importable without pip install
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest


@pytest.fixture(autouse=True)
def _disable_live_weather(monkeypatch):
    """Tests must not hit the Open-Meteo network. Default the weather module OFF;
    tests that exercise weather override this with their own monkeypatch."""
    monkeypatch.setattr("analysis.fusion.weather_fit_scores",
                        lambda *a, **k: {}, raising=False)
