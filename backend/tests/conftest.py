import os
import sys

# Add backend/ to path so `data`, `analysis`, `models`, `api` are importable without pip install
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest


@pytest.fixture(autouse=True)
def _disable_live_weather(monkeypatch):
    """Tests must not hit the Open-Meteo network. Default the weather module OFF.

    A test that exercises weather must override this by patching the name on the
    FUSION module — e.g. monkeypatch.setattr(analysis.fusion, "weather_fit_scores",
    ...) or the "analysis.fusion.weather_fit_scores" string path. Patching the
    source module analysis.weather_fit will NOT win; this fixture's patch takes
    precedence because fusion imported the name at import time.
    """
    monkeypatch.setattr("analysis.fusion.weather_fit_scores",
                        lambda *a, **k: {}, raising=False)
